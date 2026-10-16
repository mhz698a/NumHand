from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QPushButton,
)
from datetime import datetime


class YearPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Elegir año destino")
        self.resize(230, 280)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Año destino:"))

        self.table = QTableWidget(self)
        years = [str(y) for y in range(2004, datetime.now().year + 1)]
        columns = 4
        rows = (len(years) + columns - 1) // columns

        self.table.setColumnCount(columns)
        self.table.setRowCount(rows)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setShowGrid(False)
        
        self.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #2a82da;
                color: white;
            }
        """)

        for index, year in enumerate(years):
            row = index // columns
            col = index % columns
            item = QTableWidgetItem(year)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

        for col in range(columns):
            self.table.setColumnWidth(col, 50)

        current_year = str(datetime.now().year)
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and item.text() == current_year:
                    self.table.setCurrentCell(r, c)
                    break

        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(btn_ok)
        buttons.addWidget(btn_cancel)
        layout.addLayout(buttons)

    def selected_year(self):
        item = self.table.currentItem()
        return item.text() if item else None