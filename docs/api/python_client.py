"""Small generated-client-style wrapper for Article Studio's v2 public API."""

from __future__ import annotations

from typing import Iterator

import requests


class ArticleStudioClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key, 'Accept': 'application/json'})
        self.timeout = timeout

    def list_articles(self, *, page: int = 1, limit: int = 20, category: str = '', query: str = '') -> dict:
        response = self.session.get(
            f'{self.base_url}/articles/api/v2/public/articles/',
            params={'page': page, 'limit': limit, 'category': category, 'q': query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if response.headers.get('X-API-Version') != 'v2':
            raise RuntimeError('Unexpected Article Studio API version')
        return response.json()

    def iter_articles(self, *, limit: int = 20, category: str = '', query: str = '') -> Iterator[dict]:
        page = 1
        while page:
            payload = self.list_articles(page=page, limit=limit, category=category, query=query)
            yield from payload.get('results', [])
            page = payload.get('next_page')


if __name__ == '__main__':
    client = ArticleStudioClient('https://news.example.com', 'as_your_key')
    for article in client.iter_articles(limit=20):
        print(article['title'])
