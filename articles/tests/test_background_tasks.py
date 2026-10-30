from django.conf import settings
from django.test import SimpleTestCase

from articles.tasks import process_distribution_jobs_task, publish_scheduled_articles_task, send_assignment_escalations_task, send_assignment_reminders_task
from users.tasks import expire_pending_memberships_task, send_newsletter_task, send_reader_digests_task


class BackgroundTaskConfigurationTests(SimpleTestCase):
    def test_all_production_workflows_are_registered_with_celery(self):
        expected = {
            'articles.publish_scheduled_articles',
            'articles.process_distribution_jobs',
            'articles.send_assignment_reminders',
            'articles.send_assignment_escalations',
            'users.send_reader_digests',
            'users.expire_pending_memberships',
        }
        configured = {item['task'] for item in settings.CELERY_BEAT_SCHEDULE.values()}
        self.assertTrue(expected.issubset(configured))
        task_names = {
            getattr(process_distribution_jobs_task, 'name', 'articles.process_distribution_jobs'),
            getattr(publish_scheduled_articles_task, 'name', 'articles.publish_scheduled_articles'),
            getattr(send_assignment_reminders_task, 'name', 'articles.send_assignment_reminders'),
            getattr(send_assignment_escalations_task, 'name', 'articles.send_assignment_escalations'),
            getattr(send_reader_digests_task, 'name', 'users.send_reader_digests'),
            getattr(expire_pending_memberships_task, 'name', 'users.expire_pending_memberships'),
            getattr(send_newsletter_task, 'name', 'users.send_newsletter'),
        }
        self.assertEqual(task_names, expected | {'users.send_newsletter'})
