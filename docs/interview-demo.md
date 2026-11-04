# Interview demo guide

## Five-minute walkthrough

1. Open `/demo/` and choose **Journalist**.
2. Show a draft, autosave, sources, and the workflow timeline.
3. Switch to **Editor** and show assignments, comments, review, and approval.
4. Switch to **Admin** and show audit logs, operations health, permissions, and backups.
5. Finish as **Reader** on the public feed with search and bookmarks.

## Talking points

- Django + DRF with session, token, and JWT authentication.
- Workspace-scoped data and role/capability authorization.
- PostgreSQL, Redis/Celery, and Cloudinary/S3 media storage.
- CI validates migrations, tests, dependency vulnerabilities, static files,
  container builds, and browser workflows.
- Health checks, request IDs, audit events, backups, and recovery drills support
  operational readiness.

## Screenshots and visual evidence

The repository includes Playwright visual baselines under
`tests/e2e/*-snapshots/` for the public newsroom, editor dashboard, monitoring,
membership, and demo launcher. Use those artifacts or capture a short screen
recording from the five-minute walkthrough for the portfolio README.

## Interview close

Explain one trade-off: the free preview disables Celery providers and uses
Cloudinary for durable media, while the production Docker topology keeps
PostgreSQL, Redis, Celery worker/beat, Nginx, backups, and provider retries.

## Demo reset

Run `python manage.py seed_demo_data` locally, or use **Refresh workspace** on
the demo page. Never expose demo credentials in a real customer deployment.
