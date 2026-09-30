"""Safely remove local custom-app migrations and Python caches.

This is intended for local development only. Do not run it against a shared or
production database. Migration files are removed except for __init__.py.
"""

from __future__ import annotations

import shutil
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIRECTORY = REPOSITORY_ROOT / "Article"
CUSTOM_APPS = ("articles", "users")


def remove_custom_migrations() -> int:
    removed = 0
    for app_name in CUSTOM_APPS:
        migration_directory = PROJECT_DIRECTORY / app_name / "migrations"
        if not migration_directory.is_dir():
            continue

        for migration_file in migration_directory.glob("*.py"):
            if migration_file.name == "__init__.py":
                continue
            migration_file.unlink()
            removed += 1
    return removed


def remove_python_caches() -> int:
    removed = 0
    for cache_directory in REPOSITORY_ROOT.rglob("__pycache__"):
        if cache_directory.is_dir():
            shutil.rmtree(cache_directory)
            removed += 1
    return removed


def main() -> None:
    print("This removes local custom-app migrations and Python caches.")
    print("Do not run this against a shared or production database.")
    confirmation = input("Type DELETE to continue: ")
    if confirmation != "DELETE":
        print("Cancelled.")
        return

    migration_count = remove_custom_migrations()
    cache_count = remove_python_caches()
    print(f"Removed {migration_count} migration file(s).")
    print(f"Removed {cache_count} Python cache director(y/ies).")
    print("Run scripts/migrate.py to regenerate migrations from the current models.")


if __name__ == "__main__":
    main()
