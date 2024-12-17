from django.db import models
from django.core.validators import MinLengthValidator, EmailValidator
from django.utils.timezone import now
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name
class Category(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


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

    title = models.CharField(max_length=200, validators=[MinLengthValidator(10)])
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField()
    author_name = models.CharField(max_length=255, null=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.EmailField(validators=[EmailValidator()], null=True)
    image = models.ImageField(upload_to='articles/images/', null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    summary = models.TextField(max_length=500, blank=True, null=True)
    publish_date = models.DateField(null=True, blank=True)
    agreed_to_terms = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='pending')
    slug = models.SlugField(unique=True, blank=True)
    is_visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.publish_date and self.publish_date <= now().date():
            raise ValidationError('Publish date must be in the future.')
        if not self.agreed_to_terms:
            raise ValidationError('You must agree to the terms.')

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
    article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.article.title}"
