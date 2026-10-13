from django.contrib.sitemaps import Sitemap
from django.contrib.syndication.views import Feed
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import cache_page

from .models import Article
from users.models import has_active_membership


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


@cache_page(300)
def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    return HttpResponse(f'User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nSitemap: {sitemap_url}\n', content_type='text/plain')


def public_article(request, slug):
    article = get_object_or_404(published_articles(), slug=slug)
    has_article_access = not article.is_premium or has_active_membership(request.user)
    context = {
        'article': article,
        'has_article_access': has_article_access,
        'article_sources': article.sources.all() if has_article_access else [],
        'article_fact_checks': article.fact_checks.select_related('checked_by').all() if has_article_access else [],
        'article_corrections': article.corrections.filter(status='published') if has_article_access else [],
        'article_provenance': getattr(article, 'provenance', None) if has_article_access else None,
        'article_comments': article.comments.filter(moderation_status='visible').select_related('author')[:30] if has_article_access else [],
    }
    return render(request, 'articles/public_article.html', context)
