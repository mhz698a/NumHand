import tempfile
import unittest
from pathlib import Path

from folder_cache import FolderCache, windows_explorer_sort_key


class WindowsExplorerSortTests(unittest.TestCase):
    def test_sort_key_uses_natural_numeric_order(self):
        names = ["file10.txt", "file2.txt", "file1.txt"]
        self.assertEqual(
            sorted(names, key=windows_explorer_sort_key),
            ["file1.txt", "file2.txt", "file10.txt"],
        )

    def test_folder_cache_returns_naturally_sorted_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "media"
            folder.mkdir()
            cache = FolderCache(root / "cache" / "folder_cache.db")
            try:
                for name in ("file10.txt", "file2.txt", "file1.txt"):
                    (folder / name).write_text(name, encoding="utf-8")

                self.assertEqual(
                    [path.name for path in cache.list_files(folder)],
                    ["file1.txt", "file2.txt", "file10.txt"],
                )
                # The cache-hit path must retain the same order as a fresh scan.
                self.assertEqual(
                    [path.name for path in cache.list_files(folder)],
                    ["file1.txt", "file2.txt", "file10.txt"],
                )
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
