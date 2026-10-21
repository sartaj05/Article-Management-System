import hashlib
import hmac

from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from users.serializers import (
    RegistrationSerializer, 
    LoginSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    PasswordResetSerializer,
    PasswordResetWithOTPSerializer,
    RequestOTPSerializer,
    UserSerializer,
    OTPVerificationSerializer
)
from django.utils.crypto import get_random_string
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from datetime import datetime
from django.core.mail import send_mail
from users.models import CustomUser as User, NewsletterCampaignAttribution, NewsletterEdition, SecurityEvent, SecuritySession, TwoFactorAuth, TrustedDevice
from rest_framework.exceptions import ValidationError
from articles.permissions import IsAdmin
from users.decorators import role_required

# Utility function for generating tokens
def get_tokens_for_user(user, request=None):
    refresh = RefreshToken.for_user(user)
    if request is not None:
        now = timezone.now()
        SecuritySession.objects.create(
            user=user,
            refresh_jti=str(refresh['jti']),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            created_at=now,
            last_seen_at=now,
            expires_at=now + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
        )
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
class UserRegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return Response({'status': 'Error', 'message': e.detail}, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.save()

        # Send email based on the role
        self.send_registration_email(user)

        return Response({
            'status': 'Success',
            'message': 'Registration successful.',
            'user': serializer.data,
        }, status=status.HTTP_201_CREATED)
    
    def send_registration_email(self, user):
        subject = "Registration Successful"
        message = f"Dear {user.first_name},\n\nYour registration was successful!"

        # Customize the message based on the role
        if user.role == 'Journalist':
            subject = "Welcome, Journalist!"
            message += "\n\nYou have successfully registered as a Journalist."
        elif user.role == 'Editor':
            subject = "Welcome, Editor!"
            message += "\n\nYou have successfully registered as an Editor."
        elif user.role == 'Admin':
            subject = "Welcome, Admin!"
            message += "\n\nYou have successfully registered as an Admin."

        # Send the email
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,  # You can configure this in settings.py
            [user.email],
            fail_silently=False,
        )
def register_template(request):
    return render(request, 'users/register.html')

# User Login View
class UserLoginView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return render(request, 'users/login.html')

    def post(self, request, *args, **kwargs):
        username = str(request.data.get('username', '')).strip()
        ip_address = request.META.get('REMOTE_ADDR')
        recent_failures = SecurityEvent.objects.filter(
            event_type='login_failed', username=username, ip_address=ip_address,
            created_at__gte=timezone.now() - timedelta(minutes=15),
        ).count()
        if recent_failures >= 5:
            return Response(
                {'detail': 'Too many failed login attempts. Try again in 15 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = LoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            SecurityEvent.objects.create(
                username=username, event_type='login_failed', success=False,
                ip_address=ip_address, user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            raise
        user = serializer.validated_data['user']
        two_factor = TwoFactorAuth.objects.filter(user=user).first()
        trusted_token = str(request.data.get('trusted_device') or request.COOKIES.get('trusted_device') or '').strip()
        trusted_device = TrustedDevice.objects.filter(
            user=user, token_hash=hashlib.sha256(trusted_token.encode()).hexdigest(),
            revoked_at__isnull=True, expires_at__gt=timezone.now(),
        ).first() if trusted_token else None
        if two_factor and two_factor.is_enabled and not trusted_device:
            code = str(request.data.get('otp') or request.data.get('backup_code') or '').strip()
            from .two_factor import verify_totp
            valid_otp = verify_totp(two_factor.secret, code) if code else False
            valid_backup = False
            for stored_code in two_factor.backup_codes:
                if hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), stored_code):
                    valid_backup = True
                    two_factor.backup_codes.remove(stored_code)
                    two_factor.save(update_fields=['backup_codes', 'updated_at'])
                    break
            if not (valid_otp or valid_backup):
                return Response({'detail': 'A valid authenticator code is required.', 'mfa_required': True}, status=status.HTTP_401_UNAUTHORIZED)
        if trusted_device:
            trusted_device.last_used_at = timezone.now()
            trusted_device.save(update_fields=['last_used_at'])
        # Keep the browser workspace protected by Django's session as well as JWT.
        login(request, user)
        if 'remember' in request.data:
            request.session.set_expiry(settings.SESSION_COOKIE_AGE if request.data['remember'] is True else 0)
        token = get_tokens_for_user(user, request)
        SecurityEvent.objects.create(
            user=user, username=user.username, event_type='login_success',
            ip_address=ip_address, user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        dashboard_url = {
            'Journalist': '/journalist/dashboard/',
            'Editor': '/editor/dashboard/',
            'Admin': '/adminMain/dashboard/'
        }.get(user.role, '/')

        return Response({
            'token': token,
            'message': 'Login successful!',
            'user': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'email': user.email,
                'role': user.role
            },
            'dashboard_url': dashboard_url
        }, status=status.HTTP_200_OK)

