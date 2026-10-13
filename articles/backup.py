import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from .models import BackupRecord


def create_database_backup(actor=None):
    record = BackupRecord.objects.create(kind='database', initiated_by=actor)
    try:
        if connection.vendor != 'sqlite':
            raise RuntimeError('Automatic file backup currently supports SQLite. Configure pg_dump for PostgreSQL production backups.')
        source = Path(connection.settings_dict['NAME'])
        if not source.exists():
            raise FileNotFoundError(f'Database file not found: {source}')
        backup_root = Path(settings.BACKUP_ROOT)
        backup_root.mkdir(parents=True, exist_ok=True)
        destination = backup_root / f'article-studio-{timezone.now().strftime("%Y%m%d-%H%M%S")}.sqlite3'
        shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        record.status = 'completed'
        record.path = str(destination)
        record.checksum = digest
        record.size_bytes = destination.stat().st_size
        record.completed_at = timezone.now()
        record.save(update_fields=['status', 'path', 'checksum', 'size_bytes', 'completed_at'])
    except Exception as error:
        record.status = 'failed'
        record.error = str(error)[:500]
        record.completed_at = timezone.now()
        record.save(update_fields=['status', 'error', 'completed_at'])
    return record


def verify_database_backup(record):
    path = Path(record.path)
    if record.status != 'completed' or not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == record.checksum
