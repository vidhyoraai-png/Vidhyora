"""Backs up/restores db.sqlite3 to/from a Dropbox app folder, using the
store owner's Dropbox App Key/Secret + a long-lived OAuth2 refresh token
(configured from the store dashboard). Degrades gracefully if the
`dropbox` package isn't installed or credentials aren't set yet.
"""
import datetime
from pathlib import Path

from django.conf import settings as dj_settings

try:
    import dropbox
except ImportError:  # pragma: no cover - optional dependency until configured
    dropbox = None

BACKUP_ROOT = '/EduTrellis Store'
BACKUP_FOLDER = f'{BACKUP_ROOT}/backups'
LATEST_NAME = 'db_latest.sqlite3'


class BackupError(Exception):
    """Raised for any Dropbox/backup failure with a message safe to show the admin."""


def db_path():
    return Path(dj_settings.DATABASES['default']['NAME'])


def _client(settings_obj):
    if dropbox is None:
        raise BackupError("The 'dropbox' Python package isn't installed on this server.")
    if not settings_obj.is_configured:
        raise BackupError('Dropbox is not configured yet — add your App Key, App Secret and Refresh Token first.')
    return dropbox.Dropbox(
        oauth2_refresh_token=settings_obj.refresh_token,
        app_key=settings_obj.app_key,
        app_secret=settings_obj.app_secret,
    )


def _ensure_folder(dbx, path):
    try:
        dbx.files_create_folder_v2(path)
    except Exception as exc:
        if 'conflict' not in str(exc).lower():  # folder already exists — fine
            raise BackupError(f"Could not create the Dropbox folder '{path}': {exc}")


def create_backup(settings_obj):
    """Uploads the current db.sqlite3 as a timestamped file, and refreshes
    db_latest.sqlite3 alongside it. Returns the timestamped filename."""
    try:
        dbx = _client(settings_obj)
        _ensure_folder(dbx, BACKUP_ROOT)
        _ensure_folder(dbx, BACKUP_FOLDER)

        path = db_path()
        if not path.exists():
            raise BackupError('Local database file was not found.')
        data = path.read_bytes()

        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'db_{stamp}.sqlite3'
        dbx.files_upload(data, f'{BACKUP_FOLDER}/{filename}', mode=dropbox.files.WriteMode.add)
        dbx.files_upload(data, f'{BACKUP_FOLDER}/{LATEST_NAME}', mode=dropbox.files.WriteMode.overwrite)
        return filename
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f'Backup to Dropbox failed: {exc}')


def list_backups(settings_obj):
    """Returns timestamped backup files (newest first), excluding db_latest.sqlite3."""
    try:
        dbx = _client(settings_obj)
        try:
            res = dbx.files_list_folder(BACKUP_FOLDER)
        except Exception as exc:
            if 'not_found' in str(exc).lower():
                return []
            raise

        entries = list(res.entries)
        while res.has_more:
            res = dbx.files_list_folder_continue(res.cursor)
            entries.extend(res.entries)

        files = [e for e in entries if isinstance(e, dropbox.files.FileMetadata) and e.name != LATEST_NAME]
        files.sort(key=lambda e: e.name, reverse=True)
        return files
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f'Could not list Dropbox backups: {exc}')


def delete_all_backups(settings_obj):
    """Delete every file/folder inside the dedicated Dropbox backup folder.

    The backup folder itself and everything outside it are deliberately left
    untouched. This includes deleting db_latest.sqlite3, which list_backups()
    normally hides from the restore-file list.
    """
    try:
        dbx = _client(settings_obj)
        try:
            res = dbx.files_list_folder(BACKUP_FOLDER)
        except Exception as exc:
            if 'not_found' in str(exc).lower():
                return 0
            raise

        entries = list(res.entries)
        while res.has_more:
            res = dbx.files_list_folder_continue(res.cursor)
            entries.extend(res.entries)

        folder_prefix = BACKUP_FOLDER.lower().rstrip('/') + '/'
        deleted = 0
        for entry in entries:
            path = getattr(entry, 'path_lower', '') or ''
            # Refuse to pass any unexpected path to Dropbox's destructive API,
            # even if a malformed/mock response somehow puts it in the listing.
            if not path.startswith(folder_prefix):
                continue
            dbx.files_delete_v2(path)
            deleted += 1
        return deleted
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f'Could not delete Dropbox backups: {exc}')


def restore_backup(settings_obj, filename):
    """Downloads the given backup and atomically overwrites the local db.sqlite3."""
    if not filename or '/' in filename or '\\' in filename:
        raise BackupError('Invalid backup filename.')

    try:
        dbx = _client(settings_obj)
        _, resp = dbx.files_download(f'{BACKUP_FOLDER}/{filename}')
        content = resp.content
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f'Could not download that backup from Dropbox: {exc}')

    from django.db import connections
    connections.close_all()

    path = db_path()
    tmp_path = path.with_suffix(path.suffix + '.restoring')
    try:
        tmp_path.write_bytes(content)
        tmp_path.replace(path)
    except OSError as exc:
        raise BackupError(
            f'Could not write the restored database (it may be locked by the running server): {exc}'
        )
