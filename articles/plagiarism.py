import re
from difflib import SequenceMatcher

from .models import Article


def normalized_text(value):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', value.lower())).strip()


def find_plagiarism_match(article):
    source = normalized_text(article.content)
    best_article = None
    best_score = 0.0
    for candidate in Article.objects.filter(workflow_status='published').exclude(pk=article.pk).only('id', 'content'):
        score = SequenceMatcher(None, source, normalized_text(candidate.content)).ratio() * 100
        if score > best_score:
            best_score = score
            best_article = candidate
    if best_score >= 85:
        status = 'duplicate'
    elif best_score >= 50:
        status = 'review'
    else:
        status = 'clean'
    return best_article, round(best_score, 2), status
