from rest_framework import serializers

from .models import Article, ArticleAssignment, ArticleImage, ArticleRevision, AuditLog, Category, Comment, Like, Notification, Tag


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


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ['id', 'actor', 'actor_name', 'article', 'action', 'target_model', 'target_id', 'details', 'created_at']
        read_only_fields = fields


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class ArticleAssignmentSerializer(serializers.ModelSerializer):
    editor_name = serializers.CharField(source='editor.username', read_only=True)

    class Meta:
        model = ArticleAssignment
        fields = ['id', 'article', 'editor', 'editor_name', 'can_review', 'can_edit', 'can_publish', 'created_at']
        read_only_fields = ['id', 'article', 'editor_name', 'created_at']


class ArticleImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleImage
        fields = ['id', 'article', 'image', 'caption', 'sort_order', 'created_at']
        read_only_fields = ['id', 'article', 'created_at']


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
            'category_ref', 'tag_objects',
            'workflow_status', 'rejection_reason', 'submitted_at', 'reviewed_at',
            'reviewed_by', 'published_at', 'is_visible', 'slug', 'created_at',
            'scheduled_publish_at', 'updated_at', 'comments_count', 'likes_count', 'views_count',
            'is_deleted', 'deleted_at',
            'is_featured', 'featured_at',
        ]
        read_only_fields = [
            'id', 'author', 'author_name', 'workflow_status', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'reviewed_by', 'published_at', 'is_visible',
            'slug', 'created_at', 'updated_at', 'comments_count', 'likes_count',
            'views_count',
            'is_deleted', 'deleted_at',
            'is_featured', 'featured_at',
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
