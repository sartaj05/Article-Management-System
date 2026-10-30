"""Explainable newsroom intelligence using the article corpus."""

from collections import Counter, defaultdict
import re

from django.utils import timezone


STOP_WORDS = {
    'about', 'after', 'again', 'against', 'because', 'before', 'being', 'between', 'could',
    'from', 'have', 'into', 'more', 'other', 'over', 'said', 'some', 'than', 'that',
    'their', 'there', 'these', 'they', 'this', 'through', 'under', 'very', 'what', 'when',
    'where', 'which', 'while', 'with', 'would', 'your', 'will', 'were', 'also', 'only',
}


def tokens(value):
    return {word for word in re.findall(r'[a-z0-9]{4,}', (value or '').lower()) if word not in STOP_WORDS}


def similarity(left, right):
    left_tokens = tokens(f'{left.title} {left.summary} {left.content} {left.tags}')
    right_tokens = tokens(f'{right.title} {right.summary} {right.content} {right.tags}')
    return round(len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1), 3)


def _article_card(article, score):
    return {'article_id': article.id, 'title': article.title, 'category': article.category, 'slug': article.slug, 'score': score}


def build_article_intelligence(article, candidates):
    ranked = sorted(((similarity(article, candidate), candidate) for candidate in candidates if candidate.id != article.id), reverse=True, key=lambda item: item[0])
    recommendations = [_article_card(candidate, score) for score, candidate in ranked[:5] if score > 0]
    duplicates = [_article_card(candidate, score) for score, candidate in ranked if score >= 0.35][:5]
    return {
        'generated_at': timezone.now().isoformat(),
        'recommendations': recommendations,
        'duplicate_candidates': duplicates,
        'duplicate_risk': 'high' if duplicates and duplicates[0]['score'] >= 0.7 else ('medium' if duplicates else 'low'),
    }


def build_workspace_intelligence(articles):
    rows = list(articles)
    counts = Counter()
    clusters = defaultdict(list)
    for article in rows:
        counts.update(tokens(f'{article.title} {article.summary} {article.content} {article.tags}'))
        clusters[article.category or 'uncategorized'].append(article.id)
    duplicate_pairs = []
    for index, left in enumerate(rows):
        for right in rows[index + 1:]:
            score = similarity(left, right)
            if score >= 0.35:
                duplicate_pairs.append({'left_article_id': left.id, 'right_article_id': right.id, 'score': score})
    duplicate_pairs.sort(key=lambda item: item['score'], reverse=True)
    return {
        'article_count': len(rows),
        'trend_terms': [{'term': term, 'count': count} for term, count in counts.most_common(12)],
        'topic_clusters': [{'topic': topic, 'article_ids': article_ids, 'count': len(article_ids)} for topic, article_ids in clusters.items()],
        'duplicate_candidates': duplicate_pairs[:10],
    }
