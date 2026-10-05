import hashlib
import hmac
import json
import secrets

from rest_framework import serializers, status
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
from decimal import Decimal

from .models import (
    AccessibilityPreference, AlertRule, AuthorTip, CustomUser, has_active_membership, MembershipPlan,
    MembershipSubscription, MembershipWebhookEvent, NewsletterEdition, NewsletterSubscription, NotificationPreference, Profile,
    PrivacyConsent, PrivacyPreference, PrivacyRequest, PublicAPIKey, PushSubscription, ReaderInterest, WebhookDelivery, WebhookEndpoint, Workspace, WorkspaceInvitation,
    WorkspaceMembership,
)
from articles.models import Article
from .support_bot import get_support_response


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


class ReaderInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReaderInterest
        fields = ['id', 'interest_type', 'value', 'created_at']
        read_only_fields = ['id', 'created_at']


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
        fields = ['high_contrast', 'reduce_motion', 'large_text', 'updated_at']
        read_only_fields = ['updated_at']


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
        return Response({'active': has_active_membership(request.user), 'subscriptions': MembershipSubscriptionSerializer(subscriptions, many=True).data})


class MembershipCheckoutView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = get_object_or_404(MembershipPlan, pk=request.data.get('plan_id'), is_active=True)
        subscription, _ = MembershipSubscription.objects.update_or_create(
            user=request.user, plan=plan, status__in=['pending', 'canceled'],
            defaults={'status': 'active' if plan.price == 0 else 'pending', 'provider': 'manual', 'started_at': timezone.now() if plan.price == 0 else None},
        )
        if plan.price > 0:
            return Response({'detail': 'Payment provider is not configured yet.', 'checkout_required': True, 'plan': MembershipPlanSerializer(plan).data}, status=402)
        return Response(MembershipSubscriptionSerializer(subscription).data, status=201)


class MembershipCancelView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = MembershipSubscription.objects.filter(user=request.user, status='active').order_by('-created_at').first()
        if not subscription:
            return Response({'detail': 'No active membership found.'}, status=404)
        subscription.status = 'canceled'
        subscription.auto_renew = False
        subscription.save(update_fields=['status', 'auto_renew', 'updated_at'])
        return Response(MembershipSubscriptionSerializer(subscription).data)


class MembershipWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        secret = settings.PAYMENT_WEBHOOK_SECRET
        if not secret:
            return Response({'detail': 'Payment webhook is not configured.'}, status=503)
        signature = request.headers.get('X-Payment-Signature', '')
        expected = 'sha256=' + hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return Response({'detail': 'Invalid payment webhook signature.'}, status=403)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({'detail': 'Webhook payload must be valid JSON.'}, status=400)
        event_id = str(payload.get('id', '')).strip()
        event_type = str(payload.get('type', '')).strip()
        data = payload.get('data') or {}
        if not event_id or not event_type:
            return Response({'detail': 'Webhook id and type are required.'}, status=400)
        event, created = MembershipWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={'event_type': event_type, 'payload': payload},
        )
        if not created:
            return Response({'processed': True, 'duplicate': True})
        if event_type not in {'subscription.active', 'subscription.canceled', 'subscription.past_due'}:
            return Response({'processed': True, 'ignored': True})
        user = get_object_or_404(CustomUser, pk=data.get('user_id'))
        plan = get_object_or_404(MembershipPlan, pk=data.get('plan_id'), is_active=True)
        status_map = {
            'subscription.active': 'active',
            'subscription.canceled': 'canceled',
            'subscription.past_due': 'past_due',
        }
        subscription, _ = MembershipSubscription.objects.update_or_create(
            user=user,
            plan=plan,
            provider_reference=str(data.get('provider_reference', '')),
            defaults={
                'provider': str(data.get('provider', 'payment'))[:30],
                'status': status_map[event_type],
                'auto_renew': event_type == 'subscription.active',
            },
        )
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
        fields = ['id', 'sender', 'sender_name', 'author', 'author_name', 'amount', 'currency', 'message', 'status', 'provider', 'provider_reference', 'created_at', 'updated_at']
        read_only_fields = ['id', 'sender', 'author', 'sender_name', 'author_name', 'status', 'provider', 'provider_reference', 'created_at', 'updated_at']


