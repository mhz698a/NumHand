import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wutils_foobar2000 import select_foobar2000_playing_file


class Foobar2000PlayingFileSelectionTests(unittest.TestCase):
    def setUp(self):
        self.parent = Mock()
        self.parent.model.files = [
            Mock(path=Path(r"C:\\Music\\first.flac")),
            Mock(path=Path(r"C:\\Music\\Current.mp3")),
        ]
        self.parent.model.index.side_effect = lambda row, column: (row, column)
        self.parent.file_list.selectionModel.return_value = Mock()

    def test_selects_and_scrolls_to_matching_playing_file(self):
        selected = select_foobar2000_playing_file(
            self.parent, r"c:\\music\\CURRENT.mp3"
        )

        self.assertTrue(selected)
        self.parent.model.index.assert_called_once_with(1, 0)
        self.parent.file_list.selectionModel.return_value.select.assert_called_once()
        self.parent.file_list.setCurrentIndex.assert_called_once_with((1, 0))
        self.parent.file_list.scrollTo.assert_called_once()

    def test_returns_false_when_playing_file_is_not_in_list(self):
        selected = select_foobar2000_playing_file(
            self.parent, r"C:\\Music\\missing.mp3"
        )

        self.assertFalse(selected)
        self.parent.file_list.setCurrentIndex.assert_not_called()
        self.parent.file_list.scrollTo.assert_not_called()

    def test_returns_false_when_nothing_is_playing(self):
        self.assertFalse(select_foobar2000_playing_file(self.parent, None))
        self.parent.file_list.setCurrentIndex.assert_not_called()


if __name__ == "__main__":
    unittest.main()
