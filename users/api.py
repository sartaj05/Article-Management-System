import hashlib
import secrets

from rest_framework import serializers, status
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
from decimal import Decimal

from .models import (
    AccessibilityPreference, AuthorTip, CustomUser, has_active_membership, MembershipPlan,
    MembershipSubscription, NewsletterSubscription, NotificationPreference, Profile,
    PublicAPIKey, PushSubscription, ReaderInterest, WebhookEndpoint, Workspace, WorkspaceInvitation,
    WorkspaceMembership,
)
from articles.models import Article


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
