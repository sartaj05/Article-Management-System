from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import CustomUser, NewsletterSubscription, NotificationPreference, Profile, PushSubscription
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
