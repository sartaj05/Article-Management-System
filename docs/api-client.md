# Article Studio API client guide

The public headless feed is available at /articles/api/v2/public/articles/.
Create a key from /api/developer/keys/ and send it as X-API-Key.

Interactive documentation is available at `/api/docs/` and `/api/redoc/`.
The machine-readable OpenAPI document is available at `/api/openapi.json`.
The small copy-paste clients in [`docs/api/python_client.py`](api/python_client.py)
and [`docs/api/javascript_client.js`](api/javascript_client.js) follow the same
pagination and versioned response contract.

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

## Authenticated workflow example

The browser/API login endpoint returns short-lived access and refresh tokens:

```bash
curl -X POST https://news.example.com/api/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_editor","password":"DemoEditor123!"}'
```

Use the returned access token as `Authorization: Bearer <access-token>` for
authenticated workflow endpoints. Session authentication remains available for
the web application.

## Pagination and errors

List responses use `results`, `next_page`, and `previous_page`. Non-2xx
responses include `error.code`, `error.message`, `error.status`, optional
`error.fields`, and `error.request_id`; `detail` and `errors` remain for older
clients.

## Version migration

Clients should pin `/api/v2/` and check `X-API-Version: v2`. A future v3 will
be introduced alongside v2 with a deprecation window; clients should avoid
depending on undocumented fields and should log the request ID on failures.
# API error contract

Non-2xx responses include an `error` object with a stable `code`, human-readable
`message`, HTTP `status`, optional field-level `fields`, and request correlation
ID. The legacy `detail` and `errors` keys remain available for compatibility.
