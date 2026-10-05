from PyQt6.QtCore import (Qt, QMimeData,)
from PyQt6.QtWidgets import (QListView, )
from PyQt6.QtGui import (QDrag, QCursor, QPainter, QPen,)

class FileListView(QListView):

    HANDLE_WIDTH = 40

    def __init__(self, parent=None):

        super().__init__(parent)

        self.drag_start_position = None
        self.drag_row = None
        self.drop_row = None

        self.setAcceptDrops(True)

        self.setDropIndicatorShown(False)

        self.setDragDropMode(
            QListView.DragDropMode.DropOnly
        )

        self.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )

        self.setSelectionMode(
            QListView.SelectionMode.SingleSelection
        )

    # ---------------------------------
    # Mouse
    # ---------------------------------

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            position = event.position().toPoint()

            index = self.indexAt(position)

            if index.isValid():

                rect = self.visualRect(index)

                if (
                    rect.x()
                    <= position.x()
                    <= rect.x() + self.HANDLE_WIDTH
                ):

                    self.drag_start_position = position
                    self.drag_row = index.row()

                    self.setCurrentIndex(index)

                    event.accept()

                    return

        self.drag_start_position = None
        self.drag_row = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):

        position = event.position().toPoint()

        # ---------------------------------
        # No estamos arrastrando
        # ---------------------------------

        if self.drag_start_position is None:

            index = self.indexAt(position)

            if index.isValid():

                rect = self.visualRect(index)

                if (
                    rect.x()
                    <= position.x()
                    <= rect.x() + self.HANDLE_WIDTH
                ):

                    self.viewport().setCursor(
                        Qt.CursorShape.OpenHandCursor
                    )

                else:

                    self.viewport().setCursor(
                        Qt.CursorShape.ArrowCursor
                    )

            else:

                self.viewport().setCursor(
                    Qt.CursorShape.ArrowCursor
                )

            super().mouseMoveEvent(event)

            return

        # ---------------------------------
        # Estamos intentando iniciar drag
        # ---------------------------------

        if not (
            event.buttons()
            & Qt.MouseButton.LeftButton
        ):

            return

        distance = (
            position
            - self.drag_start_position
        ).manhattanLength()

        if distance < 10:

            return

        self.start_drag()

    # ---------------------------------
    # Iniciar drag
    # ---------------------------------

    def start_drag(self):

        if self.drag_row is None:

            return

        self.viewport().setCursor(
            Qt.CursorShape.ClosedHandCursor
        )

        mime_data = QMimeData()

        mime_data.setText(
            str(self.drag_row)
        )

        drag = QDrag(self)

        drag.setMimeData(
            mime_data
        )

        drag.exec(
            Qt.DropAction.MoveAction
        )

        self.viewport().setCursor(
            Qt.CursorShape.ArrowCursor
        )

        self.drag_start_position = None
        self.drag_row = None
        self.drop_row = None

        self.viewport().update()

    # ---------------------------------
    # Drag Enter
    # ---------------------------------

    def dragEnterEvent(self, event):

        if event.mimeData().hasText():
            self.drop_row = None
            event.setDropAction(
                Qt.DropAction.MoveAction
            )
            event.accept()
        else:
            event.ignore()

    # ---------------------------------
    # Drag Move
    # ---------------------------------

    def dragMoveEvent(self, event):

        if not event.mimeData().hasText():
            event.ignore()
            return

        position = event.position().toPoint()

        target_index = self.indexAt(
            position
        )

        if not target_index.isValid():
            target_row = self.model().rowCount()

        else:
            rect = self.visualRect(
                target_index
            )

            if position.y() < rect.center().y():
                target_row = target_index.row()
            else:
                target_row = target_index.row() + 1

        source_row = self.drag_row

        if source_row is not None:
            if target_row > source_row:
                target_row -= 1

        self.drop_row = target_row

        self.viewport().update()

        event.setDropAction(
            Qt.DropAction.MoveAction
        )

        event.accept()

    # ---------------------------------
    # Drop
    # ---------------------------------

    def dropEvent(self, event):

        if not event.mimeData().hasText():

            event.ignore()

            return

        try:

            source_row = int(
                event.mimeData().text()
            )

        except ValueError:

            event.ignore()

            return

        target_row = self.drop_row

        if target_row is None:

            target_row = self.model().rowCount()

        self.model().move_file(
            source_row,
            target_row
        )

        self.drop_row = None
        self.drag_row = None

        self.viewport().update()

        event.setDropAction(
            Qt.DropAction.MoveAction
        )

        event.accept()

    # ---------------------------------
    # Dibujar línea
    # ---------------------------------

    def paintEvent(self, event):

        super().paintEvent(event)

        if self.drop_row is None:

            return

        if self.model().rowCount() == 0:

            return

        painter = QPainter(
            self.viewport()
        )

        pen = QPen(
            Qt.GlobalColor.black
        )

        pen.setWidth(3)

        painter.setPen(pen)

        width = self.viewport().width()

        # ---------------------------------
        # Insertar al final
        # ---------------------------------

        if (
            self.drop_row
            >= self.model().rowCount()
        ):

            index = self.model().index(
                self.model().rowCount() - 1,
                0
            )

            rect = self.visualRect(index)

            y = rect.bottom()

        # ---------------------------------
        # Insertar antes de un elemento
        # ---------------------------------

        else:

            index = self.model().index(
                self.drop_row,
                0
            )

            rect = self.visualRect(index)

            y = rect.top()

        painter.drawLine(
            0,
            y,
            width - 15,
            y
        )
  