from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import CustomUser

@receiver(post_save, sender=CustomUser)
def send_superuser_creation_email(sender, instance, created, **kwargs):
    if created and instance.is_superuser:
        send_mail(
            subject='Superuser Account Created',
            message=f'Your superuser account has been created successfully.\n\n'
                    f'Username: {instance.username}\n'
                    f'Email: {instance.email}\n'
                    f'Role: {instance.role}',
            from_email='admin@example.com',
            recipient_list=[instance.email],
            fail_silently=False,
        )
