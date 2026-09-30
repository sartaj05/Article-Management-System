from django.db import models
from django.core.validators import MinLengthValidator, EmailValidator
from django.utils.timezone import now
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError


class ActiveArticleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Article(models.Model):
    WORKFLOW_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted for review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('published', 'Published'),
    ]

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
    category_ref = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    tag_objects = models.ManyToManyField('Tag', blank=True, related_name='articles')

    summary = models.TextField(max_length=500, blank=True, null=True)
    publish_date = models.DateField(null=True, blank=True)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    workflow_status = models.CharField(max_length=20, choices=WORKFLOW_STATUS_CHOICES, default='draft')
    rejection_reason = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_articles',
    )
    published_at = models.DateTimeField(blank=True, null=True)
    scheduled_publish_at = models.DateTimeField(blank=True, null=True)
    slug = models.SlugField(unique=True, blank=True)
    is_visible = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    featured_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # New Latitude and Longitude Fields
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # New Location Name Field
    location_name = models.CharField(max_length=255, blank=True, null=True)

    objects = ActiveArticleManager()
    all_objects = models.Manager()

    def clean(self):
        if self.publish_date and self.workflow_status != 'published' and self.publish_date <= now().date():
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
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    is_editorial = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content[:50]

# Additional Models

class ArticleImage(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='articles/gallery/')
    caption = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f"Image for {self.article.title}"

class Like(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} liked {self.article.title}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['article', 'user'], name='unique_article_like'),
        ]

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
    slug = models.SlugField(unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ArticleRevision(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='revisions')
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=35)
    subtitle = models.CharField(max_length=50, blank=True, null=True)
    content = models.TextField()
    summary = models.TextField(max_length=500, blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Revision {self.pk} for {self.article.title}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('published', 'Published'),
        ('scheduled', 'Scheduled'),
        ('comment', 'Comment'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=80)
    target_model = models.CharField(max_length=100, default='Article')
    target_id = models.CharField(max_length=100, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ArticleAssignment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='assignments')
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_assignments')
    can_review = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_publish = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['article', 'editor'], name='unique_article_editor_assignment'),
        ]


def create_notification(*, recipient, notification_type, message, article=None):
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        message=message,
        article=article,
    )

