from tokenize import Token
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.pagination import PageNumberPagination
from rest_framework.generics import ListAPIView
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import render
from django.http import JsonResponse
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
from django.conf import settings
from datetime import datetime
from django.core.mail import send_mail
from rest_framework import status
from users.models import CustomUser as User
from rest_framework.exceptions import ValidationError

# Utility function for generating tokens
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
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
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = get_tokens_for_user(user)

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

# Logout View
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
            return Response({"message": "Successfully logged out"}, status=200)
        except Token.DoesNotExist:
            return Response({"error": "Invalid token"}, status=400)


def journalist_dashboard(request):
    return render(request, 'articles/journalist_dashboard.html')

# View for Editor Dashboard
def editor_dashboard(request):
    return render(request, 'articles/editor_dashboard.html')

# View for Admin Dashboard
def admin_dashboard(request):
    return render(request, 'articles/admin_dashboard.html')
class UserListView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = PageNumberPagination
    permission_classes = [IsAuthenticated]  # All authenticated users can view the list
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role']



class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user  # Get the authenticated user
        user_data = {
            'username': user.username,
            'email': user.email,
            'total_articles': user.articles.count(),  # Assuming user has an articles relationship
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
    
from django.core.mail import send_mail
# Password Reset Request View
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        print(email)
        # Generate a 6-digit OTP
        otp = get_random_string(length=6, allowed_chars='0123456789')
        otp_created_at = datetime.now().isoformat()
        
        try:
            # Retrieve the user based on email
            user = User.objects.get(email=email)
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
    permission_classes = [IsAdminUser]

    def delete(self, request, *args, **kwargs):
        user_to_delete = self.get_object()
        if user_to_delete == request.user:
            return Response({"detail": "You cannot delete yourself."}, status=status.HTTP_400_BAD_REQUEST)
        user_to_delete.delete()
        return Response({'message': 'User deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)

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

