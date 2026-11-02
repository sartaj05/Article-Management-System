/** Small generated-client-style wrapper for Article Studio's v2 public API. */
export class ArticleStudioClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.headers = { 'X-API-Key': apiKey, Accept: 'application/json' };
  }

  async listArticles({ page = 1, limit = 20, category = '', query = '' } = {}) {
    const params = new URLSearchParams({ page, limit, category, q: query });
    const response = await fetch(`${this.baseUrl}/articles/api/v2/public/articles/?${params}`, {
      headers: this.headers,
    });
    if (!response.ok) throw new Error(`Article Studio API request failed: ${response.status}`);
    if (response.headers.get('X-API-Version') !== 'v2') throw new Error('Unexpected Article Studio API version');
    return response.json();
  }

  async *iterateArticles(options = {}) {
    let page = 1;
    while (page) {
      const payload = await this.listArticles({ ...options, page });
      yield* payload.results || [];
      page = payload.next_page;
    }
  }
}
