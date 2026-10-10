from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QLabel)


class CoverLabel(QLabel):
    """Widget para mostrar y gestionar la carátula (Convertido a PyQt6)."""
    clicked = pyqtSignal()
    rightClicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._has_cover = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(180, 180)
        self.setFixedSize(180, 180)
        self.setStyleSheet("""
            QLabel {
                border: 1px solid #444444;
                background-color: #232323;
                color: #dddddd;
            }
        """)
        self.setText("Agregar Carátula")

    def set_has_cover(self, has_cover: bool):
        self._has_cover = has_cover
        if not has_cover:
            self.setText("Agregar Carátula")

    def enterEvent(self, event):
        if not self._has_cover:
            self.setText("<u>Agregar Carátula</u>")
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._has_cover:
            self.setText("Agregar Carátula")
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit(event.globalPosition().toPoint())
        super().mousePressEvent(event)