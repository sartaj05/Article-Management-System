from rest_framework import serializers
from .models import Article, Comment, Like
from rest_framework.exceptions import ValidationError
from django.utils.text import slugify
import random

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'article', 'user', 'content', 'created_at']
        read_only_fields = ['id', 'article', 'user', 'created_at']

from rest_framework import serializers
from .models import Article, Comment
from rest_framework.exceptions import ValidationError
from django.utils.text import slugify
import random
class ArticleSerializer(serializers.ModelSerializer):
    tags = serializers.CharField(read_only=True)  # If tags is a string field; adjust if it's ManyToMany
    category = serializers.CharField(read_only=True)  # Adjust if category is a ForeignKey
    comments = CommentSerializer(many=True, read_only=True)
    likes_count = serializers.IntegerField(source='like_set.count', read_only=True)
    views_count = serializers.IntegerField(source='articleview_set.count', read_only=True)
    author_name = serializers.CharField(source='author.username', read_only=True)
    image = serializers.ImageField(required=False, allow_null=True)  # Include image field for the API response
    latitude = serializers.FloatField(required=False, allow_null=True)  # Latitude field
    longitude = serializers.FloatField(required=False, allow_null=True)  # Longitude field

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'subtitle', 'content', 'author', 'author_name', 'email',
            'image', 'tags', 'category', 'summary', 'publish_date', 'agreed_to_terms',
            'status', 'review_status', 'slug', 'is_visible', 'created_at', 'updated_at',
            'likes_count', 'views_count', 'comments', 'latitude', 'longitude'
        ]
        read_only_fields = ['id', 'author', 'slug', 'is_visible', 'created_at', 'updated_at']

    def create(self, validated_data):
        tags_data = self.context['request'].data.get('tags', [])
        category_data = self.context['request'].data.get('category')
        latitude = self.context['request'].data.get('latitude', None)  # Get latitude from request data
        longitude = self.context['request'].data.get('longitude', None)  # Get longitude from request data
        
        # Automatically set the author to the logged-in user
        request = self.context.get('request')
        if not request.user.is_authenticated:
            raise ValidationError("User must be authenticated to create an article.")
        
        validated_data['author'] = request.user  # Assign logged-in user to author
        title = validated_data['title']
        validated_data['slug'] = generate_unique_slug(title)
        
        # Handle the location data (latitude, longitude)
        if latitude is not None:
            validated_data['latitude'] = latitude
        if longitude is not None:
            validated_data['longitude'] = longitude
        
        # Create the article instance
        article = Article.objects.create(**validated_data)

        # Handle category
        if category_data:
            article.category = category_data

        article.save()
        return article

    def update(self, instance, validated_data):
        # Prevent modification of author and slug
        validated_data.pop('author', None)
        validated_data.pop('slug', None)

        # Allow the journalist to only update their own articles
        request = self.context.get('request')
        if request.user.role == 'Journalist' and instance.author != request.user:
            raise ValidationError("Journalists can only update their own articles.")

        tags_data = self.context['request'].data.get('tags', [])
        category_data = self.context['request'].data.get('category')
        latitude = self.context['request'].data.get('latitude', None)  # Get latitude from request data
        longitude = self.context['request'].data.get('longitude', None)  # Get longitude from request data

        # Update article fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle the location data (latitude, longitude)
        if latitude is not None:
            instance.latitude = latitude
        if longitude is not None:
            instance.longitude = longitude

        # Handle category
        if category_data:
            instance.category = category_data

        instance.save()
        return instance

# Helper function for slug generation
def generate_unique_slug(title):
    slug = slugify(title)
    # Check if the slug already exists, if so, append a random number to make it unique
    while Article.objects.filter(slug=slug).exists():
        slug = f"{slug}-{random.randint(1000, 9999)}"
    return slug


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'article', 'user', 'created_at']
        read_only_fields = ['id', 'article', 'user', 'created_at']

# Helper function for slug generation
def generate_unique_slug(title):
    slug = slugify(title)
    # Check if the slug already exists, if so, append a random number to make it unique
    while Article.objects.filter(slug=slug).exists():
        slug = f"{slug}-{random.randint(1000, 9999)}"
    return slug