class AuthorTipIntentView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, author_id):
        author = get_object_or_404(CustomUser, pk=author_id, is_active=True)
        if author.id == request.user.id:
            return Response({'detail': 'You cannot send a tip to yourself.'}, status=400)
        serializer = AuthorTipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tip = serializer.save(sender=request.user, author=author, status='pending', provider='manual')
        return Response({
            'tip': AuthorTipSerializer(tip).data,
            'payment_required': True,
            'detail': 'Tip intent created. Connect a payment provider to complete the donation.',
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
    class Meta:
        model = PublicAPIKey
        fields = ['id', 'name', 'prefix', 'is_active', 'created_at', 'last_used_at']
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
            prefix=raw_key[:10],
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        )
        return Response({'key': raw_key, 'details': PublicAPIKeySerializer(key).data}, status=201)


class PublicAPIKeyDetailView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        key = get_object_or_404(PublicAPIKey, pk=pk, owner=request.user)
        key.is_active = False
        key.save(update_fields=['is_active'])
        return Response({'revoked': True})


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
        return Response(WebhookEndpointSerializer(endpoint).data, status=201)


class WebhookDeliveryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        deliveries = WebhookDelivery.objects.filter(endpoint__owner=request.user).select_related('endpoint')[:100]
        return Response([{
            'id': delivery.id,
            'event_id': delivery.event_id,
            'endpoint_id': delivery.endpoint_id,
            'event_type': delivery.event_type,
            'status': delivery.status,
            'response_code': delivery.response_code,
            'attempts': delivery.attempts,
            'last_error': delivery.last_error,
            'delivered_at': delivery.delivered_at,
            'created_at': delivery.created_at,
        } for delivery in deliveries])


class DeveloperAPIDocumentationView(APIView):
    permission_classes = []

    def get(self, request):
        return Response({
            'name': 'Article Studio Headless API',
            'authentication': 'Send a generated key in the X-API-Key header.',
            'endpoints': {
                'articles': '/api/v2/public/articles/',
                'rss': '/rss.xml',
                'sitemap': '/sitemap.xml',
                'webhooks': '/api/developer/webhooks/',
            },
            'events': ['article.published', 'article.updated', 'article.deleted'],
        })


def resolve_public_api_key(raw_key):
    if not raw_key:
        return None
    key = PublicAPIKey.objects.filter(
        prefix=raw_key[:10], is_active=True,
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
    ).select_related('owner').first()
    if key:
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


class PrivacyExportView(PrivacyRequestView):
    def post(self, request):
        privacy_request = PrivacyRequest.objects.create(
            user=request.user, request_type='export', status='completed', completed_at=timezone.now(),
        )
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
        }
        return Response({'request_id': privacy_request.id, 'status': privacy_request.status, 'data': export_data})


class PrivacyDeletionRequestView(PrivacyRequestView):
    def post(self, request):
        if request.data.get('confirmation') != 'DELETE':
            return Response({'detail': 'Type DELETE to request account deletion.'}, status=400)
        deletion_request = PrivacyRequest.objects.create(user=request.user, request_type='deletion')
        return Response({'request_id': deletion_request.id, 'status': deletion_request.status, 'detail': 'Your account deletion request was recorded for review.'}, status=202)


class WorkspaceSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    member_count = serializers.IntegerField(source='memberships.count', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'description', 'owner', 'owner_username', 'member_count', 'created_at', 'updated_at']
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
        return Response(WorkspaceSerializer(workspace).data, status=201)


class WorkspaceMembersView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        members = WorkspaceMembership.objects.filter(workspace=workspace).select_related('user')
        return Response(WorkspaceMembershipSerializer(members, many=True).data)


class WorkspaceInviteView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        workspace = _workspace_admin(request, slug)
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
        return Response({
            'id': invitation.id,
            'workspace': workspace.slug,
            'email': invitation.email,
            'role': invitation.role,
            'token': str(invitation.token),
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
