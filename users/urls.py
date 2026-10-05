from django.urls import path
from .views import (
    UserRegistrationView, UserLoginView,
    UserListView, UserDetailView, UserUpdateView,
    ChangePasswordView, PasswordResetRequestView,
    RequestOTPView, PasswordResetWithOTPView,
    UserDeleteView, LogoutView, ValidateTokenView,OTPVerificationView, SecurityEventListView,
    SecurityCenterView, SecuritySessionRevokeView,
)
from . import views
from .api import (
    AccessibilityPreferenceView, MembershipCancelView, MembershipCheckoutView, MembershipWebhookView,
    MembershipMeView, MembershipPlanView, NewsletterPreviewView, NewsletterSubscriptionView,
    NotificationPreferenceView, PublicAuthorView, PushSubscriptionView, SupportChatView,
    AuthorTipHistoryView, AuthorTipIntentView, DeveloperAPIDocumentationView, PrivacyConsentView, PrivacyDeletionRequestView, PrivacyExportView, PrivacyPreferenceView, PrivacyRequestView, PublicAPIKeyDetailView, PublicAPIKeyView, ReaderInterestView, UserProfileView, WebhookDeliveryView, WebhookEndpointView, WorkspaceInviteView, WorkspaceListCreateView,
    WorkspaceMembersView, WorkspaceInvitationAcceptView,
)
urlpatterns = [
    

path('', views.home, name='home'),

    # Authentication
    path('register/', UserRegistrationView.as_view(), name='user-registration'),
    path('register-template/', views.register_template, name='user-register-template'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('login-template/', views.login_template, name='user-login-template'),
    path('logout-template/', views.logout_template, name='user-logout-template'),
    path('forgot-password/', views.password_reset_request_template, name='forgot-password-template'),  # For the forgot-password page
    path('journalist/dashboard/', views.journalist_dashboard, name='journalist-dashboard'),
    path('editor/dashboard/', views.editor_dashboard, name='editor-dashboard'),
    path('adminMain/dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('validate-token/', ValidateTokenView.as_view(), name='validate-token'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('security/events/', SecurityEventListView.as_view(), name='security-events'),
    path('security/center/', SecurityCenterView.as_view(), name='security-center'),
    path('security/sessions/<int:pk>/', SecuritySessionRevokeView.as_view(), name='security-session-revoke'),
    path('support/chat/', SupportChatView.as_view(), name='support-chat'),
    
    # User List (Admin Only)
    path('user-list/', UserListView.as_view(), name='user-list'),
    
    # User Detail (Authenticated User)
    path('users/', UserDetailView.as_view(), name='user-detail'),
    # Update User (Authenticated User)
    path('users/update/', UserUpdateView.as_view(), name='user-update'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('notification-preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
    path('newsletter/subscribe/', NewsletterSubscriptionView.as_view(), name='newsletter-subscribe'),
    path('newsletter/preview/', NewsletterPreviewView.as_view(), name='newsletter-preview'),
    path('push/subscribe/', PushSubscriptionView.as_view(), name='push-subscribe'),
    path('reader/interests/', ReaderInterestView.as_view(), name='reader-interests'),
    path('accessibility/preferences/', AccessibilityPreferenceView.as_view(), name='accessibility-preferences'),
    path('membership/plans/', MembershipPlanView.as_view(), name='membership-plans'),
    path('membership/me/', MembershipMeView.as_view(), name='membership-me'),
    path('membership/checkout/', MembershipCheckoutView.as_view(), name='membership-checkout'),
    path('membership/cancel/', MembershipCancelView.as_view(), name='membership-cancel'),
    path('membership/webhook/', MembershipWebhookView.as_view(), name='membership-webhook'),
    path('authors/<int:user_id>/', PublicAuthorView.as_view(), name='public-author'),
    path('authors/<int:author_id>/tips/', AuthorTipIntentView.as_view(), name='author-tip-intent'),
    path('tips/', AuthorTipHistoryView.as_view(), name='author-tip-history'),
    path('developer.json', DeveloperAPIDocumentationView.as_view(), name='developer-api-docs'),
    path('developer/keys/', PublicAPIKeyView.as_view(), name='public-api-keys'),
    path('developer/keys/<int:pk>/', PublicAPIKeyDetailView.as_view(), name='public-api-key-detail'),
    path('developer/webhooks/', WebhookEndpointView.as_view(), name='webhook-endpoints'),
    path('developer/webhook-deliveries/', WebhookDeliveryView.as_view(), name='webhook-deliveries'),
    path('privacy/preferences/', PrivacyPreferenceView.as_view(), name='privacy-preferences'),
    path('privacy/consents/', PrivacyConsentView.as_view(), name='privacy-consents'),
    path('privacy/requests/', PrivacyRequestView.as_view(), name='privacy-requests'),
    path('privacy/export/', PrivacyExportView.as_view(), name='privacy-export'),
    path('privacy/delete/', PrivacyDeletionRequestView.as_view(), name='privacy-delete-request'),
    path('workspaces/', WorkspaceListCreateView.as_view(), name='workspace-list-create'),
    path('workspaces/<slug:slug>/members/', WorkspaceMembersView.as_view(), name='workspace-members'),
    path('workspaces/<slug:slug>/invite/', WorkspaceInviteView.as_view(), name='workspace-invite'),
    path('workspaces/invitations/<uuid:token>/accept/', WorkspaceInvitationAcceptView.as_view(), name='workspace-invitation-accept'),
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
