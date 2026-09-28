from PyQt6.QtWidgets import QStyledItemDelegate, QStyle  # type: ignore
from PyQt6.QtCore import (  # type: ignore
    Qt
)

class FileDelegate(QStyledItemDelegate):

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

        size = super().sizeHint(
            option,
            index
        )

        size.setHeight(40)

        return size