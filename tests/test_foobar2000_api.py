import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pyutils.foobar2000_api import Foobar2000Api


class Foobar2000ApiCurrentPathTests(unittest.TestCase):
    def setUp(self):
        self.api = Foobar2000Api()
        self.api.player = Mock()

    # 🛠️ Añadimos patch para interceptar el requests.get que usa tu API internamente
    @patch('pyutils.foobar2000_api.requests.get')
    def test_returns_active_item_path_when_playing(self, mock_get):
        # 1. Configuramos el mock de self.api.player tal como lo tenías
        self.api.player.return_value = {
            "player": {
                "playbackState": "playing",
                "activeItem": {
                    "columns": [r"C:\\Music\\Current.mp3"],
                    "index": 3,
                    "playlistId": "p1",
                },
            }
        }

        # 2. Simulamos la respuesta HTTP que pide 'playlist_items' mediante requests
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "playlistItems": {
                "items": [
                    {"columns": [r"C:\\Music\\Current.mp3"]}
                ]
            }
        }
        mock_get.return_value = mock_response

        # 3. Ejecutamos la aserción
        self.assertEqual(self.api.current_path(), r"C:\\Music\\Current.mp3")
        self.api.player.assert_called_once_with(columns=["%path%"])

    def test_returns_none_when_paused(self):
        self.api.player.return_value = {
            "player": {
                "playbackState": "paused",
                "activeItem": {"columns": [r"C:\\Music\\Current.mp3"]},
            }
        }

        self.assertIsNone(self.api.current_path())

    def test_returns_none_when_active_item_has_no_path(self):
        self.api.player.return_value = {
            "player": {
                "playbackState": "playing",
                "activeItem": {"columns": []},
            }
        }

        self.assertIsNone(self.api.current_path())


if __name__ == "__main__":
    unittest.main()
