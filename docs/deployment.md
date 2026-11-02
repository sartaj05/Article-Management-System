# Production deployment

The production compose stack runs PostgreSQL, Redis, the Gunicorn web service,
Celery worker and beat, and nginx. It gates startup on database/Redis health,
applies migrations, collects static assets, and exposes `/health/` for both
container and release smoke checks.

Required production variables include `DJANGO_SECRET_KEY`, database settings,
`DJANGO_ALLOWED_HOSTS`, `INTEGRATION_SECRET_KEY`, and the HTTPS/security
settings documented in `.env.example`.

The release workflow publishes an immutable GitHub Container Registry image.
When `DEPLOYMENT_HOST`, `DEPLOYMENT_USER`, and `DEPLOYMENT_PATH` repository or
environment variables are configured, the production job pulls that exact
commit image, starts the stack, and runs a health-gated smoke test. If the
smoke test fails, it restores the previous image recorded on the host.

Use the manual **Roll back production** workflow with a known-good commit SHA
to restore a previous image. Keep database migrations backwards-compatible so
an image rollback does not require a destructive database operation.
