import csv
import difflib
import hashlib
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from users.models import CustomUser, ReaderInterest, has_active_membership
from users.api import resolve_public_api_key

from .api_serializers import (
    ArticleFactCheckSerializer, ArticlePresenceSerializer, ArticleReviewSerializer,
    ArticleScheduleSerializer,
    ArticleAssignmentSerializer,
    ArticleImageSerializer, ArticleLiveUpdateSerializer, ArticleMediaSerializer, ArticleSourceSerializer,
    ArticleAutosaveSerializer,
    BookmarkSerializer,
    PlagiarismCheckSerializer,
    ArticleTranslationSerializer,
    ModerationFlagSerializer,
    ArticleSEOSerializer,
    AuditLogSerializer,
    CategorySerializer,
    TagSerializer,
    ArticleWorkflowSerializer,
    CommentSerializer,
    NotificationSerializer,
    RevisionSerializer,
    ArticleAssetSerializer, ArticleCorrectionSerializer, ArticleProvenanceSerializer, ContentExperimentSerializer, ExperimentVariantSerializer, MediaAssetSerializer, SeriesArticleSerializer, StorySeriesSerializer,
)
from .models import Article, ArticleAsset, ArticleAssignment, ArticleAutosave, ArticleCorrection, ArticleImage, ArticleLiveUpdate, ArticleMedia, ArticlePresence, ArticleProvenance, ArticleReaction, ArticleRevision, ArticleTranslation, ArticleView, AuditLog, Bookmark, Category, Comment, ContentExperiment, ExperimentAssignment, ExperimentEvent, Like, MediaAsset, ModerationFlag, Notification, PlagiarismCheck, SeriesArticle, StorySeries, Tag
from .permissions import editor_has_capability
from .audit import record_audit_event
from .notifications import notify
from .assistant import make_suggestions


class ArticlePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class ArticleQuerySetMixin:
    def article_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role in {'Editor', 'Admin'}:
            return Article.objects.all()
        if user.is_authenticated:
            return Article.objects.filter(author=user)
        return Article.objects.filter(workflow_status='published', is_visible=True)


