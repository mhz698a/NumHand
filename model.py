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
        self.original_clean_name = self.clean_name
        self.original_row = None
        self.pending_name = None
    

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
            return file.pending_name or file.path.name

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

        if role == Qt.ItemDataRole.EditRole:
            return self.set_pending_name(index.row(), str(value).strip())

        return False

    def set_pending_name(self, row, new_base_name):
        """Cambia el nombre mostrado sin tocar el archivo en disco."""
        if row < 0 or row >= len(self.files) or not new_base_name:
            return False

        file = self.files[row]
        current_name = file.path.name
        suffix = Path(current_name).suffix
        name_body = current_name[:-len(suffix)] if suffix else current_name

        prefix_match = re.match(r"^(\d+(?:_|\.\s*))", name_body)
        prefix = prefix_match.group(1) if prefix_match else ""

        new_prefix_match = re.match(r"^(\d+(?:_|\.\s*))", new_base_name)
        if new_prefix_match:
            prefix = new_prefix_match.group(1)
            new_base_name = new_base_name[len(prefix):].strip()

        if not new_base_name:
            return False

        file.clean_name = f"{new_base_name}{suffix}"
        file.pending_name = f"{prefix}{file.clean_name}"

        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, 0),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
        )
        return True

    def set_files(self, files):
        self.beginResetModel()
        self.files = [
            FileEntry(file)
            for file in files
        ]
        for row, file in enumerate(self.files):
            file.original_row = row
        self.endResetModel()

    def set_all_checked(self, checked):
        """Marca o desmarca todos los archivos."""
        for row, file in enumerate(self.files):
            if file.is_checked == checked:
                continue
            file.is_checked = checked
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])

    def invert_selection(self):
        """Invierte el estado del checkbox de todos los archivos."""
        for row, file in enumerate(self.files):
            file.is_checked = not file.is_checked
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])

    def checked_files(self):
        """Devuelve las entradas de archivo actualmente marcadas."""
        return [file for file in self.files if file.is_checked]

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

        if self.files:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self.files) - 1, 0),
                []
            )