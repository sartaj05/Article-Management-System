"""Small, bounded-time helpers for production Celery health checks."""

from django.conf import settings


def _celery_app():
    from config.celery import app
    return app


def inspect_workers():
    """Return worker and queue state without making the web request unbounded."""
    try:
        app = _celery_app()
    except ImportError:
        return {'status': 'not_configured', 'workers': {}, 'queue_length': None, 'error': 'Celery is not installed.'}

    inspector = app.control.inspect(timeout=settings.CELERY_INSPECT_TIMEOUT)
    try:
        stats = inspector.stats() or {}
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
    except Exception as error:
        return {'status': 'unhealthy', 'workers': {}, 'queue_length': None, 'error': str(error)[:200]}

    queue_length = None
    try:
        import redis

        connection = redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=settings.CELERY_INSPECT_TIMEOUT)
        queue_length = connection.llen(settings.CELERY_TASK_DEFAULT_QUEUE)
        connection.close()
    except Exception:
        # Worker state is still useful when the broker does not expose queue metrics.
        pass

    workers = {}
    for name, worker_stats in stats.items():
        workers[name] = {
            'pool': worker_stats.get('pool', {}).get('implementation'),
            'active': len(active.get(name, [])),
            'reserved': len(reserved.get(name, [])),
        }
    return {
        'status': 'healthy' if workers else 'unhealthy',
        'workers': workers,
        'queue_length': queue_length,
        'error': None if workers else 'No responsive Celery workers found.',
    }
