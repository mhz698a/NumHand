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
