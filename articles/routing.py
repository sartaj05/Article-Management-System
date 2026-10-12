from django.urls import re_path

from .consumers import ArticleCollaborationConsumer


websocket_urlpatterns = [
    re_path(r'^ws/articles/(?P<article_id>[0-9]+)/collaboration/$', ArticleCollaborationConsumer.as_asgi()),
]
