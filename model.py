import re
from pathlib import Path
from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt
)

"""
{
    "path": Path(...),
    "name": "...",
}
"""

class FileEntry:
    def __init__(self, path_or_entry):
        if isinstance(path_or_entry, FileEntry):
            self.path = path_or_entry.path
            self.original_path = path_or_entry.original_path
            self.original_name = path_or_entry.original_name
            self.clean_name = path_or_entry.clean_name
        else:
            self.path = Path(path_or_entry)
            self.original_path = self.path
            self.original_name = self.path.name
            self.clean_name = re.sub(
                r"^\d+(?:_|\.\s*)",
                "",
                self.original_name
            )

class FileModel(QAbstractListModel):

    def __init__(self):
        super().__init__()
        self.files = []

    def rowCount(self, parent=QModelIndex()):
        return len(self.files)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def data(self, index, role):
        if not index.isValid():
            return None

        file = self.files[index.row()]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            number = index.row() + 1
            return f"{number:03d}   {file.path.name}"
        return None

    def set_files(self, files):
        self.beginResetModel()
        self.files = [
            FileEntry(file) if not isinstance(file, FileEntry) else file
            for file in files
        ]
        self.endResetModel()

    def move_file(self, source_row, target_row):
        if source_row == target_row:
            return

        qt_destination = target_row

        if source_row < target_row:
            qt_destination = target_row + 1

        self.beginMoveRows(
            QModelIndex(),
            source_row,
            source_row,
            QModelIndex(),
            qt_destination
        )

        file = self.files.pop(source_row)

        self.files.insert(
            target_row,
            file
        )

        self.endMoveRows()