class ArticleWorkflowView(ArticleQuerySetMixin, APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get_article(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
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
        record_audit_event(actor=request.user, action='editorial_assistant_used', article=article, details={'action': action})
        return Response({
            'article_id': article.id,
            'action': action,
            'provider': 'local-rule-based',
            'requires_review': True,
            'suggestions': suggestions,
        })


class PersonalizedFeedView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        interests = list(ReaderInterest.objects.filter(user=request.user).values_list('interest_type', 'value'))
        category_values = {value.lower() for kind, value in interests if kind == 'category'}
        tag_values = {value.lower() for kind, value in interests if kind == 'tag'}
        author_values = {value.lower() for kind, value in interests if kind == 'author'}
        articles = list(Article.objects.filter(workflow_status='published', is_visible=True).select_related('author').order_by('-published_at', '-created_at')[:100])

        def score(article):
            article_tags = {tag.strip().lower() for tag in (article.tags or '').split(',') if tag.strip()}
            points = 0
            if (article.category or '').lower() in category_values:
                points += 5
            points += 3 * len(article_tags & tag_values)
            if article.author.username.lower() in author_values:
                points += 6
            return points

        ranked = sorted(articles, key=lambda article: (score(article), article.published_at or article.created_at), reverse=True)
        return Response({
            'interests': [{'interest_type': kind, 'value': value} for kind, value in interests],
            'results': ArticleWorkflowSerializer(ranked[:50], many=True, context={'request': request}).data,
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
        return Response([{
            'user_id': session.user_id, 'username': session.user.username, 'status': session.status,
            'section': session.section, 'cursor_position': session.cursor_position, 'last_seen': session.last_seen,
        } for session in sessions])

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
        return Response(ArticlePresenceSerializer(session).data)

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


class ArticleWorkflowActionView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, article_id, action):
        article = get_object_or_404(Article, pk=article_id)
        now = timezone.now()

        if action == 'submit':
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
            for editor in CustomUser.objects.filter(role__in=['Editor', 'Admin'], is_active=True):
                notify(
                    recipient=editor,
                    article=article,
                    notification_type='submitted',
                    message=f'{article.title} was submitted for review.',
                )
            return Response(ArticleWorkflowSerializer(article).data, status=status.HTTP_200_OK)

        if action == 'publish':
            if request.user.role not in {'Editor', 'Admin'} or not editor_has_capability(request.user, article, 'publish'):
                return Response({'detail': 'Only editors and admins can publish articles.'}, status=status.HTTP_403_FORBIDDEN)
            if article.workflow_status != 'approved':
                return Response({'detail': 'Only approved articles can be published.'}, status=status.HTTP_400_BAD_REQUEST)
            article.workflow_status = 'published'
            article.review_status = 'approved'
            article.status = 'published'
            article.published_at = now
            article.publish_date = now.date()
            article.is_visible = True
            article.save(update_fields=['workflow_status', 'review_status', 'status', 'published_at', 'publish_date', 'is_visible', 'updated_at'])
            record_audit_event(actor=request.user, action='article_published', article=article)
            notify(
                recipient=article.author,
                article=article,
                notification_type='published',
                message=f'{article.title} was published.',
            )
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
            queryset = queryset.filter(Q(title__icontains=query) | Q(content__icontains=query) | Q(summary__icontains=query) | Q(tags__icontains=query))
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
        for field in ('workflow_status', 'category', 'author_id'):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        published_from = self.request.query_params.get('published_from')
        published_to = self.request.query_params.get('published_to')
        if published_from:
            queryset = queryset.filter(publish_date__gte=published_from)
        if published_to:
            queryset = queryset.filter(publish_date__lte=published_to)
        sort = self.request.query_params.get('sort', 'relevance' if query else 'recent')
        if sort == 'popular':
            return queryset.annotate(view_count=Count('views'), like_count=Count('likes')).order_by('-view_count', '-like_count', '-created_at')
        if sort == 'recent':
            return queryset.order_by('-created_at')
        return queryset.order_by('-relevance', '-created_at')


class ArticleAutocompleteView(generics.ListAPIView):
    serializer_class = ArticleWorkflowSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Article.objects.none()
        return Article.objects.filter(
            workflow_status='published',
            is_visible=True,
            title__icontains=query,
        ).select_related('author').order_by('title')[:10]


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


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        article = get_object_or_404(Article, pk=self.kwargs['article_id'])
        queryset = article.comments.select_related('author').all()
        if self.request.user.role not in {'Editor', 'Admin'} and article.author_id != self.request.user.id:
            queryset = queryset.filter(is_editorial=False)
        return queryset

    def perform_create(self, serializer):
        article = get_object_or_404(Article, pk=self.kwargs['article_id'])
        serializer.save(
            article=article,
            author=self.request.user,
            is_editorial=self.request.user.role in {'Editor', 'Admin'},
        )
        if article.author_id != self.request.user.id:
            notify(
                recipient=article.author,
                article=article,
                notification_type='comment',
                message=f'{self.request.user.username} commented on {article.title}.',
            )


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
        if serializer.validated_data.get('status') == 'published' and request.user.role == 'Journalist':
            return Response({'detail': 'Only editors and admins can publish translations.'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()
        return Response(serializer.data)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
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
            defaults={key: serializer.validated_data.get(key, False) for key in ('can_review', 'can_edit', 'can_publish')},
        )
        record_audit_event(actor=request.user, action='article_assignment_updated', article=article, details={'editor_id': editor.id})
        return Response(ArticleAssignmentSerializer(assignment).data, status=status.HTTP_200_OK)

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
        return Response(ArticleSEOSerializer(article, context={'request': request}).data)

    def patch(self, request, article_id):
        article = self.get_article(request, article_id)
        if article is None:
            return Response({'detail': 'You cannot edit this article SEO data.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ArticleSEOSerializer(article, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_audit_event(actor=request.user, action='article_seo_updated', article=article, details={'fields': sorted(request.data.keys())})
        return Response(serializer.data)


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
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
        except Exception:
            return Response({'status': 'unhealthy', 'database': 'unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'status': 'healthy', 'database': 'ok'})


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
                'workflow_status': article.workflow_status,
            })

        if request.user.role not in {'Editor', 'Admin'}:
            queryset = queryset.filter(author=request.user)
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
            'top_authors': [
                {'username': item['author__username'], 'article_count': item['article_count']}
                for item in top_authors
            ],
        })


class HeadlessArticleFeedView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        raw_key = request.headers.get('X-API-Key', '')
        owner = resolve_public_api_key(raw_key) if raw_key else None
        if raw_key and not owner:
            return Response({'detail': 'Invalid or revoked API key.'}, status=401)

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
        queryset = MediaAsset.objects.filter(is_archived=False)
        if request.user.role not in {'Editor', 'Admin'}:
            queryset = queryset.filter(uploaded_by=request.user)
        return queryset

    def get(self, request):
        return Response(MediaAssetSerializer(self.get_queryset(request), many=True, context={'request': request}).data)

    def post(self, request):
        serializer = MediaAssetSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        asset = serializer.save(uploaded_by=request.user)
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
