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


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3}, name='users.deliver_webhook')
def deliver_webhook_task(self, delivery_id):
    from .delivery import retry_webhook_delivery
    from .models import WebhookDelivery
    delivery = WebhookDelivery.objects.select_related('endpoint').get(pk=delivery_id)
    return {'status': retry_webhook_delivery(delivery).status, 'delivery_id': delivery_id}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 3}, name='users.deliver_email')
def deliver_email_task(self, delivery_id):
    from .delivery import deliver_email
    from .models import NotificationDelivery
    delivery = NotificationDelivery.objects.select_related('recipient').get(pk=delivery_id)
    return {'status': deliver_email(delivery).status, 'delivery_id': delivery_id}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 2}, name='users.reconcile_pending_payments')
def reconcile_pending_payments_task(self):
    from .billing_providers import reconcile_pending_payments
    return reconcile_pending_payments()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 2}, name='users.apply_data_retention')
def apply_data_retention_task(self):
    return _run_command('apply_data_retention')
