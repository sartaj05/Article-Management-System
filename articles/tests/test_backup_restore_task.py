from unittest.mock import patch

from django.test import TestCase, override_settings

from ..tasks import run_recovery_drill_task


class BackupRestoreTaskTests(TestCase):
    @override_settings(BACKUP_ENABLED=False)
    def test_restore_task_is_disabled_without_production_backups(self):
        task = getattr(run_recovery_drill_task, 'run', run_recovery_drill_task)
        self.assertEqual(task(), {'status': 'disabled'})

    @override_settings(BACKUP_ENABLED=True)
    @patch('articles.backup.run_recovery_drill', return_value=None)
    def test_restore_task_reports_missing_backup(self, run_drill):
        task = getattr(run_recovery_drill_task, 'run', run_recovery_drill_task)
        self.assertEqual(task(), {'status': 'no_backup'})
        run_drill.assert_called_once_with()

    def test_beat_schedule_runs_restore_drill_after_backup_window(self):
        from django.conf import settings
        self.assertIn('run-recovery-drill', settings.CELERY_BEAT_SCHEDULE)
