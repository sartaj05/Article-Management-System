from rest_framework import serializers

from .models import Article, ArticleAsset, ArticleAssignment, ArticleAutosave, ArticleCorrection, ArticleFactCheck, ArticleImage, ArticleLiveUpdate, ArticleMedia, ArticlePresence, ArticleProvenance, ArticleReaction, ArticleRevision, ArticleSource, ArticleTranslation, AuditLog, Bookmark, Category, Comment, Like, MediaAsset, ModerationFlag, Notification, PlagiarismCheck, SeriesArticle, StorySeries, Tag


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


class ArticleAutosaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleAutosave
        fields = ['id', 'article', 'editor', 'title', 'subtitle', 'content', 'content_format', 'summary', 'editor_state', 'updated_at']
        read_only_fields = ['id', 'article', 'editor', 'updated_at']


class ArticleTranslationSerializer(serializers.ModelSerializer):
    translated_by_name = serializers.CharField(source='translated_by.username', read_only=True, default=None)

    class Meta:
        model = ArticleTranslation
        fields = ['id', 'article', 'language_code', 'title', 'subtitle', 'content', 'summary', 'content_format', 'status', 'translated_by', 'translated_by_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'translated_by', 'translated_by_name', 'created_at', 'updated_at']


class ArticleSEOSerializer(serializers.ModelSerializer):
    class Meta:
        model = Article
        fields = ['meta_title', 'meta_description', 'seo_keywords', 'canonical_url', 'og_image']


class ArticleWorkflowSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    views_count = serializers.IntegerField(source='views.count', read_only=True)

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'subtitle', 'content', 'content_format', 'summary', 'author', 'author_name',
            'meta_title', 'meta_description', 'seo_keywords', 'canonical_url', 'og_image',
            'email', 'image', 'tags', 'category', 'publish_date', 'agreed_to_terms',
            'category_ref', 'tag_objects',
            'workflow_status', 'rejection_reason', 'submitted_at', 'reviewed_at',
            'reviewed_by', 'published_at', 'is_visible', 'slug', 'created_at',
            'scheduled_publish_at', 'updated_at', 'comments_count', 'likes_count', 'views_count',
            'is_deleted', 'deleted_at',
            'is_featured', 'featured_at',
            'is_premium',
        ]
        read_only_fields = [
            'id', 'author', 'author_name', 'workflow_status', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'reviewed_by', 'published_at', 'is_visible',
            'slug', 'created_at', 'updated_at', 'comments_count', 'likes_count',
            'views_count',
            'is_deleted', 'deleted_at',
            'is_featured', 'featured_at',
        ]


class ArticleSourceSerializer(serializers.ModelSerializer):
    added_by_name = serializers.CharField(source='added_by.username', read_only=True, default=None)

    class Meta:
        model = ArticleSource
        fields = ['id', 'article', 'url', 'title', 'publisher', 'source_type', 'notes', 'added_by', 'added_by_name', 'created_at']
        read_only_fields = ['id', 'article', 'added_by', 'added_by_name', 'created_at']


class ArticleFactCheckSerializer(serializers.ModelSerializer):
    checked_by_name = serializers.CharField(source='checked_by.username', read_only=True, default=None)

    class Meta:
        model = ArticleFactCheck
        fields = ['id', 'article', 'claim', 'verdict', 'explanation', 'checked_by', 'checked_by_name', 'checked_at', 'updated_at']
        read_only_fields = ['id', 'article', 'checked_by', 'checked_by_name', 'checked_at', 'updated_at']


class ArticlePresenceSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ArticlePresence
        fields = ['id', 'article', 'user', 'username', 'status', 'section', 'cursor_position', 'last_seen']
        read_only_fields = ['id', 'article', 'user', 'username', 'last_seen']


class ArticleMediaSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, default=None)

    class Meta:
        model = ArticleMedia
        fields = ['id', 'article', 'media_type', 'title', 'file', 'external_url', 'caption', 'transcript', 'duration_seconds', 'sort_order', 'uploaded_by', 'uploaded_by_name', 'created_at']
        read_only_fields = ['id', 'article', 'uploaded_by', 'uploaded_by_name', 'created_at']

    def validate(self, attrs):
        if not attrs.get('file') and not attrs.get('external_url'):
            raise serializers.ValidationError('Provide a media file or external URL.')
        return attrs


class ArticleLiveUpdateSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True, default=None)

    class Meta:
        model = ArticleLiveUpdate
        fields = ['id', 'article', 'author', 'author_name', 'body', 'is_pinned', 'is_published', 'published_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'author', 'author_name', 'created_at', 'updated_at']


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


class BookmarkSerializer(serializers.ModelSerializer):
    article_title = serializers.CharField(source='article.title', read_only=True)

    class Meta:
        model = Bookmark
        fields = ['id', 'article', 'article_title', 'created_at']
        read_only_fields = ['id', 'article_title', 'created_at']


class ArticleReactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ArticleReaction
        fields = ['id', 'article', 'user', 'username', 'reaction', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'user', 'username', 'created_at', 'updated_at']


class PlagiarismCheckSerializer(serializers.ModelSerializer):
    matched_article_title = serializers.CharField(source='matched_article.title', read_only=True, default=None)

    class Meta:
        model = PlagiarismCheck
        fields = ['id', 'article', 'checked_by', 'similarity_score', 'status', 'matched_article', 'matched_article_title', 'matched_excerpt', 'checked_at']
        read_only_fields = fields


class ModerationFlagSerializer(serializers.ModelSerializer):
    checked_by_name = serializers.CharField(source='checked_by.username', read_only=True, default=None)

    class Meta:
        model = ModerationFlag
        fields = ['id', 'article', 'checked_by', 'checked_by_name', 'flag_type', 'severity', 'message', 'matched_text', 'is_resolved', 'created_at']
        read_only_fields = fields


class SeriesArticleSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='article.title', read_only=True)
    slug = serializers.SlugField(source='article.slug', read_only=True)
    summary = serializers.CharField(source='article.summary', read_only=True)

    class Meta:
        model = SeriesArticle
        fields = ['id', 'article', 'title', 'slug', 'summary', 'position', 'added_at']
        read_only_fields = ['id', 'title', 'slug', 'summary', 'added_at']


class StorySeriesSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default=None)
    articles = SeriesArticleSerializer(source='series_articles', many=True, read_only=True)

    class Meta:
        model = StorySeries
        fields = ['id', 'title', 'slug', 'description', 'cover_image', 'is_published', 'created_by', 'created_by_name', 'articles', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_by', 'created_by_name', 'articles', 'created_at', 'updated_at']


class MediaAssetSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, default=None)

    class Meta:
        model = MediaAsset
        fields = ['id', 'uploaded_by', 'uploaded_by_name', 'media_type', 'title', 'file', 'external_url', 'alt_text', 'caption', 'credit', 'license', 'license_expires_at', 'metadata', 'is_archived', 'created_at', 'updated_at']
        read_only_fields = ['id', 'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at']

    def validate(self, attrs):
        if not attrs.get('file') and not attrs.get('external_url'):
            raise serializers.ValidationError('Provide a file or external URL for this asset.')
        return attrs


class ArticleAssetSerializer(serializers.ModelSerializer):
    asset = MediaAssetSerializer(read_only=True)

    class Meta:
        model = ArticleAsset
        fields = ['id', 'article', 'asset', 'role', 'position', 'created_at']
        read_only_fields = ['id', 'article', 'asset', 'created_at']


class ArticleCorrectionSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reported_by.username', read_only=True, default=None)
    reviewer_name = serializers.CharField(source='reviewed_by.username', read_only=True, default=None)

    class Meta:
        model = ArticleCorrection
        fields = ['id', 'article', 'reported_by', 'reporter_name', 'reviewed_by', 'reviewer_name', 'original_text', 'corrected_text', 'reason', 'status', 'published_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'reported_by', 'reporter_name', 'reviewed_by', 'reviewer_name', 'published_at', 'created_at', 'updated_at']


class ArticleProvenanceSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True, default=None)

    class Meta:
        model = ArticleProvenance
        fields = ['id', 'article', 'origin', 'tool_name', 'disclosure', 'sources_reviewed', 'updated_by', 'updated_by_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'article', 'updated_by', 'updated_by_name', 'created_at', 'updated_at']
