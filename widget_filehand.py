from PyQt6.QtWidgets import QStyledItemDelegate, QStyle, QLineEdit, QAbstractItemView
from PyQt6.QtCore import (Qt)
from pathlib import Path


class FileDelegate(QStyledItemDelegate):

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, option.palette.highlight())

        # Dibujar icono de arrastre
        painter.drawText(
            rect.x() + 8,
            rect.y(),
            30,
            rect.height(),
            Qt.AlignmentFlag.AlignVCenter,
            "☷"
        )

        view = option.widget
        is_editing = False
        if isinstance(view, QAbstractItemView):
            is_editing = view.indexWidget(index) is not None

        if is_editing:
            # Si se está editando, mostrar únicamente el número de índice
            number_str = f"{index.row() + 1:03d}   "
            painter.drawText(
                rect.x() + 45,
                rect.y(),
                rect.width() - 45,
                rect.height(),
                Qt.AlignmentFlag.AlignVCenter,
                number_str
            )
        else:
            # En estado normal, dibujar el texto completo (número + nombre de archivo)
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
        # SOLUCIÓN AL DESAJUSTE: Forzar un fondo sólido y remover paddings nativos del OS
        editor.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e; /* Ajusta este color al fondo de tu app */
                color: white;
                border: 1px solid #3a3a3a;
                padding: 0px;
                margin: 0px;
            }
        """)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        # Posicionar el editor después del icono y el número de índice
        # Se redujo levemente el offset en X (de 90 a 85) para coincidir con tu margen de dibujo.
        editor.setGeometry(
            rect.x() + 85,
            rect.y() + 4,
            rect.width() - 95,
            rect.height() - 8
        )

    def setEditorData(self, editor, index):
        if not self.main_window or not hasattr(self.main_window, 'model'):
            return

        file_entry = self.main_window.model.files[index.row()]
        # Nombre sin prefijo numérico inicial y sin extensión para el renombrado rápido
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
