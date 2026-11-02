#!/bin/sh
set -e

case "${1:-}" in
    gunicorn|uwsgi)
        if [ "${ENFORCE_PRODUCTION_SECURITY:-false}" = "true" ]; then
            python manage.py check_security
        fi
        python manage.py migrate --noinput
        python manage.py collectstatic --noinput
        ;;
esac

exec "$@"
