from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QLineEdit  # type: ignore
from PyQt6.QtCore import (  # type: ignore
    Qt, QEvent
)
from pathlib import Path


class FileDelegate(QStyledItemDelegate):

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(
                rect,
                option.palette.highlight()
            )

        painter.drawText(
            rect.x() + 8,
            rect.y(),
            30,
            rect.height(),
            Qt.AlignmentFlag.AlignVCenter,
            "☷"
        )

        painter.drawText(
            rect.x() + 45,
            rect.y(),
            rect.width() - 45,
            rect.height(),
            Qt.AlignmentFlag.AlignVCenter,
            index.data()
        )

        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(40)
        return size

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setContentsMargins(0, 0, 0, 0)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        # Posicionar el editor justo sobre el texto del nombre
        editor.setGeometry(
            rect.x() + 45,
            rect.y() + 4,
            rect.width() - 50,
            rect.height() - 8
        )

    def setEditorData(self, editor, index):
        if not self.main_window or not hasattr(self.main_window, 'model'):
            return

        file_entry = self.main_window.model.files[index.row()]
        path = file_entry.path
        # Nombre base sin extensión
        base_name_without_ext = path.stem

        # Si tiene prefijo de numeración (p. ej. "001. " o "01_"), obtener solo el nombre limpio sin extensión
        clean_base_name = Path(file_entry.clean_name).stem
        editor.setText(clean_base_name)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        new_base_name = editor.text().strip()
        if not new_base_name:
            return

        if self.main_window and hasattr(self.main_window, 'file_utils'):
            self.main_window.file_utils.rename_single_file(
                self.main_window, model, index.row(), new_base_name
            )
