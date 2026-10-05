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
    CONTENT_FORMAT_CHOICES = [
        ('plain', 'Plain text'),
        ('markdown', 'Markdown'),
        ('html', 'Rich text HTML'),
    ]
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
    content_format = models.CharField(max_length=20, choices=CONTENT_FORMAT_CHOICES, default='plain')
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    seo_keywords = models.CharField(max_length=255, blank=True)
    canonical_url = models.URLField(blank=True)
    og_image = models.ImageField(upload_to='articles/og-images/', null=True, blank=True)
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
    is_premium = models.BooleanField(default=False)
    is_live = models.BooleanField(default=False)
    live_started_at = models.DateTimeField(blank=True, null=True)
    live_ended_at = models.DateTimeField(blank=True, null=True)
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
            raise ValidationError("Invalid category. Available categories are: 'News', 'Opinion', 'Features'.")

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
    MODERATION_STATUS_CHOICES = [
        ('visible', 'Visible'),
        ('pending', 'Pending review'),
        ('hidden', 'Hidden'),
        ('removed', 'Removed'),
    ]
    author = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)  # Correct reference
    content = models.TextField()
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    is_editorial = models.BooleanField(default=False)
    moderation_status = models.CharField(max_length=20, choices=MODERATION_STATUS_CHOICES, default='visible')
    moderation_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content[:50]


class CommentReport(models.Model):
    STATUS_CHOICES = [('open', 'Open'), ('reviewed', 'Reviewed'), ('dismissed', 'Dismissed')]
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comment_reports')
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='comment_reports_reviewed')
    resolution = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['status', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['comment', 'reported_by'], name='unique_comment_reporter'),
        ]

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


class Bookmark(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='bookmarks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['article', 'user'], name='unique_article_bookmark'),
        ]


class ReadingProgress(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='reading_progress')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reading_progress')
    progress_percent = models.PositiveSmallIntegerField(default=0)
    position_seconds = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(fields=['article', 'user'], name='unique_article_reading_progress'),
        ]


class ArticleReaction(models.Model):
    REACTION_CHOICES = [
        ('like', 'Like'),
        ('helpful', 'Helpful'),
        ('informative', 'Informative'),
        ('interesting', 'Interesting'),
    ]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_reactions')
    reaction = models.CharField(max_length=20, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['article', 'user'], name='unique_article_reaction'),
        ]


class PlagiarismCheck(models.Model):
    STATUS_CHOICES = [
        ('clean', 'Clean'),
        ('review', 'Needs review'),
        ('duplicate', 'Likely duplicate'),
    ]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='plagiarism_checks')
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='plagiarism_checks')
    similarity_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='clean')
    matched_article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='plagiarism_matches')
    matched_excerpt = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-checked_at']


class ModerationFlag(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='moderation_flags')
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='moderation_checks')
    flag_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    message = models.CharField(max_length=500)
    matched_text = models.CharField(max_length=255, blank=True)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class ArticleView(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'} viewed {self.article.title}"


class ArticleEngagementEvent(models.Model):
    EVENT_CHOICES = [
        ('read_start', 'Read started'),
        ('read_progress', 'Read progress'),
        ('read_complete', 'Read completed'),
        ('share', 'Shared'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='engagement_events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='article_engagement_events')
    visitor_key = models.CharField(max_length=128, blank=True, db_index=True)
    session_key = models.CharField(max_length=128, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    value = models.PositiveSmallIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['article', 'event_type', 'created_at'])]


class ArticleLiveUpdate(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='live_updates')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='live_updates_created')
    body = models.TextField()
    is_pinned = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-published_at', '-created_at']

    def __str__(self):
        return f'Live update for {self.article.title}'


class ArticleSource(models.Model):
    SOURCE_TYPES = [('primary', 'Primary source'), ('secondary', 'Secondary source'), ('reference', 'Reference')]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='sources')
    url = models.URLField()
    title = models.CharField(max_length=255)
    publisher = models.CharField(max_length=150, blank=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default='reference')
    notes = models.TextField(blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='article_sources_added')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['source_type', 'created_at']

    def __str__(self):
        return self.title


class ArticleFactCheck(models.Model):
    VERDICT_CHOICES = [('verified', 'Verified'), ('partly_verified', 'Partly verified'), ('unverified', 'Unverified'), ('false', 'False')]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='fact_checks')
    claim = models.CharField(max_length=500)
    verdict = models.CharField(max_length=30, choices=VERDICT_CHOICES)
    explanation = models.TextField()
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='fact_checks_completed')
    checked_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.verdict}: {self.claim[:60]}'


class ArticlePresence(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='presence_sessions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_presence_sessions')
    status = models.CharField(max_length=20, default='editing')
    section = models.CharField(max_length=80, blank=True)
    cursor_position = models.PositiveIntegerField(default=0)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['article', 'user'], name='unique_article_presence_user')]

    def __str__(self):
        return f'{self.user.username} on {self.article.title}'


class ArticleEditEvent(models.Model):
    EVENT_CHOICES = [
        ('content_changed', 'Content changed'),
        ('selection_changed', 'Selection changed'),
        ('comment_added', 'Comment added'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='edit_events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_edit_events')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [models.Index(fields=['article', 'created_at'])]

    def __str__(self):
        return f'{self.event_type} on {self.article_id} by {self.user.username}'


class ArticleMedia(models.Model):
    MEDIA_TYPES = [('video', 'Video'), ('audio', 'Audio')]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='media_items')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to='articles/media/', blank=True, null=True)
    external_url = models.URLField(blank=True)
    caption = models.CharField(max_length=255, blank=True)
    transcript = models.TextField(blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='article_media_uploaded')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'created_at']

    def clean(self):
        if not self.file and not self.external_url:
            raise ValidationError('Provide a media file or external URL.')

    def __str__(self):
        return self.title
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


