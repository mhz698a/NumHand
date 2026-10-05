from PyQt6.QtWidgets import (
    QStyledItemDelegate, QStyle, QLineEdit, QAbstractItemView, QStyleOptionButton
)
from PyQt6.QtCore import Qt, QRect, QEvent
from PyQt6.QtGui import QColor
from pathlib import Path


class FileDelegate(QStyledItemDelegate):

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window

    def _get_checkbox_rect(self, rect: QRect) -> QRect:
        """Calcula la posición y tamaño del checkbox."""
        cb_size = 18
        y = rect.y() + (rect.height() - cb_size) // 2
        return QRect(rect.x() + 85, y, cb_size, cb_size)

    def paint(self, painter, option, index):
        painter.save()
        rect = option.rect

        file_entry = None
        if self.main_window and hasattr(self.main_window, "model"):
            row = index.row()
            if 0 <= row < len(self.main_window.model.files):
                file_entry = self.main_window.model.files[row]

        if file_entry is not None:
            name_changed = file_entry.clean_name != file_entry.original_clean_name
            position_changed = file_entry.original_row != index.row()

            if name_changed and position_changed:
                painter.fillRect(rect, QColor("#f8c8dc"))
            elif name_changed:
                painter.fillRect(rect, QColor("#ffe0b2"))
            elif position_changed:
                painter.fillRect(rect, QColor("#fff3b0"))

        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, option.palette.highlight())

        # 1. Icono de arrastre (x = 8)
        painter.drawText(
            rect.x() + 8,
            rect.y(),
            30,
            rect.height(),
            Qt.AlignmentFlag.AlignVCenter,
            "☷"
        )

        # 2. Número de índice (x = 45)
        number_str = f"{index.row() + 1:03d}"
        painter.drawText(
            rect.x() + 45,
            rect.y(),
            35,
            rect.height(),
            Qt.AlignmentFlag.AlignVCenter,
            number_str
        )

        # 3. Dibujar Checkbox (x = 85)
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        cb_opt = QStyleOptionButton()
        cb_opt.rect = self._get_checkbox_rect(rect)
        cb_opt.state = QStyle.StateFlag.State_Enabled

        if check_state == Qt.CheckState.Checked:
            cb_opt.state |= QStyle.StateFlag.State_On
        else:
            cb_opt.state |= QStyle.StateFlag.State_Off

        view = option.widget
        style = view.style() if view else QStyle()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorCheckBox, cb_opt, painter, view)

        # 4. Dibujar texto del archivo (desplazado a x = 115)
        is_editing = False
        if isinstance(view, QAbstractItemView):
            is_editing = view.indexWidget(index) is not None

        if not is_editing:
            painter.drawText(
                rect.x() + 115,
                rect.y(),
                rect.width() - 115,
                rect.height(),
                Qt.AlignmentFlag.AlignVCenter,
                index.data()
            )

        painter.restore()

    def editorEvent(self, event, model, option, index):
        # 1. Bloquear renombrado si el doble clic ocurre a la izquierda del texto (x < 115)
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if event.pos().x() < option.rect.x() + 115:
                return True

        # 2. Capturar el clic sobre la zona del checkbox
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            cb_rect = self._get_checkbox_rect(option.rect)
            if cb_rect.contains(event.pos()):
                current_state = index.data(Qt.ItemDataRole.CheckStateRole)
                new_state = (
                    Qt.CheckState.Unchecked
                    if current_state == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                return True

        return super().editorEvent(event, model, option, index)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(40)
        return size

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #3a3a3a;
                padding: 0px;
                margin: 0px;
            }
        """)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        rect = option.rect
        editor.setGeometry(
            rect.x() + 115,
            rect.y() + 4,
            rect.width() - 125,
            rect.height() - 8
        )

    def setEditorData(self, editor, index):
        if not self.main_window or not hasattr(self.main_window, 'model'):
            return

        file_entry = self.main_window.model.files[index.row()]
        clean_base_name = Path(file_entry.clean_name).stem
        editor.setText(clean_base_name)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        new_base_name = editor.text().strip()
        if not new_base_name:
            return

        # El renombrado es transaccional: solo cambia el estado del modelo.
        # El archivo físico se modifica al pulsar "Apply changes".
        model.set_pending_name(index.row(), new_base_name)