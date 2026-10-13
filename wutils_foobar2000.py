from __future__ import annotations

import ntpath
import os
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

from pyutils.foobar2000_api import Foobar2000Api


def check_foobar2000_playing_file(parent) -> None:
    """Verifica si el archivo actual de foobar2000 está en la lista de archivos del modelo y notifica al usuario."""
    try:
        api = Foobar2000Api()
        current_path = api.current_path()
        
        if not current_path:
            QMessageBox.information(
                parent, "foobar2000", "foobar2000 is not playing a file"
            )
            return

        current_normalized = ntpath.normcase(ntpath.normpath(current_path))
        files = (file.path for file in parent.model.files)
        
        is_playing = any(
            ntpath.normcase(ntpath.normpath(os.fspath(file))) == current_normalized
            for file in files
        )

        if is_playing:
            QMessageBox.information(
                parent, "foobar2000", f"Playing: {Path(current_path).stem}"
            )
        else:
            QMessageBox.information(
                parent, "foobar2000", "foobar2000 is not playing a file from this folder"
            )
            
    except Exception as exc:
        QMessageBox.warning(
            parent, "foobar2000", f"Could not connect to foobar2000: {exc}"
        )