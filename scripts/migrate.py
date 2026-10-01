"""Create migrations from the current models and apply all database migrations."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIRECTORY = REPOSITORY_ROOT
MANAGE_PY = PROJECT_DIRECTORY / "manage.py"


def run_manage(*arguments: str) -> None:
    """Run a Django management command from the project directory."""
    subprocess.run(
        [sys.executable, str(MANAGE_PY), *arguments],
        cwd=PROJECT_DIRECTORY,
        check=True,
    )


def main() -> None:
    if not MANAGE_PY.is_file():
        raise FileNotFoundError(f"Django manage.py was not found: {MANAGE_PY}")

    run_manage("makemigrations", "articles", "users")
    run_manage("migrate")
    run_manage("check")


if __name__ == "__main__":
    main()
