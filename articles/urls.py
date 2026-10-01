from django.urls import path
from . import views
from .distribution import public_article
from .views import ArticleSubmitView,ArticleCreateAPIView, ArticleListAPIView
from rest_framework.urls import path
from .views import ArticleCountAPIView
from .api import (
    ArticleAnalyticsView,
    ArticleReviewView,
    ArticleSearchViewV2,
    ArticleAutocompleteView,
    ArticleWorkflowActionView,
    ArticleWorkflowView,
    CommentDeleteView,
    CommentListCreateView,
    LikeToggleView,
    NotificationListView,
    NotificationReadView,
    RevisionListView,
    RevisionCompareView,
    AuditLogListView,
    ArticleTrashView,
    ArticleAssignmentView,
    ArticleDiscoveryView,
    ArticleFeatureView,
    ArticleGalleryView,
    ArticleImageDeleteView,
    BookmarkListView,
    BookmarkToggleView,
    ArticleReactionView,
    PlagiarismCheckView,
    ModerationView,
    ArticleTranslationListView,
    ArticleTranslationDetailView,
    ArticleAutosaveView,
    ArticleSEOView,
    ReportExportView,
    CategoryDetailView,
    CategoryListCreateView,
    TagDetailView,
    TagListCreateView,
)
urlpatterns = [
    path('read/<slug:slug>/', public_article, name='public-article'),
    path('api/articles/create/', ArticleCreateAPIView.as_view(), name='article-create'),

    path('api/articles/list/', ArticleListAPIView.as_view(), name='article-list'),
    # path('user/profile/', views.user_profile, name='user_profile'),
    # View article details
    path('articles/<int:article_id>/', views.ArticleDetailView.as_view(), name='article-detail'),
    path('api/articles/count/', ArticleCountAPIView.as_view(), name='article_count'),

    
    path('submit/', ArticleSubmitView.as_view(), name='article-submit'),
    # Search articles
    path('search/', views.ArticleSearchView.as_view(), name='article-search'),  
    # Filter articles by category
    path('category/<str:category_name>/', views.CategoryArticleListView.as_view(), name='article-category'),  
    # Edit an existing article (for editors or the author)
    path('edit/<int:article_id>/', views.ArticleUpdateView.as_view(), name='article-edit'), 
     
    # Delete an article (for editors/admins)
    path('delete/<int:article_id>/', views.ArticleDeleteView.as_view(), name='article-delete'),  

     # Approve an article (for editors/admins)
    path('approve/<int:pk>/', views.ArticleApproveView.as_view(), name='approve-article'), 

    # View published articles (for admins/editors)
    
    path('publish/<int:article_id>/', views.ArticlePublishedView.as_view(), name='publish-article'),
    path('published/', views.ArticlePublishedView.as_view(), name='published-articles'),

    path('reject/<int:article_id>/', views.reject_article, name='reject_article'),  
     # Add the pending approval endpoint
    path('pending_approval/', views.PendingApprovalArticleView.as_view(), name='article-pending-approval'),
    path('publishedlist/', views.PublishedArticleListView.as_view(), name='published_articles_list'),
    # Submit an article (for journalists)
    path('submit/', views.SubmitArticleAPIView.as_view(), name='article-submit'),  
    
    
    path('admin-dashboard-data/', views.admin_dashboard_data, name='admin-dashboard-data'),
    

    
    # View drafts (for journalists)
    path('drafts/', views.ArticleDraftsView.as_view(), name='article-drafts'),  
    

    
    # View and manage comments (for journalists/editors/admins)
    path('comments/<int:article_id>/', views.ArticleCommentsView.as_view(), name='article-comments'),  
    
    # View archived articles (for admins/editors)
    path('archive/', views.ArticleArchiveView.as_view(), name='article-archive'),  
    
    # Update article status (for editors/admins)
    path('status/<int:article_id>/', views.ArticleStatusUpdateView.as_view(), name='article-status-update'),
    path('journalist/dashboard/', views.journalist_dashboard, name='journalist-dashboard'),

    # Versioned API for the updated article-management workflow.
    path('api/v2/articles/search/', ArticleSearchViewV2.as_view(), name='article-search-v2'),
    path('api/v2/articles/autocomplete/', ArticleAutocompleteView.as_view(), name='article-autocomplete'),
    path('api/v2/articles/<int:article_id>/', ArticleWorkflowView.as_view(), name='article-detail-v2'),
    path('api/v2/articles/<int:article_id>/review/', ArticleReviewView.as_view(), name='article-review'),
    path('api/v2/articles/<int:article_id>/revisions/', RevisionListView.as_view(), name='article-revisions'),
    path('api/v2/articles/<int:article_id>/revisions/compare/', RevisionCompareView.as_view(), name='article-revision-compare'),
    path('api/v2/articles/<int:article_id>/comments/', CommentListCreateView.as_view(), name='article-comments-v2'),
    path('api/v2/comments/<int:pk>/', CommentDeleteView.as_view(), name='comment-delete-v2'),
    path('api/v2/articles/<int:article_id>/like/', LikeToggleView.as_view(), name='article-like-toggle'),
    path('api/v2/articles/<int:article_id>/bookmark/', BookmarkToggleView.as_view(), name='article-bookmark-toggle'),
    path('api/v2/bookmarks/', BookmarkListView.as_view(), name='bookmarks'),
    path('api/v2/articles/<int:article_id>/reactions/', ArticleReactionView.as_view(), name='article-reactions'),
    path('api/v2/articles/<int:article_id>/plagiarism/', PlagiarismCheckView.as_view(), name='article-plagiarism'),
    path('api/v2/articles/<int:article_id>/moderation/', ModerationView.as_view(), name='article-moderation'),
    path('api/v2/articles/<int:article_id>/translations/', ArticleTranslationListView.as_view(), name='article-translations'),
    path('api/v2/translations/<int:translation_id>/', ArticleTranslationDetailView.as_view(), name='article-translation-detail'),
    path('api/v2/notifications/', NotificationListView.as_view(), name='notifications'),
    path('api/v2/notifications/<int:notification_id>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('api/v2/audit-logs/', AuditLogListView.as_view(), name='audit-logs'),
    path('api/v2/trash/', ArticleTrashView.as_view(), name='article-trash'),
    path('api/v2/categories/', CategoryListCreateView.as_view(), name='category-list'),
    path('api/v2/categories/<int:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    path('api/v2/tags/', TagListCreateView.as_view(), name='tag-list'),
    path('api/v2/tags/<int:pk>/', TagDetailView.as_view(), name='tag-detail'),
    path('api/v2/articles/<int:article_id>/trash/', ArticleTrashView.as_view(), {'action': 'trash'}, name='article-trash-action'),
    path('api/v2/articles/<int:article_id>/restore/', ArticleTrashView.as_view(), {'action': 'restore'}, name='article-restore-action'),
    path('api/v2/articles/<int:article_id>/assignments/', ArticleAssignmentView.as_view(), name='article-assignments'),
    path('api/v2/articles/<int:article_id>/featured/', ArticleFeatureView.as_view(), name='article-featured'),
    path('api/v2/articles/<int:article_id>/gallery/', ArticleGalleryView.as_view(), name='article-gallery'),
    path('api/v2/articles/<int:article_id>/autosave/', ArticleAutosaveView.as_view(), name='article-autosave'),
    path('api/v2/articles/<int:article_id>/seo/', ArticleSEOView.as_view(), name='article-seo'),
    path('api/v2/gallery/images/<int:pk>/', ArticleImageDeleteView.as_view(), name='article-image-delete'),
    path('api/v2/discover/', ArticleDiscoveryView.as_view(), name='article-discovery'),
    path('api/v2/reports/<str:report_type>/', ReportExportView.as_view(), name='report-export'),
    path('api/v2/articles/<int:article_id>/<str:action>/', ArticleWorkflowActionView.as_view(), name='article-workflow-action'),
    path('api/v2/analytics/', ArticleAnalyticsView.as_view(), name='analytics'),
    path('api/v2/analytics/<int:article_id>/', ArticleAnalyticsView.as_view(), name='article-analytics'),

]
