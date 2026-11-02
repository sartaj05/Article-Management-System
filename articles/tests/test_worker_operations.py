from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from articles.queue_health import inspect_workers


class WorkerOperationsTests(SimpleTestCase):
    @patch('articles.queue_health._celery_app')
    def test_worker_inspection_reports_active_and_reserved_tasks(self, get_app):
        app = get_app.return_value
        app.control.inspect.return_value.stats.return_value = {
            'worker@one': {'pool': {'implementation': 'prefork'}}
        }
        app.control.inspect.return_value.active.return_value = {'worker@one': [{'id': 'active'}]}
        app.control.inspect.return_value.reserved.return_value = {'worker@one': [{'id': 'reserved'}]}
        snapshot = inspect_workers()
        self.assertEqual(snapshot['status'], 'healthy')
        self.assertEqual(snapshot['workers']['worker@one']['active'], 1)
        self.assertEqual(snapshot['workers']['worker@one']['reserved'], 1)

    @patch('articles.management.commands.check_worker.inspect_workers', return_value={'status': 'healthy', 'workers': {'worker@one': {}}, 'queue_length': 0})
    def test_worker_health_command_succeeds(self, _inspect):
        call_command('check_worker')

    @patch('articles.management.commands.check_worker.inspect_workers', return_value={'status': 'unhealthy', 'workers': {}, 'error': 'offline'})
    def test_worker_health_command_fails_without_workers(self, _inspect):
        with self.assertRaises(CommandError):
            call_command('check_worker')
