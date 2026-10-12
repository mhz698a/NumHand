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
    """Cache direct files while validating directory and file metadata on reads.

    The validation signature includes directory mtime, entry count, aggregate
    file size, and each visible file's name/size/mtime. The latter catches
    common external edits even when a directory timestamp is preserved.
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
                    last_access REAL NOT NULL,
                    entry_count INTEGER NOT NULL DEFAULT 0,
                    total_size_bytes INTEGER NOT NULL DEFAULT 0,
                    fingerprint TEXT NOT NULL DEFAULT ''
                )
            """)
            # Upgrade databases created by earlier versions without discarding cache data.
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(folder_cache)")
            }
            for name, declaration in (
                ("entry_count", "INTEGER NOT NULL DEFAULT 0"),
                ("total_size_bytes", "INTEGER NOT NULL DEFAULT 0"),
                ("fingerprint", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE folder_cache ADD COLUMN {name} {declaration}"
                    )
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

    @staticmethod
    def _snapshot(folder, excluded_prefix):
        """Return visible files and a stable metadata signature."""
        records = []
        total_size = 0
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name.startswith(excluded_prefix):
                    continue
                try:
                    if not entry.is_file(follow_symlinks=True):
                        continue
                    info = entry.stat(follow_symlinks=True)
                except (FileNotFoundError, PermissionError, OSError):
                    # Entries can disappear while an external process is editing.
                    continue
                records.append((entry.name, info.st_size, info.st_mtime_ns))
                total_size += info.st_size
        records.sort(key=lambda item: (item[0].casefold(), item[0]))
        fingerprint = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
        return records, len(records), total_size, fingerprint

    def list_files(self, folder, excluded_prefix=".__file_manager__"):
        folder = Path(folder).resolve()
        key = self._key(folder)
        directory_mtime_ns = folder.stat().st_mtime_ns
        records, entry_count, total_size, fingerprint = self._snapshot(folder, excluded_prefix)
        now = time.time()

        with self._connect() as connection:
            row = connection.execute(
                "SELECT directory_mtime_ns, files_json, entry_count, "
                "total_size_bytes, fingerprint FROM folder_cache WHERE folder_path = ?",
                (key,),
            ).fetchone()
            if row and (
                row[0] == directory_mtime_ns
                and row[2] == entry_count
                and row[3] == total_size
                and row[4] == fingerprint
            ):
                try:
                    cached_paths = [Path(item) for item in json.loads(row[1])]
                    if all(path.parent == folder for path in cached_paths):
                        connection.execute(
                            "UPDATE folder_cache SET last_access = ? WHERE folder_path = ?",
                            (now, key),
                        )
                        return cached_paths
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass

            paths = [folder / item[0] for item in records]
            serialized = json.dumps([str(path) for path in paths], ensure_ascii=False)
            connection.execute("""
                INSERT INTO folder_cache(
                    folder_path, directory_mtime_ns, files_json, last_access,
                    entry_count, total_size_bytes, fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET
                    directory_mtime_ns = excluded.directory_mtime_ns,
                    files_json = excluded.files_json,
                    last_access = excluded.last_access,
                    entry_count = excluded.entry_count,
                    total_size_bytes = excluded.total_size_bytes,
                    fingerprint = excluded.fingerprint
            """, (
                key, directory_mtime_ns, serialized, now,
                entry_count, total_size, fingerprint,
            ))
        return paths

    def sync_folder(self, folder, excluded_prefix=".__file_manager__"):
        """Refresh the persisted listing after an application-managed change."""
        folder = Path(folder).resolve()
        # Explicitly stamp successful changes where filesystem timestamp precision permits.
        try:
            os.utime(folder, None)
        except OSError:
            # Cache refresh remains useful on read-only/unsupported filesystems.
            pass
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
    
    def close(self):
        """Método de compatibilidad para cerrar recursos si fuera necesario."""
        pass
