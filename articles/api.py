import csv
import hashlib
import difflib
import json
import time
import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Case, Count, IntegerField, Q, Value, When
from django.db import connection
from django.conf import settings
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify
from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.authentication import JWTAuthentication

from users.models import CustomUser, ReaderInterest, Workspace, WorkspaceMembership, has_active_membership
from users.api import resolve_public_api_key
from users.delivery import dispatch_article_alert, dispatch_webhook_event

from .api_serializers import (
    ArticleFactCheckSerializer, ArticlePresenceSerializer, ArticleReviewSerializer,
    ArticleScheduleSerializer,
    ArticleAssignmentSerializer,
    ArticleImageSerializer, ArticleLiveUpdateSerializer, ArticleMediaSerializer, ArticleSourceSerializer,
    ArticleAutosaveSerializer,
    BookmarkSerializer, ReadingProgressSerializer,
    PlagiarismCheckSerializer,
    ArticleTranslationSerializer,
    ModerationFlagSerializer,
    ArticleSEOSerializer,
    AuditLogSerializer,
    CategorySerializer,
    TagSerializer,
    ArticleWorkflowSerializer,
    CommentSerializer, CommentReportSerializer,
    NotificationSerializer,
    RevisionSerializer,
    ArticleAssetSerializer, ArticleCorrectionSerializer, ArticleProvenanceSerializer, ContentExperimentSerializer, ExperimentVariantSerializer, MediaAssetSerializer, SeriesArticleSerializer, StorySeriesSerializer,
)
from .models import Article, ArticleAsset, ArticleAssignment, ArticleAutosave, ArticleCorrection, ArticleEditEvent, ArticleEngagementEvent, ArticleFactCheck, ArticleImage, ArticleLiveUpdate, ArticleMedia, ArticlePresence, ArticleProvenance, ArticleReaction, ArticleRevision, ArticleSource, ArticleTranslation, ArticleView, AuditLog, BackupRecord, Bookmark, Category, Comment, CommentReport, ContentExperiment, EditorialAssistantRun, ExperimentAssignment, ExperimentEvent, Like, MediaAsset, ModerationFlag, Notification, PlagiarismCheck, ReadingProgress, SeriesArticle, StorySeries, Tag, WorkflowRule
from .permissions import capabilities_for_user, editor_has_capability
from .workflow import workflow_steps
from .audit import record_audit_event
from .notifications import notify
from .assistant import make_suggestions
from .seo import build_article_seo_payload
from .accessibility import analyze_article_accessibility
from .content_io import docx_to_markdown, markdown_document, markdown_to_docx
from .media_processing import generate_image_variants


class ArticlePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class CurrentUserCapabilitiesView(APIView):
    """Expose the server-side capability contract to workspace navigation."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        capabilities = sorted(capabilities_for_user(request.user))
        return Response({
            'role': request.user.role,
            'capabilities': capabilities,
        })


class ArticleWorkflowTimelineView(APIView):
    """Return the current workflow state and its auditable transitions."""

    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        article = get_object_or_404(Article.objects.select_related('reviewed_by', 'author'), pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot view this workflow timeline.'}, status=status.HTTP_403_FORBIDDEN)

        events = []
        for item in AuditLog.objects.filter(article=article).select_related('actor').order_by('created_at', 'id'):
            events.append({
                'id': item.id,
                'action': item.action,
                'actor': item.actor.username if item.actor else 'System',
                'details': item.details or {},
                'created_at': item.created_at,
            })
        return Response({
            'article_id': article.id,
            'title': article.title,
            'workflow_status': article.workflow_status,
            'rejection_reason': article.rejection_reason,
            'workflow_steps': workflow_steps(article),
            'events': events,
        })


class ArticleQuerySetMixin:
    def active_workspace(self):
        slug = self.request.headers.get('X-Workspace-Slug') or self.request.query_params.get('workspace') or self.request.session.get('active_workspace_slug')
        if not slug or not self.request.user.is_authenticated:
            return None
        return Workspace.objects.filter(
            slug=slug, is_active=True,
            memberships__user=self.request.user,
        ).first()

    def article_queryset(self):
        user = self.request.user
        base = Article.objects.select_related('author', 'reviewed_by', 'category_ref').prefetch_related('tag_objects')
        workspace = self.active_workspace()
        if workspace:
            base = base.filter(workspace=workspace)
        if user.is_authenticated and user.role in {'Editor', 'Admin'}:
            return base
        if user.is_authenticated:
            return base.filter(author=user)
        return base.filter(workflow_status='published', is_visible=True)


class ArticleWorkflowView(ArticleQuerySetMixin, APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_article(self, request, article_id):
        article = get_object_or_404(self.article_queryset(), pk=article_id)
        if article.is_premium and not has_active_membership(request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('An active membership is required to read this article.')
        if not request.user.is_authenticated:
            if article.workflow_status != 'published' or not article.is_visible:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('This article is not publicly available.')
        elif request.user.role == 'Journalist' and article.author_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only access your own unpublished articles.')
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article.workflow_status == 'published' and (
            not request.user.is_authenticated or request.user.id != article.author_id
        ):
            ArticleView.objects.create(article=article, user=request.user if request.user.is_authenticated else None)
        return Response(ArticleWorkflowSerializer(article, context={'request': request}).data)

    def patch(self, request, article_id):
        article = self.get_article(request, article_id)
        if request.user.role == 'Editor' and not editor_has_capability(request.user, article, 'edit'):
            return Response({'detail': 'You are not assigned edit access for this article.'}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role == 'Journalist' and article.author_id != request.user.id:
            return Response({'detail': 'You can only edit your own articles.'}, status=status.HTTP_403_FORBIDDEN)
        if article.workflow_status == 'published' and request.user.role == 'Journalist':
            return Response({'detail': 'Published articles cannot be edited by journalists.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ArticleRevision.objects.create(
                article=article,
                editor=request.user,
                title=article.title,
                subtitle=article.subtitle,
                content=article.content,
                summary=article.summary,
                category=article.category,
                tags=article.tags,
            )
            serializer = ArticleWorkflowSerializer(
                article,
                data=request.data,
                partial=True,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            record_audit_event(
                actor=request.user,
                action='article_updated',
                article=article,
                details={'fields': sorted(request.data.keys())},
            )
        return Response(serializer.data)


class ArticleAssistantView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only the author, editors, or admins can use the editorial assistant.'}, status=status.HTTP_403_FORBIDDEN)
        action = str(request.data.get('action', '')).strip().lower()
        try:
            suggestions = make_suggestions(article, action)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        run = EditorialAssistantRun.objects.create(
            article=article,
            requested_by=request.user,
            action=action,
            provider=settings.AI_ASSISTANT_PROVIDER,
            suggestions=suggestions,
        )
        record_audit_event(actor=request.user, action='editorial_assistant_used', article=article, details={'action': action})
        return Response({
            'run_id': run.id,
            'article_id': article.id,
            'action': action,
            'provider': run.provider,
            'requires_review': True,
            'suggestions': suggestions,
        })


class EditorialAssistantApplyView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, run_id):
        run = get_object_or_404(EditorialAssistantRun.objects.select_related('article'), pk=run_id)
        article = run.article
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only the author, editors, or admins can apply assistant output.'}, status=403)
        requested_fields = request.data.get('fields') or list(run.suggestions.keys())
        supported_fields = {'title', 'summary', 'content', 'meta_title', 'meta_description', 'seo_keywords'}
        if not isinstance(requested_fields, list) or not set(requested_fields).issubset(supported_fields | {'headlines'}):
            return Response({'detail': 'fields contains an unsupported article field.'}, status=400)
        updates = {}
        for field in requested_fields:
            value = run.suggestions.get(field)
            if field == 'headlines' or not isinstance(value, str):
                continue
            updates[field] = value
        if 'title' in requested_fields and isinstance(run.suggestions.get('headlines'), list):
            index = int(request.data.get('headline_index', 0))
            headlines = run.suggestions['headlines']
            if 0 <= index < len(headlines):
                updates['title'] = headlines[index]
        if not updates:
            return Response({'detail': 'No applicable assistant fields were selected.'}, status=400)
        for field, value in updates.items():
            setattr(article, field, value)
        article.save(update_fields=[*updates.keys(), 'updated_at'])
        record_audit_event(actor=request.user, action='editorial_assistant_applied', article=article, details={'run_id': run.id, 'fields': sorted(updates)})
        return Response({'applied': sorted(updates), 'article_id': article.id})


class PersonalizedFeedView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        interests = list(ReaderInterest.objects.filter(user=request.user).values_list('interest_type', 'value'))
        category_values = {value.lower() for kind, value in interests if kind == 'category'}
        tag_values = {value.lower() for kind, value in interests if kind == 'tag'}
        author_values = {value.lower() for kind, value in interests if kind == 'author'}
        progress_rows = list(ReadingProgress.objects.filter(user=request.user, completed=False, progress_percent__gt=0).select_related('article').order_by('-updated_at')[:10])
        resume_ids = {row.article_id for row in progress_rows}
        resume_categories = {(row.article.category or '').lower() for row in progress_rows}
        mode = request.query_params.get('mode', 'for_you').strip().lower()
        try:
            limit = min(max(int(request.query_params.get('limit', 20)), 1), 50)
        except (TypeError, ValueError):
            limit = 20
        articles = list(Article.objects.filter(workflow_status='published', is_visible=True).select_related('author'))
        if not has_active_membership(request.user):
            articles = [article for article in articles if not article.is_premium]

        def score(article):
            article_tags = {tag.strip().lower() for tag in (article.tags or '').split(',') if tag.strip()}
            points = 0
            if (article.category or '').lower() in category_values:
                points += 5
            points += 3 * len(article_tags & tag_values)
            if article.author.username.lower() in author_values:
                points += 6
            if article.id in resume_ids:
                points += 10
            if (article.category or '').lower() in resume_categories:
                points += 2
            return points

        if mode == 'latest':
            ranked = sorted(articles, key=lambda article: article.published_at or article.created_at, reverse=True)
        elif mode == 'trending':
            ranked = sorted(articles, key=lambda article: (article.views.count(), article.likes.count(), article.published_at or article.created_at), reverse=True)
        else:
            ranked = sorted(articles, key=lambda article: (score(article), article.published_at or article.created_at), reverse=True)
        serialized = ArticleWorkflowSerializer(ranked[:limit], many=True, context={'request': request}).data
        for item, article in zip(serialized, ranked[:limit]):
            article_score = score(article)
            item['recommendation_score'] = article_score
            item['recommendation_reason'] = (
                'Continue reading where you left off.' if article.id in resume_ids else
                'Matches your saved interests.' if article_score else
                'Popular with readers.' if mode == 'trending' else
                'Recently published.' if mode == 'latest' or not interests else
                'Recommended to get you started.'
            )
        return Response({
            'mode': mode if mode in {'for_you', 'latest', 'trending'} else 'for_you',
            'cold_start': not bool(interests),
            'interests': [{'interest_type': kind, 'value': value} for kind, value in interests],
            'resume_reading': [{'article_id': row.article_id, 'progress_percent': row.progress_percent, 'position_seconds': row.position_seconds} for row in progress_rows],
            'results': serialized,
        })


class ArticleSourceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_article(self, article_id):
        return get_object_or_404(Article, pk=article_id)

    def get(self, request, article_id):
        article = self.get_article(article_id)
        if article.workflow_status != 'published' and (not request.user.is_authenticated or (request.user.role not in {'Editor', 'Admin'} and article.author_id != request.user.id)):
            return Response({'detail': 'Sources are not publicly available for this article.'}, status=403)
        return Response(ArticleSourceSerializer(article.sources.all(), many=True).data)

    def post(self, request, article_id):
        article = self.get_article(article_id)
        if not request.user.is_authenticated or (request.user.role not in {'Editor', 'Admin'} and article.author_id != request.user.id):
            return Response({'detail': 'Only the author, editors, or admins can add sources.'}, status=403)
        serializer = ArticleSourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = serializer.save(article=article, added_by=request.user)
        record_audit_event(actor=request.user, action='article_source_added', article=article, details={'source_id': source.id})
        return Response(ArticleSourceSerializer(source).data, status=201)


class ArticleSourceDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        source = get_object_or_404(ArticleSource.objects.select_related('article'), pk=pk)
        if request.user.role not in {'Editor', 'Admin'} and source.article.author_id != request.user.id:
            return Response({'detail': 'Only the author, editors, or admins can verify sources.'}, status=403)
        serializer = ArticleSourceSerializer(source, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        source = serializer.save(accessed_at=timezone.now() if serializer.validated_data.get('verification_status') == 'verified' else source.accessed_at)
        record_audit_event(actor=request.user, action='article_source_verified', article=source.article, details={'source_id': source.id, 'status': source.verification_status})
        return Response(ArticleSourceSerializer(source).data)


class ArticleFactCheckView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.workflow_status != 'published' and (not request.user.is_authenticated or request.user.role not in {'Editor', 'Admin'}):
            return Response({'detail': 'Fact checks are not publicly available for this article.'}, status=403)
        return Response(ArticleFactCheckSerializer(article.fact_checks.all(), many=True).data)

    def post(self, request, article_id):
        if not request.user.is_authenticated or request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can certify fact checks.'}, status=403)
        article = get_object_or_404(Article, pk=article_id)
        serializer = ArticleFactCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check = serializer.save(article=article, checked_by=request.user)
        record_audit_event(actor=request.user, action='article_fact_checked', article=article, details={'fact_check_id': check.id, 'verdict': check.verdict})
        return Response(ArticleFactCheckSerializer(check).data, status=201)


class ArticleEvidenceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.workflow_status != 'published' and (not request.user.is_authenticated or request.user.role not in {'Editor', 'Admin'}):
            return Response({'detail': 'Evidence is not publicly available for this article.'}, status=status.HTTP_403_FORBIDDEN)
        sources = article.sources.all()
        checks = article.fact_checks.all()
        verdicts = {value: checks.filter(verdict=value).count() for value, _ in ArticleFactCheck.VERDICT_CHOICES}
        if not sources:
            quality_status = 'missing_sources'
        elif not checks.exists():
            quality_status = 'needs_fact_check'
        elif verdicts['false'] or verdicts['unverified']:
            quality_status = 'needs_review'
        else:
            quality_status = 'reviewed'
        return Response({
            'article_id': article.id,
            'source_count': sources.count(),
            'primary_source_count': sources.filter(source_type='primary').count(),
            'fact_check_count': checks.count(),
            'verified_claims': verdicts['verified'],
            'verdicts': verdicts,
            'quality_status': quality_status,
            'sources': ArticleSourceSerializer(sources, many=True).data,
            'fact_checks': ArticleFactCheckSerializer(checks, many=True).data,
        })


class ArticleCollaborationView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You do not have collaboration access.'}, status=403)
        cutoff = timezone.now() - timedelta(minutes=2)
        sessions = article.presence_sessions.filter(last_seen__gte=cutoff).select_related('user')
        presence = [{
            'user_id': session.user_id, 'username': session.user.username, 'status': session.status,
            'section': session.section, 'cursor_position': session.cursor_position, 'last_seen': session.last_seen,
        } for session in sessions]
        since_value = request.query_params.get('since')
        if not since_value and request.query_params.get('include_events') not in {'1', 'true', 'yes'}:
            return Response(presence)
        since = parse_datetime(since_value) if since_value else cutoff
        if since_value and since is None:
            return Response({'detail': 'since must be a valid ISO-8601 datetime.'}, status=400)
        events = article.edit_events.filter(created_at__gt=since).select_related('user')[:100]
        return Response({
            'presence': presence,
            'events': [{
                'id': event.id,
                'user_id': event.user_id,
                'username': event.user.username,
                'event_type': event.event_type,
                'payload': event.payload,
                'created_at': event.created_at,
            } for event in events],
        })

    def post(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You do not have collaboration access.'}, status=403)
        session, _ = ArticlePresence.objects.update_or_create(
            article=article, user=request.user,
            defaults={
                'status': request.data.get('status', 'editing'),
                'section': request.data.get('section', '')[:80],
                'cursor_position': max(0, int(request.data.get('cursor_position', 0))),
                'last_seen': timezone.now(),
            },
        )
        event_type = str(request.data.get('event_type', '')).strip()
        if not event_type:
            return Response(ArticlePresenceSerializer(session).data)
        allowed_events = {value for value, _ in ArticleEditEvent.EVENT_CHOICES}
        if event_type not in allowed_events:
            return Response({'detail': 'Unsupported collaboration event.'}, status=400)
        payload = request.data.get('payload', {})
        if not isinstance(payload, dict):
            return Response({'detail': 'payload must be an object.'}, status=400)
        event = ArticleEditEvent.objects.create(
            article=article, user=request.user, event_type=event_type, payload=payload,
        )
        return Response({
            'presence': ArticlePresenceSerializer(session).data,
            'event': {
                'id': event.id,
                'event_type': event.event_type,
                'payload': event.payload,
                'created_at': event.created_at,
            },
        })

    def delete(self, request, article_id):
        ArticlePresence.objects.filter(article_id=article_id, user=request.user).delete()
        return Response({'left': True})


class ArticleMediaView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_article(self, article_id):
        return get_object_or_404(Article, pk=article_id)

    def can_manage(self, request, article):
        return request.user.is_authenticated and (article.author_id == request.user.id or request.user.role in {'Editor', 'Admin'})

    def get(self, request, article_id):
        article = self.get_article(article_id)
        if article.workflow_status != 'published' and not self.can_manage(request, article):
            return Response({'detail': 'Media is not publicly available for this article.'}, status=403)
        return Response(ArticleMediaSerializer(article.media_items.all(), many=True, context={'request': request}).data)

    def post(self, request, article_id):
        article = self.get_article(article_id)
        if not self.can_manage(request, article):
            return Response({'detail': 'Only the author, editors, or admins can add media.'}, status=403)
        serializer = ArticleMediaSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        media = serializer.save(article=article, uploaded_by=request.user)
        record_audit_event(actor=request.user, action='article_media_added', article=article, details={'media_id': media.id, 'media_type': media.media_type})
        return Response(ArticleMediaSerializer(media, context={'request': request}).data, status=201)


class ArticleMediaProcessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        media = get_object_or_404(ArticleMedia, pk=pk)
        if media.article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot process this media.'}, status=status.HTTP_403_FORBIDDEN)
        if not media.file and not media.external_url:
            return Response({'detail': 'A file or external URL is required before processing.'}, status=status.HTTP_400_BAD_REQUEST)
        media.processing_status = 'processing'
        media.processing_error = ''
        media.save(update_fields=['processing_status', 'processing_error'])
        if media.file:
            media.file_size = media.file.size
            extension = media.file.name.rsplit('.', 1)[-1].lower() if '.' in media.file.name else ''
            media.mime_type = getattr(media.file.file, 'content_type', '') or {
                'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'mp4': 'video/mp4', 'webm': 'video/webm',
            }.get(extension, 'application/octet-stream')
        elif media.external_url:
            media.mime_type = 'external/url'
        media.processing_status = 'ready'
        media.save(update_fields=['file_size', 'mime_type', 'processing_status', 'updated_at'] if hasattr(media, 'updated_at') else ['file_size', 'mime_type', 'processing_status'])
        record_audit_event(actor=request.user, action='article_media_processed', article=media.article, details={'media_id': media.id, 'status': media.processing_status})
        return Response(ArticleMediaSerializer(media, context={'request': request}).data)


class ArticleMediaDeleteView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        media = get_object_or_404(ArticleMedia, pk=pk)
        if media.article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot delete this media.'}, status=403)
        article = media.article
        media.delete()
        record_audit_event(actor=request.user, action='article_media_deleted', article=article, details={'media_id': pk})
        return Response(status=204)


class ArticleLiveUpdateView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_article(self, article_id):
        return get_object_or_404(Article, pk=article_id)

    def can_manage(self, request, article):
        return request.user.is_authenticated and (
            article.author_id == request.user.id or request.user.role in {'Editor', 'Admin'}
        )

    def get(self, request, article_id):
        article = self.get_article(article_id)
        if not article.is_live and article.workflow_status != 'published' and not self.can_manage(request, article):
            return Response({'detail': 'This live coverage is not publicly available.'}, status=403)
        updates = article.live_updates.filter(is_published=True)
        return Response({
            'article_id': article.id,
            'is_live': article.is_live,
            'live_started_at': article.live_started_at,
            'live_ended_at': article.live_ended_at,
            'updates': ArticleLiveUpdateSerializer(updates, many=True).data,
        })

    def post(self, request, article_id):
        article = self.get_article(article_id)
        if not self.can_manage(request, article):
            return Response({'detail': 'Only the author, editors, or admins can manage live coverage.'}, status=403)

        action = str(request.data.get('action', '')).strip().lower()
        if action in {'start', 'end'}:
            if action == 'start':
                article.is_live = True
                article.live_started_at = timezone.now()
                article.live_ended_at = None
            else:
                article.is_live = False
                article.live_ended_at = timezone.now()
            article.save(update_fields=['is_live', 'live_started_at', 'live_ended_at', 'updated_at'])
            record_audit_event(actor=request.user, action=f'live_coverage_{action}ed', article=article)
            return Response({'is_live': article.is_live, 'live_started_at': article.live_started_at, 'live_ended_at': article.live_ended_at})

        body = str(request.data.get('body', '')).strip()
        if not body:
            return Response({'detail': 'Live update text is required.'}, status=400)
        is_pinned = bool(request.data.get('is_pinned', False)) and request.user.role in {'Editor', 'Admin'}
        update = ArticleLiveUpdate.objects.create(
            article=article,
            author=request.user,
            body=body,
            is_pinned=is_pinned,
            is_published=bool(request.data.get('is_published', True)),
        )
        record_audit_event(actor=request.user, action='live_update_created', article=article, details={'update_id': update.id})
        return Response(ArticleLiveUpdateSerializer(update).data, status=201)


class ArticleLiveUpdateDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def can_manage(self, request, update):
        return update.author_id == request.user.id or request.user.role in {'Editor', 'Admin'}

    def patch(self, request, pk):
        update = get_object_or_404(ArticleLiveUpdate, pk=pk)
        if not self.can_manage(request, update):
            return Response({'detail': 'You cannot edit this live update.'}, status=403)
        serializer = ArticleLiveUpdateSerializer(update, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if 'is_pinned' in serializer.validated_data and request.user.role not in {'Editor', 'Admin'}:
            serializer.validated_data['is_pinned'] = False
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        update = get_object_or_404(ArticleLiveUpdate, pk=pk)
        if not self.can_manage(request, update):
            return Response({'detail': 'You cannot delete this live update.'}, status=403)
        update.delete()
        return Response(status=204)


class WorkflowRuleView(APIView):
    permission_classes = [IsAuthenticated]

    def _payload(self, rule):
        return {'id': rule.id, 'workspace_id': rule.workspace_id, 'name': rule.name, 'from_status': rule.from_status, 'to_status': rule.to_status, 'required_role': rule.required_role, 'require_sources': rule.require_sources, 'require_fact_check': rule.require_fact_check, 'is_active': rule.is_active}

    def get(self, request):
        queryset = WorkflowRule.objects.all()
        if request.user.role != 'Admin':
            queryset = queryset.filter(workspace__memberships__user=request.user)
        return Response([self._payload(rule) for rule in queryset])

    def post(self, request):
        if request.user.role not in {'Admin', 'Editor'}:
            return Response({'detail': 'Only editors and admins can configure workflow rules.'}, status=403)
        workspace = get_object_or_404(Workspace, slug=request.data.get('workspace_slug'), memberships__user=request.user, is_active=True)
        if request.user.role == 'Editor' and not WorkspaceMembership.objects.filter(workspace=workspace, user=request.user, role__in=['owner', 'admin', 'editor']).exists():
            return Response({'detail': 'Workspace editor access is required.'}, status=403)
        rule = WorkflowRule.objects.create(workspace=workspace, name=str(request.data.get('name', 'Editorial rule'))[:120], from_status=request.data.get('from_status'), to_status=request.data.get('to_status'), required_role=str(request.data.get('required_role', ''))[:20], require_sources=bool(request.data.get('require_sources', False)), require_fact_check=bool(request.data.get('require_fact_check', False)), is_active=bool(request.data.get('is_active', True)))
        return Response(self._payload(rule), status=201)

    def patch(self, request, pk):
        if request.user.role not in {'Admin', 'Editor'}:
            return Response({'detail': 'Only editors and admins can configure workflow rules.'}, status=403)
        rule = get_object_or_404(WorkflowRule, pk=pk, workspace__memberships__user=request.user)
        for field in ('name', 'from_status', 'to_status', 'required_role'):
            if field in request.data:
                setattr(rule, field, str(request.data[field])[:120])
        for field in ('require_sources', 'require_fact_check', 'is_active'):
            if field in request.data:
                setattr(rule, field, bool(request.data[field]))
        rule.save()
        return Response(self._payload(rule))


def _workflow_rule_errors(article, from_status, to_status, user):
    if not article.workspace_id:
        return []
    errors = []
    for rule in WorkflowRule.objects.filter(workspace_id=article.workspace_id, from_status=from_status, to_status=to_status, is_active=True):
        if rule.required_role and user.role.lower() != rule.required_role.lower():
            errors.append(f'{rule.name}: role {rule.required_role} is required.')
        if rule.require_sources and not article.sources.exists():
            errors.append(f'{rule.name}: at least one source is required.')
        if rule.require_fact_check and not article.fact_checks.exists():
            errors.append(f'{rule.name}: a fact check is required.')
    return errors


class ArticleWorkflowActionView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id, action):
        article = get_object_or_404(Article, pk=article_id)
        now = timezone.now()

        if action == 'submit':
            rule_errors = _workflow_rule_errors(article, article.workflow_status, 'submitted', request.user)
            if rule_errors:
                return Response({'detail': 'Workflow rules blocked submission.', 'rules': rule_errors}, status=400)
            if article.author_id != request.user.id and request.user.role not in {'Admin'}:
                return Response({'detail': 'Only the author can submit this article.'}, status=status.HTTP_403_FORBIDDEN)
            if article.workflow_status not in {'draft', 'rejected'}:
                return Response({'detail': 'Only draft or rejected articles can be submitted.'}, status=status.HTTP_400_BAD_REQUEST)
            from .moderation import moderate_text
            moderation_flags = moderate_text(article.title, article.content)
            high_risk = [flag for flag in moderation_flags if flag['severity'] == 'high']
            for flag in moderation_flags:
                ModerationFlag.objects.create(article=article, checked_by=request.user, **flag)
            if high_risk:
                return Response({'detail': 'Article submission blocked by content moderation.', 'flags': high_risk}, status=status.HTTP_400_BAD_REQUEST)
            article.workflow_status = 'submitted'
            article.review_status = 'pending'
            article.status = 'draft'
            article.rejection_reason = None
            article.submitted_at = now
            article.is_visible = False
            article.save(update_fields=['workflow_status', 'review_status', 'status', 'rejection_reason', 'submitted_at', 'is_visible', 'updated_at'])
            record_audit_event(actor=request.user, action='article_submitted', article=article)
            dispatch_webhook_event(
                owner=article.author,
                event_type='article.submitted',
                payload={'article_id': article.id, 'title': article.title, 'status': article.workflow_status},
            )
            for editor in CustomUser.objects.filter(role__in=['Editor', 'Admin'], is_active=True):
                notify(
                    recipient=editor,
                    article=article,
                    notification_type='submitted',
                    message=f'{article.title} was submitted for review.',
                )
            return Response(ArticleWorkflowSerializer(article).data, status=status.HTTP_200_OK)

        if action == 'publish':
            rule_errors = _workflow_rule_errors(article, article.workflow_status, 'published', request.user)
            if rule_errors:
                return Response({'detail': 'Workflow rules blocked publishing.', 'rules': rule_errors}, status=400)
            if request.user.role not in {'Editor', 'Admin'} or not editor_has_capability(request.user, article, 'publish'):
                return Response({'detail': 'Only editors and admins can publish articles.'}, status=status.HTTP_403_FORBIDDEN)
            if article.workflow_status != 'approved':
                return Response({'detail': 'Only approved articles can be published.'}, status=status.HTTP_400_BAD_REQUEST)
            if settings.ACCESSIBILITY_PUBLISH_GATE:
                accessibility = analyze_article_accessibility(article)
                if not accessibility['passed']:
                    return Response({
                        'detail': 'Fix accessibility errors before publishing.',
                        'accessibility': accessibility,
                    }, status=status.HTTP_400_BAD_REQUEST)
            article.workflow_status = 'published'
            article.review_status = 'approved'
            article.status = 'published'
            article.published_at = now
            article.publish_date = now.date()
            article.is_visible = True
            article.save(update_fields=['workflow_status', 'review_status', 'status', 'published_at', 'publish_date', 'is_visible', 'updated_at'])
            record_audit_event(actor=request.user, action='article_published', article=article)
            dispatch_webhook_event(
                owner=article.author,
                event_type='article.published',
                payload={'article_id': article.id, 'title': article.title, 'status': article.workflow_status, 'published_at': article.published_at},
            )
            notify(
                recipient=article.author,
                article=article,
                notification_type='published',
                message=f'{article.title} was published.',
            )
            dispatch_article_alert(article=article, title='New article published', body=article.title)
            return Response(ArticleWorkflowSerializer(article).data)

        if action in {'schedule', 'unschedule'}:
            if request.user.role not in {'Editor', 'Admin'}:
                return Response({'detail': 'Only editors and admins can schedule publishing.'}, status=status.HTTP_403_FORBIDDEN)
            if article.workflow_status != 'approved':
                return Response({'detail': 'Only approved articles can be scheduled.'}, status=status.HTTP_400_BAD_REQUEST)
            if action == 'unschedule':
                article.scheduled_publish_at = None
            else:
                schedule = ArticleScheduleSerializer(data=request.data)
                schedule.is_valid(raise_exception=True)
                scheduled_at = schedule.validated_data.get('scheduled_publish_at')
                if not scheduled_at or scheduled_at <= now:
                    return Response({'detail': 'scheduled_publish_at must be a future datetime.'}, status=status.HTTP_400_BAD_REQUEST)
                article.scheduled_publish_at = scheduled_at
                notify(
                    recipient=article.author,
                    article=article,
                    notification_type='scheduled',
                    message=f'{article.title} is scheduled for publication at {scheduled_at.isoformat()}.',
                )
            article.save(update_fields=['scheduled_publish_at', 'updated_at'])
            record_audit_event(
                actor=request.user,
                action=f'article_{action}d' if action == 'schedule' else 'article_unscheduled',
                article=article,
                details={'scheduled_publish_at': article.scheduled_publish_at.isoformat() if article.scheduled_publish_at else None},
            )
            return Response(ArticleWorkflowSerializer(article).data)

        return Response({'detail': 'Unknown workflow action.'}, status=status.HTTP_404_NOT_FOUND)


class ArticleReviewView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, article_id):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can review articles.'}, status=status.HTTP_403_FORBIDDEN)

        article = get_object_or_404(Article, pk=article_id)
        if not editor_has_capability(request.user, article, 'review'):
            return Response({'detail': 'You are not assigned review access for this article.'}, status=status.HTTP_403_FORBIDDEN)
        if article.workflow_status != 'submitted':
            return Response({'detail': 'Only submitted articles can be reviewed.'}, status=status.HTTP_400_BAD_REQUEST)

        review = ArticleReviewSerializer(data=request.data)
        review.is_valid(raise_exception=True)
        now = timezone.now()
        decision = review.validated_data['decision']
        reason = review.validated_data.get('reason', '').strip()
        article.reviewed_by = request.user
        article.reviewed_at = now
        article.rejection_reason = reason or None
        article.review_status = 'approved' if decision == 'approve' else 'rejected'
        article.workflow_status = 'approved' if decision == 'approve' else 'rejected'
        article.status = 'draft'
        article.is_visible = False
        article.save(update_fields=['reviewed_by', 'reviewed_at', 'rejection_reason', 'review_status', 'workflow_status', 'status', 'is_visible', 'updated_at'])
        record_audit_event(
            actor=request.user,
            action=f'article_{decision}d',
            article=article,
            details={'reason': reason} if reason else {},
        )

        if decision == 'reject':
            Comment.objects.create(article=article, author=request.user, content=reason, is_editorial=True)
        notify(
            recipient=article.author,
            article=article,
            notification_type=article.workflow_status,
            message=(f'{article.title} was approved.' if decision == 'approve' else f'{article.title} was rejected: {reason}'),
        )
        return Response(ArticleWorkflowSerializer(article).data)


class ArticleExportView(APIView):
    permission_classes = [AllowAny]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.workflow_status != 'published' and (not request.user.is_authenticated or (article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'})):
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot export this article.'}, status=status.HTTP_403_FORBIDDEN)
        file_format = request.query_params.get('export_format', 'markdown').lower()
        if file_format == 'markdown':
            response = HttpResponse(markdown_document(article.title, article.subtitle, article.content, article.summary), content_type='text/markdown; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{article.slug}.md"'
            return response
        if file_format == 'docx':
            response = HttpResponse(markdown_to_docx(article.title, article.content).getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="{article.slug}.docx"'
            return response
        if file_format == 'json':
            response = HttpResponse(json.dumps(ArticleWorkflowSerializer(article).data, default=str, indent=2), content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{article.slug}.json"'
            return response
        return Response({'detail': 'format must be markdown, docx, or json.'}, status=status.HTTP_400_BAD_REQUEST)


class ArticleImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        uploaded = request.FILES.get('file')
        content_format = str(request.data.get('content_format', '')).lower().strip()
        title = str(request.data.get('title', '')).strip()
        if uploaded:
            filename = uploaded.name.lower()
            if filename.endswith('.docx'):
                content = docx_to_markdown(uploaded)
                content_format = 'markdown'
            elif filename.endswith(('.md', '.markdown')):
                content = uploaded.read().decode('utf-8')
                content_format = 'markdown'
            else:
                return Response({'detail': 'Only DOCX and Markdown files are supported.'}, status=status.HTTP_400_BAD_REQUEST)
            title = title or uploaded.name.rsplit('.', 1)[0]
        else:
            content = str(request.data.get('content', ''))
            content_format = content_format or 'plain'
        if not content.strip():
            return Response({'detail': 'Article content is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(title) < 10:
            title = f'Imported article: {title}'.strip()[:35]
        article = Article.objects.create(
            title=title[:35], content=content, content_format=content_format,
            summary=content[:500], author=request.user, email=request.user.email,
            agreed_to_terms=True, category=request.data.get('category') or None,
        )
        record_audit_event(actor=request.user, action='article_imported', article=article, details={'content_format': content_format, 'filename': uploaded.name if uploaded else None})
        return Response(ArticleWorkflowSerializer(article).data, status=status.HTTP_201_CREATED)


class ArticleSearchViewV2(ArticleQuerySetMixin, generics.ListAPIView):
    serializer_class = ArticleWorkflowSerializer
    pagination_class = ArticlePagination
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = self.article_queryset().select_related('author').order_by('-created_at')
        if not has_active_membership(self.request.user):
            queryset = queryset.filter(is_premium=False)
        query = self.request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(content__icontains=query) |
                Q(summary__icontains=query) | Q(tags__icontains=query) |
                Q(category__icontains=query)
            )
            queryset = queryset.annotate(
                relevance=Case(
                    When(title__iexact=query, then=Value(100)),
                    When(title__istartswith=query, then=Value(80)),
                    When(title__icontains=query, then=Value(60)),
                    When(summary__icontains=query, then=Value(40)),
                    When(content__icontains=query, then=Value(20)),
                    default=Value(10),
                    output_field=IntegerField(),
                )
            )
        workflow_status = self.request.query_params.get('workflow_status') or self.request.query_params.get('status')
        if workflow_status:
            queryset = queryset.filter(workflow_status=workflow_status)
        for field in ('category', 'author_id'):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        published_from = self.request.query_params.get('published_from')
        published_to = self.request.query_params.get('published_to')
        if published_from:
            if parse_date(published_from) is None:
                raise ValidationError({'published_from': 'Use YYYY-MM-DD.'})
            queryset = queryset.filter(publish_date__gte=published_from)
        if published_to:
            if parse_date(published_to) is None:
                raise ValidationError({'published_to': 'Use YYYY-MM-DD.'})
            queryset = queryset.filter(publish_date__lte=published_to)
        sort = self.request.query_params.get('sort', 'relevance' if query else 'recent')
        if sort == 'popular':
            return queryset.annotate(view_count=Count('views'), like_count=Count('likes')).order_by('-view_count', '-like_count', '-created_at')
        if sort == 'recent':
            return queryset.order_by('-created_at')
        if sort == 'oldest':
            return queryset.order_by('created_at')
        return queryset.order_by('-relevance', '-created_at')


@method_decorator(cache_page(60), name='dispatch')
class ArticleAutocompleteView(generics.ListAPIView):
    serializer_class = ArticleWorkflowSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()[:80]
        if len(query) < 2:
            return Article.objects.none()
        return Article.objects.filter(
            workflow_status='published',
            is_visible=True,
            title__icontains=query,
        ).select_related('author').order_by('title')[:10]


def _semantic_tokens(value):
    return {token for token in re.findall(r'[a-z0-9]{3,}', (value or '').lower()) if token not in {'the', 'and', 'for', 'with', 'from', 'this', 'that'}}


def _article_similarity(left, right):
    left_tokens = _semantic_tokens(f'{left.title} {left.summary} {left.content} {left.tags}')
    right_tokens = _semantic_tokens(f'{right.title} {right.summary} {right.content} {right.tags}')
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    title_score = difflib.SequenceMatcher(None, (left.title or '').lower(), (right.title or '').lower()).ratio()
    return round((overlap * 0.7 + title_score * 0.3) * 100, 2)


class SemanticArticleSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = str(request.query_params.get('q', '')).strip()
        if len(query) < 3:
            return Response({'detail': 'q must contain at least 3 characters.'}, status=400)
        query_tokens = _semantic_tokens(query)
        queryset = Article.objects.filter(workflow_status='published', is_visible=True).select_related('author')
        if not has_active_membership(request.user):
            queryset = queryset.filter(is_premium=False)
        ranked = []
        for article in queryset[:500]:
            article_tokens = _semantic_tokens(f'{article.title} {article.summary} {article.content} {article.tags}')
            overlap = len(query_tokens & article_tokens) / max(len(query_tokens), 1)
            title_score = difflib.SequenceMatcher(None, query.lower(), (article.title or '').lower()).ratio()
            score = round((overlap * 0.75 + title_score * 0.25) * 100, 2)
            if score >= 5:
                ranked.append((score, article))
        ranked.sort(key=lambda item: (item[0], item[1].published_at or item[1].created_at), reverse=True)
        articles = [article for _, article in ranked[:20]]
        data = ArticleWorkflowSerializer(articles, many=True, context={'request': request}).data
        for item, (score, _) in zip(data, ranked[:20]):
            item['semantic_score'] = score
        return Response({'query': query, 'results': data, 'count': len(data), 'engine': 'local-token-similarity-v1'})


class HybridArticleSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = str(request.query_params.get('q', '')).strip()
        if len(query) < 2:
            return Response({'detail': 'q must contain at least 2 characters.'}, status=400)
        lexical = Article.objects.filter(workflow_status='published', is_visible=True).filter(
            Q(title__icontains=query) | Q(summary__icontains=query) | Q(content__icontains=query) |
            Q(category__icontains=query) | Q(tags__icontains=query)
        ).select_related('author')
        if not has_active_membership(request.user):
            lexical = lexical.filter(is_premium=False)
        query_tokens = _semantic_tokens(query)
        ranked = []
        for article in lexical[:100]:
            lexical_score = 100 if query.lower() in (article.title or '').lower() else 55
            semantic_score = _article_similarity(article, article) if query.lower() == (article.title or '').lower() else round(
                len(query_tokens & _semantic_tokens(f'{article.title} {article.summary} {article.content} {article.tags}')) / max(len(query_tokens), 1) * 100, 2
            )
            ranked.append((round(lexical_score * 0.65 + semantic_score * 0.35, 2), article))
        ranked.sort(key=lambda item: item[0], reverse=True)
        data = ArticleWorkflowSerializer([item[1] for item in ranked[:20]], many=True, context={'request': request}).data
        for item, (score, _) in zip(data, ranked[:20]):
            item['hybrid_score'] = score
        return Response({'query': query, 'engine': 'lexical-plus-token-v1', 'count': len(data), 'results': data})


class ArticleDuplicateCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot check duplicates for this article.'}, status=403)
        candidates = Article.objects.exclude(pk=article.id).filter(author=article.author).order_by('-updated_at')[:100]
        matches = sorted(((_article_similarity(article, candidate), candidate) for candidate in candidates), key=lambda item: item[0], reverse=True)[:5]
        return Response({'article_id': article.id, 'matches': [{'article_id': candidate.id, 'title': candidate.title, 'similarity': score, 'review_required': score >= 55} for score, candidate in matches]})


class RevisionListView(generics.ListAPIView):
    serializer_class = RevisionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        article = get_object_or_404(Article, pk=self.kwargs['article_id'])
        if article.author_id != self.request.user.id and self.request.user.role not in {'Editor', 'Admin'}:
            return ArticleRevision.objects.none()
        return article.revisions.select_related('editor').all()


class RevisionCompareView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot compare revisions for this article.'}, status=status.HTTP_403_FORBIDDEN)
        from_id = request.query_params.get('from')
        to_id = request.query_params.get('to')
        if not from_id or not to_id:
            return Response({'detail': 'Both from and to revision IDs are required.'}, status=status.HTTP_400_BAD_REQUEST)

        def snapshot(revision_id):
            if revision_id == 'current':
                return {'id': 'current', 'title': article.title, 'content': article.content, 'summary': article.summary or ''}
            revision = get_object_or_404(article.revisions, pk=revision_id)
            return {'id': revision.id, 'title': revision.title, 'content': revision.content, 'summary': revision.summary or ''}

        left = snapshot(from_id)
        right = snapshot(to_id)
        diff = list(difflib.unified_diff(
            left['content'].splitlines(),
            right['content'].splitlines(),
            fromfile=f"revision-{left['id']}",
            tofile=f"revision-{right['id']}",
            lineterm='',
        ))
        return Response({'from': left, 'to': right, 'changed': left != right, 'content_diff': diff})


class RevisionRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot restore revisions for this article.'}, status=403)
        revision = get_object_or_404(article.revisions, pk=request.data.get('revision_id'))
        with transaction.atomic():
            ArticleRevision.objects.create(
                article=article, editor=request.user, title=article.title,
                subtitle=article.subtitle, content=article.content,
                summary=article.summary, category=article.category, tags=article.tags,
            )
            article.title = revision.title
            article.subtitle = revision.subtitle
            article.content = revision.content
            article.summary = revision.summary
            article.category = revision.category
            article.tags = revision.tags
            article.save(update_fields=['title', 'subtitle', 'content', 'summary', 'category', 'tags', 'updated_at'])
            record_audit_event(actor=request.user, action='article_revision_restored', article=article, details={'revision_id': revision.id})
        return Response(ArticleWorkflowSerializer(article, context={'request': request}).data)


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        article = get_object_or_404(Article, pk=self.kwargs['article_id'])
        queryset = article.comments.select_related('author').all()
        if self.request.user.role not in {'Editor', 'Admin'} and article.author_id != self.request.user.id:
            queryset = queryset.filter(is_editorial=False, moderation_status='visible')
        return queryset

    def perform_create(self, serializer):
        article = get_object_or_404(Article, pk=self.kwargs['article_id'])
        parent = serializer.validated_data.get('parent')
        if parent and parent.article_id != article.id:
            raise ValidationError({'parent': 'Parent comment must belong to the same article.'})
        comment = serializer.save(
            article=article,
            author=self.request.user,
            is_editorial=self.request.user.role in {'Editor', 'Admin'},
        )
        from .moderation import moderate_comment
        flags = moderate_comment(comment.content)
        if flags:
            comment.moderation_status = 'pending'
            comment.moderation_reason = flags[0]
            comment.save(update_fields=['moderation_status', 'moderation_reason', 'updated_at'])
        if article.author_id != self.request.user.id:
            notify(
                recipient=article.author,
                article=article,
                notification_type='comment',
                    message=f'{self.request.user.username} commented on {article.title}.',
            )


class CommentReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        reason = str(request.data.get('reason', '')).strip()
        if len(reason) < 3:
            return Response({'detail': 'A report reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
        report, created = CommentReport.objects.get_or_create(
            comment=comment, reported_by=request.user, defaults={'reason': reason},
        )
        if not created:
            return Response({'detail': 'You have already reported this comment.'}, status=status.HTTP_409_CONFLICT)
        return Response(CommentReportSerializer(report).data, status=status.HTTP_201_CREATED)


class CommentModerationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can view the moderation queue.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = CommentReport.objects.select_related('comment', 'reported_by', 'reviewed_by').all()
        if request.query_params.get('status'):
            queryset = queryset.filter(status=request.query_params['status'])
        return Response(CommentReportSerializer(queryset, many=True).data)

    def patch(self, request, pk):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can resolve comment reports.'}, status=status.HTTP_403_FORBIDDEN)
        report = get_object_or_404(CommentReport.objects.select_related('comment'), pk=pk)
        decision = str(request.data.get('decision', '')).strip().lower()
        decisions = {'hide': 'hidden', 'remove': 'removed', 'restore': 'visible', 'dismiss': 'visible'}
        if decision not in decisions:
            return Response({'detail': 'Decision must be hide, remove, restore, or dismiss.'}, status=status.HTTP_400_BAD_REQUEST)
        report.status = 'dismissed' if decision == 'dismiss' else 'reviewed'
        report.resolution = str(request.data.get('resolution', '')).strip()
        report.reviewed_by = request.user
        report.save(update_fields=['status', 'resolution', 'reviewed_by', 'updated_at'])
        comment = report.comment
        comment.moderation_status = decisions[decision]
        comment.moderation_reason = report.resolution
        comment.save(update_fields=['moderation_status', 'moderation_reason', 'updated_at'])
        record_audit_event(actor=request.user, action='comment_moderated', article=comment.article, details={'comment_id': comment.id, 'decision': decision})
        return Response(CommentReportSerializer(report).data)


class CommentDeleteView(generics.DestroyAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Comment.objects.all()

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot delete this comment.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class LikeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        like, created = Like.objects.get_or_create(article=article, user=request.user)
        if not created:
            like.delete()
        return Response({'article': article.id, 'liked': created, 'likes_count': article.likes.count()})


class BookmarkListView(generics.ListAPIView):
    serializer_class = BookmarkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Bookmark.objects.filter(user=self.request.user).select_related('article')


class BookmarkToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        bookmark, created = Bookmark.objects.get_or_create(article=article, user=request.user)
        if not created:
            bookmark.delete()
        return Response({'article': article.id, 'bookmarked': created})


class ReadingProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.workflow_status != 'published' and article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot access this article progress.'}, status=status.HTTP_403_FORBIDDEN)
        progress = ReadingProgress.objects.filter(article=article, user=request.user).first()
        return Response(ReadingProgressSerializer(progress).data if progress else {
            'article': article.id, 'article_title': article.title, 'progress_percent': 0,
            'position_seconds': 0, 'completed': False,
        })

    def put(self, request, article_id):
        return self.save_progress(request, article_id)

    def patch(self, request, article_id):
        return self.save_progress(request, article_id)

    def save_progress(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot update this article progress.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ReadingProgressSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if values.get('progress_percent') == 100:
            values['completed'] = True
        progress, _ = ReadingProgress.objects.update_or_create(
            article=article, user=request.user, defaults=values,
        )
        return Response(ReadingProgressSerializer(progress).data)


class ArticleReactionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        counts = {value: article.reactions.filter(reaction=value).count() for value, _ in ArticleReaction.REACTION_CHOICES}
        current = None
        if request.user.is_authenticated:
            current = article.reactions.filter(user=request.user).values_list('reaction', flat=True).first()
        return Response({'article': article.id, 'counts': counts, 'my_reaction': current})

    def post(self, request, article_id):
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication is required to react.'}, status=status.HTTP_401_UNAUTHORIZED)
        article = get_object_or_404(Article, pk=article_id)
        reaction = request.data.get('reaction')
        valid_reactions = {value for value, _ in ArticleReaction.REACTION_CHOICES}
        if reaction not in valid_reactions:
            return Response({'reaction': f'Choose one of: {", ".join(sorted(valid_reactions))}.'}, status=status.HTTP_400_BAD_REQUEST)
        current = ArticleReaction.objects.filter(article=article, user=request.user).first()
        if current and current.reaction == reaction:
            current.delete()
            active = None
        else:
            if current:
                current.reaction = reaction
                current.save(update_fields=['reaction', 'updated_at'])
            else:
                ArticleReaction.objects.create(article=article, user=request.user, reaction=reaction)
            active = reaction
        return Response({'article': article.id, 'my_reaction': active, 'counts': {value: article.reactions.filter(reaction=value).count() for value, _ in ArticleReaction.REACTION_CHOICES}})


class PlagiarismCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot view this plagiarism report.'}, status=status.HTTP_403_FORBIDDEN)
        check = article.plagiarism_checks.select_related('matched_article', 'checked_by').first()
        return Response(PlagiarismCheckSerializer(check).data if check else {'check': None})

    def post(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot check this article.'}, status=status.HTTP_403_FORBIDDEN)
        from .plagiarism import find_plagiarism_match
        matched_article, score, result_status = find_plagiarism_match(article)
        check = PlagiarismCheck.objects.create(
            article=article,
            checked_by=request.user,
            similarity_score=score,
            status=result_status,
            matched_article=matched_article,
            matched_excerpt=matched_article.content[:500] if matched_article else '',
        )
        return Response(PlagiarismCheckSerializer(check).data, status=status.HTTP_201_CREATED)


class ModerationView(APIView):
    permission_classes = [IsAuthenticated]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot view moderation results for this article.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(ModerationFlagSerializer(article.moderation_flags.select_related('checked_by'), many=True).data)

    def post(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot moderate this article.'}, status=status.HTTP_403_FORBIDDEN)
        from .moderation import moderate_text
        flags = moderate_text(article.title, article.content)
        created = [ModerationFlag.objects.create(article=article, checked_by=request.user, **flag) for flag in flags]
        return Response(ModerationFlagSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class ArticleTranslationListView(APIView):
    permission_classes = [AllowAny]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.workflow_status != 'published' and (
            not request.user.is_authenticated or (article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'})
        ):
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'Translations are not publicly available.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = article.translations.all()
        if not request.user.is_authenticated or (request.user.role == 'Journalist' and request.user.id != article.author_id):
            queryset = queryset.filter(status='published')
        return Response(ArticleTranslationSerializer(queryset, many=True).data)

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot manage translations for this article.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ArticleTranslationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('status') == 'published' and request.user.role == 'Journalist':
            return Response({'detail': 'Only editors and admins can publish translations.'}, status=status.HTTP_403_FORBIDDEN)
        translation, _ = ArticleTranslation.objects.update_or_create(
            article=article,
            language_code=serializer.validated_data['language_code'],
            defaults={**serializer.validated_data, 'translated_by': request.user},
        )
        record_audit_event(actor=request.user, action='article_translation_updated', article=article, details={'language_code': translation.language_code})
        return Response(ArticleTranslationSerializer(translation).data, status=status.HTTP_201_CREATED)


class ArticleTranslationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, translation_id):
        translation = get_object_or_404(ArticleTranslation, pk=translation_id)
        if translation.article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot edit this translation.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ArticleTranslationSerializer(translation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get('status') in {'approved', 'published'} and request.user.role == 'Journalist':
            return Response({'detail': 'Only editors and admins can publish translations.'}, status=status.HTTP_403_FORBIDDEN)
        values = dict(serializer.validated_data)
        if request.user.role in {'Editor', 'Admin'} and values.get('status') in {'approved', 'published'}:
            values.update({'reviewed_by': request.user, 'reviewed_at': timezone.now()})
        serializer.save(**values)
        return Response(serializer.data)


class ArticleTranslationReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, translation_id):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can review translations.'}, status=status.HTTP_403_FORBIDDEN)
        translation = get_object_or_404(ArticleTranslation, pk=translation_id)
        decision = str(request.data.get('decision', '')).strip().lower()
        status_map = {'approve': 'approved', 'publish': 'published', 'return': 'draft'}
        if decision not in status_map:
            return Response({'detail': 'Decision must be approve, publish, or return.'}, status=status.HTTP_400_BAD_REQUEST)
        translation.status = status_map[decision]
        translation.review_notes = str(request.data.get('review_notes', '')).strip()
        translation.reviewed_by = request.user
        translation.reviewed_at = timezone.now()
        translation.save(update_fields=['status', 'review_notes', 'reviewed_by', 'reviewed_at', 'updated_at'])
        record_audit_event(actor=request.user, action='article_translation_reviewed', article=translation.article, details={'translation_id': translation.id, 'decision': decision})
        return Response(ArticleTranslationSerializer(translation).data)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get('unread') in {'1', 'true'}:
            queryset = queryset.filter(is_read=False)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response['X-Unread-Count'] = str(Notification.objects.filter(recipient=request.user, is_read=False).count())
        return response


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        return Response(NotificationSerializer(notification).data)


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ArticlePagination

    def get_queryset(self):
        if self.request.user.role not in {'Editor', 'Admin'}:
            return AuditLog.objects.filter(actor=self.request.user)
        queryset = AuditLog.objects.select_related('actor', 'article').all()
        article_id = self.request.query_params.get('article_id')
        action = self.request.query_params.get('action')
        if article_id:
            queryset = queryset.filter(article_id=article_id)
        if action:
            queryset = queryset.filter(action=action)
        return queryset


class ArticleTrashView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id, action):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can manage the article trash.'}, status=status.HTTP_403_FORBIDDEN)
        article = get_object_or_404(Article.all_objects, pk=article_id)
        if action == 'trash':
            if article.is_deleted:
                return Response({'detail': 'Article is already in the trash.'}, status=status.HTTP_400_BAD_REQUEST)
            article.is_deleted = True
            article.deleted_at = timezone.now()
            article.is_visible = False
            article.save(update_fields=['is_deleted', 'deleted_at', 'is_visible', 'updated_at'])
            record_audit_event(actor=request.user, action='article_trashed', article=article)
        elif action == 'restore':
            if not article.is_deleted:
                return Response({'detail': 'Article is not in the trash.'}, status=status.HTTP_400_BAD_REQUEST)
            article.is_deleted = False
            article.deleted_at = None
            article.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
            record_audit_event(actor=request.user, action='article_restored', article=article)
        else:
            return Response({'detail': 'Unknown trash action.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ArticleWorkflowSerializer(article).data)

    def get(self, request, article_id=None, action=None):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can view the article trash.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = Article.all_objects.filter(is_deleted=True).select_related('author').order_by('-deleted_at')
        if article_id:
            queryset = queryset.filter(pk=article_id)
        return Response(ArticleWorkflowSerializer(queryset, many=True).data)


class ArticleAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can view assignments.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(ArticleAssignmentSerializer(article.assignments.select_related('editor'), many=True).data)

    def post(self, request, article_id):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage article assignments.'}, status=status.HTTP_403_FORBIDDEN)
        article = get_object_or_404(Article, pk=article_id)
        serializer = ArticleAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        editor = serializer.validated_data['editor']
        if editor.role != 'Editor':
            return Response({'detail': 'Assignments can only be given to Editors.'}, status=status.HTTP_400_BAD_REQUEST)
        assignment, _ = ArticleAssignment.objects.update_or_create(
            article=article,
            editor=editor,
            defaults={key: serializer.validated_data[key] for key in ('can_review', 'can_edit', 'can_publish', 'status', 'priority', 'due_at', 'notes') if key in serializer.validated_data},
        )
        record_audit_event(actor=request.user, action='article_assignment_updated', article=article, details={'editor_id': editor.id})
        return Response(ArticleAssignmentSerializer(assignment).data, status=status.HTTP_200_OK)

    def patch(self, request, article_id):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can update assignments.'}, status=status.HTTP_403_FORBIDDEN)
        assignment = get_object_or_404(ArticleAssignment, article_id=article_id, pk=request.data.get('assignment_id'))
        serializer = ArticleAssignmentSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_audit_event(actor=request.user, action='article_assignment_board_updated', article=assignment.article, details={'assignment_id': assignment.id})
        return Response(serializer.data)

    def delete(self, request, article_id):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage article assignments.'}, status=status.HTTP_403_FORBIDDEN)
        article = get_object_or_404(Article, pk=article_id)
        editor_id = request.query_params.get('editor_id')
        deleted, _ = ArticleAssignment.objects.filter(article=article, editor_id=editor_id).delete()
        if not deleted:
            return Response({'detail': 'Assignment not found.'}, status=status.HTTP_404_NOT_FOUND)
        record_audit_event(actor=request.user, action='article_assignment_removed', article=article, details={'editor_id': editor_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignmentBoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can view the assignment board.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = ArticleAssignment.objects.select_related('article', 'article__author', 'editor')
        status_filter = request.query_params.get('status')
        priority_filter = request.query_params.get('priority')
        editor_id = request.query_params.get('editor_id')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        if editor_id:
            queryset = queryset.filter(editor_id=editor_id)
        return Response({
            'count': queryset.count(),
            'columns': {column: ArticleAssignmentSerializer(queryset.filter(status=column), many=True).data for column, _ in ArticleAssignment.STATUS_CHOICES},
        })


class EditorialSLADashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can view editorial SLA metrics.'}, status=403)
        now = timezone.now()
        assignments = ArticleAssignment.objects.select_related('article', 'editor').all()
        overdue = assignments.filter(due_at__lt=now).exclude(status='done')
        upcoming = assignments.filter(due_at__gte=now, due_at__lte=now + timedelta(hours=48)).exclude(status='done')
        workload = {}
        for item in assignments.exclude(status='done'):
            bucket = workload.setdefault(item.editor_id, {'editor_id': item.editor_id, 'editor': item.editor.username, 'open_assignments': 0, 'urgent': 0})
            bucket['open_assignments'] += 1
            bucket['urgent'] += int(item.priority == 'urgent')
        turnaround = []
        for article in Article.objects.filter(submitted_at__isnull=False, reviewed_at__isnull=False).only('submitted_at', 'reviewed_at')[:500]:
            turnaround.append((article.reviewed_at - article.submitted_at).total_seconds() / 3600)
        average_hours = round(sum(turnaround) / len(turnaround), 2) if turnaround else None
        return Response({
            'overdue_count': overdue.count(),
            'upcoming_deadline_count': upcoming.count(),
            'average_review_hours': average_hours,
            'workload': sorted(workload.values(), key=lambda item: (-item['open_assignments'], item['editor'])),
            'overdue': [{'id': item.id, 'article': item.article.title, 'editor': item.editor.username, 'due_at': item.due_at, 'priority': item.priority} for item in overdue[:30]],
            'upcoming': [{'id': item.id, 'article': item.article.title, 'editor': item.editor.username, 'due_at': item.due_at, 'priority': item.priority} for item in upcoming[:30]],
        })


class EditorialCalendarView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can manage the editorial calendar.'}, status=403)
        articles = Article.objects.filter(scheduled_publish_at__isnull=False).select_related('author').order_by('scheduled_publish_at')
        return Response([{'id': article.id, 'title': article.title, 'author': article.author.username, 'workflow_status': article.workflow_status, 'scheduled_publish_at': article.scheduled_publish_at} for article in articles])

    def patch(self, request, article_id):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can reschedule articles.'}, status=403)
        article = get_object_or_404(Article, pk=article_id)
        scheduled_at = parse_datetime(str(request.data.get('scheduled_publish_at', '')))
        if not scheduled_at or scheduled_at <= timezone.now():
            return Response({'detail': 'Choose a future publication time.'}, status=400)
        if article.workflow_status not in {'approved', 'published'}:
            return Response({'detail': 'Only approved articles can be scheduled.'}, status=400)
        article.scheduled_publish_at = scheduled_at
        article.save(update_fields=['scheduled_publish_at', 'updated_at'])
        record_audit_event(actor=request.user, action='article_rescheduled', article=article, details={'scheduled_publish_at': scheduled_at.isoformat()})
        return Response({'id': article.id, 'scheduled_publish_at': article.scheduled_publish_at})


class ArticleFeatureView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, article_id):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can feature articles.'}, status=status.HTTP_403_FORBIDDEN)
        article = get_object_or_404(Article, pk=article_id)
        is_featured = request.data.get('is_featured')
        if not isinstance(is_featured, bool):
            return Response({'is_featured': 'This value must be true or false.'}, status=status.HTTP_400_BAD_REQUEST)
        article.is_featured = is_featured
        article.featured_at = timezone.now() if is_featured else None
        article.save(update_fields=['is_featured', 'featured_at', 'updated_at'])
        record_audit_event(actor=request.user, action='article_featured' if is_featured else 'article_unfeatured', article=article)
        return Response(ArticleWorkflowSerializer(article).data)


class ArticleGalleryView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.workflow_status != 'published' and (
            article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}
        ):
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'This gallery is not publicly available.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(ArticleImageSerializer(article.images.all(), many=True, context={'request': request}).data)

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot add images to this article.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ArticleImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.save(article=article)
        record_audit_event(actor=request.user, action='article_image_added', article=article, details={'image_id': image.id})
        return Response(ArticleImageSerializer(image, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ArticleImageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        image = get_object_or_404(ArticleImage, pk=pk)
        if image.article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot delete this image.'}, status=status.HTTP_403_FORBIDDEN)
        article = image.article
        image.delete()
        record_audit_event(actor=request.user, action='article_image_deleted', article=article, details={'image_id': pk})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArticleAutosaveView(APIView):
    permission_classes = [IsAuthenticated]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot access this draft.'}, status=status.HTTP_403_FORBIDDEN)
        autosave = ArticleAutosave.objects.filter(article=article).first()
        if autosave is None:
            return Response({'autosave': None})
        return Response(ArticleAutosaveSerializer(autosave).data)

    def put(self, request, article_id):
        return self.save_autosave(request, article_id)

    def patch(self, request, article_id):
        return self.save_autosave(request, article_id)

    def save_autosave(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot edit this draft.'}, status=status.HTTP_403_FORBIDDEN)
        if article.workflow_status == 'published' and request.user.role == 'Journalist':
            return Response({'detail': 'Published articles cannot be autosaved by journalists.'}, status=status.HTTP_400_BAD_REQUEST)
        base_updated_at = request.data.get('base_updated_at')
        current_autosave = ArticleAutosave.objects.filter(article=article).first()
        if base_updated_at and current_autosave:
            client_timestamp = parse_datetime(str(base_updated_at))
            if client_timestamp is None:
                return Response({'detail': 'base_updated_at must be a valid ISO-8601 datetime.'}, status=status.HTTP_400_BAD_REQUEST)
            if client_timestamp < current_autosave.updated_at:
                return Response({
                    'detail': 'This draft changed in another session. Reload the latest autosave before saving.',
                    'conflict': True,
                    'autosave': ArticleAutosaveSerializer(current_autosave).data,
                }, status=status.HTTP_409_CONFLICT)

        serializer = ArticleAutosaveSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        autosave, _ = ArticleAutosave.objects.update_or_create(
            article=article,
            defaults={**serializer.validated_data, 'editor': request.user},
        )
        record_audit_event(actor=request.user, action='article_autosaved', article=article)
        return Response(ArticleAutosaveSerializer(autosave).data)

    def delete(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot clear this draft.'}, status=status.HTTP_403_FORBIDDEN)
        ArticleAutosave.objects.filter(article=article).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArticleSEOView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return None
        return article

    def get(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot access this article SEO data.'}, status=status.HTTP_403_FORBIDDEN)
        response = ArticleSEOSerializer(article, context={'request': request}).data
        response['seo_preview'] = build_article_seo_payload(article, request)
        return Response(response)

    def patch(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot edit this article SEO data.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ArticleSEOSerializer(article, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_audit_event(actor=request.user, action='article_seo_updated', article=article, details={'fields': sorted(request.data.keys())})
        response = serializer.data
        response['seo_preview'] = build_article_seo_payload(article, request)
        return Response(response)


class ArticleAccessibilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot access this article quality report.'}, status=status.HTTP_403_FORBIDDEN)
        return Response({'article_id': article.id, 'title': article.title, **analyze_article_accessibility(article)})


class ArticleDiscoveryView(generics.ListAPIView):
    serializer_class = ArticleWorkflowSerializer
    pagination_class = ArticlePagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Article.objects.filter(workflow_status='published', is_visible=True).select_related('author')
        if not has_active_membership(self.request.user):
            queryset = queryset.filter(is_premium=False)
        mode = self.request.query_params.get('mode', 'featured')
        if mode == 'trending':
            return queryset.annotate(
                view_count=Count('views'),
                like_count=Count('likes'),
            ).order_by('-view_count', '-like_count', '-published_at')
        return queryset.filter(is_featured=True).order_by('-featured_at', '-published_at')


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self, report_type):
        if report_type == 'audit':
            queryset = AuditLog.objects.select_related('actor', 'article').all()
            return queryset if self.request.user.role in {'Editor', 'Admin'} else queryset.filter(actor=self.request.user)
        queryset = Article.objects.select_related('author').prefetch_related('views', 'likes')
        return queryset if self.request.user.role in {'Editor', 'Admin'} else queryset.filter(author=self.request.user)

    def get(self, request, report_type):
        if report_type not in {'articles', 'analytics', 'audit'}:
            return Response({'detail': 'Supported reports are articles, analytics, and audit.'}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report_type}-report.csv"'
        writer = csv.writer(response)
        queryset = self.get_queryset(report_type)
        if report_type == 'audit':
            writer.writerow(['id', 'actor', 'article_id', 'action', 'target_model', 'target_id', 'details', 'created_at'])
            for item in queryset:
                writer.writerow([item.id, item.actor.username if item.actor else '', item.article_id, item.action, item.target_model, item.target_id, item.details, item.created_at.isoformat()])
        elif report_type == 'analytics':
            writer.writerow(['article_id', 'title', 'views', 'likes', 'comments', 'workflow_status'])
            for item in queryset:
                writer.writerow([item.id, item.title, item.views.count(), item.likes.count(), item.comments.count(), item.workflow_status])
        else:
            writer.writerow(['id', 'title', 'author', 'category', 'workflow_status', 'is_featured', 'published_at', 'created_at'])
            for item in queryset:
                writer.writerow([item.id, item.title, item.author.username, item.category, item.workflow_status, item.is_featured, item.published_at.isoformat() if item.published_at else '', item.created_at.isoformat()])
        return response


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        started_at = time.perf_counter()
        checks = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            checks['database'] = 'ok'
        except Exception:
            checks['database'] = 'unavailable'
            if request.query_params.get('verbose') not in {'1', 'true', 'yes'}:
                return Response({'status': 'unhealthy', 'database': 'unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if request.query_params.get('verbose') in {'1', 'true', 'yes'}:
            try:
                cache_key = f'health-check-{getattr(request, "request_id", "local")}'
                cache.set(cache_key, 'ok', timeout=5)
                checks['cache'] = 'ok' if cache.get(cache_key) == 'ok' else 'unavailable'
                cache.delete(cache_key)
            except Exception:
                checks['cache'] = 'unavailable'
            try:
                default_storage.listdir('')
                checks['storage'] = 'ok'
            except Exception:
                checks['storage'] = 'unavailable'
            checks['channel_layer'] = 'ok' if getattr(settings, 'CHANNEL_LAYERS', None) else 'not_configured'
            checks['queue'] = 'ok' if getattr(settings, 'CELERY_BROKER_URL', '') or getattr(settings, 'CELERY_BROKER_TRANSPORT', '') else 'not_configured'
            healthy = all(value in {'ok', 'not_configured'} for value in checks.values())
            return Response({
                'status': 'healthy' if healthy else 'unhealthy',
                'database': checks['database'],
                'checks': checks,
                'latency_ms': round((time.perf_counter() - started_at) * 1000, 2),
                'environment': 'development' if settings.DEBUG else 'production',
                'database_engine': settings.DATABASES['default']['ENGINE'].rsplit('.', 1)[-1],
                'request_id': getattr(request, 'request_id', None),
            }, status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'status': 'healthy', 'database': 'ok'})


class BackupOperationsView(APIView):
    permission_classes = [IsAuthenticated]

    def admin_only(self, request):
        return request.user.role == 'Admin'

    def get(self, request):
        if not self.admin_only(request):
            return Response({'detail': 'Only admins can view backup operations.'}, status=403)
        from .backup import verify_database_backup
        records = BackupRecord.objects.select_related('initiated_by')[:50]
        return Response({
            'database_engine': settings.DATABASES['default']['ENGINE'].rsplit('.', 1)[-1],
            'backup_root': str(settings.BACKUP_ROOT),
            'retention_days': settings.BACKUP_RETENTION_DAYS,
            'records': [{'id': item.id, 'kind': item.kind, 'status': item.status, 'path': item.path, 'checksum': item.checksum, 'size_bytes': item.size_bytes, 'error': item.error, 'initiated_by': item.initiated_by.username if item.initiated_by else None, 'created_at': item.created_at, 'completed_at': item.completed_at, 'verified': verify_database_backup(item) if item.kind == 'database' else None} for item in records],
        })

    def post(self, request):
        if not self.admin_only(request):
            return Response({'detail': 'Only admins can create backups.'}, status=403)
        from .backup import create_database_backup
        record = create_database_backup(request.user)
        payload = {'id': record.id, 'status': record.status, 'path': record.path, 'checksum': record.checksum, 'size_bytes': record.size_bytes, 'error': record.error}
        return Response(payload, status=201 if record.status == 'completed' else 503)


class WorkspaceContentMigrationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can inspect workspace migration.'}, status=403)
        return Response({
            'unassigned_articles': Article.objects.filter(workspace__isnull=True).count(),
            'unassigned_media_assets': MediaAsset.objects.filter(workspace__isnull=True).count(),
        })

    def post(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can migrate workspace content.'}, status=403)
        workspace = get_object_or_404(Workspace, slug=request.data.get('workspace_slug'), is_active=True)
        kinds = set(request.data.get('kinds') or ['articles', 'media'])
        dry_run = bool(request.data.get('dry_run', False))
        article_qs = Article.objects.filter(workspace__isnull=True)
        media_qs = MediaAsset.objects.filter(workspace__isnull=True)
        article_ids = request.data.get('article_ids')
        if article_ids:
            article_qs = article_qs.filter(pk__in=article_ids)
        media_ids = request.data.get('media_ids')
        if media_ids:
            media_qs = media_qs.filter(pk__in=media_ids)
        counts = {'articles': article_qs.count() if 'articles' in kinds else 0, 'media': media_qs.count() if 'media' in kinds else 0}
        if not dry_run:
            with transaction.atomic():
                if 'articles' in kinds:
                    article_qs.update(workspace=workspace)
                if 'media' in kinds:
                    media_qs.update(workspace=workspace)
                record_audit_event(actor=request.user, action='workspace_content_migrated', details={'workspace': workspace.slug, **counts})
        return Response({'workspace': workspace.slug, 'dry_run': dry_run, 'migrated': counts})


class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        if self.request.user.role != 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can create categories.')
        serializer.save()


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def check_admin(self):
        if self.request.user.role != 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can manage categories.')

    def perform_update(self, serializer):
        self.check_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self.check_admin()
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class TagListCreateView(generics.ListCreateAPIView):
    queryset = Tag.objects.order_by('name')
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        if self.request.user.role != 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can create tags.')
        serializer.save()


class TagDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

    def check_admin(self):
        if self.request.user.role != 'Admin':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Only admins can manage tags.')

    def perform_update(self, serializer):
        self.check_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self.check_admin()
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class ArticleAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, article_id=None):
        queryset = Article.objects.all()
        if article_id:
            article = get_object_or_404(queryset, pk=article_id)
            if article.author_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
                return Response({'detail': 'You cannot view these analytics.'}, status=status.HTTP_403_FORBIDDEN)
            return Response({
                'article_id': article.id,
                'title': article.title,
                'views': article.views.count(),
                'likes': article.likes.count(),
                'comments': article.comments.count(),
                'engagement_events': article.engagement_events.count(),
                'completed_reads': article.engagement_events.filter(event_type='read_complete').count(),
                'shares': article.engagement_events.filter(event_type='share').count(),
                'average_read_progress': article.engagement_events.filter(event_type='read_progress').aggregate(avg=Avg('value'))['avg'] or 0,
                'workflow_status': article.workflow_status,
            })

        if request.user.role not in {'Editor', 'Admin'}:
            queryset = queryset.filter(author=request.user)
        window_start = timezone.now() - timedelta(days=7)
        event_queryset = ArticleEngagementEvent.objects.filter(article__in=queryset, created_at__gte=window_start)
        active_readers = event_queryset.exclude(user__isnull=True).values('user_id').distinct().count()
        returning_readers = event_queryset.exclude(user__isnull=True).filter(user_id__in=ArticleEngagementEvent.objects.filter(article__in=queryset, created_at__lt=window_start).values('user_id')).values('user_id').distinct().count()
        funnel = {event_type: event_queryset.filter(event_type=event_type).count() for event_type, _ in ArticleEngagementEvent.EVENT_CHOICES}
        category_performance = list(queryset.values('category').annotate(views=Count('views'), articles=Count('id')).order_by('-views', '-articles')[:5])
        top_authors = list(
            queryset.values('author__username')
            .annotate(article_count=Count('id'))
            .order_by('-article_count', 'author__username')[:5]
        )
        return Response({
            'articles': queryset.count(),
            'published': queryset.filter(workflow_status='published').count(),
            'pending_review': queryset.filter(workflow_status='submitted').count(),
            'approved': queryset.filter(workflow_status='approved').count(),
            'rejected': queryset.filter(workflow_status='rejected').count(),
            'total_views': sum(article.views.count() for article in queryset),
            'total_likes': sum(article.likes.count() for article in queryset),
            'total_completed_reads': ArticleEngagementEvent.objects.filter(
                article__in=queryset, event_type='read_complete',
            ).count(),
            'total_shares': ArticleEngagementEvent.objects.filter(
                article__in=queryset, event_type='share',
            ).count(),
            'active_readers_7d': active_readers,
            'returning_readers_7d': returning_readers,
            'funnel': funnel,
            'category_performance': category_performance,
            'top_authors': [
                {'username': item['author__username'], 'article_count': item['article_count']}
                for item in top_authors
            ],
        })


class ArticleEngagementView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id, workflow_status='published', is_visible=True)
        if request.user.is_authenticated and request.headers.get('X-Analytics-Consent') != 'granted':
            return Response({'detail': 'Analytics consent is required.'}, status=status.HTTP_428_PRECONDITION_REQUIRED)
        event_type = str(request.data.get('event_type', '')).strip()
        allowed_events = {value for value, _ in ArticleEngagementEvent.EVENT_CHOICES}
        if event_type not in allowed_events:
            return Response({'detail': 'Unsupported engagement event.'}, status=400)
        try:
            value = min(max(int(request.data.get('value', 0)), 0), 100)
        except (TypeError, ValueError):
            return Response({'detail': 'value must be an integer from 0 to 100.'}, status=400)
        event = ArticleEngagementEvent.objects.create(
            article=article,
            user=request.user if request.user.is_authenticated else None,
            visitor_key=str(request.data.get('visitor_key', ''))[:128],
            session_key=str(request.data.get('session_key', ''))[:128],
            event_type=event_type,
            value=value,
            metadata=request.data.get('metadata') if isinstance(request.data.get('metadata'), dict) else {},
        )
        return Response({'accepted': True, 'event_id': event.id}, status=status.HTTP_201_CREATED)


class HeadlessArticleFeedView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raw_key = request.headers.get('X-API-Key', '')
        owner = resolve_public_api_key(raw_key, required_scope='articles:read') if raw_key else None
        if raw_key and not owner:
            return Response({'detail': 'Invalid, revoked, unauthorized, or rate-limited API key.'}, status=401)

        queryset = Article.objects.filter(workflow_status='published', is_visible=True).select_related('author')
        category = request.query_params.get('category')
        search = request.query_params.get('q')
        if category:
            queryset = queryset.filter(Q(category=category) | Q(category_ref__slug=category))
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(summary__icontains=search) | Q(content__icontains=search))
        try:
            limit = min(max(int(request.query_params.get('limit', 20)), 1), 100)
        except ValueError:
            limit = 20
        articles = queryset.order_by('-published_at', '-created_at')[:limit]
        return Response({
            'count': queryset.count(),
            'results': [
                {
                    'id': article.id,
                    'slug': article.slug,
                    'title': article.title,
                    'subtitle': article.subtitle,
                    'summary': article.summary,
                    'content': article.content,
                    'author': article.author.get_full_name() or article.author.username,
                    'category': article.category_ref.slug if article.category_ref else article.category,
                    'published_at': article.published_at,
                    'updated_at': article.updated_at,
                    'url': request.build_absolute_uri(f'/articles/read/{article.slug}/'),
                }
                for article in articles
            ],
        })


class StorySeriesListView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        series = StorySeries.objects.filter(is_published=True).prefetch_related('series_articles__article')
        return Response(StorySeriesSerializer(series, many=True, context={'request': request}).data)

    def post(self, request):
        if not request.user.is_authenticated or request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can create story series.'}, status=403)
        serializer = StorySeriesSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data['title']
        slug = slugify(serializer.validated_data.get('slug') or title)
        if StorySeries.objects.filter(slug=slug).exists():
            return Response({'detail': 'A series with this slug already exists.'}, status=400)
        series = StorySeries.objects.create(
            title=title,
            slug=slug,
            description=serializer.validated_data.get('description', ''),
            is_published=serializer.validated_data.get('is_published', False),
            created_by=request.user,
        )
        return Response(StorySeriesSerializer(series, context={'request': request}).data, status=201)


class StorySeriesDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_series(self, slug):
        return get_object_or_404(StorySeries.objects.prefetch_related('series_articles__article'), slug=slug)

    def get(self, request, slug):
        series = self.get_series(slug)
        if not series.is_published and (not request.user.is_authenticated or request.user.role not in {'Editor', 'Admin'}):
            return Response({'detail': 'This story series is not published.'}, status=404)
        return Response(StorySeriesSerializer(series, context={'request': request}).data)

    def post(self, request, slug):
        series = self.get_series(slug)
        if not request.user.is_authenticated or request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can manage story series.'}, status=403)
        article = get_object_or_404(Article, pk=request.data.get('article_id'))
        item, created = SeriesArticle.objects.get_or_create(
            series=series,
            article=article,
            defaults={'position': int(request.data.get('position', 0))},
        )
        if not created:
            return Response({'detail': 'This article is already in the series.'}, status=400)
        return Response(SeriesArticleSerializer(item).data, status=201)


class StorySeriesArticleDeleteView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug, article_id):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can manage story series.'}, status=403)
        item = get_object_or_404(SeriesArticle, series__slug=slug, article_id=article_id)
        item.delete()
        return Response(status=204)


class MediaAssetLibraryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self, request):
        queryset = MediaAsset.objects.all()
        if request.query_params.get('include_archived') not in {'1', 'true', 'yes'}:
            queryset = queryset.filter(is_archived=False)
        if request.user.role not in {'Editor', 'Admin'}:
            queryset = queryset.filter(uploaded_by=request.user)
        query = request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(Q(title__icontains=query) | Q(alt_text__icontains=query) | Q(credit__icontains=query))
        media_type = request.query_params.get('media_type')
        if media_type:
            queryset = queryset.filter(media_type=media_type)
        return queryset

    def get(self, request):
        return Response(MediaAssetSerializer(self.get_queryset(request), many=True, context={'request': request}).data)

    def post(self, request):
        serializer = MediaAssetSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data.get('file')
        file_hash = ''
        if uploaded_file:
            digest = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                digest.update(chunk)
            uploaded_file.seek(0)
            file_hash = digest.hexdigest()
            duplicate = MediaAsset.objects.filter(file_hash=file_hash, is_archived=False).first()
            if duplicate:
                return Response({
                    'detail': 'This file already exists in the media library.',
                    'duplicate_asset_id': duplicate.id,
                }, status=status.HTTP_409_CONFLICT)
        asset = serializer.save(uploaded_by=request.user, file_hash=file_hash)
        if uploaded_file:
            asset.metadata = {
                **(asset.metadata or {}),
                'original_name': uploaded_file.name,
                'content_type': getattr(uploaded_file, 'content_type', ''),
                'size_bytes': uploaded_file.size,
            }
            asset.save(update_fields=['metadata', 'updated_at'])
            if asset.media_type == 'image':
                try:
                    generate_image_variants(asset)
                except (OSError, ValueError):
                    asset.metadata = {**(asset.metadata or {}), 'processing': 'failed'}
                    asset.save(update_fields=['metadata', 'updated_at'])
        return Response(MediaAssetSerializer(asset, context={'request': request}).data, status=201)


class MediaAssetDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def can_manage(self, request, asset):
        return asset.uploaded_by_id == request.user.id or request.user.role in {'Editor', 'Admin'}

    def patch(self, request, pk):
        asset = get_object_or_404(MediaAsset, pk=pk)
        if not self.can_manage(request, asset):
            return Response({'detail': 'You cannot edit this asset.'}, status=403)
        serializer = MediaAssetSerializer(asset, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        asset = get_object_or_404(MediaAsset, pk=pk)
        if not self.can_manage(request, asset):
            return Response({'detail': 'You cannot archive this asset.'}, status=403)
        asset.is_archived = True
        asset.save(update_fields=['is_archived', 'updated_at'])
        return Response({'archived': True})

    def post(self, request, pk):
        asset = get_object_or_404(MediaAsset, pk=pk)
        if not self.can_manage(request, asset):
            return Response({'detail': 'You cannot process this asset.'}, status=403)
        try:
            generate_image_variants(asset)
        except (OSError, ValueError):
            return Response({'detail': 'The image could not be processed.'}, status=400)
        return Response(MediaAssetSerializer(asset, context={'request': request}).data)


class ArticleAssetView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_article(self, article_id):
        return get_object_or_404(Article, pk=article_id)

    def can_manage(self, request, article):
        return article.author_id == request.user.id or request.user.role in {'Editor', 'Admin'}

    def get(self, request, article_id):
        article = self.get_article(article_id)
        if not self.can_manage(request, article):
            return Response({'detail': 'You cannot view this asset list.'}, status=403)
        return Response(ArticleAssetSerializer(article.asset_links.select_related('asset'), many=True, context={'request': request}).data)

    def post(self, request, article_id):
        article = self.get_article(article_id)
        if not self.can_manage(request, article):
            return Response({'detail': 'You cannot attach assets to this article.'}, status=403)
        asset = get_object_or_404(MediaAsset, pk=request.data.get('asset_id'), is_archived=False)
        link, created = ArticleAsset.objects.get_or_create(
            article=article,
            asset=asset,
            defaults={'role': request.data.get('role', 'inline'), 'position': int(request.data.get('position', 0))},
        )
        if not created:
            return Response({'detail': 'This asset is already attached to the article.'}, status=400)
        return Response(ArticleAssetSerializer(link, context={'request': request}).data, status=201)


class ArticleCorrectionView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        corrections = article.corrections.filter(status='published')
        return Response(ArticleCorrectionSerializer(corrections, many=True).data)

    def post(self, request, article_id):
        if not request.user.is_authenticated:
            return Response({'detail': 'Sign in to report a correction.'}, status=401)
        article = get_object_or_404(Article, pk=article_id)
        serializer = ArticleCorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_editor = request.user.role in {'Editor', 'Admin'}
        correction = serializer.save(
            article=article,
            reported_by=request.user,
            status='published' if is_editor else 'draft',
            reviewed_by=request.user if is_editor else None,
            published_at=timezone.now() if is_editor else None,
        )
        return Response(ArticleCorrectionSerializer(correction).data, status=201)


class ArticleCorrectionDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can publish corrections.'}, status=403)
        correction = get_object_or_404(ArticleCorrection, pk=pk)
        serializer = ArticleCorrectionSerializer(correction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        correction = serializer.save(reviewed_by=request.user)
        if correction.status == 'published' and not correction.published_at:
            correction.published_at = timezone.now()
            correction.save(update_fields=['published_at', 'updated_at'])
        return Response(ArticleCorrectionSerializer(correction).data)


class ArticleProvenanceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_article(self, article_id):
        return get_object_or_404(Article, pk=article_id)

    def can_manage(self, request, article):
        return request.user.is_authenticated and (article.author_id == request.user.id or request.user.role in {'Editor', 'Admin'})

    def get(self, request, article_id):
        article = self.get_article(article_id)
        provenance = getattr(article, 'provenance', None)
        if not provenance:
            return Response({'article': article.id, 'origin': 'human', 'tool_name': '', 'disclosure': '', 'sources_reviewed': False})
        return Response(ArticleProvenanceSerializer(provenance).data)

    def post(self, request, article_id):
        article = self.get_article(article_id)
        if not self.can_manage(request, article):
            return Response({'detail': 'Only the author, editors, or admins can update provenance.'}, status=403)
        serializer = ArticleProvenanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provenance, _ = ArticleProvenance.objects.update_or_create(
            article=article,
            defaults={**serializer.validated_data, 'updated_by': request.user},
        )
        return Response(ArticleProvenanceSerializer(provenance).data, status=201)

    patch = post


class ContentExperimentListView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        queryset = ContentExperiment.objects.prefetch_related('variants')
        if request.user.role not in {'Editor', 'Admin'}:
            queryset = queryset.filter(created_by=request.user)
        return queryset

    def get(self, request):
        return Response(ContentExperimentSerializer(self.get_queryset(request), many=True).data)

    def post(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can create experiments.'}, status=403)
        serializer = ContentExperimentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        article = serializer.validated_data['article']
        if article.workflow_status != 'published' or not article.is_visible:
            return Response({'detail': 'Experiments require a visible published article.'}, status=400)
        experiment = serializer.save(created_by=request.user)
        return Response(ContentExperimentSerializer(experiment).data, status=201)


class ContentExperimentDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_experiment(self, request, pk):
        experiment = get_object_or_404(ContentExperiment.objects.prefetch_related('variants'), pk=pk)
        if experiment.created_by_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You cannot manage this experiment.')
        return experiment

    def get(self, request, pk):
        return Response(ContentExperimentSerializer(self.get_experiment(request, pk)).data)

    def delete(self, request, pk):
        self.get_experiment(request, pk).delete()
        return Response(status=204)


class ExperimentVariantView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        experiment = get_object_or_404(ContentExperiment, pk=pk)
        if experiment.created_by_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot manage this experiment.'}, status=403)
        if experiment.status != 'draft':
            return Response({'detail': 'Variants can only be added to draft experiments.'}, status=400)
        serializer = ExperimentVariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = serializer.save(experiment=experiment)
        return Response(ExperimentVariantSerializer(variant).data, status=201)


class ExperimentStartView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        experiment = get_object_or_404(ContentExperiment, pk=pk)
        if experiment.created_by_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot start this experiment.'}, status=403)
        if experiment.variants.count() < 2:
            return Response({'detail': 'Add at least two variants before starting.'}, status=400)
        experiment.status = 'running'
        experiment.started_at = timezone.now()
        experiment.save(update_fields=['status', 'started_at', 'updated_at'])
        return Response(ContentExperimentSerializer(experiment).data)


class ExperimentAssignmentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        experiment = get_object_or_404(ContentExperiment.objects.prefetch_related('variants'), pk=pk, status='running')
        visitor_key = str(request.data.get('visitor_key', '')).strip()
        if not visitor_key:
            return Response({'detail': 'visitor_key is required.'}, status=400)
        assignment = ExperimentAssignment.objects.filter(experiment=experiment, visitor_key=visitor_key).select_related('variant').first()
        if not assignment:
            variants = list(experiment.variants.all())
            digest = hashlib.sha256(f'{experiment.id}:{visitor_key}'.encode()).hexdigest()
            variant = variants[int(digest[:8], 16) % len(variants)]
            assignment = ExperimentAssignment.objects.create(experiment=experiment, variant=variant, visitor_key=visitor_key)
        return Response({'assignment_id': assignment.id, 'variant': ExperimentVariantSerializer(assignment.variant).data})


class ExperimentEventView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        experiment = get_object_or_404(ContentExperiment, pk=pk)
        visitor_key = str(request.data.get('visitor_key', '')).strip()
        event_type = str(request.data.get('event_type', '')).strip().lower()
        if event_type not in {'view', 'click', 'read'} or not visitor_key:
            return Response({'detail': 'Provide a visitor_key and a valid event_type.'}, status=400)
        assignment = get_object_or_404(ExperimentAssignment, experiment=experiment, visitor_key=visitor_key)
        event = ExperimentEvent.objects.create(assignment=assignment, event_type=event_type)
        return Response({'id': event.id, 'recorded': True}, status=201)


class ExperimentResultsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        experiment = get_object_or_404(ContentExperiment.objects.prefetch_related('variants'), pk=pk)
        if experiment.created_by_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot view these experiment results.'}, status=403)
        results = []
        for variant in experiment.variants.all():
            assignments = ExperimentAssignment.objects.filter(variant=variant)
            events = ExperimentEvent.objects.filter(assignment__in=assignments)
            views = events.filter(event_type='view').count()
            clicks = events.filter(event_type='click').count()
            reads = events.filter(event_type='read').count()
            results.append({
                'variant': ExperimentVariantSerializer(variant).data,
                'assignments': assignments.count(), 'views': views, 'clicks': clicks, 'reads': reads,
                'click_rate': round(clicks / views, 4) if views else 0,
                'read_rate': round(reads / views, 4) if views else 0,
            })
        return Response({'experiment': ContentExperimentSerializer(experiment).data, 'results': results})


class ExperimentCompleteView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        experiment = get_object_or_404(ContentExperiment.objects.prefetch_related('variants'), pk=pk)
        if experiment.created_by_id != request.user.id and request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'You cannot complete this experiment.'}, status=status.HTTP_403_FORBIDDEN)
        if experiment.status != 'running':
            return Response({'detail': 'Only running experiments can be completed.'}, status=status.HTTP_400_BAD_REQUEST)
        requested_variant = request.data.get('variant_id')
        if requested_variant:
            winner = get_object_or_404(experiment.variants, pk=requested_variant)
        else:
            winner = None
            best_key = (-1, -1, '')
            for variant in experiment.variants.all():
                views = variant.assignments.filter(events__event_type='view').distinct().count()
                reads = variant.assignments.filter(events__event_type='read').distinct().count()
                clicks = variant.assignments.filter(events__event_type='click').distinct().count()
                key = (reads / views if views else 0, clicks / views if views else 0, variant.label)
                if key > best_key:
                    best_key = key
                    winner = variant
        if winner is None:
            return Response({'detail': 'The experiment has no variants.'}, status=status.HTTP_400_BAD_REQUEST)
        experiment.status = 'completed'
        experiment.winning_variant = winner
        experiment.ended_at = timezone.now()
        experiment.save(update_fields=['status', 'winning_variant', 'ended_at', 'updated_at'])
        record_audit_event(actor=request.user, action='content_experiment_completed', article=experiment.article, details={'experiment_id': experiment.id, 'winner_id': winner.id})
        return Response(ContentExperimentSerializer(experiment).data)
