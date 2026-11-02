from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings

from articles.backup import create_media_backup


class BackupTests(TestCase):
    def test_local_media_backup_creates_archive(self):
        with TemporaryDirectory() as backup_directory, TemporaryDirectory() as media_directory:
            with override_settings(BACKUP_ROOT=backup_directory, MEDIA_ROOT=media_directory, MEDIA_STORAGE_BACKEND='filesystem'):
                record = create_media_backup()
            self.assertEqual(record.status, 'completed')
            self.assertTrue(record.path.endswith('.tar.gz'))

