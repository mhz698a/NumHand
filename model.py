import re
from pathlib import Path
from PyQt6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt
)


class FileEntry:
    def __init__(self, path, is_checked=False):       # 1. Cambiado a False
        self.path = Path(path)
        self.original_path = self.path
        self.original_name = self.path.name
        self.is_checked = is_checked

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
            | Qt.ItemFlag.ItemIsUserCheckable
        )

    def data(self, index, role):
        if not index.isValid():
            return None

        file = self.files[index.row()]

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            # 2. Retorna solo el nombre para evitar duplicar el número del delegate
            return file.path.name

        if role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if file.is_checked else Qt.CheckState.Unchecked

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        file = self.files[index.row()]

        if role == Qt.ItemDataRole.CheckStateRole:
            file.is_checked = (value == Qt.CheckState.Checked)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True

        return False

    def set_files(self, files):
        self.beginResetModel()
        self.files = [
            FileEntry(file)
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