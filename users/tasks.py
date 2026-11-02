try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(function):
            return function
        return decorator


def _run_command(name, **options):
    from django.core.management import call_command
    call_command(name, **options)
    return {'status': 'completed', 'job': name}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3}, name='users.send_reader_digests')
def send_reader_digests_task(self, frequency='daily'):
    return _run_command('send_reader_digests', frequency=frequency)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3}, name='users.expire_pending_memberships')
def expire_pending_memberships_task(self):
    return _run_command('expire_pending_memberships')


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3}, name='users.send_newsletter')
def send_newsletter_task(self, frequency='weekly'):
    return _run_command('send_newsletter', frequency=frequency)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 2}, name='users.retry_failed_webhooks')
def retry_failed_webhooks_task(self):
    from .delivery import retry_failed_webhook_deliveries
    return retry_failed_webhook_deliveries()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 2}, name='users.reconcile_pending_payments')
def reconcile_pending_payments_task(self):
    from .billing_providers import reconcile_pending_payments
    return reconcile_pending_payments()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 2}, name='users.apply_data_retention')
def apply_data_retention_task(self):
    return _run_command('apply_data_retention')
