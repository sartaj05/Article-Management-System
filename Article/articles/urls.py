from django.urls import path
from . import views
from .views import ArticleSubmitView,ArticleCreateAPIView, ArticleListAPIView
from rest_framework.urls import path
from .views import ArticleCountAPIView
urlpatterns = [
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

    path('published/', views.ArticlePublishedView.as_view(), name='published_articles'),
    # Add the pending approval endpoint
    path('pending_approval/', views.PendingApprovalArticleView.as_view(), name='article-pending-approval'),

    path('reject/<int:article_id>/', views.reject_article, name='reject_article'),  
    
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

]
