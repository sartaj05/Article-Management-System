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


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
    name='articles.process_distribution_jobs',
)
def process_distribution_jobs_task(self):
    from django.core.management import call_command
    call_command('process_distribution_jobs')
    return {'status': 'completed', 'job': 'distribution'}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
    name='articles.send_assignment_reminders',
)
def send_assignment_reminders_task(self):
    from django.core.management import call_command
    call_command('send_assignment_reminders')
    return {'status': 'completed', 'job': 'assignment_reminders'}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
    name='articles.send_assignment_escalations',
)
def send_assignment_escalations_task(self):
    from django.core.management import call_command
    call_command('send_assignment_escalations')
    return {'status': 'completed', 'job': 'assignment_escalations'}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={'max_retries': 3},
    name='articles.run_ai_job',
)
def run_ai_job_task(self, job_id):
    from .ai_jobs import execute_ai_job
    job = execute_ai_job(job_id)
    return {'status': job.status, 'job_id': job.id}
