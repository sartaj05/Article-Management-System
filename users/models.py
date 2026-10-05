from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from uuid import uuid4
from decimal import Decimal

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Journalist', 'Journalist'),
        ('Editor', 'Editor'),
        ('Admin', 'Admin'),
    ]
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Journalist')
    checkbox = models.BooleanField(default=False)  # Example extra field

    def save(self, *args, **kwargs):
        # Automatically assign permissions based on the role
        super().save(*args, **kwargs)
        if self.role == 'Journalist':
            self.user_permissions.set(Permission.objects.filter(codename__in=['add_article', 'view_article']))
        elif self.role == 'Editor':
            self.user_permissions.set(Permission.objects.filter(codename__in=['change_article', 'view_article']))
        elif self.role == 'Admin':
            self.user_permissions.set(Permission.objects.all())

    def __str__(self):
        return self.username


class Workspace(models.Model):
    """A newsroom organization that owns editorial work and memberships."""
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_workspaces')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkspaceMembership(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Workspace admin'),
        ('editor', 'Editor'),
        ('writer', 'Writer'),
        ('viewer', 'Viewer'),
    ]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workspace_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='writer')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['role', 'user__username']
        constraints = [
            models.UniqueConstraint(fields=['workspace', 'user'], name='unique_workspace_membership'),
        ]

    def __str__(self):
        return f'{self.user.username} in {self.workspace.slug}'


class WorkspaceInvitation(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('revoked', 'Revoked')]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=WorkspaceMembership.ROLE_CHOICES, default='writer')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='workspace_invitations_sent')
    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

# Profile model linked to the CustomUser model
class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    contact_info = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    workflow_enabled = models.BooleanField(default=True)
    comments_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification preferences for {self.user.username}"


class SecurityEvent(models.Model):
    EVENT_CHOICES = [
        ('login_success', 'Login success'),
        ('login_failed', 'Login failed'),
        ('logout', 'Logout'),
        ('token_revoked', 'Token revoked'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='security_events')
    username = models.CharField(max_length=150, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    success = models.BooleanField(default=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} for {self.username or 'anonymous'}"


class SecuritySession(models.Model):
    """A refresh-token session shown in the user's security center."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='security_sessions')
    refresh_jti = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_seen_at']

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'{self.user.username} session {self.refresh_jti[:8]}'


class NewsletterSubscription(models.Model):
    FREQUENCY_CHOICES = [('daily', 'Daily'), ('weekly', 'Weekly')]

    email = models.EmailField(unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='newsletter_subscriptions')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    categories = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    unsubscribe_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email


class NewsletterEdition(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('sent', 'Sent')]

    frequency = models.CharField(max_length=10, choices=NewsletterSubscription.FREQUENCY_CHOICES)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    article_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    recipient_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.frequency} newsletter: {self.subject}'


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Push subscription for {self.user.username}"


class ReaderInterest(models.Model):
    INTEREST_TYPES = [('category', 'Category'), ('tag', 'Tag'), ('author', 'Author')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reader_interests')
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPES)
    value = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['interest_type', 'value']
        constraints = [models.UniqueConstraint(fields=['user', 'interest_type', 'value'], name='unique_reader_interest')]

    def __str__(self):
        return f'{self.user.username}: {self.interest_type}={self.value}'


class AccessibilityPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accessibility_preferences')
    high_contrast = models.BooleanField(default=False)
    reduce_motion = models.BooleanField(default=False)
    large_text = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Accessibility preferences for {self.user.username}'


class MembershipPlan(models.Model):
    INTERVAL_CHOICES = [('month', 'Monthly'), ('year', 'Yearly')]

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='INR')
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default='month')
    features = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price', 'name']

    def __str__(self):
        return self.name


class MembershipSubscription(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('active', 'Active'), ('canceled', 'Canceled'), ('past_due', 'Past due')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='membership_subscriptions')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=30, default='manual')
    provider_reference = models.CharField(max_length=160, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.plan.name} ({self.status})'


class AuthorTip(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('refunded', 'Refunded')]
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='tips_sent')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='tips_received')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    message = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=30, default='manual')
    provider_reference = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.amount} {self.currency} tip for {self.author.username}'


class PublicAPIKey(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='public_api_keys')
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, db_index=True)
    key_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.prefix}...)'


class WebhookEndpoint(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webhook_endpoints')
    url = models.URLField()
    secret = models.CharField(max_length=128)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.url


class PrivacyPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='privacy_preferences')
    analytics_enabled = models.BooleanField(default=False)
    marketing_enabled = models.BooleanField(default=False)
    functional_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Privacy preferences for {self.user.username}'


class PrivacyConsent(models.Model):
    PURPOSE_CHOICES = [
        ('analytics', 'Analytics'),
        ('marketing', 'Marketing'),
        ('functional', 'Functional'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='privacy_consents')
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    granted = models.BooleanField(default=False)
    policy_version = models.CharField(max_length=20, default='1.0')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class PrivacyRequest(models.Model):
    REQUEST_CHOICES = [('export', 'Data export'), ('deletion', 'Account deletion')]
    STATUS_CHOICES = [('pending', 'Pending'), ('completed', 'Completed'), ('canceled', 'Canceled')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='privacy_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


def has_active_membership(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return MembershipSubscription.objects.filter(
        user=user, status='active',
    ).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())).exists()

# Signal to send email when a superuser is created
@receiver(post_save, sender=CustomUser)
def send_superuser_creation_email(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        send_mail(
            subject='Superuser Account Created',
            message=f'Your superuser account has been created successfully.\n\n'
                    f'Username: {instance.username}\n'
                    f'Email: {instance.email}\n'
                    f'Role: {instance.role}',
            from_email='admin@example.com',  # Replace with your admin email
            recipient_list=[instance.email],
            fail_silently=False,
        )
