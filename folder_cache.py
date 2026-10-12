"""SQLite cache for direct file listings, isolated from UI and file operations."""
import json
import os
import sqlite3
import time
from pathlib import Path


def _default_cache_path():
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / ".local" / "share"
    directory = root / "NumHand" / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "folder_cache.db"


class FolderCache:
    """Caches a folder's immediate file list keyed by its normalized absolute path.

    Directory mtime is checked on every read. When it changes, the listing is
    rebuilt, so additions, removals and renames made outside the application
    are reflected on the next open/refresh.
    """

    def __init__(self, database_path=None):
        self.database_path = Path(database_path) if database_path else _default_cache_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS folder_cache (
                    folder_path TEXT PRIMARY KEY,
                    directory_mtime_ns INTEGER NOT NULL,
                    files_json TEXT NOT NULL,
                    last_access REAL NOT NULL
                )
            """)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_folder_cache_last_access "
                "ON folder_cache(last_access)"
            )

    def _connect(self):
        connection = sqlite3.connect(str(self.database_path), timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    @staticmethod
    def _key(folder):
        return str(Path(folder).resolve())

    def list_files(self, folder, excluded_prefix=".__file_manager__"):
        folder = Path(folder).resolve()
        stat = folder.stat()
        directory_mtime_ns = stat.st_mtime_ns
        key = self._key(folder)
        now = time.time()

        with self._connect() as connection:
            row = connection.execute(
                "SELECT directory_mtime_ns, files_json FROM folder_cache "
                "WHERE folder_path = ?", (key,)
            ).fetchone()
            if row and row[0] == directory_mtime_ns:
                try:
                    paths = [Path(item) for item in json.loads(row[1])]
                    if all(path.parent == folder for path in paths):
                        connection.execute(
                            "UPDATE folder_cache SET last_access = ? WHERE folder_path = ?",
                            (now, key)
                        )
                        return paths
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass

        paths = sorted(
            (
                entry for entry in folder.iterdir()
                if entry.is_file() and not entry.name.startswith(excluded_prefix)
            ),
            key=lambda path: path.name.lower()
        )
        serialized = json.dumps([str(path) for path in paths], ensure_ascii=False)
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO folder_cache(folder_path, directory_mtime_ns, files_json, last_access)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET
                    directory_mtime_ns = excluded.directory_mtime_ns,
                    files_json = excluded.files_json,
                    last_access = excluded.last_access
            """, (key, directory_mtime_ns, serialized, now))
        return paths

    def sync_folder(self, folder, excluded_prefix=".__file_manager__"):
        """Rebuild and persist the listing after an application-managed change.

        Directory entry changes normally update the filesystem mtime. Removing
        the old row first also guarantees a fresh listing on filesystems whose
        timestamp granularity is coarse.
        """
        folder = Path(folder).resolve()
        key = self._key(folder)
        with self._connect() as connection:
            connection.execute("DELETE FROM folder_cache WHERE folder_path = ?", (key,))
        return self.list_files(folder, excluded_prefix=excluded_prefix)

    def clear_older_than(self, days=30):
        cutoff = time.time() - max(0, days) * 24 * 60 * 60
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM folder_cache WHERE last_access < ?", (cutoff,)
            )
            return cursor.rowcount
