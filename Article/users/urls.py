from django.urls import path
from .views import (
    UserRegistrationView, UserLoginView,
    UserListView, UserDetailView, UserUpdateView,
    ChangePasswordView, PasswordResetRequestView,
    RequestOTPView, PasswordResetWithOTPView,
    UserDeleteView, LogoutView, ValidateTokenView,OTPVerificationView
)
from . import views
from .views import user_profile
urlpatterns = [
    

path('', views.home, name='home'),

    # Authentication
    path('register/', UserRegistrationView.as_view(), name='user-registration'),
    path('register-template/', views.register_template, name='user-register-template'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('login-template/', views.login_template, name='user-login-template'),
    path('forgot-password/', views.password_reset_request_template, name='forgot-password-template'),  # For the forgot-password page
    path('journalist/dashboard/', views.journalist_dashboard, name='journalist-dashboard'),
    path('editor/dashboard/', views.editor_dashboard, name='editor-dashboard'),
    path('adminMain/dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('validate-token/', ValidateTokenView.as_view(), name='validate-token'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # User List (Admin Only)
    path('user-list/', UserListView.as_view(), name='user-list'),
    
    # User Detail (Authenticated User)
    path('users/', UserDetailView.as_view(), name='user-detail'),
    # Update User (Authenticated User)
    path('users/update/', UserUpdateView.as_view(), name='user-update'),
    path('profile/', user_profile, name='user_profile'),  # Profile endpoint
    # Change Password (Authenticated User)
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    # Password Reset Request
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('verify-otp/', OTPVerificationView.as_view(), name='verify-otp'),
    # path('reset-password/<uidb64>/<token>/', PasswordResetRequestView.as_view(), name='reset-password'),
    # Password Reset with OTP
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('reset-password-with-otp/', PasswordResetWithOTPView.as_view(), name='reset-password-with-otp'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password-reset'),
    # Delete User (Admin Only) - This path could be more RESTful
    path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user-delete'),
]