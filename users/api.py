import hashlib
import re
import hmac
import json
import secrets
import base64
import hashlib
import requests

from rest_framework import serializers, status
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.text import slugify
from datetime import timedelta
from decimal import Decimal

from .models import (
    AccessibilityPreference, AlertRule, AuthorTip, AuthenticationPolicy, CustomUser, FeatureFlag, has_active_membership, MembershipPlan,
    MembershipSubscription, MembershipWebhookEvent, MembershipInvoice, PaymentTransaction, NewsletterCampaignAttribution, NewsletterEdition, NewsletterSubscription, NotificationPreference, Profile,
    NotificationDelivery, PrivacyConsent, PrivacyPreference, PrivacyRequest, PublicAPIKey, PublicAPIKeyUsage, PushSubscription, ReaderDigestDelivery, ReaderInterest, RoleCapabilityOverride, SavedSearch, SSOProvider, SCIMToken, PasskeyCredential, TrustedDevice, TwoFactorAuth, WebhookDelivery, WebhookEndpoint, Workspace, WorkspaceInvitation, PersonalizationPreference,
    WorkspaceMembership, WorkspaceBillingContract, WorkspaceIntegration, SupportTicket, SupportTicketMessage, ImpersonationSession,
)
from articles.models import Article
from .support_bot import get_support_response
from .integration_secrets import decrypt_integration_secret, encrypt_integration_secret, IntegrationSecretError
from .impersonation import SESSION_ID_KEY, SESSION_TOKEN_KEY, hash_impersonation_token
from articles.audit import record_audit_event


class SupportChatView(APIView):
    """Answer support questions from the project's own documentation."""

    permission_classes = []

    def get(self, request):
        return Response(get_support_response(''))

    def post(self, request):
        message = str(request.data.get('message', '')).strip()
        if not message:
            return Response({'detail': 'message is required.'}, status=400)
        if len(message) > 500:
            return Response({'detail': 'message must be 500 characters or fewer.'}, status=400)
        return Response(get_support_response(message))


