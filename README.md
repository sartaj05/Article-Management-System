# Article Management System

Django and Django REST Framework application for managing articles through Journalist, Editor, and Admin roles.

## Project structure

```text
Article-Management-System/
├── config/                      # Django project settings, URLs, ASGI/WSGI
├── articles/                    # Article models, APIs, forms, static files
│   └── tests/                    # Organized article application test modules
├── users/                       # Authentication, profiles, APIs, and static files
├── templates/                   # Shared users/articles templates and sitemap
├── static/                      # Source static assets
├── manage.py
├── requirements.txt
├── vercel.json
├── build_files.sh
├── scripts/
│   ├── migrate.py               # Create migrations and apply them
│   └── clean_migrations.py      # Remove local custom-app migrations/caches after confirmation
├── .gitignore
└── README.md
```

Generated files such as `__pycache__`, `*.pyc`, `db.sqlite3`, uploaded media, collected static files, and virtual environments are intentionally kept out of Git.

## Local setup

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Copy `.env.example` to `.env` and provide deployment secrets before using SMTP or production settings.

For future model changes, run `python scripts/migrate.py` from the repository root.

## Deployment and monitoring

The project includes `Dockerfile`, `docker-compose.yml`, and a production topology in
`docker-compose.production.yml` with Nginx, PostgreSQL, Redis, Gunicorn, Celery worker, and Celery beat.
Run `docker compose -f docker-compose.production.yml up --build` after providing the required environment
variables. The health endpoint is available at
`/health/` and verifies database connectivity. Set `DATABASE_ENGINE=postgresql` and the `POSTGRES_*`
environment variables in production.

Set `ENFORCE_PRODUCTION_SECURITY=true` only after HTTPS is active and the public host,
CSRF origin, metrics token, PostgreSQL, and secure-cookie settings are configured. The
container entrypoint then runs `python manage.py check_security` before migrations and
refuses to start if a required production control is unsafe. `DJANGO_SECRET_KEY_FALLBACKS`
supports staged secret rotation.

The CI workflow validates tests, migrations, production security checks, dependency integrity, and the
container build. Version tags or a manual release can publish an image to GitHub Container Registry. Set
the repository variable `DEPLOYMENT_BASE_URL` to enable the post-release health smoke test.

For a database backup, run `./docker/backup_postgres.sh` on Linux/macOS or
`./docker/backup_postgres.ps1` in PowerShell. Backups are intentionally ignored by Git; copy them to
durable encrypted storage as part of your operations policy.

## Implemented feature set

The versioned `/articles/api/v2/` API now supports:

1. Draft, submit, approve, reject, and publish workflow.
2. Journalist, Editor, and Admin role permissions.
3. Rejection reasons and editorial review comments.
4. Article revision history.
5. Article comments and discussion notifications.
6. Search, filters, and pagination.
7. In-app and best-effort email notifications.
8. Profile and password updates.
9. Per-article and dashboard analytics.
10. Automated workflow/profile tests and environment-controlled security settings.

Useful endpoints include `/articles/api/v2/articles/search/`,
`/articles/api/v2/notifications/`, and `/articles/api/v2/analytics/`.
Public API client examples are documented in [`docs/api-client.md`](docs/api-client.md).

## Branch workflow

- `main` is the stable branch.
- `sartaj` is the working branch.
- Push feature work to `sartaj`.
- Open a pull request from `sartaj` into `main` after verification.

## Checks

```powershell
python manage.py check
python manage.py test
npm ci
npx playwright install chromium
npm run test:e2e
```

Pull requests also run a PostgreSQL/Redis integration job and deployment smoke checks.
Browser failures are uploaded as Playwright artifacts for review; visual baselines are
stored under `tests/e2e/*-snapshots/`.

## Interview demo

Run `python manage.py seed_demo_data` after migrations and open `/demo/`.

| Persona | Username | Password |
| --- | --- | --- |
| Journalist | `demo_journalist` | `DemoJournalist123!` |
| Editor | `demo_editor` | `DemoEditor123!` |
| Admin | `demo_admin` | `DemoAdmin123!` |
| Reader | `demo_reader` | `DemoReader123!` |

These accounts are for local/demo environments only. Disable them with
`DEMO_MODE_ENABLED=false` in real deployments. See
[`docs/interview-demo.md`](docs/interview-demo.md) for the walkthrough.

Interactive API documentation is available at `/api/docs/`; the OpenAPI JSON is
available at `/api/openapi.json`.

## Free Render preview

`render.yaml` is a starting point for a free interview preview. Free instances
sleep when idle and local files are not durable. Use PostgreSQL, set
`CACHE_BACKEND=locmem`, disable asynchronous workers, and configure
`MEDIA_STORAGE_BACKEND=cloudinary` with `CLOUDINARY_URL` before accepting uploads.
The Docker Compose topology remains the production reference architecture.
