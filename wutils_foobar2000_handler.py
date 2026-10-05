"""Handler for foobar2000 utilities."""
from PyQt6.QtWidgets import QMessageBox

from wutils_foobar2000 import is_file_from_list_playing
from pyutils.foobar2000_api import Foobar2000Api


class Foobar2000Handler:
    """Encapsulates foobar2000 UI interactions."""
    
    @staticmethod
    def check_playing_file(parent_window, model):
        """Check if a file from the loaded folder is currently playing.
        
        Args:
            parent_window: The parent QWidget for message dialogs
            model: The FileModel containing the list of files
        """
        try:
            api = Foobar2000Api()
            is_playing = is_file_from_list_playing(
                (file.path for file in model.files),
                api=api,
            )
        except Exception as exc:
            QMessageBox.warning(
                parent_window,
                "foobar2000",
                f"Could not connect to foobar2000: {exc}"
            )
            return

        if is_playing:
            current_file = api.current_path()
            QMessageBox.information(
                parent_window,
                "foobar2000",
                f"foobar2000 is playing: {current_file}"
            )
        else:
            QMessageBox.information(
                parent_window,
                "foobar2000",
                "foobar2000 is not playing a file from the loaded folder."
            )
