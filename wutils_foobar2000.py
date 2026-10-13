from __future__ import annotations

import ntpath
import os
from pathlib import Path

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QMessageBox, QAbstractItemView

from pyutils.foobar2000_api import Foobar2000Api


_UNSET = object()


def select_foobar2000_playing_file(parent, current_path=_UNSET) -> bool:
    """Selecciona y hace visible el archivo reproducido si está en el modelo."""
    if current_path is _UNSET:
        try:
            current_path = Foobar2000Api().current_path_playbackState()
        except Exception:
            # La API puede no estar disponible; no debe impedir abrir NumHand.
            return False

    if not current_path:
        return False

    current_normalized = ntpath.normcase(ntpath.normpath(os.fspath(current_path)))
    for row, file in enumerate(parent.model.files):
        file_path = ntpath.normcase(ntpath.normpath(os.fspath(file.path)))
        if file_path == current_normalized:
            index = parent.model.index(row, 0)
            selection = parent.file_list.selectionModel()
            selection.select(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            parent.file_list.setCurrentIndex(index)
            parent.file_list.scrollTo(
                index, QAbstractItemView.ScrollHint.PositionAtCenter
            )
            return True
    return False


def check_foobar2000_playing_file(parent) -> None:
    """Verifica si el archivo actual de foobar2000 está en la lista y notifica al usuario."""
    try:
        current_path = Foobar2000Api().current_path()

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
