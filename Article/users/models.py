from django.contrib.auth.models import AbstractUser, Permission
from django.db import models
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Journalist', 'Journalist'),
        ('Editor', 'Editor'),
        ('Admin', 'Admin'),
    ]
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Admin')
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
