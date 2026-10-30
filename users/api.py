import hashlib
import re
import hmac
import json
import secrets
import base64
import hashlib

from rest_framework import serializers, status
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
from decimal import Decimal

from .models import (
    AccessibilityPreference, AlertRule, AuthorTip, CustomUser, FeatureFlag, has_active_membership, MembershipPlan,
    MembershipSubscription, MembershipWebhookEvent, MembershipInvoice, PaymentTransaction, NewsletterCampaignAttribution, NewsletterEdition, NewsletterSubscription, NotificationPreference, Profile,
    PrivacyConsent, PrivacyPreference, PrivacyRequest, PublicAPIKey, PushSubscription, ReaderDigestDelivery, ReaderInterest, RoleCapabilityOverride, SavedSearch, SSOProvider, PasskeyCredential, TrustedDevice, TwoFactorAuth, WebhookDelivery, WebhookEndpoint, Workspace, WorkspaceInvitation, PersonalizationPreference,
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
            return Response({'enabled': True, 'backup_codes': codes})
        return Response({'enabled': True})

    def put(self, request):
        factor = get_object_or_404(TwoFactorAuth, user=request.user, is_enabled=True)
        from .two_factor import verify_totp
        if not verify_totp(factor.secret, request.data.get('code', '')):
            return Response({'detail': 'Invalid authenticator code.'}, status=400)
        factor.is_enabled = False
        factor.save(update_fields=['is_enabled', 'updated_at'])
        return Response({'enabled': False})


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
        return Response({'id': device.id, 'token': raw_token, 'expires_at': device.expires_at}, status=201)

    def delete(self, request, pk=None):
        device = get_object_or_404(TrustedDevice, pk=pk, user=request.user)
        device.revoked_at = timezone.now()
        device.save(update_fields=['revoked_at'])
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
            'detail': 'Complete the provider authorization redirect and callback exchange on the configured SSO adapter.',
        })


class SSOProviderCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, provider):
        state = str(request.query_params.get('state', '')).strip()
        state_data = request.session.pop(f'sso_state_{state}', None)
        if not state_data or state_data.get('provider') != provider:
            return Response({'detail': 'Invalid or expired SSO state.'}, status=400)
        if not request.query_params.get('code'):
            return Response({'detail': 'The identity provider did not return an authorization code.'}, status=400)
        return Response({
            'provider': provider,
            'ready': False,
            'detail': 'Authorization code received. Configure the provider token/userinfo adapter before enabling account login.',
        }, status=501)


class SSOProviderView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage SSO providers.'}, status=403)
        providers = SSOProvider.objects.all()
        return Response([{'provider': item.provider, 'client_id': item.client_id, 'discovery_url': item.discovery_url, 'is_enabled': item.is_enabled} for item in providers])

    def patch(self, request):
        if request.user.role != 'Admin':
            return Response({'detail': 'Only admins can manage SSO providers.'}, status=403)
        provider = str(request.data.get('provider', '')).strip().lower()
        if provider not in {'oidc', 'google', 'microsoft'}:
            return Response({'detail': 'Choose oidc, google, or microsoft.'}, status=400)
        item, _ = SSOProvider.objects.update_or_create(provider=provider, defaults={
            'client_id': str(request.data.get('client_id', '')).strip(),
            'discovery_url': str(request.data.get('discovery_url', '')).strip(),
            'is_enabled': bool(request.data.get('is_enabled', False)),
        })
        return Response({'provider': item.provider, 'client_id': item.client_id, 'discovery_url': item.discovery_url, 'is_enabled': item.is_enabled})


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
        provider = str(request.headers.get('X-Payment-Provider') or payload.get('provider') or 'payment').strip().lower()[:30]
        event_id = str(payload.get('id', '')).strip()
        event_type = str(payload.get('type', '')).strip()
        data = payload.get('data') or {}
        if isinstance(data, dict) and isinstance(data.get('object'), dict):
            data = {**data['object'], **{f'metadata_{key}': value for key, value in (data['object'].get('metadata') or {}).items()}}
        metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
        user_id = data.get('user_id') or metadata.get('user_id') or data.get('metadata_user_id')
        plan_id = data.get('plan_id') or metadata.get('plan_id') or data.get('metadata_plan_id')
        transaction_id = data.get('transaction_id') or metadata.get('transaction_id') or data.get('metadata_transaction_id')
        checkout_token = data.get('checkout_token') or metadata.get('checkout_token') or data.get('metadata_checkout_token')
        provider_reference = str(data.get('provider_reference') or data.get('subscription_id') or data.get('subscription') or data.get('id') or '')[:160]
        if not event_id or not event_type:
            return Response({'detail': 'Webhook id and type are required.'}, status=400)
        event, created = MembershipWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={'provider': provider, 'event_type': event_type, 'payload': payload},
        )
        if not created:
            return Response({'processed': True, 'duplicate': True})
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
        }
        if event_type not in status_map:
            return Response({'processed': True, 'ignored': True})
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
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=['articles:read']),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = PublicAPIKey
        fields = ['id', 'name', 'prefix', 'scopes', 'is_active', 'created_at', 'last_used_at']
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
            scopes=serializer.validated_data.get('scopes', []),
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
        return Response({'status': retry_webhook_delivery(delivery).status, 'attempts': delivery.attempts})


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
            'events': ['article.published', 'article.updated', 'article.deleted'],
        })


def resolve_public_api_key(raw_key, required_scope=None):
    if not raw_key:
        return None
    key = PublicAPIKey.objects.filter(
        prefix=raw_key[:10], is_active=True,
        key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
    ).select_related('owner').first()
    if key:
        if required_scope and key.scopes and required_scope not in key.scopes:
            return None
        rate_key = f'public-api-key:{key.id}:{timezone.now().strftime("%Y%m%d%H%M")}'
        requests_in_window = cache.get(rate_key, 0)
        if requests_in_window >= 120:
            return None
        cache.set(rate_key, requests_in_window + 1, timeout=70)
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
        fields = ['id', 'name', 'slug', 'description', 'owner', 'owner_username', 'member_count', 'plan', 'seat_limit', 'logo_url', 'primary_color', 'accent_color', 'custom_domain', 'email_from_name', 'created_at', 'updated_at']
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
        return self.get(request, slug)


class WorkspaceControlsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        membership = WorkspaceMembership.objects.get(workspace=workspace, user=request.user)
        article_queryset = Article.objects.filter(workspace=workspace)
        article_limit = {'starter': 100, 'team': 1000, 'enterprise': None}[workspace.plan]
        return Response({
            'workspace': WorkspaceSerializer(workspace).data,
            'membership': WorkspaceMembershipSerializer(membership).data,
            'roles': [choice[0] for choice in WorkspaceMembership.ROLE_CHOICES],
            'quotas': {
                'seats': {'used': workspace.memberships.count(), 'limit': workspace.seat_limit},
                'articles': {'used': article_queryset.count(), 'limit': article_limit},
            },
            'analytics_scope': {'workspace_id': workspace.id, 'workspace_slug': workspace.slug},
        })


class WorkspaceSelectView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        workspace = _workspace_for_member(request, slug)
        request.session['active_workspace_slug'] = workspace.slug
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
