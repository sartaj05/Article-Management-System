import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from pathlib import Path

from django.test import TestCase, override_settings

from articles.backup import create_database_backup, run_recovery_drill, verify_database_backup


class ProductionReadinessTests(TestCase):
    def test_health_endpoint_has_request_id_and_verbose_checks(self):
        response = self.client.get('/health/?verbose=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'healthy')
        self.assertEqual(response.data['checks']['database'], 'ok')
        self.assertTrue(response.headers.get('X-Request-ID'))

    def test_database_backup_and_recovery_drill_verify_the_archive(self):
        with TemporaryDirectory() as backup_root:
            source = Path(backup_root) / 'source.sqlite3'
            database = sqlite3.connect(source)
            database.execute('CREATE TABLE smoke_check (id INTEGER PRIMARY KEY)')
            database.commit()
            database.close()
            fake_connection = Mock(vendor='sqlite', settings_dict={'NAME': str(source)})
            with override_settings(BACKUP_ROOT=backup_root), patch('articles.backup.connection', fake_connection):
                record = create_database_backup()
                self.assertEqual(record.status, 'completed', record.error)
                self.assertTrue(verify_database_backup(record))
                drill = run_recovery_drill()
        self.assertIsNotNone(drill)
        self.assertIn(drill.status, {'passed', 'unsupported'})
        self.assertNotEqual(drill.status, 'failed')
