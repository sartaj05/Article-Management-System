from rest_framework import serializers

from .models import Article, ArticleRevision, Comment, Like, Notification


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'article', 'author', 'author_name', 'content', 'is_editorial', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'author', 'author_name', 'created_at', 'updated_at']


class RevisionSerializer(serializers.ModelSerializer):
    editor_name = serializers.CharField(source='editor.username', read_only=True, default=None)

    class Meta:
        model = ArticleRevision
        fields = ['id', 'article', 'editor', 'editor_name', 'title', 'subtitle', 'content', 'summary', 'category', 'tags', 'created_at']
        read_only_fields = ['id', 'article', 'editor', 'editor_name', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'article', 'notification_type', 'message', 'is_read', 'created_at']
        read_only_fields = fields


class ArticleWorkflowSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    views_count = serializers.IntegerField(source='views.count', read_only=True)

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'subtitle', 'content', 'summary', 'author', 'author_name',
            'email', 'image', 'tags', 'category', 'publish_date', 'agreed_to_terms',
            'workflow_status', 'rejection_reason', 'submitted_at', 'reviewed_at',
            'reviewed_by', 'published_at', 'is_visible', 'slug', 'created_at',
            'scheduled_publish_at', 'updated_at', 'comments_count', 'likes_count', 'views_count',
        ]
        read_only_fields = [
            'id', 'author', 'author_name', 'workflow_status', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'reviewed_by', 'published_at', 'is_visible',
            'slug', 'created_at', 'updated_at', 'comments_count', 'likes_count',
            'views_count',
        ]


class ArticleReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, attrs):
        if attrs['decision'] == 'reject' and not attrs.get('reason', '').strip():
            raise serializers.ValidationError({'reason': 'A rejection reason is required.'})
        return attrs


class ArticleScheduleSerializer(serializers.Serializer):
    scheduled_publish_at = serializers.DateTimeField(required=False, allow_null=True)


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ['id', 'article', 'user', 'created_at']
        read_only_fields = fields
