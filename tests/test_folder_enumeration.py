import sys
import tempfile
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from sysfiles import FileUtils
from wutils_sysfiles import is_folder_cleanly_enumerated


class FolderEnumerationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_files(self, names):
        paths = []
        for name in names:
            path = self.temp_dir / name
            path.write_bytes(b"test")
            paths.append(path)
        return paths

    def test_accepts_contiguous_enumeration_independent_of_visual_order(self):
        paths = self.create_files([
            "01. first.mp3",
            "02. second.mp3",
            "03. third.mp3",
        ])

        self.assertTrue(is_folder_cleanly_enumerated(paths[::-1]))

    def test_rejects_missing_numbers(self):
        paths = self.create_files([
            "01. first.mp3",
            "03. third.mp3",
        ])

        self.assertFalse(is_folder_cleanly_enumerated(paths))

    def test_rejects_unnumbered_files(self):
        paths = self.create_files(["first.mp3", "second.mp3"])

        self.assertFalse(is_folder_cleanly_enumerated(paths))

    def test_accepts_three_digit_enumeration_for_one_hundred_files(self):
        paths = self.create_files([
            f"{index:03d}. track{index}.mp3"
            for index in range(1, 101)
        ])

        self.assertTrue(is_folder_cleanly_enumerated(paths))

    def test_apply_order_skips_confirmation_for_correctly_enumerated_folder(self):
        paths = self.create_files(["01. first.mp3", "02. second.mp3"])
        parent = SimpleNamespace(folder=self.temp_dir)
        model = SimpleNamespace(
            files=[
                SimpleNamespace(path=path, clean_name=path.name)
                for path in paths
            ],
            layoutChanged=MagicMock(),
        )
        file_utils = FileUtils()
        file_utils.thread_pool = MagicMock()
        file_utils.check_files_locked = MagicMock(return_value=False)

        with patch("sysfiles.QMessageBox.question") as question:
            with patch("sysfiles.DualProgressDialog") as progress_dialog:
                with patch("sysfiles.ApplyOrderTask") as task_class:
                    file_utils.apply_order(parent, model)

        question.assert_not_called()
        file_utils.check_files_locked.assert_called_once_with(parent, paths)
        task_class.assert_called_once_with(parent.folder, model.files, file_utils)
        progress_dialog.return_value.show.assert_called_once()
        file_utils.thread_pool.start.assert_called_once_with(task_class.return_value)

    def test_apply_order_cancels_when_user_declines_enumeration(self):
        path = self.create_files(["track.mp3"])[0]
        parent = SimpleNamespace(folder=self.temp_dir)
        model = SimpleNamespace(
            files=[SimpleNamespace(path=path, clean_name="track.mp3")],
            layoutChanged=MagicMock(),
        )
        file_utils = FileUtils()
        file_utils.thread_pool = MagicMock()
        file_utils.check_files_locked = MagicMock(return_value=False)

        with patch(
            "sysfiles.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            file_utils.apply_order(parent, model)

        question.assert_called_once()
        file_utils.check_files_locked.assert_not_called()
        file_utils.thread_pool.start.assert_not_called()

    def test_apply_order_continues_when_user_accepts_enumeration(self):
        path = self.create_files(["track.mp3"])[0]
        parent = SimpleNamespace(folder=self.temp_dir)
        model = SimpleNamespace(
            files=[SimpleNamespace(path=path, clean_name="track.mp3")],
            layoutChanged=MagicMock(),
        )
        file_utils = FileUtils()
        file_utils.thread_pool = MagicMock()
        file_utils.check_files_locked = MagicMock(return_value=False)

        with patch(
            "sysfiles.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question:
            with patch("sysfiles.DualProgressDialog") as progress_dialog:
                with patch("sysfiles.ApplyOrderTask") as task_class:
                    file_utils.apply_order(parent, model)

        question.assert_called_once()
        file_utils.check_files_locked.assert_called_once_with(parent, [path])
        task_class.assert_called_once_with(parent.folder, model.files, file_utils)
        progress_dialog.return_value.show.assert_called_once()
        file_utils.thread_pool.start.assert_called_once_with(task_class.return_value)


if __name__ == "__main__":
    unittest.main()
