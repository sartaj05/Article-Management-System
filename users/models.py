from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from uuid import uuid4

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
