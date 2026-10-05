from __future__ import annotations

import ntpath
import os
from os import PathLike
from typing import Iterable

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
