from django.urls import path
from .views import (
    ArticleCreateView, ArticleListView, ArticleDetailView,
    TagListView, CategoryListView, CommentListCreateView
)
from . import views

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('api/create/', ArticleCreateView.as_view(), name='article-create'),
    path('api/articles/', ArticleListView.as_view(), name='article-list'),
    path('api/articles/<int:pk>/', ArticleDetailView.as_view(), name='article-detail'),

    # Tags and Categories
    path('api/tags/', TagListView.as_view(), name='tag-list'),
    path('api/categories/', CategoryListView.as_view(), name='category-list'),

    # Comments
    path('api/articles/<int:article_id>/comments/', CommentListCreateView.as_view(), name='comment-list-create'),

    # JWT Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/submit-article/', views.submit_article, name='submit-article'),
    
    # URL for listing articles (the list of articles that the authenticated user can see)
    path('list/', ArticleListView.as_view(), name='article-list'),
]
