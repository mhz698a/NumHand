"""SQLite cache for direct file listings, isolated from UI and file operations."""
import json
import os
import re
from functools import cmp_to_key
import sqlite3
import stat
import time
from pathlib import Path


def windows_explorer_sort_key(filename):
    """Clave de orden natural similar al Explorador de Windows.

    Compara los bloques numéricos como números, por lo que file2 precede
    a file10. El desempate conserva un orden estable entre mayúsculas y
    minúsculas y entre representaciones numéricas equivalentes.
    """
    parts = re.split(r"(\d+)", str(filename).casefold())
    natural_parts = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in parts
    )
    return natural_parts, str(filename).casefold(), str(filename)


def _compare_explorer_names(left, right):
    """Use the native Windows Explorer comparator when available."""
    if os.name == "nt":
        import ctypes
        compare = ctypes.windll.shlwapi.StrCmpLogicalW
        compare.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        compare.restype = ctypes.c_int
        return compare(str(left), str(right))

    left_key = windows_explorer_sort_key(left)
    right_key = windows_explorer_sort_key(right)
    return (left_key > right_key) - (left_key < right_key)


def _contains_surrogate(value):
    return any(0xD800 <= ord(char) <= 0xDFFF for char in str(value))


def _sort_names(items, get_name):
    """Sort normally through Explorer; fall back for names Qt/UTF-8 cannot encode."""
    names = [str(get_name(item)) for item in items]
    if os.name == "nt" and not any(_contains_surrogate(name) for name in names):
        items.sort(key=cmp_to_key(lambda left, right: _compare_explorer_names(
            get_name(left), get_name(right)
        )))
    else:
        # Keep the comparator consistent for the whole collection; don't mix
        # native and Python comparisons when one filename has an isolated surrogate.
        items.sort(key=lambda item: windows_explorer_sort_key(get_name(item)))
    return items


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
        key = str(Path(folder).resolve())
        # sqlite3 cannot UTF-8 encode a path containing isolated UTF-16 surrogates.
        # Use a reversible ASCII key only for that unusual case; normal cache keys
        # remain unchanged for backward compatibility.
        if _contains_surrogate(key):
            return "surrogate-path:" + key.encode("utf-8", "surrogatepass").hex()
        return key

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
        _sort_names(records, lambda record: record[0])
        # ASCII-escape unusual code points so SQLite never has to encode a
        # surrogate-containing filename/fingerprint as UTF-8.
        fingerprint = json.dumps(records, ensure_ascii=True, separators=(",", ":"))
        return records, len(records), total_size, fingerprint

    def get_cached_files(self, folder, excluded_prefix=".__file_manager__"):
        """Return a cached listing without enumerating the directory.

        The directory timestamp is a cheap invalidation signal for additions,
        removals, and renames. Missing cached entries also invalidate the fast
        path. Use list_files() or an explicit UI refresh for a full metadata scan.
        """
        folder = Path(folder).resolve()
        try:
            directory_mtime_ns = folder.stat().st_mtime_ns
        except OSError:
            return None

        key = self._key(folder)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT directory_mtime_ns, files_json FROM folder_cache "
                "WHERE folder_path = ?",
                (key,),
            ).fetchone()
            if row and row[0] == directory_mtime_ns:
                connection.execute(
                    "UPDATE folder_cache SET last_access = ? WHERE folder_path = ?",
                    (time.time(), key),
                )

        if not row or row[0] != directory_mtime_ns:
            return None

        try:
            paths = [Path(item) for item in json.loads(row[1])]
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

        for path in paths:
            if path.parent != folder or path.name.startswith(excluded_prefix):
                return None
            try:
                if not path.is_file():
                    return None
            except OSError:
                return None

        _sort_names(paths, lambda path: path.name)
        return paths

    def _cache_known_files(self, folder, files, excluded_prefix, progress_callback=None):
        """Persist a caller-supplied listing without scanning the directory."""
        records = []
        total_size = 0
        files = list(files)
        total_files = len(files)
        for index, value in enumerate(files, start=1):
            path = Path(value)
            if not path.is_absolute():
                path = folder / path
            if path.parent.resolve() != folder or path.name.startswith(excluded_prefix):
                continue
            try:
                info = path.stat()
            except (FileNotFoundError, PermissionError, OSError):
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            records.append((path.name, info.st_size, info.st_mtime_ns))
            total_size += info.st_size
            if progress_callback is not None:
                progress_callback(index, total_files, path)

        _sort_names(records, lambda record: record[0])
        fingerprint = json.dumps(records, ensure_ascii=True, separators=(",", ":"))
        paths = [folder / item[0] for item in records]
        serialized = json.dumps([str(path) for path in paths], ensure_ascii=True)
        directory_mtime_ns = folder.stat().st_mtime_ns
        now = time.time()
        key = self._key(folder)

        with self._connect() as connection:
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
                len(records), total_size, fingerprint,
            ))
        return paths

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
            if row:
                cached_mtime, cached_json, cached_entry_count, cached_total_size, cached_fingerprint = row
                # Verificar si el número de archivos o el tamaño total de archivos es distinto
                if cached_entry_count != entry_count or cached_total_size != total_size:
                    # Anular la cache existente por discrepancia en número de archivos o tamaño total
                    connection.execute("DELETE FROM folder_cache WHERE folder_path = ?", (key,))
                elif (
                    cached_mtime == directory_mtime_ns
                    and cached_fingerprint == fingerprint
                ):
                    try:
                        cached_paths = [Path(item) for item in json.loads(cached_json)]
                        _sort_names(cached_paths, lambda path: path.name)
                        if all(path.parent == folder for path in cached_paths):
                            connection.execute(
                                "UPDATE folder_cache SET last_access = ? WHERE folder_path = ?",
                                (now, key),
                            )
                            return cached_paths
                    except (TypeError, ValueError, json.JSONDecodeError):
                        pass

            paths = [folder / item[0] for item in records]
            serialized = json.dumps([str(path) for path in paths], ensure_ascii=True)
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

    def sync_folder(
        self,
        folder,
        excluded_prefix=".__file_manager__",
        files=None,
        progress_callback=None,
    ):
        """Refresh the listing after a managed change.

        When the caller already knows the resulting paths, persist those paths
        directly and only stat the supplied files. Otherwise perform a full scan.
        """
        folder = Path(folder).resolve()
        # Explicitly stamp successful changes where filesystem timestamp precision permits.
        try:
            os.utime(folder, None)
        except OSError:
            # Cache refresh remains useful on read-only/unsupported filesystems.
            pass

        if files is not None:
            return self._cache_known_files(
                folder,
                files,
                excluded_prefix,
                progress_callback=progress_callback,
            )

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
