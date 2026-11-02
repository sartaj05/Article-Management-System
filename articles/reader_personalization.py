"""Explainable reader recommendations and newsletter-ready selections."""

from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from users.models import PersonalizationPreference, ReaderInterest

from .models import AIReaderRecommendation, Article, ArticleView, ReadingProgress
from .newsroom_intelligence import similarity


def generate_reader_recommendations(user, limit=20):
    preference, _ = PersonalizationPreference.objects.get_or_create(user=user)
    if not preference.enabled:
        AIReaderRecommendation.objects.filter(user=user).delete()
        return []
    interests = list(ReaderInterest.objects.filter(user=user).values_list('interest_type', 'value')) if preference.use_topic_interests else []
    categories = {value.lower() for kind, value in interests if kind == 'category'}
    tags = {value.lower() for kind, value in interests if kind == 'tag'}
    authors = {value.lower() for kind, value in interests if kind == 'author'}
    completed_ids = set(ReadingProgress.objects.filter(user=user, completed=True).values_list('article_id', flat=True))
    history_ids = set(ReadingProgress.objects.filter(user=user).order_by('-updated_at').values_list('article_id', flat=True)[:8])
    history_ids.update(ArticleView.objects.filter(user=user).order_by('-viewed_at').values_list('article_id', flat=True)[:8])
    history = list(Article.objects.filter(id__in=history_ids)) if preference.use_reading_history else []
    candidates = list(Article.objects.filter(workflow_status='published', is_visible=True).exclude(id__in=completed_ids).select_related('author').order_by('-published_at', '-created_at')[:150])
    now = timezone.now()
    ranked = []
    for article in candidates:
        article_tags = {item.strip().lower() for item in (article.tags or '').split(',') if item.strip()}
        score = 0.0
        reasons = []
        if (article.category or '').lower() in categories:
            score += 5; reasons.append('matches a followed category')
        matched_tags = article_tags & tags
        if matched_tags:
            score += 3 * len(matched_tags); reasons.append(f'matches topics: {", ".join(sorted(matched_tags)[:3])}')
        if article.author.username.lower() in authors:
            score += 6; reasons.append('matches a followed author')
        if history:
            similarity_score = max((similarity(article, item) for item in history if item.id != article.id), default=0)
            if similarity_score:
                score += similarity_score * 10; reasons.append('similar to stories you read')
        published = article.published_at or article.created_at
        if max(0, (now - published).days) <= 7:
            score += 2; reasons.append('published recently')
        if not reasons:
            reasons.append('recommended to broaden your reading')
        ranked.append((score, article, reasons))
    ranked.sort(key=lambda item: (item[0], item[1].published_at or item[1].created_at), reverse=True)
    AIReaderRecommendation.objects.filter(user=user).delete()
    expires_at = now + timedelta(hours=6)
    AIReaderRecommendation.objects.bulk_create([
        AIReaderRecommendation(user=user, article=article, score=Decimal(str(round(score, 3))), reasons=reasons, expires_at=expires_at)
        for score, article, reasons in ranked[:limit]
    ])
    return list(AIReaderRecommendation.objects.filter(user=user).select_related('article', 'article__author').order_by('-score')[:limit])
