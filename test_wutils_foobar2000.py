import unittest
from pathlib import Path

from wutils_foobar2000 import is_file_from_list_playing


class FakeFoobar2000Api:
    def __init__(self, current_path):
        self._current_path = current_path

    def current_path(self):
        return self._current_path


class Foobar2000PlayingFileTests(unittest.TestCase):
    def test_returns_true_when_current_file_is_in_list(self):
        api = FakeFoobar2000Api(r"C:\Music\001. track.mp3")

        self.assertTrue(
            is_file_from_list_playing(
                [Path(r"C:\Music\001. track.mp3")],
                api=api,
            )
        )

    def test_returns_false_when_current_file_is_not_in_list(self):
        api = FakeFoobar2000Api(r"C:\Music\001. track.mp3")

        self.assertFalse(
            is_file_from_list_playing(
                [Path(r"C:\Music\002. track.mp3")],
                api=api,
            )
        )

    def test_returns_false_when_nothing_is_playing(self):
        api = FakeFoobar2000Api(None)

        self.assertFalse(
            is_file_from_list_playing(
                [Path(r"C:\Music\001. track.mp3")],
                api=api,
            )
        )

    def test_normalizes_path_case_and_separators(self):
        api = FakeFoobar2000Api(r"C:\Music\001. track.mp3")

        self.assertTrue(
            is_file_from_list_playing(
                [Path("c:/music/001. track.mp3")],
                api=api,
            )
        )


if __name__ == "__main__":
    unittest.main()
