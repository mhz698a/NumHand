import unittest
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, Qt

from model import FileModel


class FileModelSelectionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.model = FileModel()
        self.model.set_files([
            Path("001. first.txt"),
            Path("002. second.txt"),
            Path("003. third.txt"),
        ])

    def test_checkbox_state_can_be_toggled(self):
        index = self.model.index(1, 0)

        self.assertEqual(
            self.model.data(index, Qt.ItemDataRole.CheckStateRole),
            Qt.CheckState.Unchecked,
        )

        self.assertTrue(
            self.model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        )
        self.assertEqual(
            self.model.data(index, Qt.ItemDataRole.CheckStateRole),
            Qt.CheckState.Checked,
        )

    def test_select_and_unselect_all(self):
        self.model.set_all_checked(True)
        self.assertEqual(len(self.model.checked_files()), 3)

        self.model.set_all_checked(False)
        self.assertEqual(len(self.model.checked_files()), 0)

    def test_rename_is_deferred_until_apply(self):
        index = self.model.index(0, 0)

        self.assertTrue(
            self.model.setData(
                index,
                "renamed",
                Qt.ItemDataRole.EditRole,
            )
        )

        file = self.model.files[0]
        self.assertEqual(file.path.name, "001. first.txt")
        self.assertEqual(file.original_name, "001. first.txt")
        self.assertEqual(file.original_clean_name, "first.txt")
        self.assertEqual(file.clean_name, "renamed.txt")
        self.assertEqual(file.pending_name, "001. renamed.txt")
        self.assertEqual(
            self.model.data(index, Qt.ItemDataRole.DisplayRole),
            "001. renamed.txt",
        )

    def test_move_marks_new_position(self):
        self.model.move_file(0, 2)

        moved_file = self.model.files[2]
        self.assertEqual(moved_file.original_row, 0)
        self.assertEqual(moved_file.path.name, "001. first.txt")

        self.assertEqual(self.model.files[0].original_row, 1)
        self.assertEqual(self.model.files[1].original_row, 2)

    def test_rename_and_move_are_tracked_independently(self):
        self.model.setData(
            self.model.index(0, 0),
            "renamed",
            Qt.ItemDataRole.EditRole,
        )
        self.model.move_file(0, 2)

        file = self.model.files[2]
        self.assertNotEqual(file.clean_name, file.original_clean_name)
        self.assertNotEqual(file.original_row, 2)

    def test_invert_selection(self):
        self.model.setData(
            self.model.index(0, 0),
            Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )
        self.model.invert_selection()

        self.assertEqual(
            [file.path.name for file in self.model.checked_files()],
            ["002. second.txt", "003. third.txt"],
        )


if __name__ == "__main__":
    unittest.main()
