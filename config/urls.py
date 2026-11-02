"""
URL configuration for Article project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# config/urls.py

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse, JsonResponse
from articles.api import HealthCheckView, PublicStatusView
from config.metrics import metrics_view
from articles.distribution import ArticleSitemap, ArticleFeed, LocalizedArticleFeed, LocalizedArticleSitemap, robots_txt
from django.contrib.sitemaps.views import sitemap
from django.template import TemplateDoesNotExist


def openapi_json_fallback(request):
    return JsonResponse({
        'openapi': '3.0.0',
        'info': {'title': 'Article Studio API', 'version': 'v2', 'description': 'Install drf-yasg in production for the complete generated schema.'},
        'paths': {},
    })


def openapi_docs_fallback(request):
    return HttpResponse('<!doctype html><title>Article Studio API docs</title><h1>Article Studio API</h1><p>Install drf-yasg to enable interactive Swagger and ReDoc documentation.</p>')


try:
    from rest_framework import permissions
    from drf_yasg import openapi
    from drf_yasg.views import get_schema_view
    from django.template.loader import get_template

    # Some minimal deployments include drf-yasg for schema generation but omit
    # its UI templates. Use the stable fallback routes instead of returning 500.
    get_template('drf-yasg/swagger-ui.html')

    schema_view = get_schema_view(
        openapi.Info(
            title='Article Studio API',
            default_version='v2',
            description='Workflow, collaboration, media, and publishing APIs for Article Studio.',
            contact=openapi.Contact(email='support@example.com'),
        ),
        public=True,
        permission_classes=(permissions.AllowAny,),
    )
except (ImportError, TemplateDoesNotExist):
    schema_view = None
# Redirect root URL to login page
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),  # Include users API for login
    path('', include('users.urls')), 
    path('articles/', include('articles.urls')),
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('status/', PublicStatusView.as_view(), name='public-status'),
    path('metrics/', metrics_view, name='metrics'),
    path('sitemap.xml', sitemap, {'sitemaps': {'articles': ArticleSitemap, 'translations': LocalizedArticleSitemap}}, name='sitemap'),
    path('rss.xml', ArticleFeed(), name='article-feed'),
    path('rss/<str:language_code>.xml', LocalizedArticleFeed(), name='localized-article-feed'),
    path('robots.txt', robots_txt, name='robots-txt'),
    #   path('users/', include('users.urls')), 
    
]

if schema_view:
    urlpatterns += [
        path('api/schema/', schema_view.without_ui(cache_timeout=0), name='api-schema'),
        path('api/openapi.json', schema_view.without_ui(cache_timeout=0), name='api-openapi-json'),
        path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-docs'),
        path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='api-redoc'),
    ]
else:
    urlpatterns += [
        path('api/schema/', openapi_json_fallback, name='api-schema'),
        path('api/openapi.json', openapi_json_fallback, name='api-openapi-json'),
        path('api/docs/', openapi_docs_fallback, name='api-docs'),
        path('api/redoc/', openapi_docs_fallback, name='api-redoc'),
    ]
from django.conf import settings
from django.conf.urls.static import static
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


