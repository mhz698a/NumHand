import sys
import tempfile
import shutil
import unittest
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox, QApplication

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from wutils_sysfiles import (
    rename_with_retry,
    get_unclean_enumeration_details,
    get_classify_selected_details,
)
from sysmove import get_mixed_numbering_details, check_folder_numbering
from sysfiles import FileUtils
from sys_folder_cache import FolderCache
from tag_ngex import download_ng_stream
from pyutils.wctime import setctime_blocking


class InteractionImprovementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_files(self, names, content=b"test"):
        paths = []
        for name in names:
            path = self.temp_dir / name
            path.write_bytes(content)
            paths.append(path)
        return paths

    # --- 1. Detail Text Helper Tests ---
    def test_get_unclean_enumeration_details_identifies_unclean_files(self):
        paths = self.create_files(["01. track1.mp3", "03. track3.mp3", "other.mp3"])
        details = get_unclean_enumeration_details(paths)
        self.assertIn("03. track3.mp3", details)
        self.assertIn("other.mp3", details)

    def test_get_classify_selected_details_identifies_strange_files(self):
        paths = [
            Path(p) for p in self.create_files(["01. track1.mp3", "prefix_05_track5.mp3"])
        ]
        details = get_classify_selected_details(paths)
        self.assertIn("prefix_05_track5.mp3", details)

    def test_get_mixed_numbering_details_identifies_inconsistent_files(self):
        paths = self.create_files(["01. a.mp3", "02. b.mp3", "001. c.mp3", "d.mp3"])
        details = get_mixed_numbering_details(paths)
        self.assertIn("001. c.mp3", details)
        self.assertIn("d.mp3", details)

    def test_check_folder_numbering_sets_detailed_text_on_mixed(self):
        self.create_files(["01. a.mp3", "001. b.mp3"])
        parent = SimpleNamespace(folder=self.temp_dir)
        with patch("sysmove.QMessageBox") as mock_msgbox_cls:
            mock_inst = MagicMock()
            mock_msgbox_cls.return_value = mock_inst
            check_folder_numbering(parent, None)
            mock_inst.setDetailedText.assert_called_once()
            detailed_arg = mock_inst.setDetailedText.call_args[0][0]
            self.assertIn("001. b.mp3", detailed_arg)

    # --- 2. Retry Delay 50% Increase Tests ---
    def test_retry_delays_increased_by_50_percent(self):
        sig_rename = inspect.signature(rename_with_retry)
        self.assertEqual(sig_rename.parameters["delay"].default, 3.0)

        fu = FileUtils()
        sig_read = inspect.signature(fu._read_backup_with_retry)
        self.assertEqual(sig_read.parameters["delay"].default, 1.5)

        sig_unlink = inspect.signature(fu._unlink_backup_with_retry)
        self.assertEqual(sig_unlink.parameters["delay"].default, 1.5)

        sig_ctime = inspect.signature(setctime_blocking)
        self.assertEqual(sig_ctime.parameters["retry"].default, 1.35)

    # --- 3. Cache Check & Invalidation Tests ---
    def test_folder_cache_invalidates_and_updates_on_size_or_count_mismatch(self):
        db_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(db_dir, ignore_errors=True))
        db_path = db_dir / "cache.db"
        cache = FolderCache(database_path=db_path)

        f1 = self.temp_dir / "file1.txt"
        f1.write_bytes(b"hello")

        # Initial load populates cache
        res1 = cache.list_files(self.temp_dir)
        self.assertEqual(len(res1), 1)

        # Modify file size (mismatch in aggregate size)
        f1.write_bytes(b"hello world long content")

        # Next list_files should detect mismatch, invalidate, and update cache
        res2 = cache.list_files(self.temp_dir)
        self.assertEqual(len(res2), 1)

        # Add a new file (mismatch in file count)
        f2 = self.temp_dir / "file2.txt"
        f2.write_bytes(b"another")

        res3 = cache.list_files(self.temp_dir)
        self.assertEqual(len(res3), 2)


if __name__ == "__main__":
    unittest.main()
