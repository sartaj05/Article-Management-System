from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser
# users/models.py
from django.contrib.auth.models import User

# Custom User model
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('Journalist', 'Journalist'),
        ('Editor', 'Editor'),
        ('Admin', 'Admin'),
    ]
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Journalist')
    checkbox = models.BooleanField(default=False)# Example extra field

    def __str__(self):
        return self.username


# Profile model linked to the CustomUser model

from django.conf import settings
from django.db import models

# users/models.py
from django.conf import settings
from django.db import models

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

