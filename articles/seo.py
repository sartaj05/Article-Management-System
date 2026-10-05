from django.urls import reverse


def _absolute_url(request, value):
    if not value:
        return ''
    return request.build_absolute_uri(value) if request and value.startswith('/') else value


def build_article_seo_payload(article, request=None):
    """Build reusable SEO metadata and validation results for an article."""
    title = (article.meta_title or article.title or '').strip()
    description = (article.meta_description or article.summary or article.content or '').strip()[:160]
    canonical = article.canonical_url or (
        request.build_absolute_uri(reverse('public-article', kwargs={'slug': article.slug}))
        if request and article.slug else ''
    )
    image = None
    image_field = article.og_image or article.image
    if image_field:
        image = _absolute_url(request, image_field.url)

    checks = {
        'title_length': {'passed': 30 <= len(title) <= 60, 'message': 'Use a title between 30 and 60 characters.'},
        'description_length': {'passed': 50 <= len(description) <= 160, 'message': 'Use a description between 50 and 160 characters.'},
        'canonical_url': {'passed': bool(canonical), 'message': 'Add a canonical URL before publishing.'},
        'social_image': {'passed': bool(image), 'message': 'Add a social sharing image.'},
        'keywords': {'passed': bool(article.seo_keywords.strip()), 'message': 'Add focused SEO keywords.'},
    }
    passed = sum(1 for check in checks.values() if check['passed'])
    json_ld = {
        '@context': 'https://schema.org',
        '@type': 'NewsArticle',
        'headline': article.title,
        'description': description,
        'url': canonical,
        'datePublished': article.published_at.isoformat() if article.published_at else None,
        'dateModified': article.updated_at.isoformat() if article.updated_at else None,
        'author': {
            '@type': 'Person',
            'name': article.author.get_full_name() or article.author.username,
        },
    }
    if image:
        json_ld['image'] = [image]

    return {
        'meta_title': title,
        'meta_description': description,
        'canonical_url': canonical,
        'social_image': image,
        'seo_keywords': [keyword.strip() for keyword in article.seo_keywords.split(',') if keyword.strip()],
        'score': round((passed / len(checks)) * 100),
        'checks': checks,
        'json_ld': json_ld,
    }
