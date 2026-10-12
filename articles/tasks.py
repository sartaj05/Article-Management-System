from .jobs import publish_scheduled_articles

try:
    from celery import shared_task
except ImportError:  # Local development can continue using the management command.
    def shared_task(*args, **kwargs):
        def decorator(function):
            return function
        return decorator


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3},
    name='articles.publish_scheduled_articles',
)
def publish_scheduled_articles_task(self):
    """Run the same lock-safe publisher from a production worker."""
    return publish_scheduled_articles()