class ArticleAutosave(models.Model):
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name='autosave')
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_autosaves')
    title = models.CharField(max_length=35, blank=True)
    subtitle = models.CharField(max_length=50, blank=True)
    content = models.TextField(blank=True)
    content_format = models.CharField(max_length=20, choices=Article.CONTENT_FORMAT_CHOICES, default='plain')
    summary = models.TextField(max_length=500, blank=True)
    editor_state = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Autosave for {self.article.title}"


class ArticleTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('gu', 'Gujarati'),
        ('mr', 'Marathi'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('ar', 'Arabic'),
    ]
    STATUS_CHOICES = [('draft', 'Draft'), ('in_review', 'In review'), ('approved', 'Approved'), ('published', 'Published')]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='translations')
    language_code = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=35)
    subtitle = models.CharField(max_length=50, blank=True)
    content = models.TextField()
    summary = models.TextField(max_length=500, blank=True)
    content_format = models.CharField(max_length=20, choices=Article.CONTENT_FORMAT_CHOICES, default='plain')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    translated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='article_translations')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='article_translations_reviewed')
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['language_code']
        constraints = [
            models.UniqueConstraint(fields=['article', 'language_code'], name='unique_article_translation_language'),
        ]

    def __str__(self):
        return f"{self.article.title} ({self.language_code})"


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
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('in_progress', 'In progress'),
        ('review', 'Review'),
        ('blocked', 'Blocked'),
        ('done', 'Done'),
    ]
    PRIORITY_CHOICES = [('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='assignments')
    editor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_assignments')
    can_review = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_publish = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    due_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'due_at', '-updated_at']
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


class StorySeries(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='series/covers/', blank=True, null=True)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='story_series_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class SeriesArticle(models.Model):
    series = models.ForeignKey(StorySeries, on_delete=models.CASCADE, related_name='series_articles')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='story_series_items')
    position = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', '-added_at']
        constraints = [
            models.UniqueConstraint(fields=['series', 'article'], name='unique_story_series_article'),
        ]


class MediaAsset(models.Model):
    MEDIA_TYPES = [('image', 'Image'), ('audio', 'Audio'), ('video', 'Video'), ('document', 'Document')]
    LICENSE_CHOICES = [
        ('owned', 'Owned'),
        ('licensed', 'Licensed'),
        ('cc', 'Creative Commons'),
        ('public_domain', 'Public domain'),
    ]
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='media_assets')
    media_type = models.CharField(max_length=15, choices=MEDIA_TYPES, default='image')
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to='media-library/', blank=True, null=True)
    external_url = models.URLField(blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=500, blank=True)
    credit = models.CharField(max_length=255, blank=True)
    license = models.CharField(max_length=20, choices=LICENSE_CHOICES, default='owned')
    license_expires_at = models.DateField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    file_hash = models.CharField(max_length=64, blank=True, db_index=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if not self.file and not self.external_url:
            raise ValidationError('Provide a file or external URL for this asset.')

    def __str__(self):
        return self.title


class ArticleAsset(models.Model):
    ROLE_CHOICES = [('hero', 'Hero image'), ('inline', 'Inline media'), ('attachment', 'Attachment')]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='asset_links')
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name='article_links')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='inline')
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['article', 'asset'], name='unique_article_media_asset'),
        ]


class ArticleCorrection(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('published', 'Published')]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='corrections')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='corrections_reported')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='corrections_reviewed')
    original_text = models.TextField()
    corrected_text = models.TextField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']


class ArticleProvenance(models.Model):
    ORIGIN_CHOICES = [('human', 'Human written'), ('assisted', 'AI assisted'), ('generated', 'AI generated')]
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name='provenance')
    origin = models.CharField(max_length=20, choices=ORIGIN_CHOICES, default='human')
    tool_name = models.CharField(max_length=100, blank=True)
    disclosure = models.TextField(blank=True)
    sources_reviewed = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='provenance_updates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EditorialAssistantRun(models.Model):
    STATUS_CHOICES = [('completed', 'Completed'), ('failed', 'Failed')]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='assistant_runs')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='assistant_runs_requested')
    action = models.CharField(max_length=30)
    provider = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    suggestions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']


class ContentExperiment(models.Model):
    TYPE_CHOICES = [('headline', 'Headline'), ('thumbnail', 'Thumbnail')]
    STATUS_CHOICES = [('draft', 'Draft'), ('running', 'Running'), ('paused', 'Paused'), ('completed', 'Completed')]
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='experiments')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='content_experiments')
    name = models.CharField(max_length=160)
    experiment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='headline')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    winning_variant = models.ForeignKey('ExperimentVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class ExperimentVariant(models.Model):
    experiment = models.ForeignKey(ContentExperiment, on_delete=models.CASCADE, related_name='variants')
    label = models.CharField(max_length=20)
    headline = models.CharField(max_length=160, blank=True)
    image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['experiment', 'label'], name='unique_experiment_variant_label'),
        ]


class ExperimentAssignment(models.Model):
    experiment = models.ForeignKey(ContentExperiment, on_delete=models.CASCADE, related_name='assignments')
    variant = models.ForeignKey(ExperimentVariant, on_delete=models.CASCADE, related_name='assignments')
    visitor_key = models.CharField(max_length=128)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['experiment', 'visitor_key'], name='unique_experiment_visitor'),
        ]


class ExperimentEvent(models.Model):
    EVENT_CHOICES = [('view', 'View'), ('click', 'Click'), ('read', 'Read')]
    assignment = models.ForeignKey(ExperimentAssignment, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

