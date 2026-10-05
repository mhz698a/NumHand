from __future__ import annotations

import ntpath
import os
from os import PathLike
from typing import Iterable
from pathlib import Path

from PyQt6.QtWidgets import (QMessageBox)

from pyutils.foobar2000_api import Foobar2000Api


def is_file_from_list_playing(
    files: Iterable[str | PathLike[str]],
    api: Foobar2000Api | None = None,
) -> bool:
    """Return whether the currently playing foobar2000 file is in *files*."""
    current_path = (api or Foobar2000Api()).current_path()
    if current_path is None:
        return False

    current_normalized = ntpath.normcase(ntpath.normpath(current_path))
    return any(
        ntpath.normcase(ntpath.normpath(os.fspath(file))) == current_normalized
        for file in files
    )

def check_foobar2000_playing_file(parent):
    try:
        api = Foobar2000Api()
        is_playing = is_file_from_list_playing(
            (file.path for file in parent.model.files),
            api=api,
        )
    except Exception as exc:
        QMessageBox.warning(
            parent,
            "foobar2000", f"Could not connect to foobar2000: {exc}"
        )
        return

    if is_playing:
        current_file = api.current_path()
        QMessageBox.information(
            parent,
            "foobar2000", f"Playing: {Path(current_file).stem}"
        )
    else:
        QMessageBox.information(
            parent,
            "foobar2000", "foobar2000 is not playing a file from this folder"
        )
