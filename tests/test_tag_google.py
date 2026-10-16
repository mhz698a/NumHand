import unittest
from unittest.mock import patch

from tag_google import (
    build_google_search_url,
    build_song_search_query,
    open_song_search,
)


class TagGoogleTests(unittest.TestCase):
    def test_filename_query_with_lyrics(self):
        self.assertEqual(
            build_song_search_query(
                filename="Night Drive",
                search_by="filename",
                qualifier="lyrics",
            ),
            "Night Drive lyrics",
        )

    def test_title_artist_query_with_release_date(self):
        self.assertEqual(
            build_song_search_query(
                title="Night Drive",
                artist="Example Artist",
                search_by="title_artist",
                qualifier="release date",
            ),
            "Night Drive - Example Artist release date",
        )

    def test_missing_artist_does_not_leave_separator(self):
        self.assertEqual(
            build_song_search_query(
                title="Night Drive",
                artist="",
                search_by="title_artist",
            ),
            "Night Drive",
        )

    def test_google_url_encodes_query(self):
        self.assertEqual(
            build_google_search_url("Night Drive - Example Artist lyrics"),
            "https://www.google.com/search?q=Night+Drive+-+Example+Artist+lyrics",
        )

    @patch("tag_google.webbrowser.open")
    def test_open_song_search_opens_browser_and_returns_url(self, open_browser):
        url = open_song_search(
            filename="A Song",
            search_by="filename",
            qualifier="release date",
        )
        self.assertEqual(
            url,
            "https://www.google.com/search?q=A+Song+release+date",
        )
        open_browser.assert_called_once_with(url, new=2)

    def test_empty_query_is_not_opened(self):
        with patch("tag_google.webbrowser.open") as open_browser:
            self.assertIsNone(open_song_search(filename=""))
            open_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
