from rest_framework import serializers
from django.utils.timezone import now
from .models import Article, Tag, Category, Comment

class ArticleSerializer(serializers.ModelSerializer):
    tags = serializers.SlugRelatedField(
        many=True, slug_field='name', queryset=Tag.objects.all()
    )
    category = serializers.SlugRelatedField(
        slug_field='name', queryset=Category.objects.all()
    )
    author = serializers.StringRelatedField(read_only=True)  # Display the author's username

    class Meta:
        model = Article
        fields = '__all__'
        read_only_fields = ['author', 'slug', 'created_at', 'updated_at', 'status', 'review_status']
        extra_kwargs = {
            'status': {'required': False, 'default': 'draft'},  # Default status to 'draft'
        }

    def validate_publish_date(self, value):
        """
        Ensure the publish_date is in the future.
        """
        if value and value <= now().date():
            raise serializers.ValidationError("Publish date must be in the future.")
        return value

    def validate_status(self, value):
        """
        Ensure that the status field is one of the valid choices.
        """
        if value not in dict(Article.STATUS_CHOICES).keys():
            raise serializers.ValidationError("Invalid status. Choose either 'draft' or 'published'.")
        return value

    def create(self, validated_data):
        # Handle the creation of the article, including the author
        tags = validated_data.pop('tags', [])
        category = validated_data.pop('category', None)

        # Create the article and set the author automatically
        article = Article.objects.create(
            **validated_data,
            author=self.context['request'].user  # Automatically set the logged-in user as the author
        )

        # Add tags to the article after it's created
        article.tags.set(tags)

        # If there's a category, assign it to the article
        if category:
            article.category = category
            article.save()

        return article
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class CommentSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'article', 'user', 'text', 'created_at']
