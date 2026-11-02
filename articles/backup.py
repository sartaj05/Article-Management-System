import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.core.files.storage import default_storage

from .models import BackupRecord, RecoveryDrill


def create_database_backup(actor=None):
    record = BackupRecord.objects.create(kind='database', initiated_by=actor)
    try:
        backup_root = Path(settings.BACKUP_ROOT)
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        if connection.vendor == 'sqlite':
            source = Path(connection.settings_dict['NAME'])
            if not source.exists():
                raise FileNotFoundError(f'Database file not found: {source}')
            destination = backup_root / f'article-studio-{timestamp}.sqlite3'
            shutil.copy2(source, destination)
        elif connection.vendor == 'postgresql':
            destination = backup_root / f'article-studio-{timestamp}.dump'
            dump_database(destination)
        else:
            raise RuntimeError(f'Automatic database backup is not supported for {connection.vendor}.')
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


def dump_database(destination):
    """Create a PostgreSQL custom-format archive without exposing the password in argv."""
    if shutil.which('pg_dump') is None:
        raise RuntimeError('pg_dump is required for PostgreSQL production backups.')
    database = connection.settings_dict
    env = os.environ.copy()
    if database.get('PASSWORD'):
        env['PGPASSWORD'] = str(database['PASSWORD'])
    command = [
        'pg_dump', '--format=custom', '--no-owner', '--file', str(destination),
        '--host', str(database.get('HOST') or 'localhost'),
        '--port', str(database.get('PORT') or '5432'),
        '--username', str(database.get('USER') or ''),
        str(database['NAME']),
    ]
    completed = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=settings.BACKUP_COMMAND_TIMEOUT,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or 'pg_dump failed').strip()[:500])


def create_media_backup(actor=None):
    """Snapshot local media or create a manifest for object-storage media."""
    record = BackupRecord.objects.create(kind='media_manifest', initiated_by=actor)
    try:
        backup_root = Path(settings.BACKUP_ROOT)
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        if getattr(settings, 'MEDIA_STORAGE_BACKEND', 'filesystem') == 's3':
            destination = backup_root / f'article-studio-media-{timestamp}.json'
            entries = []
            directories, files = default_storage.listdir('')
            for name in [*directories, *files]:
                entries.append({'name': name})
            destination.write_text(json.dumps({'storage': 's3', 'files': entries}, indent=2), encoding='utf-8')
        else:
            destination = backup_root / f'article-studio-media-{timestamp}.tar.gz'
            media_root = Path(settings.MEDIA_ROOT)
            with tarfile.open(destination, 'w:gz') as archive:
                if media_root.exists():
                    for path in media_root.rglob('*'):
                        if path.is_file():
                            archive.add(path, arcname=path.relative_to(media_root))
        record.status = 'completed'
        record.path = str(destination)
        record.checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
        record.size_bytes = destination.stat().st_size
        record.completed_at = timezone.now()
        record.save(update_fields=['status', 'path', 'checksum', 'size_bytes', 'completed_at'])
    except Exception as error:
        record.status = 'failed'
        record.error = str(error)[:500]
        record.completed_at = timezone.now()
        record.save(update_fields=['status', 'error', 'completed_at'])
    return record


def prune_old_backups():
    cutoff = timezone.now() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
    deleted = 0
    for record in BackupRecord.objects.filter(created_at__lt=cutoff):
        if record.path:
            path = Path(record.path)
            if path.exists() and path.is_file():
                path.unlink()
        record.delete()
        deleted += 1
    return deleted


def verify_database_backup(record):
    path = Path(record.path)
    if record.status != 'completed' or not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == record.checksum


def run_recovery_drill(actor=None):
    record = BackupRecord.objects.filter(kind='database', status='completed').order_by('-created_at').first()
    if not record:
        return None
    if not verify_database_backup(record):
        return RecoveryDrill.objects.create(backup=record, status='failed', details='Backup checksum verification failed.')
    if connection.vendor == 'postgresql':
        if shutil.which('pg_restore') is None:
            return RecoveryDrill.objects.create(backup=record, status='unsupported', details='pg_restore is required to validate PostgreSQL archives.')
        completed = subprocess.run(['pg_restore', '--list', record.path], capture_output=True, text=True, timeout=settings.BACKUP_COMMAND_TIMEOUT, check=False)
        drill_status = 'passed' if completed.returncode == 0 else 'failed'
        details = 'PostgreSQL archive manifest validation passed.' if drill_status == 'passed' else (completed.stderr or 'pg_restore validation failed')[:500]
        return RecoveryDrill.objects.create(backup=record, status=drill_status, details=details)
    if connection.vendor != 'sqlite':
        return RecoveryDrill.objects.create(backup=record, status='unsupported', details=f'Recovery validation is not configured for {connection.vendor}.')
    try:
        database = sqlite3.connect(f'file:{record.path}?mode=ro', uri=True)
        database.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        database.close()
        return RecoveryDrill.objects.create(backup=record, status='passed', details='Read-only SQLite restore verification passed.')
    except (OSError, sqlite3.Error) as error:
        return RecoveryDrill.objects.create(backup=record, status='failed', details=str(error)[:500])
