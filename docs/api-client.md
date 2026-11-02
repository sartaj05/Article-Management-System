# Article Studio API client guide

The public headless feed is available at /articles/api/v2/public/articles/.
Create a key from /api/developer/keys/ and send it as X-API-Key.

Python example:

    import requests
    response = requests.get(
        "https://news.example.com/articles/api/v2/public/articles/",
        headers={"X-API-Key": "as_your_key"},
        params={"page": 1, "limit": 20},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

JavaScript example:

    const response = await fetch(
      "https://news.example.com/articles/api/v2/public/articles/?page=1&limit=20",
      { headers: { "X-API-Key": "as_your_key" } }
    );
    if (!response.ok) throw new Error("API request failed");
    const payload = await response.json();

Responses include X-API-Version: v2, next_page, and previous_page.
Keys are scoped to articles:read by default and are rate-limited per minute.