def login_template(request):
    return render(request, 'users/login.html')

def logout_template(request):
    return render(request, 'users/logout.html')


@login_required(login_url='/login-template/')
def account_settings(request):
    return render(request, 'users/account_settings.html')


def newsletter_campaign_landing(request, edition_id):
    edition = get_object_or_404(NewsletterEdition, pk=edition_id, status='sent')
    if not request.session.session_key:
        request.session.create()
    attribution, _ = NewsletterCampaignAttribution.objects.get_or_create(
        edition=edition,
        visitor_key=request.session.session_key,
        defaults={'user': request.user if request.user.is_authenticated else None},
    )
    if request.user.is_authenticated and attribution.user_id is None:
        attribution.user = request.user
        attribution.save(update_fields=['user'])
    request.session['newsletter_attribution_id'] = attribution.id
    return redirect('membership-plans-page')


@role_required('Editor', 'Admin')
def newsletter_campaigns(request):
    return render(request, 'users/newsletter_campaigns.html')


@login_required
def membership_plans(request):
    return render(request, 'users/membership_plans.html')

# Logout View
class AccessTokenRefreshView(APIView):
    """Renew access without extending the original login session's lifetime."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh = RefreshToken(request.data.get('refresh', ''))
            user = User.objects.filter(pk=refresh['user_id'], is_active=True).first()
            if not user or SecuritySession.objects.filter(
                user=user, refresh_jti=str(refresh['jti']), revoked_at__isnull=False,
            ).exists():
                return Response({'detail': 'Please sign in again.'}, status=401)
            SecuritySession.objects.filter(user=user, refresh_jti=str(refresh['jti'])).update(last_seen_at=timezone.now())
            return Response({'access': str(refresh.access_token)})
        except (TokenError, KeyError, TypeError):
            return Response({'detail': 'Your session expired. Please sign in again.'}, status=401)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                if str(refresh['user_id']) != str(request.user.pk):
                    return Response({'detail': 'This refresh token belongs to another user.'}, status=status.HTTP_403_FORBIDDEN)
                refresh.blacklist()
                SecuritySession.objects.filter(
                    user=request.user,
                    refresh_jti=str(refresh['jti']),
                    revoked_at__isnull=True,
                ).update(revoked_at=timezone.now())
            except Exception:
                return Response({'detail': 'Invalid refresh token.'}, status=status.HTTP_400_BAD_REQUEST)
        SecurityEvent.objects.create(
            user=request.user, username=request.user.username, event_type='logout',
            ip_address=request.META.get('REMOTE_ADDR'), user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        logout(request)
        return Response({"message": "Successfully logged out"}, status=200)


class SecurityEventListView(ListAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SecurityEvent.objects.filter(user=self.request.user).order_by('-created_at')[:100]

    def list(self, request, *args, **kwargs):
        events = self.get_queryset()
        return Response([
            {
                'id': event.id, 'event_type': event.event_type, 'success': event.success,
                'ip_address': event.ip_address, 'user_agent': event.user_agent,
                'created_at': event.created_at,
            }
            for event in events
        ])


class SecurityCenterView(APIView):
    """Return the user's active sessions and recent security activity."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = SecuritySession.objects.filter(user=request.user)
        events = SecurityEvent.objects.filter(user=request.user)[:100]
        return Response({
            'sessions': [
                {
                    'id': session.id,
                    'ip_address': session.ip_address,
                    'user_agent': session.user_agent,
                    'created_at': session.created_at,
                    'last_seen_at': session.last_seen_at,
                    'expires_at': session.expires_at,
                    'is_active': session.is_active,
                    'revoked_at': session.revoked_at,
                }
                for session in sessions
            ],
            'events': [
                {
                    'id': event.id,
                    'event_type': event.event_type,
                    'success': event.success,
                    'ip_address': event.ip_address,
                    'user_agent': event.user_agent,
                    'created_at': event.created_at,
                }
                for event in events
            ],
        })


class SecuritySessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        session = get_object_or_404(SecuritySession, pk=pk, user=request.user)
        if session.revoked_at is None:
            session.revoked_at = timezone.now()
            session.save(update_fields=['revoked_at'])
            SecurityEvent.objects.create(
                user=request.user,
                username=request.user.username,
                event_type='token_revoked',
                success=True,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={'session_id': session.id},
            )
        return Response({'revoked': True})


@role_required('Journalist')
def journalist_dashboard(request):
    return render(request, 'articles/journalist_dashboard.html')

# View for Editor Dashboard
@role_required('Editor')
def editor_dashboard(request):
    return render(request, 'articles/editor_dashboard.html')

# View for Admin Dashboard
@role_required('Admin')
def admin_dashboard(request):
    return render(request, 'articles/admin_dashboard.html')
class UserListView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = PageNumberPagination
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role']



class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user  # Get the authenticated user
        user_data = {
            'username': user.username,
            'email': user.email,
            'total_articles': user.article_set.count(),
        }
        return JsonResponse(user_data)

# User Update View
class UserUpdateView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated users can update their profile

    def get_object(self):
        return self.request.user  # Ensure users can only update their own profile

# Change Password View
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password updated successfully.'}, status=status.HTTP_200_OK)
    
# Password Reset Request View
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        # Generate a 6-digit OTP
        otp = get_random_string(length=6, allowed_chars='0123456789')
        otp_created_at = datetime.now().isoformat()
        
        try:
            # Retrieve the user based on email
            User.objects.get(email=email)
            # Save OTP and expiry time to the user's model (you may customize your model for this)
            request.session['otp'] = otp
            request.session['otp_created_at'] = otp_created_at
            request.session['otp_email'] = email
            request.session.set_expiry(600)  # Session expires in 10 minutes

            # Send the OTP to the user's email
            send_mail(
                subject="Password Reset OTP",
                message=f"Your OTP for password reset is: {otp}. This OTP will expire in 10 minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            return Response({'message': 'OTP sent to your email.'}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)
        
class OTPVerificationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # Initialize the serializer with request data
        serializer = OTPVerificationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # If OTP is valid, we can allow the password reset process
        return Response({'message': 'OTP verified successfully. You can now reset your password.'}, status=status.HTTP_200_OK)
    
    

# Password Reset with OTP View
class PasswordResetWithOTPView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetWithOTPSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # Update the user's password
        serializer.update(instance=None, validated_data=serializer.validated_data)

        return Response({'message': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)

# Request OTP View
class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'message': 'OTP sent to email.'}, status=status.HTTP_200_OK)

# User Delete View
class UserDeleteView(generics.DestroyAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAdmin]

    def delete(self, request, *args, **kwargs):
        user_to_delete = self.get_object()
        if user_to_delete == request.user:
            return Response({"detail": "You cannot delete yourself."}, status=status.HTTP_400_BAD_REQUEST)
        user_to_delete.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# Validate Token View
class ValidateTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email
        })

# Password Reset Request Template
def password_reset_request_template(request):
    return render(request, 'users/password_reset_request.html')

# Password Reset Template
def password_reset_template(request, uidb64, token):
    return render(request, 'users/password_reset.html', {
        'uidb64': uidb64,
        'token': token,
    })

# Home Template
def home(request):
    return render(request, 'users/home.html')


@login_required
def user_profile(request):
    # You can return a simple JsonResponse or render an HTML page
    return JsonResponse({
        "username": request.user.username,
        "email": request.user.email,
        "bio": getattr(request.user.profile, 'bio', 'No bio available'),
    })

