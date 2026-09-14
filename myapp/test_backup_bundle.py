import io
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from myapp import dropbox_backup as backup


class BackupBundleTests(SimpleTestCase):
    def test_missing_avatar_is_reported_without_blocking_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'db.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('CREATE TABLE example (id INTEGER)')
                connection.commit()
            storage = Mock()
            storage.open.side_effect = [FileNotFoundError('avatars/ll.png'), io.BytesIO(b'icon')]
            dbx = Mock()
            missing = []
            with patch.object(backup, 'db_path', return_value=path), patch.object(backup, '_client', return_value=dbx), patch.object(backup, '_image_files', return_value=[('avatars/ll.png', storage), ('pwa/icon.png', storage)]):
                backup.create_backup(SimpleNamespace(), missing_images=missing)
            self.assertEqual(missing, ['avatars/ll.png'])
            with zipfile.ZipFile(io.BytesIO(dbx.files_upload.call_args_list[0].args[0])) as archive:
                self.assertEqual(archive.read('media/pwa/icon.png'), b'icon')
                self.assertNotIn('media/avatars/ll.png', archive.namelist())
                self.assertEqual(json.loads(archive.read('backup_manifest.json'))['missing_images'], missing)

    def test_legacy_database_backup_still_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'db.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('CREATE TABLE legacy (id INTEGER)')
                connection.commit()
            content = path.read_bytes()
            path.write_bytes(b'changed')
            dbx = Mock()
            dbx.files_download.return_value = (None, SimpleNamespace(content=content))
            with patch.object(backup, '_client', return_value=dbx), patch.object(backup, 'db_path', return_value=path):
                backup.restore_backup(SimpleNamespace(), 'db_old.sqlite3')
            self.assertEqual(path.read_bytes(), content)

    def test_round_trip_restores_database_and_branding_images(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = root / 'db.sqlite3'
            with closing(sqlite3.connect(database)) as connection:
                connection.execute('CREATE TABLE example (value TEXT)')
                connection.execute("INSERT INTO example VALUES ('original')")
                connection.commit()
            storage = Mock()
            storage.open.side_effect = lambda name, mode: io.BytesIO(b'image-' + name.encode())
            dbx = Mock()
            with override_settings(MEDIA_ROOT=root / 'media'), patch.object(backup, 'db_path', return_value=database), patch.object(backup, '_client', return_value=dbx), patch.object(backup, '_image_files', return_value=[('pwa/icon.png', storage), ('branding/favicon.ico', storage), ('branding/social/share.png', storage)]):
                filename = backup.create_backup(SimpleNamespace())
                self.assertEqual(dbx.files_upload.call_count, 2)
                self.assertTrue(dbx.files_upload.call_args_list[1].args[1].endswith('/latest.json'))
                self.assertLess(len(dbx.files_upload.call_args_list[1].args[0]), 200)
                content = dbx.files_upload.call_args_list[0].args[0]
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    self.assertIn('media/pwa/icon.png', archive.namelist())
                    self.assertIn('media/branding/favicon.ico', archive.namelist())
                database.write_bytes(b'changed')
                dbx.files_download.return_value = (None, SimpleNamespace(content=content))
                backup.restore_backup(SimpleNamespace(), filename)
                with closing(sqlite3.connect(database)) as connection:
                    self.assertEqual(connection.execute('SELECT value FROM example').fetchone()[0], 'original')
                self.assertEqual((root / 'media/pwa/icon.png').read_bytes(), b'image-pwa/icon.png')

    def test_unsafe_archive_is_rejected_before_database_changes(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('db.sqlite3', b'SQLite format 3\x00')
            archive.writestr('media/../../outside.png', b'bad')
        dbx = Mock()
        dbx.files_download.return_value = (None, SimpleNamespace(content=data.getvalue()))
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder), patch.object(backup, '_client', return_value=dbx):
            with self.assertRaises(backup.BackupError):
                backup.restore_backup(SimpleNamespace(), 'backup.zip')
