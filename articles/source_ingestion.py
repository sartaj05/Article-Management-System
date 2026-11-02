"""Fetch, extract, chunk, and retrieve evidence from article sources."""

from hashlib import sha256
from io import BytesIO
from html.parser import HTMLParser
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from .models import ArticleSource, ArticleSourceChunk, ArticleSourceDocument


class SourceIngestionError(RuntimeError):
    pass


def _validate_source_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise SourceIngestionError('Only HTTP and HTTPS source URLs are supported.')
    if not settings.SOURCE_SSRF_PROTECTION:
        return parsed
    hostname = parsed.hostname.lower().rstrip('.')
    if hostname in {'localhost', 'localhost.localdomain'} or hostname.endswith('.local'):
        raise SourceIngestionError('Private or local source URLs are not allowed.')
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise SourceIngestionError('The source hostname could not be resolved.') from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SourceIngestionError('Private or local source URLs are not allowed.')
    return parsed


def _fetch_source(url):
    current_url = url
    for redirect_count in range(settings.SOURCE_MAX_REDIRECTS + 1):
        _validate_source_url(current_url)
        cache_key = f'source-ingestion:{sha256(current_url.encode()).hexdigest()}'
        cached = cache.get(cache_key)
        if cached:
            return cached['content'], cached['content_type']
        response = requests.get(
            current_url,
            timeout=settings.SOURCE_FETCH_TIMEOUT,
            headers={'User-Agent': 'ArticleStudio/1.0 source-ingestion'},
            allow_redirects=False,
        )
        status_code = response.status_code if isinstance(response.status_code, int) else 200
        if status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get('Location')
            if not location or redirect_count >= settings.SOURCE_MAX_REDIRECTS:
                raise SourceIngestionError('Source redirected too many times.')
            current_url = urljoin(current_url, location)
            continue
        response.raise_for_status()
        content = response.content[:settings.SOURCE_MAX_BYTES + 1]
        if len(content) > settings.SOURCE_MAX_BYTES:
            raise SourceIngestionError('Source exceeded the configured size limit.')
        content_type = (response.headers.get('Content-Type') or '').lower()
        cache.set(cache_key, {'content': content, 'content_type': content_type}, timeout=settings.SOURCE_CACHE_TIMEOUT)
        return content, content_type
    raise SourceIngestionError('Source redirected too many times.')


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
        _validate_source_url(source.url)
        content, content_type = _fetch_source(source.url)
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
    query_text = query or article.content or ''
    evidence = []
    sources = ArticleSource.objects.filter(article=article, document__status='ready').select_related('document')
    rows = []
    for source in sources:
        for chunk in source.document.chunks.all():
            rows.append((source, chunk))
    if not rows:
        return []
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        matrix = TfidfVectorizer(stop_words='english').fit_transform([query_text] + [chunk.text for _, chunk in rows])
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    except (ImportError, ValueError):
        query_tokens = set(re.findall(r'[a-z0-9]{4,}', query_text.lower()))
        scores = [
            len(query_tokens & set(re.findall(r'[a-z0-9]{4,}', chunk.text.lower()))) / max(len(query_tokens), 1)
            for _, chunk in rows
        ]
    ranked = sorted(zip(scores, rows), key=lambda item: item[0], reverse=True)
    for score, (source, chunk) in ranked[:limit * 5]:
        if score <= 0:
            continue
        evidence.append({'source_id': source.id, 'title': source.title, 'publisher': source.publisher, 'url': source.url, 'citation_key': source.citation_key, 'passage': chunk.text, 'relevance': round(float(score), 3)})
    return sorted(evidence, key=lambda item: item['relevance'], reverse=True)[:limit * 5]