class DemoModeView(APIView):
    permission_classes = [AllowAny]

    personas = {
        'journalist': {'label': 'Journalist', 'description': 'Write, revise, and follow the reader experience.', 'icon': 'pen-nib', 'dashboard_url': '/journalist/dashboard/'},
        'editor': {'label': 'Editor', 'description': 'Review assignments, collaborate, and publish with confidence.', 'icon': 'check-double', 'dashboard_url': '/editor/dashboard/'},
        'admin': {'label': 'Admin', 'description': 'Manage workspaces, billing, permissions, and operations.', 'icon': 'shield-halved', 'dashboard_url': '/adminMain/dashboard/'},
        'reader': {'label': 'Reader', 'description': 'Explore published stories, save articles, and personalize the reading experience.', 'icon': 'book-open-reader', 'dashboard_url': '/'},
    }

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEMO_MODE_ENABLED:
            return Response({'detail': 'Demo mode is disabled.'}, status=status.HTTP_404_NOT_FOUND)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        workspace_name = Workspace.objects.filter(slug='demo-newsroom').values_list('name', flat=True).first() or 'Northstar Newsroom'
        return Response({'enabled': True, 'workspace': workspace_name, 'personas': [{'key': key, **value} for key, value in self.personas.items()], 'features': ['Editorial workflow', 'Workspace collaboration', 'Membership billing', 'Distribution monitoring', 'Reader personalization']})

    def post(self, request):
        action = str(request.data.get('action', 'login')).strip().lower()
        if action == 'reset':
            from django.core.management import call_command
            call_command('seed_demo_data', verbosity=0)
            return Response({'reset': True, 'message': 'Northstar workspace refreshed. Choose a perspective to continue.'})
        persona = str(request.data.get('persona', '')).strip().lower()
        from users.management.commands.seed_demo_data import DEMO_USERS
        account = DEMO_USERS.get(persona)
        if not account or persona not in self.personas:
            return Response({'detail': 'Choose a valid demo persona.'}, status=status.HTTP_400_BAD_REQUEST)
        user = authenticate(request, username=account['username'], password=account['password'])
        if user is None:
            return Response({'detail': 'Demo accounts are not seeded yet. Refresh the demo workspace first.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        login(request, user)
        return Response({'authenticated': True, 'persona': persona, 'username': user.username, 'dashboard_url': self.personas[persona]['dashboard_url']})


class ProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)
    bio = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    contact_info = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    new_password = serializers.CharField(required=False, write_only=True, min_length=8)


class UserProfileView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_profile(self, user):
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile

    def get(self, request):
        profile = self.get_profile(request.user)
        return Response({
            'id': request.user.id,
            'username': request.user.username,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'role': request.user.role,
            'bio': profile.bio or '',
            'contact_info': profile.contact_info or '',
            'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
        })

    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        user = request.user
        profile = self.get_profile(user)

        for field in ('first_name', 'last_name', 'email'):
            if field in values:
                setattr(user, field, values[field])
        if 'new_password' in values:
            user.set_password(values['new_password'])
        user.save()

        for field in ('bio', 'contact_info', 'profile_picture'):
            if field in values:
                setattr(profile, field, values[field])
        profile.save()
        return self.get(request)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['in_app_enabled', 'email_enabled', 'workflow_enabled', 'comments_enabled', 'updated_at']
        read_only_fields = ['updated_at']


class NotificationPreferenceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_preferences(self, user):
        preferences, _ = NotificationPreference.objects.get_or_create(user=user)
        return preferences

    def get(self, request):
        return Response(NotificationPreferenceSerializer(self.get_preferences(request.user)).data)

    def patch(self, request):
        preferences = self.get_preferences(request.user)
        serializer = NotificationPreferenceSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NotificationDeliveryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = NotificationDelivery.objects.filter(recipient=request.user)
        channel = request.query_params.get('channel')
        status_filter = request.query_params.get('status')
        if channel in {'email', 'push'}:
            queryset = queryset.filter(channel=channel)
        if status_filter in {'queued', 'sent', 'failed', 'skipped'}:
            queryset = queryset.filter(status=status_filter)
        return Response([{
            'id': item.id,
            'channel': item.channel,
            'status': item.status,
            'attempts': item.attempts,
            'last_error': item.last_error,
            'delivered_at': item.delivered_at,
            'created_at': item.created_at,
        } for item in queryset[:100]])

    def post(self, request):
        from users.delivery import deliver_email, deliver_push_notification
        delivery = get_object_or_404(NotificationDelivery, pk=request.data.get('delivery_id'), recipient=request.user)
        if delivery.status not in {'failed', 'skipped'}:
            return Response({'detail': 'Only failed or skipped deliveries can be retried.'}, status=400)
        if delivery.channel == 'email':
            deliver_email(delivery)
        else:
            subscription = PushSubscription.objects.filter(pk=delivery.provider_reference, user=request.user, is_active=True).first()
            if subscription is None:
                delivery.status = 'failed'
                delivery.last_error = 'Push subscription is no longer active.'
                delivery.save(update_fields=['status', 'last_error'])
            else:
                deliver_push_notification(delivery, subscription)
        return Response({'id': delivery.id, 'status': delivery.status, 'attempts': delivery.attempts})


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = ['email', 'frequency', 'categories', 'is_active', 'unsubscribe_token', 'created_at', 'updated_at']
        read_only_fields = ['unsubscribe_token', 'created_at', 'updated_at']


class NewsletterSubscriptionView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = NewsletterSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        subscription, _ = NewsletterSubscription.objects.update_or_create(
            email=values['email'], defaults={**values, 'user': request.user if request.user.is_authenticated else None, 'is_active': True},
        )
        return Response(NewsletterSubscriptionSerializer(subscription).data, status=201)

    def delete(self, request):
        email = request.data.get('email') or request.query_params.get('email')
        token = request.data.get('token') or request.query_params.get('token')
        queryset = NewsletterSubscription.objects.filter(email=email) if email else NewsletterSubscription.objects.filter(unsubscribe_token=token)
        updated = queryset.update(is_active=False)
        return Response({'unsubscribed': bool(updated)})


class NewsletterPreviewView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can preview newsletters.'}, status=403)
        frequency = request.query_params.get('frequency', 'weekly')
        if frequency not in {'daily', 'weekly'}:
            return Response({'detail': 'frequency must be daily or weekly.'}, status=400)
        since = timezone.now() - timedelta(days=1 if frequency == 'daily' else 7)
        articles = Article.objects.filter(
            workflow_status='published', is_visible=True, published_at__gte=since,
        ).order_by('-published_at')[:10]
        return Response({
            'frequency': frequency,
            'active_subscribers': NewsletterSubscription.objects.filter(frequency=frequency, is_active=True).count(),
            'articles': [
                {'id': article.id, 'title': article.title, 'summary': article.summary or article.content[:160]}
                for article in articles
            ],
        })


class NewsletterEditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterEdition
        fields = ['id', 'frequency', 'subject', 'body', 'article_ids', 'status', 'recipient_count', 'sent_at', 'created_at']
        read_only_fields = ['id', 'status', 'recipient_count', 'sent_at', 'created_at']


class NewsletterEditionView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def allowed(self, request):
        return request.user.role in {'Editor', 'Admin'}

    def get(self, request):
        if not self.allowed(request): return Response({'detail': 'Editor access is required.'}, status=403)
        editions = NewsletterEdition.objects.all()[:50]
        return Response([{'id': item.id, 'frequency': item.frequency, 'subject': item.subject, 'body': item.body, 'status': item.status, 'recipient_count': item.recipient_count, 'sent_at': item.sent_at, 'created_at': item.created_at} for item in editions])

    def post(self, request):
        if not self.allowed(request): return Response({'detail': 'Editor access is required.'}, status=403)
        action = str(request.data.get('action', 'draft')).lower()
        if action == 'send':
            edition = get_object_or_404(NewsletterEdition, pk=request.data.get('id'), status='draft')
            recipients = list(NewsletterSubscription.objects.filter(is_active=True, frequency=edition.frequency).values_list('email', flat=True))
            campaign_url = request.build_absolute_uri(f'/newsletter/campaign/{edition.id}/')
            message = f'{edition.body}\n\nExplore member-only stories and support the newsroom:\n{campaign_url}'
            send_mail(edition.subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
            edition.status = 'sent'; edition.recipient_count = len(recipients); edition.sent_at = timezone.now(); edition.save(update_fields=['status', 'recipient_count', 'sent_at'])
            return Response({'id': edition.id, 'status': edition.status, 'recipient_count': edition.recipient_count, 'sent_at': edition.sent_at})
        serializer = NewsletterEditionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        edition = serializer.save(status='draft')
        return Response({'id': edition.id, 'frequency': edition.frequency, 'subject': edition.subject, 'body': edition.body, 'status': edition.status, 'recipient_count': edition.recipient_count}, status=201)


class NewsletterConversionAnalyticsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Editor access is required.'}, status=403)
        editions = NewsletterEdition.objects.filter(status='sent').order_by('-sent_at')[:50]
        campaigns = []
        totals = {'recipients': 0, 'clicks': 0, 'checkouts': 0, 'conversions': 0, 'revenue_by_currency': {}}
        for edition in editions:
            attributions = NewsletterCampaignAttribution.objects.filter(edition=edition)
            clicks = attributions.count()
            checkouts = attributions.filter(checkout_started_at__isnull=False).count()
            conversions = attributions.filter(converted_at__isnull=False).count()
            revenue_by_currency = list(PaymentTransaction.objects.filter(
                newsletter_attributions__edition=edition,
                status='succeeded',
            ).values('currency').annotate(total=models.Sum('amount')).order_by('currency'))
            for amount in revenue_by_currency:
                amount['total'] = str(amount['total'])
            campaigns.append({
                'id': edition.id,
                'subject': edition.subject,
                'frequency': edition.frequency,
                'sent_at': edition.sent_at,
                'recipient_count': edition.recipient_count,
                'clicks': clicks,
                'checkouts': checkouts,
                'conversions': conversions,
                'conversion_rate': round(conversions * 100 / clicks, 1) if clicks else 0,
                'revenue_by_currency': revenue_by_currency,
            })
            totals['recipients'] += edition.recipient_count
            totals['clicks'] += clicks
            totals['checkouts'] += checkouts
            totals['conversions'] += conversions
            for amount in revenue_by_currency:
                currency = amount['currency']
                totals['revenue_by_currency'][currency] = str(
                    Decimal(totals['revenue_by_currency'].get(currency, '0.00')) + Decimal(amount['total'])
                )
        totals['conversion_rate'] = round(totals['conversions'] * 100 / totals['clicks'], 1) if totals['clicks'] else 0
        totals['revenue_by_currency'] = [
            {'currency': currency, 'total': total}
            for currency, total in sorted(totals['revenue_by_currency'].items())
        ]
        return Response({'summary': totals, 'campaigns': campaigns})


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ['endpoint', 'p256dh', 'auth', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class PushSubscriptionView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        return PushSubscription.objects.filter(user=request.user)

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription, _ = PushSubscription.objects.update_or_create(
            endpoint=serializer.validated_data['endpoint'], defaults={**serializer.validated_data, 'user': request.user, 'is_active': True},
        )
        return Response(PushSubscriptionSerializer(subscription).data, status=201)

    def delete(self, request):
        endpoint = request.data.get('endpoint') or request.query_params.get('endpoint')
        deleted, _ = self.get_queryset(request).filter(endpoint=endpoint).delete()
        return Response({'removed': bool(deleted)})


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = ['id', 'rule_type', 'value', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        if attrs.get('rule_type') in {'category', 'author'} and not str(attrs.get('value', '')).strip():
            raise serializers.ValidationError({'value': 'A value is required for category and author alerts.'})
        if attrs.get('rule_type') == 'all':
            attrs['value'] = ''
        return attrs


class AlertRuleView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(AlertRuleSerializer(AlertRule.objects.filter(user=request.user), many=True).data)

    def post(self, request):
        serializer = AlertRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule, _ = AlertRule.objects.update_or_create(
            user=request.user,
            rule_type=serializer.validated_data['rule_type'],
            value=serializer.validated_data.get('value', ''),
            defaults={'is_active': serializer.validated_data.get('is_active', True)},
        )
        return Response(AlertRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        rule = get_object_or_404(AlertRule, pk=pk, user=request.user)
        serializer = AlertRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk=None):
        queryset = AlertRule.objects.filter(user=request.user)
        if pk:
            deleted, _ = queryset.filter(pk=pk).delete()
        else:
            deleted, _ = queryset.filter(
                rule_type=request.data.get('rule_type') or request.query_params.get('rule_type'),
                value=request.data.get('value') or request.query_params.get('value', ''),
            ).delete()
        return Response({'removed': bool(deleted)})


class SavedSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedSearch
        fields = ['id', 'name', 'query', 'frequency', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_query(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter a search query.')
        return value


class SavedSearchView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self, request):
        return SavedSearch.objects.filter(user=request.user)

    def get(self, request):
        return Response(SavedSearchSerializer(self.get_queryset(request), many=True).data)

    def post(self, request):
        serializer = SavedSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved_search, _ = SavedSearch.objects.update_or_create(
            user=request.user,
            query=serializer.validated_data['query'],
            defaults=serializer.validated_data,
        )
        return Response(SavedSearchSerializer(saved_search).data, status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        saved_search = get_object_or_404(self.get_queryset(request), pk=pk)
        serializer = SavedSearchSerializer(saved_search, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk=None):
        saved_search = get_object_or_404(self.get_queryset(request), pk=pk)
        saved_search.delete()
        return Response({'removed': True})


class ReaderDigestDeliveryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = ReaderDigestDelivery.objects.filter(user=request.user)
        if request.user.role in {'Editor', 'Admin'} and request.query_params.get('all') in {'1', 'true'}:
            queryset = ReaderDigestDelivery.objects.select_related('user')
        return Response([{
            'id': item.id,
            'user': item.user.username,
            'frequency': item.frequency,
            'period_key': item.period_key,
            'notification_count': item.notification_count,
            'status': item.status,
            'attempts': item.attempts,
            'last_error': item.last_error,
            'sent_at': item.sent_at,
            'created_at': item.created_at,
        } for item in queryset[:50]])


class FeatureFlagView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def _enabled_for(self, flag, request):
        if not flag.is_enabled:
            return False
        if flag.allowed_roles and request.user.role not in flag.allowed_roles:
            return False
        if flag.workspace_id:
            slug = request.headers.get('X-Workspace-Slug') or request.session.get('active_workspace_slug')
            if not slug or flag.workspace.slug != slug or not WorkspaceMembership.objects.filter(workspace=flag.workspace, user=request.user).exists():
                return False
        bucket = int(hashlib.sha256(f'{flag.key}:{request.user.pk}'.encode()).hexdigest()[:8], 16) % 100
        return bucket < flag.rollout_percent

    def _payload(self, flag, request):
        return {
            'id': flag.id, 'key': flag.key, 'description': flag.description,
            'is_enabled': flag.is_enabled, 'rollout_percent': flag.rollout_percent,
            'allowed_roles': flag.allowed_roles, 'workspace_id': flag.workspace_id,
            'enabled_for_request': self._enabled_for(flag, request), 'updated_at': flag.updated_at,
        }

    def get(self, request):
        key = str(request.query_params.get('key', '')).strip()
        flags = FeatureFlag.objects.select_related('workspace')
        if key:
            flag = get_object_or_404(flags, key=key)
            return Response(self._payload(flag, request))
        if request.user.role != 'Admin':
            flags = flags.filter(is_enabled=True)
        return Response([self._payload(flag, request) for flag in flags])

    def post(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage feature flags.'}, status=403)
        key = str(request.data.get('key', '')).strip().lower()
        if not key:
            return Response({'detail': 'key is required.'}, status=400)
        try:
            rollout = int(request.data.get('rollout_percent', 100))
        except (TypeError, ValueError):
            return Response({'detail': 'rollout_percent must be an integer from 0 to 100.'}, status=400)
        if not 0 <= rollout <= 100:
            return Response({'detail': 'rollout_percent must be between 0 and 100.'}, status=400)
        flag, _ = FeatureFlag.objects.update_or_create(key=key, defaults={
            'description': str(request.data.get('description', ''))[:255],
            'is_enabled': bool(request.data.get('is_enabled', False)),
            'rollout_percent': rollout,
            'allowed_roles': request.data.get('allowed_roles') or [],
            'workspace_id': request.data.get('workspace_id') or None,
        })
        record_audit_event(actor=request.user, action='feature_flag_updated', target_model='FeatureFlag', target_id=flag.id, details={'key': flag.key, 'is_enabled': flag.is_enabled, 'rollout_percent': flag.rollout_percent, 'allowed_roles': flag.allowed_roles, 'workspace_id': flag.workspace_id})
        return Response(self._payload(flag, request), status=201)

    patch = post


class RoleCapabilityView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage role permissions.'}, status=403)
        from articles.permissions import ROLE_CAPABILITIES
        capabilities = sorted({capability for values in ROLE_CAPABILITIES.values() for capability in values if capability != 'admin.*'})
        overrides = {(item.role, item.capability): item.is_enabled for item in RoleCapabilityOverride.objects.all()}
        return Response({'roles': {role: [{'capability': capability, 'enabled': overrides.get((role, capability), capability in ROLE_CAPABILITIES.get(role, set()))} for capability in capabilities] for role in ROLE_CAPABILITIES if role != 'Admin'}, 'capabilities': capabilities})

    def patch(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage role permissions.'}, status=403)
        role = str(request.data.get('role', '')).strip()
        capability = str(request.data.get('capability', '')).strip()
        if role not in {'Journalist', 'Editor'} or not capability or not isinstance(request.data.get('enabled'), bool):
            return Response({'detail': 'Provide a valid role, capability, and boolean enabled value.'}, status=400)
        override, _ = RoleCapabilityOverride.objects.update_or_create(role=role, capability=capability, defaults={'is_enabled': request.data['enabled']})
        record_audit_event(actor=request.user, action='role_capability_updated', target_model='RoleCapabilityOverride', target_id=override.id, details={'role': override.role, 'capability': override.capability, 'enabled': override.is_enabled})
        return Response({'role': override.role, 'capability': override.capability, 'enabled': override.is_enabled})


class TwoFactorView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .two_factor import generate_secret
        factor, _ = TwoFactorAuth.objects.get_or_create(user=request.user, defaults={'secret': generate_secret()})
        payload = {'enabled': factor.is_enabled}
        if not factor.is_enabled:
            payload.update({'secret': factor.secret, 'otp_uri': f'otpauth://totp/Article%20Studio:{request.user.username}?secret={factor.secret}&issuer=Article%20Studio'})
        return Response(payload)

    def post(self, request):
        from .two_factor import generate_secret, verify_totp
        factor, _ = TwoFactorAuth.objects.get_or_create(user=request.user, defaults={'secret': generate_secret()})
        if not factor.is_enabled:
            if not verify_totp(factor.secret, request.data.get('code', '')):
                return Response({'detail': 'Enter the current code from your authenticator app to finish setup.'}, status=400)
            import secrets, hashlib
            codes = [secrets.token_hex(4) for _ in range(8)]
            factor.backup_codes = [hashlib.sha256(code.encode()).hexdigest() for code in codes]
            factor.is_enabled = True
            factor.save(update_fields=['backup_codes', 'is_enabled', 'updated_at'])
            record_audit_event(actor=request.user, action='two_factor_enabled', target_model='TwoFactorAuth', target_id=factor.id)
            return Response({'enabled': True, 'backup_codes': codes})
        return Response({'enabled': True})

    def put(self, request):
        factor = get_object_or_404(TwoFactorAuth, user=request.user, is_enabled=True)
        from .two_factor import verify_totp
        if not verify_totp(factor.secret, request.data.get('code', '')):
            return Response({'detail': 'Invalid authenticator code.'}, status=400)
        factor.is_enabled = False
        factor.save(update_fields=['is_enabled', 'updated_at'])
        record_audit_event(actor=request.user, action='two_factor_disabled', target_model='TwoFactorAuth', target_id=factor.id)
        return Response({'enabled': False})


class AuthenticationPolicyView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        policy, _ = AuthenticationPolicy.objects.get_or_create(name='default')
        return Response({'require_mfa': policy.require_mfa, 'max_session_minutes': policy.max_session_minutes, 'max_idle_minutes': policy.max_idle_minutes, 'require_sso': policy.require_sso, 'is_active': policy.is_active})

    def patch(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage authentication policy.'}, status=403)
        policy, _ = AuthenticationPolicy.objects.get_or_create(name='default')
        for field in ('require_mfa', 'require_sso', 'is_active'):
            if field in request.data:
                setattr(policy, field, bool(request.data[field]))
        for field in ('max_session_minutes', 'max_idle_minutes'):
            if field in request.data:
                try:
                    value = int(request.data[field])
                except (TypeError, ValueError):
                    return Response({'detail': f'{field} must be a positive integer.'}, status=400)
                if value <= 0:
                    return Response({'detail': f'{field} must be a positive integer.'}, status=400)
                setattr(policy, field, value)
        policy.save()
        record_audit_event(actor=request.user, action='authentication_policy_updated', target_model='AuthenticationPolicy', target_id=policy.id, details={'changed_fields': sorted(request.data.keys()), 'require_mfa': policy.require_mfa, 'require_sso': policy.require_sso})
        return self.get(request)


class AdminImpersonationView(APIView):
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _ip(request):
        return (request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', ''))[:45]

    def get(self, request):
        session = getattr(request, 'impersonation_session', None)
        if not getattr(request, 'impersonating', False) or session is None:
            return Response({'active': False})
        return Response({'active': True, 'session_id': session.id, 'admin': request.impersonator.username, 'target': request.user.username, 'expires_at': session.expires_at, 'reason': session.reason})

    def post(self, request):
        if getattr(request, 'impersonating', False):
            return Response({'detail': 'End the current impersonation before starting another.'}, status=409)
        if request.user.role != 'Admin':
            return Response({'detail': 'Only platform admins can impersonate users.'}, status=403)
        target = get_object_or_404(CustomUser, pk=request.data.get('user_id'), is_active=True)
        if target.pk == request.user.pk:
            return Response({'detail': 'An admin cannot impersonate their own account.'}, status=400)
        reason = str(request.data.get('reason', '')).strip()[:240]
        if len(reason) < 5:
            return Response({'detail': 'A support or incident reason is required.'}, status=400)
        try:
            duration_minutes = min(max(int(request.data.get('duration_minutes', 30)), 5), 60)
        except (TypeError, ValueError):
            return Response({'detail': 'duration_minutes must be an integer between 5 and 60.'}, status=400)
        raw_token = secrets.token_urlsafe(32)
        session = ImpersonationSession.objects.create(
            admin=request.user,
            target=target,
            token_hash=hash_impersonation_token(raw_token),
            reason=reason,
            expires_at=timezone.now() + timedelta(minutes=duration_minutes),
            start_ip=self._ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )
        request.session[SESSION_ID_KEY] = session.id
        request.session[SESSION_TOKEN_KEY] = raw_token
        request.session.modified = True
        record_audit_event(actor=request.user, action='impersonation_started', target_model='CustomUser', target_id=target.id, details={'session_id': session.id, 'reason': reason, 'expires_at': session.expires_at.isoformat()})
        return Response({'active': True, 'session_id': session.id, 'target': {'id': target.id, 'username': target.username, 'email': target.email}, 'expires_at': session.expires_at, 'reason': reason}, status=201)

    def delete(self, request):
        session = getattr(request, 'impersonation_session', None)
        if not getattr(request, 'impersonating', False) or session is None:
            return Response({'detail': 'No active impersonation session.'}, status=400)
        admin = request.impersonator
        session.ended_at = timezone.now()
        session.end_ip = self._ip(request)
        session.save(update_fields=['ended_at', 'end_ip'])
        request.session.pop(SESSION_ID_KEY, None)
        request.session.pop(SESSION_TOKEN_KEY, None)
        request.session.modified = True
        record_audit_event(actor=admin, action='impersonation_ended', target_model='CustomUser', target_id=request.user.id, details={'session_id': session.id, 'reason': session.reason})
        return Response({'active': False, 'ended': True})


class TrustedDeviceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = TrustedDevice.objects.filter(user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now())
        return Response([{'id': item.id, 'label': item.label, 'user_agent': item.user_agent, 'created_at': item.created_at, 'expires_at': item.expires_at, 'last_used_at': item.last_used_at} for item in devices])

    def post(self, request):
        factor = TwoFactorAuth.objects.filter(user=request.user, is_enabled=True).first()
        if not factor:
            return Response({'detail': 'Enable two-factor authentication before trusting a device.'}, status=400)
        from .two_factor import verify_totp
        if not verify_totp(factor.secret, request.data.get('code', '')):
            return Response({'detail': 'Enter a valid authenticator code to trust this device.'}, status=400)
        raw_token = secrets.token_urlsafe(36)
        device = TrustedDevice.objects.create(
            user=request.user,
            label=str(request.data.get('label', 'Trusted device')).strip()[:120] or 'Trusted device',
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            expires_at=timezone.now() + timedelta(days=30),
        )
        record_audit_event(actor=request.user, action='trusted_device_created', target_model='TrustedDevice', target_id=device.id, details={'label': device.label, 'expires_at': device.expires_at.isoformat()})
        return Response({'id': device.id, 'token': raw_token, 'expires_at': device.expires_at}, status=201)

    def delete(self, request, pk=None):
        device = get_object_or_404(TrustedDevice, pk=pk, user=request.user)
        device.revoked_at = timezone.now()
        device.save(update_fields=['revoked_at'])
        record_audit_event(actor=request.user, action='trusted_device_revoked', target_model='TrustedDevice', target_id=device.id, details={'label': device.label})
        return Response({'revoked': True})


class PasskeyView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _b64(value):
        return base64.urlsafe_b64encode(value).rstrip(b'=').decode()

    def get(self, request):
        credentials = PasskeyCredential.objects.filter(user=request.user)
        if request.query_params.get('action') == 'options':
            challenge = secrets.token_bytes(32)
            request.session['passkey_registration_challenge'] = self._b64(challenge)
            request.session['passkey_registration_user'] = request.user.pk
            return Response({
                'supported': True,
                'publicKey': {
                    'challenge': self._b64(challenge),
                    'rp': {'name': 'Article Studio'},
                    'user': {
                        'id': self._b64(str(request.user.pk).encode()),
                        'name': request.user.username,
                        'displayName': request.user.get_full_name() or request.user.username,
                    },
                    'pubKeyCredParams': [{'type': 'public-key', 'alg': -7}, {'type': 'public-key', 'alg': -257}],
                    'timeout': 60000,
                    'attestation': 'none',
                },
            })
        return Response({
            'supported': True,
            'rp_id': settings.WEBAUTHN_RP_ID,
            'origin': settings.WEBAUTHN_ORIGIN,
            'registration': 'Use ?action=options to request a browser registration challenge.',
            'verification': 'A WebAuthn server adapter must verify the attestation before a credential is stored.',
            'credentials': [{'id': item.id, 'label': item.label, 'created_at': item.created_at, 'last_used_at': item.last_used_at} for item in credentials],
        })

    def post(self, request):
        if request.data.get('action') != 'register':
            return Response({'detail': 'Use action=register with a WebAuthn credential.'}, status=400)
        if not request.session.get('passkey_registration_challenge'):
            return Response({'detail': 'Registration challenge expired. Request passkey options again.'}, status=400)
        # The project deliberately does not persist client-provided public keys. A
        # WebAuthn verifier must validate origin, RP ID, challenge and signature.
        return Response({'detail': 'WebAuthn verification is not configured on this deployment.'}, status=501)


class SSOProviderStartView(APIView):
    """Create a short-lived PKCE state without pretending to complete OAuth."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, provider):
        provider = str(provider).strip().lower()
        item = get_object_or_404(SSOProvider, provider=provider, is_enabled=True)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        request.session[f'sso_state_{state}'] = {'provider': provider, 'verifier': verifier}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        return Response({
            'provider': provider,
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
            'discovery_url': item.discovery_url,
            'authorization_url': item.discovery_url,
            'detail': 'Redirect the user to the configured identity provider authorization endpoint.',
        })


class SSOProviderCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, provider):
        provider = str(provider).strip().lower()
        state = str(request.query_params.get('state', '')).strip()
        state_data = request.session.pop(f'sso_state_{state}', None)
        if not state_data or state_data.get('provider') != provider:
            return Response({'detail': 'Invalid or expired SSO state.'}, status=400)
        if provider != 'saml' and not request.query_params.get('code'):
            return Response({'detail': 'The identity provider did not return an authorization code.'}, status=400)
        if provider == 'saml' and not request.query_params.get('SAMLResponse'):
            return Response({'detail': 'The identity provider did not return a SAML response.'}, status=400)
        item = get_object_or_404(SSOProvider, provider=provider, is_enabled=True)
        if provider == 'saml':
            try:
                from .saml import SAMLConfigurationError, validate_saml_response
                profile = validate_saml_response(item, request)
            except SAMLConfigurationError as exc:
                return Response({'detail': str(exc)}, status=503)
        elif not item.token_url or not item.userinfo_url or not item.client_id:
            return Response({'detail': 'The SSO provider is missing token or userinfo configuration.'}, status=503)
        else:
            try:
                token_response = requests.post(item.token_url, data={
                    'grant_type': 'authorization_code', 'code': request.query_params['code'],
                    'client_id': item.client_id, 'client_secret': item.client_secret,
                    'redirect_uri': request.build_absolute_uri(f'/api/sso/{provider}/callback/'),
                    'code_verifier': (state_data or {}).get('verifier', ''),
                }, timeout=settings.SSO_HTTP_TIMEOUT)
                if not token_response.ok:
                    return Response({'detail': 'The identity provider rejected the authorization code.'}, status=502)
                token_payload = token_response.json()
                userinfo = requests.get(item.userinfo_url, headers={'Authorization': f"Bearer {token_payload.get('access_token', '')}"}, timeout=settings.SSO_HTTP_TIMEOUT)
                if not userinfo.ok:
                    return Response({'detail': 'The identity provider user profile request failed.'}, status=502)
                profile = userinfo.json()
            except (requests.RequestException, ValueError):
                return Response({'detail': 'The identity provider exchange could not be completed.'}, status=502)
        email = str(profile.get('email') or profile.get('preferred_username') or '').strip().lower()
        if not email:
            return Response({'detail': 'The identity provider did not return an email address.'}, status=400)
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            if not item.auto_provision:
                return Response({'detail': 'This account is not provisioned for the newsroom.'}, status=403)
            base_username = slugify(email.split('@', 1)[0]) or 'sso-user'
            username = base_username
            suffix = 1
            while CustomUser.objects.filter(username=username).exists():
                suffix += 1
                username = f'{base_username}-{suffix}'
            user = CustomUser.objects.create_user(username=username, email=email, role=item.default_role, is_active=True)
        if not user.is_active:
            return Response({'detail': 'This account is disabled.'}, status=403)
        login(request, user)
        from users.views import get_tokens_for_user
        return Response({'provider': provider, 'authenticated': True, 'user': {'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role}, 'tokens': get_tokens_for_user(user, request)})


class SSOProviderView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage SSO providers.'}, status=403)
        providers = SSOProvider.objects.all()
        return Response([{'provider': item.provider, 'client_id': item.client_id, 'discovery_url': item.discovery_url, 'token_url': item.token_url, 'userinfo_url': item.userinfo_url, 'metadata_url': item.metadata_url, 'default_role': item.default_role, 'auto_provision': item.auto_provision, 'is_enabled': item.is_enabled} for item in providers])

    def patch(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage SSO providers.'}, status=403)
        provider = str(request.data.get('provider', '')).strip().lower()
        if provider not in {'oidc', 'google', 'microsoft', 'saml'}:
            return Response({'detail': 'Choose oidc, google, microsoft, or saml.'}, status=400)
        existing = SSOProvider.objects.filter(provider=provider).first()
        client_secret = str(request.data.get('client_secret', '')).strip()
        item, _ = SSOProvider.objects.update_or_create(provider=provider, defaults={
            'client_id': str(request.data.get('client_id', '')).strip(),
            'client_secret': client_secret or (existing.client_secret if existing else ''),
            'discovery_url': str(request.data.get('discovery_url', '')).strip(),
            'token_url': str(request.data.get('token_url', '')).strip(),
            'userinfo_url': str(request.data.get('userinfo_url', '')).strip(),
            'metadata_url': str(request.data.get('metadata_url', '')).strip(),
            'default_role': str(request.data.get('default_role') or 'Journalist'),
            'auto_provision': bool(request.data.get('auto_provision', True)),
            'is_enabled': bool(request.data.get('is_enabled', False)),
        })
        record_audit_event(actor=request.user, action='sso_provider_updated', target_model='SSOProvider', target_id=item.id, details={'provider': item.provider, 'is_enabled': item.is_enabled, 'auto_provision': item.auto_provision})
        return Response({'provider': item.provider, 'client_id': item.client_id, 'discovery_url': item.discovery_url, 'token_url': item.token_url, 'userinfo_url': item.userinfo_url, 'metadata_url': item.metadata_url, 'default_role': item.default_role, 'auto_provision': item.auto_provision, 'is_enabled': item.is_enabled})


def _scim_response(user, workspace, request=None):
    base = request.build_absolute_uri(f'/scim/v2/{workspace.slug}/Users/{user.id}') if request else ''
    return {
        'schemas': ['urn:ietf:params:scim:schemas:core:2.0:User'],
        'id': str(user.id),
        'userName': user.email,
        'active': user.is_active,
        'emails': [{'value': user.email, 'primary': True}],
        'name': {'givenName': user.first_name, 'familyName': user.last_name},
        'meta': {'resourceType': 'User', 'location': base},
    }


def _scim_workspace(request, slug):
    authorization = str(request.headers.get('Authorization', ''))
    raw_token = authorization[7:].strip() if authorization.lower().startswith('bearer ') else ''
    if not raw_token:
        return None, None
    token = SCIMToken.objects.select_related('workspace').filter(
        prefix=raw_token[:12], is_active=True, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        workspace__slug=slug,
    ).first()
    if not token or token.expires_at and token.expires_at <= timezone.now():
        return None, None
    token.last_used_at = timezone.now()
    token.save(update_fields=['last_used_at'])
    return token.workspace, token


class SCIMTokenView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        membership = WorkspaceMembership.objects.filter(workspace=workspace, user=request.user, role__in={'owner', 'admin'}).first()
        if request.user.role != 'Admin' and not membership:
            return Response({'detail': 'Only workspace admins can manage SCIM tokens.'}, status=403)
        raw = f'scim_{secrets.token_urlsafe(32)}'
        token = SCIMToken.objects.create(workspace=workspace, prefix=raw[:12], token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=timezone.now() + timedelta(days=90))
        record_audit_event(actor=request.user, workspace=workspace, action='scim_token_created', target_model='SCIMToken', target_id=token.id, details={'prefix': token.prefix, 'expires_at': token.expires_at.isoformat()})
        return Response({'token': raw, 'workspace': workspace.slug, 'expires_at': token.expires_at}, status=201)

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        membership = WorkspaceMembership.objects.filter(workspace=workspace, user=request.user, role__in={'owner', 'admin'}).first()
        if request.user.role != 'Admin' and not membership:
            return Response({'detail': 'Only workspace admins can view SCIM tokens.'}, status=403)
        return Response([{'id': token.id, 'prefix': token.prefix, 'is_active': token.is_active, 'expires_at': token.expires_at, 'last_used_at': token.last_used_at} for token in workspace.scim_tokens.all()])


class SCIMUsersView(APIView):
    authentication_classes = []
    permission_classes = []

    def _workspace(self, request, slug):
        workspace, token = _scim_workspace(request, slug)
        if not workspace:
            return Response({'detail': 'A valid SCIM bearer token is required.'}, status=401), None
        return None, workspace

    def get(self, request, slug):
        error, workspace = self._workspace(request, slug)
        if error:
            return error
        members = workspace.memberships.select_related('user').all()
        return Response({'schemas': ['urn:ietf:params:scim:api:messages:2.0:ListResponse'], 'totalResults': members.count(), 'Resources': [_scim_response(item.user, workspace, request) for item in members]})

    def post(self, request, slug):
        error, workspace = self._workspace(request, slug)
        if error:
            return error
        emails = request.data.get('emails') or []
        email = str((emails[0].get('value') if emails and isinstance(emails[0], dict) else request.data.get('userName')) or '').strip().lower()
        if not email:
            return Response({'detail': 'SCIM userName or emails[0].value is required.'}, status=400)
        user = CustomUser.objects.filter(email=email).first()
        if not user:
            username = slugify(email.split('@', 1)[0]) or 'scim-user'
            suffix = 1
            while CustomUser.objects.filter(username=username).exists():
                suffix += 1
                username = f'{username}-{suffix}'
            user = CustomUser.objects.create_user(username=username, email=email, password=secrets.token_urlsafe(24), role='Journalist', is_active=bool(request.data.get('active', True)))
        role = str(request.data.get('role') or 'writer').lower()
        if role not in {'viewer', 'writer', 'editor'}:
            role = 'writer'
        WorkspaceMembership.objects.update_or_create(workspace=workspace, user=user, defaults={'role': role})
        return Response(_scim_response(user, workspace, request), status=201)


class SCIMUserDetailView(SCIMUsersView):
    def get(self, request, slug, pk):
        error, workspace = self._workspace(request, slug)
        if error:
            return error
        membership = get_object_or_404(WorkspaceMembership.objects.select_related('user'), workspace=workspace, user_id=pk)
        return Response(_scim_response(membership.user, workspace, request))

    def patch(self, request, slug, pk):
        error, workspace = self._workspace(request, slug)
        if error:
            return error
        membership = get_object_or_404(WorkspaceMembership.objects.select_related('user'), workspace=workspace, user_id=pk)
        user = membership.user
        if 'active' in request.data:
            user.is_active = bool(request.data['active'])
        emails = request.data.get('emails') or []
        if emails and isinstance(emails[0], dict) and emails[0].get('value'):
            user.email = str(emails[0]['value']).strip().lower()
        user.save(update_fields=['is_active', 'email'])
        return Response(_scim_response(user, workspace, request))

    def delete(self, request, slug, pk):
        error, workspace = self._workspace(request, slug)
        if error:
            return error
        membership = get_object_or_404(WorkspaceMembership.objects.select_related('user'), workspace=workspace, user_id=pk)
        membership.user.is_active = False
        membership.user.save(update_fields=['is_active'])
        return Response(status=204)


class ReaderInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReaderInterest
        fields = ['id', 'interest_type', 'value', 'created_at']
        read_only_fields = ['id', 'created_at']


class PersonalizationPreferenceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def preference(self, user):
        return PersonalizationPreference.objects.get_or_create(user=user)[0]

    def payload(self, item):
        return {'enabled': item.enabled, 'use_reading_history': item.use_reading_history, 'use_topic_interests': item.use_topic_interests, 'updated_at': item.updated_at}

    def get(self, request):
        return Response(self.payload(self.preference(request.user)))

    def patch(self, request):
        item = self.preference(request.user)
        for field in ('enabled', 'use_reading_history', 'use_topic_interests'):
            if field in request.data:
                setattr(item, field, bool(request.data[field]))
        item.save()
        return Response(self.payload(item))

    def delete(self, request):
        from articles.models import ArticleEngagementEvent, ArticleView, ReadingProgress
        ArticleView.objects.filter(user=request.user).delete()
        ArticleEngagementEvent.objects.filter(user=request.user).delete()
        ReadingProgress.objects.filter(user=request.user).delete()
        item = self.preference(request.user)
        item.use_reading_history = False
        item.save(update_fields=['use_reading_history', 'updated_at'])
        return Response({'history_reset': True, **self.payload(item)})


class ReaderInterestView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ReaderInterestSerializer(ReaderInterest.objects.filter(user=request.user), many=True).data)

    def post(self, request):
        serializer = ReaderInterestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        interest, _ = ReaderInterest.objects.get_or_create(user=request.user, **serializer.validated_data)
        return Response(ReaderInterestSerializer(interest).data, status=201)

    def delete(self, request):
        deleted, _ = ReaderInterest.objects.filter(
            user=request.user,
            interest_type=request.data.get('interest_type') or request.query_params.get('interest_type'),
            value=request.data.get('value') or request.query_params.get('value'),
        ).delete()
        return Response({'removed': bool(deleted)})


class AccessibilityPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessibilityPreference
        fields = ['high_contrast', 'reduce_motion', 'large_text']


class AccessibilityPreferenceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_preferences(self, user):
        preferences, _ = AccessibilityPreference.objects.get_or_create(user=user)
        return preferences

    def get(self, request):
        return Response(AccessibilityPreferenceSerializer(self.get_preferences(request.user)).data)

    def patch(self, request):
        preferences = self.get_preferences(request.user)
        serializer = AccessibilityPreferenceSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MembershipPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipPlan
        fields = ['id', 'name', 'slug', 'description', 'price', 'currency', 'interval', 'features']
        read_only_fields = fields


class MembershipPlanView(generics.ListAPIView):
    serializer_class = MembershipPlanSerializer
    permission_classes = []
    queryset = MembershipPlan.objects.filter(is_active=True)


class MembershipSubscriptionSerializer(serializers.ModelSerializer):
    plan = MembershipPlanSerializer(read_only=True)

    class Meta:
        model = MembershipSubscription
        fields = ['id', 'plan', 'status', 'provider', 'provider_reference', 'started_at', 'expires_at', 'auto_renew', 'created_at', 'updated_at']
        read_only_fields = fields


class MembershipMeView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscriptions = MembershipSubscription.objects.filter(user=request.user).select_related('plan')
        transactions = PaymentTransaction.objects.filter(user=request.user).select_related('plan')[:20]
        return Response({'active': has_active_membership(request.user), 'subscriptions': MembershipSubscriptionSerializer(subscriptions, many=True).data, 'transactions': [{'id': item.id, 'plan': item.plan.name, 'provider': item.provider, 'amount': item.amount, 'currency': item.currency, 'status': item.status, 'provider_reference': item.provider_reference, 'created_at': item.created_at} for item in transactions]})


class MembershipCheckoutView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = get_object_or_404(MembershipPlan, pk=request.data.get('plan_id'), is_active=True)
        provider = str(request.data.get('provider', getattr(settings, 'PAYMENT_PROVIDER', 'manual'))).strip().lower()
        if provider not in {'manual', 'stripe', 'razorpay'}:
            return Response({'detail': 'Choose manual, stripe, or razorpay.'}, status=400)
        attribution = NewsletterCampaignAttribution.objects.filter(
            pk=request.session.get('newsletter_attribution_id'),
            clicked_at__gte=timezone.now() - timedelta(days=30),
            converted_at__isnull=True,
        ).first()
        if attribution:
            attribution.user = request.user
            attribution.checkout_started_at = timezone.now()
            attribution.save(update_fields=['user', 'checkout_started_at'])
        subscription, _ = MembershipSubscription.objects.update_or_create(
            user=request.user, plan=plan, status__in=['pending', 'canceled'],
            defaults={'status': 'active' if plan.price == 0 else 'pending', 'provider': provider, 'started_at': timezone.now() if plan.price == 0 else None},
        )
        record_audit_event(actor=request.user, action='membership_checkout_started', target_model='MembershipSubscription', target_id=subscription.id, details={'plan': plan.slug, 'provider': provider, 'price': str(plan.price)})
        if plan.price > 0:
            transaction = PaymentTransaction.objects.create(user=request.user, plan=plan, provider=provider, checkout_token=secrets.token_urlsafe(40), amount=plan.price, currency=plan.currency)
            invoice = MembershipInvoice.objects.create(invoice_number=f'AS-{timezone.now().strftime("%Y%m%d")}-{transaction.id:06d}', user=request.user, plan=plan, transaction=transaction, amount=plan.price, currency=plan.currency, status='issued', due_at=timezone.now() + timedelta(days=7))
            if attribution:
                attribution.transaction = transaction
                attribution.save(update_fields=['transaction'])
            from .billing_providers import ProviderRequestError, create_checkout
            try:
                checkout = create_checkout(transaction, request)
            except ProviderRequestError as error:
                transaction.status = 'failed'
                transaction.save(update_fields=['status', 'updated_at'])
                invoice.status = 'void'
                invoice.save(update_fields=['status'])
                return Response({'detail': str(error)}, status=502)
            transaction.provider_reference = checkout.get('provider_reference', '')[:160]
            transaction.checkout_url = checkout.get('checkout_url', '')[:500]
            transaction.save(update_fields=['provider_reference', 'checkout_url', 'updated_at'])
            detail = 'Checkout session created. Complete payment with the configured provider.' if checkout.get('configured') else 'Checkout created. Provider credentials are not configured yet.'
            return Response({'detail': detail, 'checkout_required': True, 'provider': provider, 'provider_configured': checkout.get('configured', False), 'checkout_token': transaction.checkout_token, 'checkout_url': transaction.checkout_url, 'transaction_id': transaction.id, 'invoice_number': invoice.invoice_number, 'plan': MembershipPlanSerializer(plan).data}, status=202)
        if attribution:
            attribution.subscription = subscription
            attribution.converted_at = timezone.now()
            attribution.save(update_fields=['subscription', 'converted_at'])
        return Response(MembershipSubscriptionSerializer(subscription).data, status=201)


class MembershipCheckoutStatusView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, checkout_token):
        transaction = get_object_or_404(
            PaymentTransaction.objects.select_related('plan', 'invoice'),
            checkout_token=checkout_token,
            user=request.user,
        )
        subscription = MembershipSubscription.objects.filter(user=request.user, plan=transaction.plan).order_by('-created_at').first()
        return Response({
            'transaction_id': transaction.id,
            'status': transaction.status,
            'provider': transaction.provider,
            'provider_reference': transaction.provider_reference,
            'checkout_url': transaction.checkout_url,
            'invoice': {
                'number': transaction.invoice.invoice_number,
                'status': transaction.invoice.status,
                'paid_at': transaction.invoice.paid_at,
            } if hasattr(transaction, 'invoice') else None,
            'subscription': MembershipSubscriptionSerializer(subscription).data if subscription else None,
        })


class PaymentTransactionView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = PaymentTransaction.objects.filter(user=request.user).select_related('plan')[:50]
        return Response([{'id': item.id, 'plan': item.plan.name, 'provider': item.provider, 'amount': item.amount, 'currency': item.currency, 'status': item.status, 'provider_reference': item.provider_reference, 'created_at': item.created_at} for item in transactions])


class RevenueEntitlementView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscriptions = MembershipSubscription.objects.filter(user=request.user).select_related('plan').order_by('-created_at')
        invoices = MembershipInvoice.objects.filter(user=request.user).select_related('plan').order_by('-created_at')[:50]
        return Response({
            'active': has_active_membership(request.user),
            'entitlements': [{'plan': item.plan.slug, 'features': item.plan.features, 'status': item.status, 'expires_at': item.expires_at} for item in subscriptions if item.status in {'active', 'past_due'}],
            'invoices': [{'invoice_number': item.invoice_number, 'plan': item.plan.name, 'amount': item.amount, 'currency': item.currency, 'status': item.status, 'due_at': item.due_at, 'paid_at': item.paid_at} for item in invoices],
        })


class MembershipCancelView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = MembershipSubscription.objects.filter(user=request.user, status='active').order_by('-created_at').first()
        if not subscription:
            return Response({'detail': 'No active membership found.'}, status=404)
        try:
            from .billing_providers import cancel_remote_subscription
            remote = cancel_remote_subscription(subscription)
        except Exception as error:
            return Response({'detail': str(error)}, status=502)
        subscription.status = 'canceled'
        subscription.auto_renew = False
        subscription.save(update_fields=['status', 'auto_renew', 'updated_at'])
        record_audit_event(actor=request.user, action='membership_canceled', target_model='MembershipSubscription', target_id=subscription.id, details={'provider': subscription.provider, 'remote_cancellation': bool(remote)})
        response = MembershipSubscriptionSerializer(subscription).data
        response['remote_cancellation'] = remote
        return Response(response)


class ProviderHealthView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in {'Editor', 'Admin'}:
            return Response({'detail': 'Only editors and admins can view provider health.'}, status=403)
        from .provider_health import provider_health
        return Response(provider_health())


class MembershipWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        secret = settings.PAYMENT_WEBHOOK_SECRET
        provider = str(request.headers.get('X-Payment-Provider') or '').strip().lower()
        if not secret and not (
            provider == 'stripe' and request.headers.get('Stripe-Signature') and settings.STRIPE_WEBHOOK_SECRET
        ) and not (
            provider == 'razorpay' and request.headers.get('X-Razorpay-Signature') and settings.RAZORPAY_WEBHOOK_SECRET
        ):
            return Response({'detail': 'Payment webhook is not configured.'}, status=503)
        from .billing_providers import verify_payment_webhook_signature
        if not verify_payment_webhook_signature(provider, request.body, request.headers):
            return Response({'detail': 'Invalid payment webhook signature.'}, status=403)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({'detail': 'Webhook payload must be valid JSON.'}, status=400)
        provider = str(request.headers.get('X-Payment-Provider') or payload.get('provider') or 'payment').strip().lower()[:30]
        event_id = str(payload.get('id', '')).strip()
        event_type = str(payload.get('type', '')).strip()
        data = payload.get('data') or {}
        if isinstance(data, dict) and isinstance(data.get('object'), dict):
            data = {**data['object'], **{f'metadata_{key}': value for key, value in (data['object'].get('metadata') or {}).items()}}
        metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
        notes = data.get('notes') if isinstance(data.get('notes'), dict) else {}
        user_id = data.get('user_id') or metadata.get('user_id') or data.get('metadata_user_id')
        plan_id = data.get('plan_id') or metadata.get('plan_id') or data.get('metadata_plan_id')
        transaction_id = data.get('transaction_id') or metadata.get('transaction_id') or data.get('metadata_transaction_id')
        checkout_token = data.get('checkout_token') or metadata.get('checkout_token') or data.get('metadata_checkout_token')
        tip_id = data.get('tip_id') or metadata.get('tip_id') or data.get('metadata_tip_id') or notes.get('tip_id')
        tip_checkout_token = checkout_token or notes.get('checkout_token')
        provider_reference = str(data.get('provider_reference') or data.get('subscription_id') or data.get('subscription') or data.get('id') or '')[:160]
        if not event_id or not event_type:
            return Response({'detail': 'Webhook id and type are required.'}, status=400)
        event, created = MembershipWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={'provider': provider, 'event_type': event_type, 'payload': payload},
        )
        if not created:
            return Response({'processed': True, 'duplicate': True})
        record_audit_event(actor=None, action='payment_webhook_received', target_model='MembershipWebhookEvent', target_id=event.id, details={'provider': provider, 'event_type': event_type})
        status_map = {
            'subscription.active': 'active',
            'subscription.canceled': 'canceled',
            'subscription.past_due': 'past_due',
            'checkout.session.completed': 'active',
            'invoice.payment_succeeded': 'active',
            'invoice.payment_failed': 'past_due',
            'customer.subscription.deleted': 'canceled',
            'payment.captured': 'active',
            'subscription.cancelled': 'canceled',
            'subscription.charged': 'active',
            'charge.refunded': 'canceled',
            'payment.refunded': 'canceled',
            'refund.created': 'canceled',
            'payment.failed': 'failed',
            'payment.canceled': 'failed',
        }
        if event_type not in status_map:
            return Response({'processed': True, 'ignored': True})
        if tip_id or tip_checkout_token:
            tip_query = AuthorTip.objects.all()
            if tip_id:
                tip_query = tip_query.filter(pk=tip_id)
            else:
                tip_query = tip_query.filter(checkout_token=tip_checkout_token)
            tip = tip_query.first()
            if not tip:
                return Response({'processed': True, 'ignored': True, 'reason': 'tip_not_found'})
            if event_type in {'checkout.session.completed', 'payment.captured', 'subscription.charged', 'payment.succeeded'}:
                tip.status = 'succeeded'
            elif event_type in {'charge.refunded', 'payment.refunded', 'refund.created'}:
                tip.status = 'refunded'
            else:
                tip.status = 'failed'
            tip.provider = provider
            tip.provider_reference = provider_reference or tip.provider_reference
            tip.save(update_fields=['status', 'provider', 'provider_reference', 'updated_at'])
            return Response({'processed': True, 'tip_id': tip.id, 'status': tip.status})
        user = get_object_or_404(CustomUser, pk=user_id)
        plan = get_object_or_404(MembershipPlan, pk=plan_id, is_active=True)
        subscription_defaults = {
            'provider': provider,
            'status': status_map[event_type],
            'auto_renew': status_map[event_type] == 'active',
        }
        if status_map[event_type] == 'active':
            subscription_defaults['started_at'] = timezone.now()
        subscription = MembershipSubscription.objects.filter(user=user, plan=plan).order_by('-created_at').first()
        if subscription:
            for field, value in subscription_defaults.items():
                setattr(subscription, field, value)
            subscription.provider_reference = provider_reference or subscription.provider_reference
            subscription.save(update_fields=[*subscription_defaults.keys(), 'provider_reference', 'updated_at'])
        else:
            subscription = MembershipSubscription.objects.create(
                user=user, plan=plan, provider_reference=provider_reference, **subscription_defaults,
            )
        transaction_statuses = ['pending', 'succeeded'] if status_map[event_type] == 'canceled' else ['pending']
        transaction_query = PaymentTransaction.objects.filter(user=user, plan=plan, status__in=transaction_statuses)
        if transaction_id:
            transaction_query = transaction_query.filter(pk=transaction_id)
        elif checkout_token:
            transaction_query = transaction_query.filter(checkout_token=checkout_token)
        payment = transaction_query.order_by('-created_at').first()
        if status_map[event_type] == 'active':
            if payment:
                payment.status = 'succeeded'
                payment.provider_reference = provider_reference or payment.provider_reference
                payment.save(update_fields=['status', 'provider_reference', 'updated_at'])
                if hasattr(payment, 'invoice'):
                    payment.invoice.status = 'paid'
                    payment.invoice.paid_at = timezone.now()
                    payment.invoice.save(update_fields=['status', 'paid_at'])
            attribution = NewsletterCampaignAttribution.objects.filter(transaction=payment).first() if payment else None
            if attribution is None:
                attribution = NewsletterCampaignAttribution.objects.filter(
                    user=user,
                    checkout_started_at__isnull=False,
                    converted_at__isnull=True,
                ).order_by('-checkout_started_at').first()
            if attribution:
                attribution.user = user
                attribution.subscription = subscription
                attribution.converted_at = timezone.now()
                attribution.save(update_fields=['user', 'subscription', 'converted_at'])
        elif payment:
            payment.status = 'failed' if status_map[event_type] == 'past_due' else 'refunded'
            payment.provider_reference = provider_reference or payment.provider_reference
            payment.save(update_fields=['status', 'provider_reference', 'updated_at'])
            if hasattr(payment, 'invoice') and status_map[event_type] == 'past_due':
                payment.invoice.status = 'issued'
                payment.invoice.save(update_fields=['status'])
            elif hasattr(payment, 'invoice') and status_map[event_type] == 'canceled':
                payment.invoice.status = 'refunded'
                payment.invoice.paid_at = None
                payment.invoice.save(update_fields=['status', 'paid_at'])
        return Response({'processed': True, 'subscription_id': subscription.id})


class PublicAuthorView(APIView):
    permission_classes = []

    def get(self, request, user_id):
        from django.shortcuts import get_object_or_404
        author = get_object_or_404(CustomUser, pk=user_id, is_active=True)
        articles = Article.objects.filter(
            author=author,
            workflow_status='published',
            is_visible=True,
        ).order_by('-published_at', '-created_at')
        return Response({
            'id': author.id,
            'username': author.username,
            'first_name': author.first_name,
            'last_name': author.last_name,
            'display_name': author.get_full_name() or author.username,
            'bio': getattr(getattr(author, 'profile', None), 'bio', '') or '',
            'profile_picture': (
                author.profile.profile_picture.url
                if hasattr(author, 'profile') and author.profile.profile_picture else None
            ),
            'published_count': articles.count(),
            'total_views': sum(article.views.count() for article in articles),
            'articles': [
                {
                    'id': article.id,
                    'title': article.title,
                    'slug': article.slug,
                    'summary': article.summary,
                    'category': article.category,
                    'published_at': article.published_at,
                }
                for article in articles
            ],
        })


class AuthorTipSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('1.00'))
    author_name = serializers.CharField(source='author.username', read_only=True)
    sender_name = serializers.CharField(source='sender.username', read_only=True, default=None)

    class Meta:
        model = AuthorTip
        fields = ['id', 'sender', 'sender_name', 'author', 'author_name', 'amount', 'currency', 'message', 'status', 'provider', 'checkout_token', 'checkout_url', 'provider_reference', 'created_at', 'updated_at']
        read_only_fields = ['id', 'sender', 'author', 'sender_name', 'author_name', 'status', 'provider', 'checkout_token', 'checkout_url', 'provider_reference', 'created_at', 'updated_at']


class AuthorTipIntentView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, author_id):
        author = get_object_or_404(CustomUser, pk=author_id, is_active=True)
        if author.id == request.user.id:
            return Response({'detail': 'You cannot send a tip to yourself.'}, status=400)
        serializer = AuthorTipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = str(request.data.get('provider') or 'manual').strip().lower()
        if provider not in {'manual', 'stripe', 'razorpay'}:
            return Response({'detail': 'Choose manual, stripe, or razorpay.'}, status=400)
        tip = serializer.save(
            sender=request.user,
            author=author,
            status='pending',
            provider=provider,
            checkout_token=secrets.token_urlsafe(40),
        )
        checkout = {'configured': False, 'checkout_url': '', 'provider_reference': ''}
        if provider in {'stripe', 'razorpay'}:
            from .billing_providers import ProviderRequestError, create_tip_checkout
            try:
                checkout = create_tip_checkout(tip, request)
            except ProviderRequestError as exc:
                tip.status = 'failed'
                tip.save(update_fields=['status', 'updated_at'])
                return Response({'detail': str(exc), 'tip': AuthorTipSerializer(tip).data}, status=502)
            tip.checkout_url = checkout.get('checkout_url', '')[:500]
            tip.provider_reference = checkout.get('provider_reference', '')[:160]
            tip.save(update_fields=['checkout_url', 'provider_reference', 'updated_at'])
        return Response({
            'tip': AuthorTipSerializer(tip).data,
            'payment_required': True,
            'provider_configured': bool(checkout.get('configured')) if provider != 'manual' else False,
            'detail': 'Tip checkout created. Complete payment with the configured provider.' if provider != 'manual' and checkout.get('configured') else 'Tip intent created. Complete payment with the configured provider.',
        }, status=202)


class AuthorTipHistoryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sent = AuthorTip.objects.filter(sender=request.user).select_related('author')
        received = AuthorTip.objects.filter(author=request.user).select_related('sender')
        return Response({
            'sent': AuthorTipSerializer(sent, many=True).data,
            'received': AuthorTipSerializer(received, many=True).data,
            'received_total': sum((tip.amount for tip in received if tip.status == 'succeeded'), Decimal('0.00')),
        })


class PublicAPIKeySerializer(serializers.ModelSerializer):
    API_SCOPE_CHOICES = ['articles:read', 'articles:search', 'analytics:read']
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=API_SCOPE_CHOICES),
        required=False,
        allow_empty=True,
        default=['articles:read'],
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = PublicAPIKey
        fields = ['id', 'name', 'prefix', 'scopes', 'is_active', 'expires_at', 'created_at', 'last_used_at']
        read_only_fields = ['id', 'prefix', 'is_active', 'created_at', 'last_used_at']


class PublicAPIKeyView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        keys = PublicAPIKey.objects.filter(owner=request.user)
        return Response(PublicAPIKeySerializer(keys, many=True).data)

    def post(self, request):
        serializer = PublicAPIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_key = f'as_{secrets.token_urlsafe(32)}'
        key = PublicAPIKey.objects.create(
            owner=request.user,
            name=serializer.validated_data['name'],
            scopes=serializer.validated_data.get('scopes') or ['articles:read'],
            prefix=raw_key[:10],
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
            expires_at=serializer.validated_data.get('expires_at') or timezone.now() + timedelta(days=90),
        )
        record_audit_event(actor=request.user, action='api_key_created', target_model='PublicAPIKey', target_id=key.id, details={'name': key.name, 'scopes': key.scopes, 'expires_at': key.expires_at.isoformat() if key.expires_at else None})
        return Response({'key': raw_key, 'details': PublicAPIKeySerializer(key).data}, status=201)


class PublicAPIKeyDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        key = get_object_or_404(PublicAPIKey, pk=pk, owner=request.user)
        key.is_active = False
        key.save(update_fields=['is_active'])
        record_audit_event(actor=request.user, action='api_key_revoked', target_model='PublicAPIKey', target_id=key.id, details={'prefix': key.prefix})
        return Response({'revoked': True})

    def post(self, request, pk):
        key = get_object_or_404(PublicAPIKey, pk=pk, owner=request.user)
        raw_key = f'as_{secrets.token_urlsafe(32)}'
        key.prefix = raw_key[:10]
        key.key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key.is_active = True
        key.expires_at = timezone.now() + timedelta(days=90)
        key.save(update_fields=['prefix', 'key_hash', 'is_active', 'expires_at'])
        record_audit_event(actor=request.user, action='api_key_rotated', target_model='PublicAPIKey', target_id=key.id, details={'prefix': key.prefix, 'expires_at': key.expires_at.isoformat()})
        return Response({'key': raw_key, 'details': PublicAPIKeySerializer(key).data})


class PublicAPIKeyUsageView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        key = get_object_or_404(PublicAPIKey, pk=pk, owner=request.user)
        events = PublicAPIKeyUsage.objects.filter(api_key=key)
        recent = events[:100]
        status_counts = {}
        for code in events.values_list('status_code', flat=True):
            status_counts[str(code)] = status_counts.get(str(code), 0) + 1
        return Response({
            'key_id': key.id,
            'prefix': key.prefix,
            'request_count': events.count(),
            'status_counts': status_counts,
            'recent': [{'endpoint': item.endpoint, 'method': item.method, 'status_code': item.status_code, 'response_ms': item.response_ms, 'created_at': item.created_at} for item in recent],
        })


class WebhookEndpointSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = WebhookEndpoint
        fields = ['id', 'url', 'secret', 'events', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at']


class WebhookEndpointView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(WebhookEndpointSerializer(WebhookEndpoint.objects.filter(owner=request.user), many=True).data)

    def post(self, request):
        serializer = WebhookEndpointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        endpoint = serializer.save(owner=request.user, secret=serializer.validated_data.get('secret') or secrets.token_urlsafe(32))
        record_audit_event(actor=request.user, action='webhook_endpoint_created', target_model='WebhookEndpoint', target_id=endpoint.id, details={'url': endpoint.url, 'events': endpoint.events})
        return Response(WebhookEndpointSerializer(endpoint).data, status=201)


class WebhookEndpointRotateSecretView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        endpoint = get_object_or_404(WebhookEndpoint, pk=pk, owner=request.user)
        endpoint.secret = secrets.token_urlsafe(32)
        endpoint.save(update_fields=['secret', 'updated_at'])
        record_audit_event(actor=request.user, action='webhook_secret_rotated', target_model='WebhookEndpoint', target_id=endpoint.id, details={'url': endpoint.url})
        return Response({'secret': endpoint.secret, 'endpoint': WebhookEndpointSerializer(endpoint).data})


class WebhookDeliveryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        deliveries = WebhookDelivery.objects.filter(endpoint__owner=request.user).select_related('endpoint')
        status_filter = request.query_params.get('status')
        if status_filter in dict(WebhookDelivery.STATUS_CHOICES):
            deliveries = deliveries.filter(status=status_filter)
        deliveries = deliveries[:100]
        return Response([{
            'id': delivery.id,
            'event_id': delivery.event_id,
            'endpoint_id': delivery.endpoint_id,
            'endpoint_url': delivery.endpoint.url,
            'event_type': delivery.event_type,
            'status': delivery.status,
            'response_code': delivery.response_code,
            'attempts': delivery.attempts,
            'last_error': delivery.last_error,
            'delivered_at': delivery.delivered_at,
            'created_at': delivery.created_at,
        } for delivery in deliveries])

    def post(self, request):
        from .delivery import retry_webhook_delivery
        delivery = get_object_or_404(WebhookDelivery.objects.select_related('endpoint'), pk=request.data.get('delivery_id'), endpoint__owner=request.user)
        if delivery.status != 'failed':
            return Response({'detail': 'Only failed deliveries can be retried.'}, status=400)
        delivery = retry_webhook_delivery(delivery)
        record_audit_event(actor=request.user, action='webhook_delivery_retried', target_model='WebhookDelivery', target_id=delivery.id, details={'endpoint_id': delivery.endpoint_id, 'status': delivery.status, 'attempts': delivery.attempts})
        return Response({'status': delivery.status, 'attempts': delivery.attempts})


class DeveloperAPIDocumentationView(APIView):
    permission_classes = []

    def get(self, request):
        return Response({
            'name': 'Article Studio Headless API',
            'authentication': 'Send a generated key in the X-API-Key header.',
            'rate_limit': '120 requests per minute per API key.',
            'scopes': {'articles:read': 'Read published articles from the headless feed.'},
            'endpoints': {
                'articles': '/api/v2/public/articles/',
                'rss': '/rss.xml',
                'sitemap': '/sitemap.xml',
                'webhooks': '/api/developer/webhooks/',
            },
            'version': 'v2',
            'examples': {'curl': 'curl -H "X-API-Key: as_..." https://news.example.com/api/v2/public/articles/'},
            'events': ['article.published', 'article.updated', 'article.deleted'],
            'authentication': {'header': 'X-API-Key', 'scopes': PublicAPIKeySerializer.API_SCOPE_CHOICES},
            'pagination': {'query': {'page': '1-based page number', 'limit': '1-100'}, 'response': ['count', 'page', 'page_size', 'next_page', 'previous_page', 'results']},
            'rate_limit': {'requests_per_minute': settings.PUBLIC_API_KEY_RATE_LIMIT},
        })


def resolve_public_api_key(raw_key, required_scope=None, endpoint='', method='GET'):
    if not raw_key:
        return None
    key = PublicAPIKey.objects.filter(
        prefix=raw_key[:10], is_active=True,
    ).filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now()),
    ).filter(
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
    ).select_related('owner').first()
    if key:
        if required_scope and required_scope not in (key.scopes or ['articles:read']):
            return None
        rate_key = f'public-api-key:{key.id}:{timezone.now().strftime("%Y%m%d%H%M")}'
        requests_in_window = cache.get(rate_key, 0)
        if requests_in_window >= settings.PUBLIC_API_KEY_RATE_LIMIT:
            return None
        cache.set(rate_key, requests_in_window + 1, timeout=70)
        if getattr(settings, 'API_KEY_USAGE_LOGGING_ENABLED', True):
            PublicAPIKeyUsage.objects.create(api_key=key, endpoint=endpoint[:160], method=method[:10], status_code=200)
        key.last_used_at = timezone.now()
        key.save(update_fields=['last_used_at'])
        return key.owner
    return None


class PrivacyPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyPreference
        fields = ['analytics_enabled', 'marketing_enabled', 'functional_enabled', 'updated_at']
        read_only_fields = ['updated_at']


class PrivacyPreferenceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_preference(self, user):
        preference, _ = PrivacyPreference.objects.get_or_create(user=user)
        return preference

    def get(self, request):
        return Response(PrivacyPreferenceSerializer(self.get_preference(request.user)).data)

    def patch(self, request):
        preference = self.get_preference(request.user)
        serializer = PrivacyPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        preference = serializer.save()
        for purpose, enabled in (
            ('analytics', preference.analytics_enabled),
            ('marketing', preference.marketing_enabled),
            ('functional', preference.functional_enabled),
        ):
            PrivacyConsent.objects.create(
                user=request.user, purpose=purpose, granted=enabled,
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        record_audit_event(actor=request.user, action='privacy_preferences_updated', target_model='PrivacyPreference', target_id=preference.id, details={'changed_fields': sorted(request.data.keys())})
        return Response(serializer.data)


class PrivacyConsentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyConsent
        fields = ['id', 'purpose', 'granted', 'policy_version', 'ip_address', 'created_at']
        read_only_fields = ['id', 'ip_address', 'created_at']


class PrivacyConsentView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        consents = PrivacyConsent.objects.filter(user=request.user)
        return Response(PrivacyConsentSerializer(consents, many=True).data)

    def post(self, request):
        serializer = PrivacyConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent = serializer.save(user=request.user, ip_address=request.META.get('REMOTE_ADDR'))
        record_audit_event(actor=request.user, action='privacy_consent_recorded', target_model='PrivacyConsent', target_id=consent.id, details={'purpose': consent.purpose, 'granted': consent.granted})
        return Response(PrivacyConsentSerializer(consent).data, status=201)


class PrivacyRequestView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requests = PrivacyRequest.objects.filter(user=request.user)
        return Response([
            {'id': item.id, 'request_type': item.request_type, 'status': item.status, 'created_at': item.created_at, 'completed_at': item.completed_at}
            for item in requests
        ])


class PrivacyComplianceView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can review privacy requests.'}, status=status.HTTP_403_FORBIDDEN)
        requests = PrivacyRequest.objects.select_related('user').all()[:100]
        return Response([
            {
                'id': item.id,
                'username': item.user.username,
                'email': item.user.email,
                'request_type': item.request_type,
                'status': item.status,
                'created_at': item.created_at,
                'completed_at': item.completed_at,
            }
            for item in requests
        ])


class PrivacyExportView(PrivacyRequestView):
    def post(self, request):
        from articles.models import AIUsageEvent
        privacy_request = PrivacyRequest.objects.create(
            user=request.user, request_type='export', status='completed', completed_at=timezone.now(),
        )
        record_audit_event(actor=request.user, action='privacy_export_requested', target_model='PrivacyRequest', target_id=privacy_request.id, details={'request_type': privacy_request.request_type})
        articles = Article.objects.filter(author=request.user).values(
            'id', 'title', 'slug', 'summary', 'workflow_status', 'created_at', 'updated_at',
        )
        export_data = {
            'profile': {
                'username': request.user.username,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'role': request.user.role,
            },
            'articles': list(articles),
            'interests': list(ReaderInterest.objects.filter(user=request.user).values('interest_type', 'value', 'created_at')),
            'newsletter_subscriptions': list(NewsletterSubscription.objects.filter(user=request.user).values('email', 'frequency', 'categories', 'is_active')),
            'consents': PrivacyConsentSerializer(PrivacyConsent.objects.filter(user=request.user), many=True).data,
            'ai_usage': list(AIUsageEvent.objects.filter(user=request.user).values('provider', 'model', 'action', 'total_tokens', 'estimated_cost', 'redacted_pii', 'metadata', 'created_at')),
        }
        return Response({'request_id': privacy_request.id, 'status': privacy_request.status, 'data': export_data})


class WorkspaceDataExportView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        membership = WorkspaceMembership.objects.filter(workspace=workspace, user=request.user).first()
        if request.user.role != 'Admin' and not (
            workspace.owner_id == request.user.id or membership and membership.role in {'owner', 'admin'}
        ):
            return Response({'detail': 'Only workspace owners and admins can export workspace data.'}, status=403)
        from articles.models import AIUsageEvent, Article, MediaAsset
        data = {
            'workspace': {'id': workspace.id, 'name': workspace.name, 'slug': workspace.slug, 'plan': workspace.plan, 'created_at': workspace.created_at},
            'members': list(workspace.memberships.select_related('user').values('user__username', 'user__email', 'role', 'joined_at')),
            'articles': list(Article.objects.filter(workspace=workspace).values('id', 'title', 'slug', 'workflow_status', 'created_at', 'updated_at')),
            'media_assets': list(MediaAsset.objects.filter(workspace=workspace).values('id', 'title', 'media_type', 'alt_text', 'file_hash', 'created_at', 'updated_at')),
            'ai_usage': list(AIUsageEvent.objects.filter(workspace=workspace).values('provider', 'model', 'action', 'total_tokens', 'estimated_cost', 'redacted_pii', 'metadata', 'created_at')),
            'exported_at': timezone.now(),
        }
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_data_exported', target_model='Workspace', target_id=workspace.id, details={'member_count': len(data['members']), 'article_count': len(data['articles']), 'media_count': len(data['media_assets'])})
        return Response({'status': 'completed', 'data': data})


class PrivacyDeletionRequestView(PrivacyRequestView):
    def post(self, request):
        if request.data.get('confirmation') != 'DELETE':
            return Response({'detail': 'Type DELETE to request account deletion.'}, status=400)
        deletion_request = PrivacyRequest.objects.create(user=request.user, request_type='deletion')
        record_audit_event(actor=request.user, action='privacy_deletion_requested', target_model='PrivacyRequest', target_id=deletion_request.id, details={'request_type': deletion_request.request_type})
        return Response({'request_id': deletion_request.id, 'status': deletion_request.status, 'detail': 'Your account deletion request was recorded for review.'}, status=202)


class WorkspaceSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    member_count = serializers.IntegerField(source='memberships.count', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'description', 'owner', 'owner_username', 'member_count', 'plan', 'seat_limit', 'logo_url', 'primary_color', 'accent_color', 'custom_domain', 'email_from_name', 'data_region', 'retention_days', 'created_at', 'updated_at']
        read_only_fields = ['id', 'owner', 'owner_username', 'member_count', 'created_at', 'updated_at']


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = ['id', 'user', 'username', 'email', 'role', 'joined_at']
        read_only_fields = fields


def _workspace_for_member(request, slug):
    workspace = get_object_or_404(Workspace, slug=slug, is_active=True)
    if not WorkspaceMembership.objects.filter(workspace=workspace, user=request.user).exists():
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('You are not a member of this workspace.')
    return workspace


def _workspace_admin(request, slug):
    workspace = _workspace_for_member(request, slug)
    membership = WorkspaceMembership.objects.get(workspace=workspace, user=request.user)
    if membership.role not in {'owner', 'admin'}:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Workspace admin access is required.')
    return workspace


class WorkspaceListCreateView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspaces = Workspace.objects.filter(
            models.Q(owner=request.user) | models.Q(memberships__user=request.user),
            is_active=True,
        ).distinct()
        return Response(WorkspaceSerializer(workspaces, many=True).data)

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['name']
        slug = slugify(serializer.validated_data.get('slug') or name)
        if Workspace.objects.filter(slug=slug).exists():
            return Response({'detail': 'A workspace with this name already exists.'}, status=400)
        workspace = Workspace.objects.create(
            name=name,
            slug=slug,
            description=serializer.validated_data.get('description', ''),
            owner=request.user,
        )
        WorkspaceMembership.objects.create(workspace=workspace, user=request.user, role='owner')
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_created', target_model='Workspace', target_id=workspace.id, details={'plan': workspace.plan})
        return Response(WorkspaceSerializer(workspace).data, status=201)


class WorkspaceMembersView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        members = WorkspaceMembership.objects.filter(workspace=workspace).select_related('user')
        return Response(WorkspaceMembershipSerializer(members, many=True).data)


class WorkspaceBillingView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        member_count = workspace.memberships.count()
        return Response({
            'workspace': workspace.slug,
            'plan': workspace.plan,
            'seat_limit': workspace.seat_limit,
            'members': member_count,
            'seats_available': max(workspace.seat_limit - member_count, 0),
            'billing_status': 'active' if workspace.is_active else 'inactive',
        })

    def patch(self, request, slug):
        workspace = _workspace_admin(request, slug)
        plan = str(request.data.get('plan', workspace.plan)).strip().lower()
        seat_limit = request.data.get('seat_limit', workspace.seat_limit)
        if plan not in dict(Workspace.PLAN_CHOICES):
            return Response({'detail': 'Choose starter, team, or enterprise.'}, status=400)
        try:
            seat_limit = int(seat_limit)
        except (TypeError, ValueError):
            return Response({'detail': 'seat_limit must be a positive integer.'}, status=400)
        if seat_limit < workspace.memberships.count():
            return Response({'detail': 'Seat limit cannot be lower than current membership count.'}, status=400)
        for color_field in ('primary_color', 'accent_color'):
            color = str(request.data.get(color_field, getattr(workspace, color_field))).strip()
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                return Response({'detail': f'{color_field} must be a six-digit hex color.'}, status=400)
            setattr(workspace, color_field, color)
        for text_field in ('logo_url', 'custom_domain', 'email_from_name'):
            if text_field in request.data:
                setattr(workspace, text_field, str(request.data.get(text_field, '')).strip()[:255])
        workspace.plan = plan
        workspace.seat_limit = seat_limit
        workspace.save(update_fields=['plan', 'seat_limit', 'primary_color', 'accent_color', 'logo_url', 'custom_domain', 'email_from_name', 'updated_at'])
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_settings_updated', target_model='Workspace', target_id=workspace.id, details={'changed_fields': sorted(request.data.keys()), 'plan': workspace.plan, 'seat_limit': workspace.seat_limit})
        return self.get(request, slug)


class WorkspaceSettingsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug):
        workspace = _workspace_admin(request, slug)
        name = str(request.data.get('name', workspace.name)).strip()
        if not name:
            return Response({'detail': 'Workspace name is required.'}, status=400)
        if len(name) > 120:
            return Response({'detail': 'Workspace name must be 120 characters or fewer.'}, status=400)
        for color_field in ('primary_color', 'accent_color'):
            color = str(request.data.get(color_field, getattr(workspace, color_field))).strip()
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                return Response({'detail': f'{color_field} must be a six-digit hex color.'}, status=400)
            setattr(workspace, color_field, color)
        workspace.name = name
        workspace.description = str(request.data.get('description', workspace.description)).strip()[:500]
        workspace.logo_url = str(request.data.get('logo_url', workspace.logo_url)).strip()[:255]
        workspace.email_from_name = str(request.data.get('email_from_name', workspace.email_from_name)).strip()[:120]
        workspace.custom_domain = str(request.data.get('custom_domain', workspace.custom_domain)).strip()[:255]
        workspace.save(update_fields=['name', 'description', 'logo_url', 'primary_color', 'accent_color', 'email_from_name', 'custom_domain', 'updated_at'])
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_settings_updated', target_model='Workspace', target_id=workspace.id, details={'changed_fields': sorted(request.data.keys())})
        return Response(WorkspaceSerializer(workspace).data)


class WorkspaceBillingContractView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def payload(self, workspace, contract):
        members = workspace.memberships.count()
        return {
            'workspace': workspace.slug,
            'contract': {
                'id': contract.id,
                'contract_type': contract.contract_type,
                'status': contract.status,
                'seat_commitment': contract.seat_commitment,
                'monthly_commitment': contract.monthly_commitment,
                'currency': contract.currency,
                'tax_id': contract.tax_id,
                'purchase_order': contract.purchase_order,
                'invoice_email': contract.invoice_email,
                'payment_terms_days': contract.payment_terms_days,
                'starts_at': contract.starts_at,
                'ends_at': contract.ends_at,
                'renewal_at': contract.renewal_at,
            },
            'seat_usage': {'used': members, 'committed': contract.seat_commitment, 'overage': max(members - contract.seat_commitment, 0)},
        }

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        contract, _ = WorkspaceBillingContract.objects.get_or_create(workspace=workspace, defaults={'seat_commitment': workspace.seat_limit})
        return Response(self.payload(workspace, contract))

    def patch(self, request, slug):
        workspace = _workspace_admin(request, slug)
        contract, _ = WorkspaceBillingContract.objects.get_or_create(workspace=workspace, defaults={'seat_commitment': workspace.seat_limit})
        for field in ('contract_type', 'status', 'currency', 'tax_id', 'purchase_order', 'invoice_email'):
            if field in request.data:
                value = str(request.data.get(field, '')).strip()
                choices = dict(WorkspaceBillingContract.CONTRACT_TYPES if field == 'contract_type' else WorkspaceBillingContract.STATUS_CHOICES) if field in {'contract_type', 'status'} else None
                if choices is not None and value not in choices:
                    return Response({'detail': f'Invalid {field}.'}, status=400)
                setattr(contract, field, value.upper() if field == 'currency' else value)
        for field in ('seat_commitment', 'payment_terms_days'):
            if field in request.data:
                try:
                    value = int(request.data[field])
                except (TypeError, ValueError):
                    return Response({'detail': f'{field} must be a non-negative integer.'}, status=400)
                if value < 0 or (field == 'seat_commitment' and value < workspace.memberships.count()):
                    return Response({'detail': f'{field} is below the current requirement.'}, status=400)
                setattr(contract, field, value)
        if 'monthly_commitment' in request.data:
            try:
                amount = Decimal(str(request.data['monthly_commitment']))
            except Exception:
                return Response({'detail': 'monthly_commitment must be a non-negative amount.'}, status=400)
            if amount < 0:
                return Response({'detail': 'monthly_commitment must be a non-negative amount.'}, status=400)
            contract.monthly_commitment = amount
        for field in ('starts_at', 'ends_at', 'renewal_at'):
            if field in request.data:
                parsed = parse_date(str(request.data.get(field) or ''))
                if request.data.get(field) and not parsed:
                    return Response({'detail': f'{field} must use YYYY-MM-DD.'}, status=400)
                setattr(contract, field, parsed)
        contract.save()
        from articles.audit import record_audit_event
        record_audit_event(actor=request.user, workspace=workspace, action='billing_contract_updated', target_model='WorkspaceBillingContract', target_id=contract.id, details={'status': contract.status, 'contract_type': contract.contract_type})
        return Response(self.payload(workspace, contract))


def _integration_payload(integration):
    return {
        'id': integration.id, 'provider': integration.provider, 'name': integration.name,
        'endpoint_url': integration.endpoint_url, 'config': integration.config,
        'status': integration.status, 'is_active': integration.is_active,
        'last_checked_at': integration.last_checked_at, 'last_error': integration.last_error,
        'secret_configured': bool(integration.encrypted_secret or integration.secret), 'created_at': integration.created_at,
    }


class WorkspaceIntegrationView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        return Response([_integration_payload(item) for item in workspace.integrations.all()])

    def post(self, request, slug):
        workspace = _workspace_admin(request, slug)
        provider = str(request.data.get('provider', '')).strip().lower()
        name = str(request.data.get('name', '')).strip()
        if provider not in dict(WorkspaceIntegration.PROVIDER_CHOICES) or not name:
            return Response({'detail': 'provider and name are required.'}, status=400)
        if WorkspaceIntegration.objects.filter(workspace=workspace, name=name).exists():
            return Response({'detail': 'An integration with this name already exists.'}, status=409)
        integration = WorkspaceIntegration.objects.create(
            workspace=workspace, provider=provider, name=name,
            endpoint_url=str(request.data.get('endpoint_url', '')).strip(),
            encrypted_secret=encrypt_integration_secret(request.data.get('secret', '')),
            config=request.data.get('config') if isinstance(request.data.get('config'), dict) else {},
            created_by=request.user,
        )
        record_audit_event(actor=request.user, workspace=workspace, action='integration_created', target_model='WorkspaceIntegration', target_id=integration.id, details={'provider': integration.provider, 'name': integration.name})
        return Response(_integration_payload(integration), status=201)


class WorkspaceIntegrationDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_integration(self, request, slug, pk):
        workspace = _workspace_admin(request, slug)
        return workspace, get_object_or_404(WorkspaceIntegration, workspace=workspace, pk=pk)

    def patch(self, request, slug, pk):
        workspace, integration = self.get_integration(request, slug, pk)
        for field in ('name', 'endpoint_url'):
            if field in request.data:
                setattr(integration, field, str(request.data.get(field, '')).strip())
        if 'secret' in request.data:
            integration.encrypted_secret = encrypt_integration_secret(request.data.get('secret', ''))
            integration.secret = ''
        if 'config' in request.data and isinstance(request.data['config'], dict):
            integration.config = request.data['config']
        if 'is_active' in request.data:
            integration.is_active = bool(request.data['is_active'])
            if not integration.is_active:
                integration.status = 'disabled'
        integration.save()
        record_audit_event(actor=request.user, workspace=workspace, action='integration_updated', target_model='WorkspaceIntegration', target_id=integration.id, details={'changed_fields': sorted(request.data.keys()), 'is_active': integration.is_active, 'status': integration.status})
        return Response(_integration_payload(integration))

    def post(self, request, slug, pk):
        workspace, integration = self.get_integration(request, slug, pk)
        if not integration.endpoint_url:
            return Response({'detail': 'Configure an endpoint URL before testing.'}, status=400)
        try:
            try:
                integration_secret = decrypt_integration_secret(integration.encrypted_secret)
            except IntegrationSecretError as exc:
                integration.status = 'degraded'
                integration.last_error = str(exc)
                integration.last_checked_at = timezone.now()
                integration.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
                return Response({'integration': _integration_payload(integration), 'test': {'ok': False, 'error': integration.last_error}}, status=503)
            if not integration_secret and integration.secret:
                integration_secret = integration.secret
            response = requests.post(
                integration.endpoint_url,
                json={'text': request.data.get('message', f'Article Studio {integration.provider} integration test')},
                headers={'Authorization': f'Bearer {integration_secret}'} if integration_secret else {},
                timeout=getattr(settings, 'SSO_HTTP_TIMEOUT', 10),
            )
            response.raise_for_status()
            integration.status = 'healthy'
            integration.last_error = ''
            result = {'ok': True, 'status_code': response.status_code}
        except Exception as exc:
            integration.status = 'degraded'
            integration.last_error = str(exc)[:500]
            result = {'ok': False, 'error': integration.last_error}
        integration.last_checked_at = timezone.now()
        integration.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
        record_audit_event(actor=request.user, workspace=workspace, action='integration_tested', target_model='WorkspaceIntegration', target_id=integration.id, details={'provider': integration.provider, 'ok': result['ok'], 'status_code': result.get('status_code')})
        return Response({'integration': _integration_payload(integration), 'test': result}, status=200 if result['ok'] else 503)


def _support_payload(ticket):
    return {
        'id': ticket.id, 'workspace': ticket.workspace.slug, 'requester': ticket.requester.username,
        'assigned_to': ticket.assigned_to.username if ticket.assigned_to else None,
        'subject': ticket.subject, 'description': ticket.description, 'priority': ticket.priority,
        'status': ticket.status, 'sla_due_at': ticket.sla_due_at, 'first_response_at': ticket.first_response_at,
        'resolved_at': ticket.resolved_at, 'created_at': ticket.created_at, 'updated_at': ticket.updated_at,
        'messages': [{'id': item.id, 'author': item.author.username if item.author else 'System', 'body': item.body, 'is_internal': item.is_internal, 'created_at': item.created_at} for item in ticket.messages.select_related('author').all()],
    }


def _support_workspace(request):
    slug = request.headers.get('X-Workspace-Slug') or request.data.get('workspace_slug') or request.query_params.get('workspace')
    if not slug:
        return None
    return _workspace_for_member(request, slug)


class SupportTicketView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspace = _support_workspace(request)
        if workspace is None:
            return Response({'detail': 'Select a workspace with X-Workspace-Slug.'}, status=400)
        tickets = SupportTicket.objects.filter(workspace=workspace)
        membership = WorkspaceMembership.objects.filter(workspace=workspace, user=request.user).first()
        if request.user.role not in {'Admin'} and (not membership or membership.role not in {'owner', 'admin'}):
            tickets = tickets.filter(requester=request.user)
        status_filter = request.query_params.get('status')
        if status_filter:
            tickets = tickets.filter(status=status_filter)
        return Response([_support_payload(ticket) for ticket in tickets.select_related('requester', 'assigned_to')[:100]])

    def post(self, request):
        workspace = _support_workspace(request)
        if workspace is None:
            return Response({'detail': 'Select a workspace with X-Workspace-Slug.'}, status=400)
        subject = str(request.data.get('subject', '')).strip()
        description = str(request.data.get('description', '')).strip()
        priority = str(request.data.get('priority', 'normal')).strip().lower()
        if not subject or not description:
            return Response({'detail': 'subject and description are required.'}, status=400)
        if priority not in dict(SupportTicket.PRIORITY_CHOICES):
            return Response({'detail': 'Invalid priority.'}, status=400)
        sla_hours = {'low': 72, 'normal': 24, 'high': 8, 'urgent': 4}[priority]
        ticket = SupportTicket.objects.create(
            workspace=workspace, requester=request.user, subject=subject, description=description,
            priority=priority, sla_due_at=timezone.now() + timedelta(hours=sla_hours),
        )
        SupportTicketMessage.objects.create(ticket=ticket, author=request.user, body=description)
        record_audit_event(actor=request.user, workspace=workspace, action='support_ticket_created', target_model='SupportTicket', target_id=ticket.id, details={'priority': ticket.priority, 'sla_due_at': ticket.sla_due_at.isoformat()})
        return Response(_support_payload(ticket), status=201)


class SupportTicketDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_ticket(self, request, pk):
        workspace = _support_workspace(request)
        if workspace is None:
            return None, Response({'detail': 'Select a workspace with X-Workspace-Slug.'}, status=400)
        ticket = get_object_or_404(SupportTicket.objects.select_related('workspace', 'requester', 'assigned_to'), workspace=workspace, pk=pk)
        membership = WorkspaceMembership.objects.filter(workspace=workspace, user=request.user).first()
        is_admin = request.user.role == 'Admin' or membership and membership.role in {'owner', 'admin'}
        if not is_admin and ticket.requester_id != request.user.id:
            return None, Response({'detail': 'You cannot access this support ticket.'}, status=403)
        return ticket, None

    def get(self, request, pk):
        ticket, error = self.get_ticket(request, pk)
        if error:
            return error
        return Response(_support_payload(ticket))

    def patch(self, request, pk):
        ticket, error = self.get_ticket(request, pk)
        if error:
            return error
        membership = WorkspaceMembership.objects.filter(workspace=ticket.workspace, user=request.user).first()
        is_admin = request.user.role == 'Admin' or membership and membership.role in {'owner', 'admin'}
        if not is_admin:
            return Response({'detail': 'Only workspace admins can update support tickets.'}, status=403)
        if 'status' in request.data:
            status_value = str(request.data['status']).strip().lower()
            if status_value not in dict(SupportTicket.STATUS_CHOICES):
                return Response({'detail': 'Invalid status.'}, status=400)
            ticket.status = status_value
            if status_value in {'resolved', 'closed'}:
                ticket.resolved_at = timezone.now()
        if 'priority' in request.data:
            priority = str(request.data['priority']).strip().lower()
            if priority not in dict(SupportTicket.PRIORITY_CHOICES):
                return Response({'detail': 'Invalid priority.'}, status=400)
            ticket.priority = priority
        if 'assigned_to' in request.data:
            assignee = get_object_or_404(CustomUser, pk=request.data['assigned_to'])
            if not WorkspaceMembership.objects.filter(workspace=ticket.workspace, user=assignee).exists():
                return Response({'detail': 'Assignee must belong to this workspace.'}, status=400)
            ticket.assigned_to = assignee
        message = str(request.data.get('message', '')).strip()
        if message:
            SupportTicketMessage.objects.create(ticket=ticket, author=request.user, body=message, is_internal=bool(request.data.get('is_internal', False)))
            if ticket.first_response_at is None:
                ticket.first_response_at = timezone.now()
        ticket.save()
        record_audit_event(actor=request.user, workspace=ticket.workspace, action='support_ticket_updated', target_model='SupportTicket', target_id=ticket.id, details={'changed_fields': sorted(request.data.keys()), 'status': ticket.status, 'priority': ticket.priority, 'assigned_to': ticket.assigned_to_id})
        return Response(_support_payload(ticket))

class WorkspaceControlsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        membership = WorkspaceMembership.objects.get(workspace=workspace, user=request.user)
        article_queryset = Article.objects.filter(workspace=workspace)
        article_limit = {'starter': 100, 'team': 1000, 'enterprise': None}[workspace.plan]
        checklist = [
            {
                'key': 'workspace_profile',
                'label': 'Add a workspace description',
                'complete': bool(workspace.description.strip()),
                'href': '#workspace-details',
            },
            {
                'key': 'invite_team',
                'label': 'Invite a teammate',
                'complete': workspace.memberships.count() > 1,
                'href': '#workspace-invite-form',
            },
            {
                'key': 'create_story',
                'label': 'Create your first story',
                'complete': article_queryset.exists(),
                'href': '/editor/dashboard/?section=create-article-page',
            },
            {
                'key': 'configure_brand',
                'label': 'Personalize workspace branding',
                'complete': bool(workspace.logo_url or workspace.primary_color != '#2f5d62' or workspace.accent_color != '#f28f6b'),
                'href': '#workspace-details',
            },
            {
                'key': 'connect_integration',
                'label': 'Connect a delivery integration',
                'complete': workspace.integrations.filter(is_active=True).exists(),
                'href': '/workspace/integrations/',
            },
        ]
        checklist_complete = sum(item['complete'] for item in checklist)
        return Response({
            'workspace': WorkspaceSerializer(workspace).data,
            'membership': WorkspaceMembershipSerializer(membership).data,
            'roles': [choice[0] for choice in WorkspaceMembership.ROLE_CHOICES],
            'quotas': {
                'seats': {'used': workspace.memberships.count(), 'limit': workspace.seat_limit},
                'articles': {'used': article_queryset.count(), 'limit': article_limit},
            },
            'analytics_scope': {'workspace_id': workspace.id, 'workspace_slug': workspace.slug},
            'onboarding': {
                'completed': checklist_complete,
                'total': len(checklist),
                'percent': round(checklist_complete / len(checklist) * 100),
                'items': checklist,
            },
        })

    def patch(self, request, slug):
        workspace = _workspace_admin(request, slug)
        region = str(request.data.get('data_region', workspace.data_region)).strip().lower()
        if region not in dict(Workspace.DATA_REGION_CHOICES):
            return Response({'detail': 'Choose a supported data region.'}, status=400)
        try:
            retention_days = int(request.data.get('retention_days', workspace.retention_days))
        except (TypeError, ValueError):
            return Response({'detail': 'retention_days must be an integer.'}, status=400)
        if retention_days < 30 or retention_days > 3650:
            return Response({'detail': 'retention_days must be between 30 and 3650.'}, status=400)
        workspace.data_region = region
        workspace.retention_days = retention_days
        workspace.save(update_fields=['data_region', 'retention_days', 'updated_at'])
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_data_policy_updated', target_model='Workspace', target_id=workspace.id, details={'data_region': workspace.data_region, 'retention_days': workspace.retention_days})
        return Response({'workspace': WorkspaceSerializer(workspace).data, 'updated': True})


class WorkspaceSelectView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        request.session['active_workspace_slug'] = workspace.slug
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_selected', target_model='Workspace', target_id=workspace.id)
        return Response({'workspace': WorkspaceSerializer(workspace).data, 'active': True})

    def delete(self, request):
        request.session.pop('active_workspace_slug', None)
        return Response({'active': False})


class WorkspaceInviteView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        workspace = _workspace_admin(request, slug)
        if workspace.memberships.count() >= workspace.seat_limit:
            return Response({'detail': 'This workspace has reached its seat limit.'}, status=409)
        email = str(request.data.get('email', '')).strip().lower()
        role = str(request.data.get('role', 'writer')).strip().lower()
        allowed_roles = {choice[0] for choice in WorkspaceMembership.ROLE_CHOICES if choice[0] != 'owner'}
        if not email or '@' not in email:
            return Response({'detail': 'Enter a valid email address.'}, status=400)
        if role not in allowed_roles:
            return Response({'detail': 'Choose a valid workspace role.'}, status=400)
        invitation = WorkspaceInvitation.objects.create(
            workspace=workspace,
            email=email,
            role=role,
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )
        accept_url = request.build_absolute_uri(f'/workspace/invitations/{invitation.token}/')
        send_mail(
            subject=f'You are invited to join {workspace.name}',
            message=(
                f'{request.user.get_full_name() or request.user.username} invited you to join '
                f'{workspace.name} as a {invitation.role}.\n\nAccept the invitation: {accept_url}\n\n'
                'This invitation expires in 7 days.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=True,
        )
        record_audit_event(actor=request.user, workspace=workspace, action='workspace_invitation_created', target_model='WorkspaceInvitation', target_id=invitation.id, details={'email': invitation.email, 'role': invitation.role})
        return Response({
            'id': invitation.id,
            'workspace': workspace.slug,
            'email': invitation.email,
            'role': invitation.role,
            'token': str(invitation.token),
            'accept_url': accept_url,
            'expires_at': invitation.expires_at,
            'status': invitation.status,
        }, status=201)


class WorkspaceInvitationAcceptView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        invitation = get_object_or_404(WorkspaceInvitation.objects.select_related('workspace'), token=token)
        if invitation.status != 'pending' or invitation.is_expired:
            return Response({'detail': 'This invitation is no longer active.'}, status=400)
        if invitation.email.lower() != request.user.email.lower():
            return Response({'detail': 'Sign in with the invited email address to accept this invitation.'}, status=403)
        membership, _ = WorkspaceMembership.objects.get_or_create(
            workspace=invitation.workspace,
            user=request.user,
            defaults={'role': invitation.role},
        )
        invitation.status = 'accepted'
        invitation.save(update_fields=['status'])
        return Response({
            'workspace': WorkspaceSerializer(invitation.workspace).data,
            'membership': WorkspaceMembershipSerializer(membership).data,
        })
