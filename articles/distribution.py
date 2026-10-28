from django.contrib.sitemaps import Sitemap
from django.contrib.syndication.views import Feed
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_page

from .models import Article, ArticleTranslation
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


class LocalizedArticleSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.7

    def items(self):
        return ArticleTranslation.objects.filter(
            status='published', article__workflow_status='published', article__is_visible=True,
        ).select_related('article').order_by('-updated_at')

    def lastmod(self, translation):
        return translation.updated_at

    def location(self, translation):
        return reverse('public-article-translation', kwargs={'slug': translation.article.slug, 'language_code': translation.language_code})


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


class LocalizedArticleFeed(Feed):
    description = 'Localized published stories from Article Studio.'

    def get_object(self, request, language_code):
        return language_code

    def title(self, language_code):
        return f'Article Studio | {language_code} stories'

    def link(self, language_code):
        return reverse('home')

    def items(self, language_code):
        return ArticleTranslation.objects.filter(
            language_code=language_code, status='published', article__workflow_status='published', article__is_visible=True,
        ).select_related('article').order_by('-article__published_at', '-updated_at')[:25]

    def item_title(self, translation):
        return translation.title

    def item_description(self, translation):
        return translation.summary or translation.content[:300]

    def item_link(self, translation):
        return reverse('public-article-translation', kwargs={'slug': translation.article.slug, 'language_code': translation.language_code})

    def item_pubdate(self, translation):
        return translation.article.published_at or translation.updated_at


@cache_page(300)
def robots_txt(request):
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    return HttpResponse(f'User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nSitemap: {sitemap_url}\n', content_type='text/plain')


def public_article(request, slug):
    return public_article_translation(request, slug, None)


def public_article_translation(request, slug, language_code=None):
    article = get_object_or_404(published_articles(), slug=slug)
    translation = None
    if language_code:
        translation = article.translations.filter(language_code=language_code, status='published').first()
        if translation is None:
            return redirect('public-article', slug=slug)
        article.title = translation.title
        article.subtitle = translation.subtitle
        article.content = translation.content
        article.summary = translation.summary or article.summary
    has_article_access = not article.is_premium or has_active_membership(request.user)
    context = {
        'article': article,
        'article_translation': translation,
        'available_translations': article.translations.filter(status='published'),
        'current_language': language_code or 'en',
        'has_article_access': has_article_access,
        'article_sources': article.sources.all() if has_article_access else [],
        'article_fact_checks': article.fact_checks.select_related('checked_by').all() if has_article_access else [],
        'article_corrections': article.corrections.filter(status='published') if has_article_access else [],
        'article_provenance': getattr(article, 'provenance', None) if has_article_access else None,
        'article_comments': article.comments.filter(moderation_status='visible').select_related('author')[:30] if has_article_access else [],
        'article_assets': article.asset_links.select_related('asset').all() if has_article_access else [],
        'media_url': settings.MEDIA_URL,
    }
    return render(request, 'articles/public_article.html', context)
