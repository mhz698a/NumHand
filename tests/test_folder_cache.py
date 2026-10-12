import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from folder_cache import FolderCache


class FolderCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.folder = self.root / "media"
        self.folder.mkdir()
        self.cache = FolderCache(self.root / "cache" / "folder_cache.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def names(self):
        return [path.name for path in self.cache.list_files(self.folder)]

    def test_empty_folder_and_new_file(self):
        self.assertEqual(self.names(), [])
        (self.folder / "b.txt").write_text("b", encoding="utf-8")
        (self.folder / "A.txt").write_text("a", encoding="utf-8")
        self.assertEqual(self.names(), ["A.txt", "b.txt"])

    def test_external_create_delete_and_rename(self):
        first = self.folder / "one.txt"
        first.write_text("123", encoding="utf-8")
        self.assertEqual(self.names(), ["one.txt"])

        second = self.folder / "two.txt"
        first.rename(second)
        self.assertEqual(self.names(), ["two.txt"])

        second.unlink()
        self.assertEqual(self.names(), [])

    def test_size_change_detected_when_directory_mtime_is_restored(self):
        item = self.folder / "file.txt"
        item.write_text("a", encoding="utf-8")
        self.names()
        previous_dir_mtime = self.folder.stat().st_mtime_ns

        item.write_text("a much longer payload", encoding="utf-8")
        os.utime(self.folder, ns=(previous_dir_mtime, previous_dir_mtime))

        self.assertEqual(self.names(), ["file.txt"])
        with sqlite3.connect(self.cache.database_path) as connection:
            row = connection.execute(
                "SELECT total_size_bytes FROM folder_cache WHERE folder_path = ?",
                (str(self.folder.resolve()),),
            ).fetchone()
        self.assertEqual(row[0], len("a much longer payload".encode("utf-8")))

    def test_rename_detected_when_directory_mtime_is_restored(self):
        original = self.folder / "old.txt"
        original.write_text("same", encoding="utf-8")
        self.names()
        previous_dir_mtime = self.folder.stat().st_mtime_ns

        original.rename(self.folder / "new.txt")
        os.utime(self.folder, ns=(previous_dir_mtime, previous_dir_mtime))

        self.assertEqual(self.names(), ["new.txt"])

    def test_excluded_temporary_files(self):
        (self.folder / "visible.txt").write_text("ok", encoding="utf-8")
        (self.folder / ".__file_manager__tmp.txt").write_text("tmp", encoding="utf-8")
        self.assertEqual(
            [p.name for p in self.cache.list_files(self.folder, excluded_prefix=".__file_manager__")],
            ["visible.txt"],
        )

    def test_persistence_across_instances(self):
        (self.folder / "persist.txt").write_text("ok", encoding="utf-8")
        self.cache.list_files(self.folder)
        reopened = FolderCache(self.cache.database_path)
        self.assertEqual([p.name for p in reopened.list_files(self.folder)], ["persist.txt"])

    def test_sync_refreshes_and_touches_directory(self):
        (self.folder / "before.txt").write_text("before", encoding="utf-8")
        self.cache.list_files(self.folder)
        (self.folder / "after.txt").write_text("after", encoding="utf-8")
        result = self.cache.sync_folder(self.folder)
        self.assertEqual([p.name for p in result], ["after.txt", "before.txt"])

    def test_clear_stale_entries(self):
        (self.folder / "old.txt").write_text("old", encoding="utf-8")
        self.cache.list_files(self.folder)
        with sqlite3.connect(self.cache.database_path) as connection:
            connection.execute(
                "UPDATE folder_cache SET last_access = ? WHERE folder_path = ?",
                (time.time() - 40 * 86400, str(self.folder.resolve())),
            )
        self.assertEqual(self.cache.clear_older_than(30), 1)
        self.assertEqual(self.cache.clear_older_than(30), 0)


if __name__ == "__main__":
    unittest.main()
