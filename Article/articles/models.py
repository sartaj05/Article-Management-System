from django.db import models
from django.core.validators import MinLengthValidator, EmailValidator
from django.utils.timezone import now
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
class Article(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    REVIEW_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    TAG_CHOICES = [
        ('tech', 'Tech'),
        ('political', 'Political'),
        ('entertainment', 'Entertainment'),
    ]

    CATEGORY_CHOICES = [
        ('news', 'News'),
        ('opinion', 'Opinion'),
        ('features', 'Features'),
    ]

    title = models.CharField(max_length=35, validators=[MinLengthValidator(10)])
    subtitle = models.CharField(max_length=50, blank=True, null=True)
    content = models.TextField()
    author_name = models.CharField(max_length=80, null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.EmailField(validators=[EmailValidator()], null=True)
    image = models.ImageField(upload_to='articles/images/', null=True, blank=True)

    # Tags and Categories
    tags = models.CharField(max_length=255, blank=True, null=True)
    category = models.CharField(max_length=255, choices=CATEGORY_CHOICES, blank=True, null=True)

    summary = models.TextField(max_length=500, blank=True, null=True)
    publish_date = models.DateField(null=True, blank=True)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    slug = models.SlugField(unique=True, blank=True)
    is_visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # New Latitude and Longitude Fields
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # New Location Name Field
    location_name = models.CharField(max_length=255, blank=True, null=True)

    def clean(self):
        if self.publish_date and self.publish_date <= now().date():
            raise ValidationError('Publish date must be in the future.')

        if not self.agreed_to_terms:
            raise ValidationError('You must agree to the terms.')

        if self.tags:
            tags = [tag.strip() for tag in self.tags.split(',')]
            if len(tags) > 3:
                raise ValidationError('You can only select up to 3 tags.')
            for tag in tags:
                if tag not in [choice[0] for choice in self.TAG_CHOICES]:
                    raise ValidationError(f"Invalid tag: {tag}. Available tags are: 'Tech', 'Political', 'Entertainment'.")
        
        if self.category and self.category not in dict(self.CATEGORY_CHOICES):
            raise ValidationError(f"Invalid category. Available categories are: 'News', 'Opinion', 'Features'.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            if Article.objects.filter(slug=self.slug).exists():
                self.slug = f"{self.slug}-{self.id or 1}" 
        if not self.summary:
            self.summary = self.content[:500] 
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Comment(models.Model):
    author = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)  # Correct reference
    content = models.TextField()
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content[:50]

# Additional Models

class ArticleImage(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='articles/gallery/')

    def __str__(self):
        return f"Image for {self.article.title}"

class Like(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} liked {self.article.title}"

class ArticleView(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'} viewed {self.article.title}"
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name

