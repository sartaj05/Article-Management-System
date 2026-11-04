# Performance notes

The application records request duration and exposes operational metrics. The
executive analytics endpoint is cached per user and workspace for
`ANALYTICS_CACHE_SECONDS` (30 seconds by default), while public feeds and RSS
are cached separately.

Profile a representative endpoint locally with:

```powershell
python scripts/profile_queries.py /articles/api/v2/analytics/
```

Record the query count and p95 latency before and after changes. Prefer
`select_related`, `prefetch_related`, aggregate queries, and bounded pagination
before increasing cache duration.
