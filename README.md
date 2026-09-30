# Article Management System

Django and Django REST Framework application for managing articles through Journalist, Editor, and Admin roles.

## Project structure

```text
Article-Management-System/
├── Article/
│   ├── Article/                 # Django project settings, URLs, ASGI/WSGI
│   ├── articles/                # Article models, APIs, forms, templates, static files
│   ├── users/                   # Authentication, profiles, and user APIs
│   ├── static/                  # Source static assets
│   ├── manage.py
│   ├── requirements.txt
│   ├── vercel.json
│   └── build_files.sh
├── scripts/
│   ├── migrate.ps1              # Create migrations and apply them
│   └── clean_migrations.ps1     # Remove local custom-app migrations/caches after confirmation
├── .gitignore
└── README.md
```

Generated files such as `__pycache__`, `*.pyc`, `db.sqlite3`, uploaded media, collected static files, and virtual environments are intentionally kept out of Git.

## Local setup

```powershell
cd Article
python -m venv ..\venv
..\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

For future model changes, run `..\scripts\migrate.ps1` from the repository root or run the Django commands manually from `Article/`.

## Branch workflow

- `main` is the stable branch.
- `sartaj` is the working branch.
- Push feature work to `sartaj`.
- Open a pull request from `sartaj` into `main` after verification.

## Checks

```powershell
cd Article
python manage.py check
python manage.py test
```
