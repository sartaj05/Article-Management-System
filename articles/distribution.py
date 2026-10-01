from django.contrib.sitemaps import Sitemap
from django.contrib.syndication.views import Feed
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Article


def published_articles():
    return Article.objects.filter(workflow_status='published', is_visible=True).select_related('author').order_by('-published_at', '-created_at')


class ArticleSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return published_articles()

    def lastmod(self, article):
        return article.updated_at

    def location(self, article):
        return reverse('public-article', kwargs={'slug': article.slug})


class ArticleFeed(Feed):
    title = 'Article Studio | Latest stories'
    description = 'The latest published stories from Article Studio.'

    def link(self):
        return reverse('home')

    def items(self):
        return published_articles()[:25]

    def item_title(self, article):
        return article.title

    def item_description(self, article):
        return article.summary or article.content[:300]

    def item_link(self, article):
        return reverse('public-article', kwargs={'slug': article.slug})

    def item_pubdate(self, article):
        return article.published_at or article.updated_at


def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    return HttpResponse(f'User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nSitemap: {sitemap_url}\n', content_type='text/plain')


def public_article(request, slug):
    article = get_object_or_404(published_articles(), slug=slug)
    return render(request, 'articles/public_article.html', {'article': article})
