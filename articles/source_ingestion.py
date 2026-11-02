"""Fetch, extract, chunk, and retrieve evidence from article sources."""

from hashlib import sha256
from io import BytesIO
from html.parser import HTMLParser
import re

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import ArticleSource, ArticleSourceChunk, ArticleSourceDocument


class SourceIngestionError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {'script', 'style', 'noscript', 'svg'}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in {'script', 'style', 'noscript', 'svg'} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())


def _html_text(content):
    parser = _TextExtractor()
    parser.feed(content.decode('utf-8', errors='ignore'))
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()


def _pdf_text(content):
    try:
        from PyPDF2 import PdfReader
    except ImportError as exc:
        raise SourceIngestionError('PDF ingestion requires the PyPDF2 dependency.') from exc
    return re.sub(r'\s+', ' ', ' '.join(page.extract_text() or '' for page in PdfReader(BytesIO(content)).pages)).strip()


def _chunks(text):
    size = max(300, settings.SOURCE_CHUNK_SIZE)
    words = text.split()
    rows = []
    current = []
    current_length = 0
    for word in words:
        if current and current_length + len(word) + 1 > size:
            rows.append(' '.join(current).strip())
            current = current[-35:]
            current_length = sum(len(item) + 1 for item in current)
        current.append(word)
        current_length += len(word) + 1
    if current:
        rows.append(' '.join(current).strip())
    return [row for row in rows if row]


@transaction.atomic
def ingest_source(source_id):
    source = ArticleSource.objects.select_for_update().get(pk=source_id)
    document, _ = ArticleSourceDocument.objects.get_or_create(source=source)
    document.status = 'fetching'
    document.error = ''
    document.save(update_fields=['status', 'error', 'updated_at'])
    try:
        if not source.url.lower().startswith(('http://', 'https://')):
            raise SourceIngestionError('Only HTTP and HTTPS source URLs are supported.')
        response = requests.get(source.url, timeout=settings.SOURCE_FETCH_TIMEOUT, headers={'User-Agent': 'ArticleStudio/1.0 source-ingestion'})
        response.raise_for_status()
        content = response.content[:settings.SOURCE_MAX_BYTES + 1]
        if len(content) > settings.SOURCE_MAX_BYTES:
            raise SourceIngestionError('Source exceeded the configured size limit.')
        content_type = (response.headers.get('Content-Type') or '').lower()
        is_pdf = 'pdf' in content_type or source.url.lower().split('?', 1)[0].endswith('.pdf')
        text = _pdf_text(content) if is_pdf else _html_text(content)
        if len(text) < 20:
            raise SourceIngestionError('Source did not contain enough extractable text.')
        document.status = 'ready'
        document.content_type = content_type or ('application/pdf' if is_pdf else 'text/html')
        document.text_content = text
        document.content_hash = sha256(content).hexdigest()
        document.fetched_at = timezone.now()
        document.save(update_fields=['status', 'content_type', 'text_content', 'content_hash', 'fetched_at', 'error', 'updated_at'])
        document.chunks.all().delete()
        ArticleSourceChunk.objects.bulk_create([
            ArticleSourceChunk(document=document, ordinal=index, text=chunk, token_count=len(chunk.split()))
            for index, chunk in enumerate(_chunks(text))
        ])
        source.accessed_at = document.fetched_at
        source.save(update_fields=['accessed_at'])
    except Exception as exc:
        document.status = 'failed'
        document.error = str(exc)[:2000]
        document.save(update_fields=['status', 'error', 'updated_at'])
        if isinstance(exc, SourceIngestionError):
            raise
        raise SourceIngestionError(f'Source ingestion failed: {exc}') from exc
    return document


def retrieve_evidence_for_article(article, query=None, limit=3):
    query_tokens = set(re.findall(r'[a-z0-9]{4,}', (query or article.content or '').lower()))
    evidence = []
    sources = ArticleSource.objects.filter(article=article, document__status='ready').select_related('document')
    for source in sources:
        ranked = []
        for chunk in source.document.chunks.all():
            chunk_tokens = set(re.findall(r'[a-z0-9]{4,}', chunk.text.lower()))
            overlap = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
            if overlap:
                ranked.append((overlap, chunk))
        ranked.sort(key=lambda item: item[0], reverse=True)
        for score, chunk in ranked[:limit]:
            evidence.append({'source_id': source.id, 'title': source.title, 'publisher': source.publisher, 'url': source.url, 'citation_key': source.citation_key, 'passage': chunk.text, 'relevance': round(score, 3)})
    return sorted(evidence, key=lambda item: item['relevance'], reverse=True)[:limit * 5]
