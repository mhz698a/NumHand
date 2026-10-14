from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6 import QtWidgets
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QListWidget,
    QPushButton,
    QAbstractItemView,
)

class SubfolderListItemWidget(QWidget):
    """Widget personalizado para cada ítem con alineación uniforme."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        layout.setContentsMargins(4, 2, 6, 2)
        layout.setSpacing(8)

        self.btn_arrow = QPushButton("➤")
        self.btn_arrow.setFixedSize(26, 26)
        
        size_policy = self.btn_arrow.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        self.btn_arrow.setSizePolicy(size_policy)
        
        self.btn_arrow.setVisible(False)
        layout.addWidget(self.btn_arrow)

        self.label = QLabel(text)
        layout.addWidget(self.label, stretch=1)

    def set_active(self, active: bool):
        # Muestra u oculta el botón manteniendo la estructura alineada
        self.btn_arrow.setVisible(active)

class YearSubFolderPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # -------------------------------------------------------------
        # 1. Selector de Años (QTableWidget con 2 columnas, sin headers)
        # -------------------------------------------------------------
        year_layout = QVBoxLayout()

        years = [str(y) for y in range(2004, datetime.now().year + 1)]
        rows = (len(years) + 1) // 2

        self.YearSelectorCells = QTableWidget(rows, 2)
        self.YearSelectorCells.setFixedWidth(95)
        self.YearSelectorCells.horizontalHeader().setVisible(False)
        self.YearSelectorCells.verticalHeader().setVisible(False)
        self.YearSelectorCells.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.YearSelectorCells.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.YearSelectorCells.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.YearSelectorCells.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.YearSelectorCells.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.YearSelectorCells.setShowGrid(False)
        
        self.YearSelectorCells.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: #2a82da;
                color: white;
            }
        """)

        for index, year in enumerate(years):
            row = index // 2
            col = index % 2
            item = QTableWidgetItem(year)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.YearSelectorCells.setItem(row, col, item)

        self.YearSelectorCells.setColumnWidth(0, 45)
        self.YearSelectorCells.setColumnWidth(1, 45)

        year_layout.addWidget(self.YearSelectorCells)
        main_layout.addLayout(year_layout)

        # Seleccionar por defecto el año actual
        current_year = str(datetime.now().year)
        for r in range(self.YearSelectorCells.rowCount()):
            for c in range(self.YearSelectorCells.columnCount()):
                item = self.YearSelectorCells.item(r, c)
                if item and item.text() == current_year:
                    self.YearSelectorCells.setCurrentCell(r, c)
                    break

        # -------------------------------------------------------------
        # 2. Subcarpetas y Botón (QListWidget dinámico + botón ">")
        # -------------------------------------------------------------
        sub_layout = QVBoxLayout()
        self.SubFolderYearList = QListWidget()
        self.SubFolderYearList.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.SubFolderYearList.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.SubFolderYearList.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, 
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        
        sub_layout.addWidget(self.SubFolderYearList)
        main_layout.addLayout(sub_layout, stretch=1)

    def _on_subfolder_changed(self, current, previous):
        if current and not current.text().startswith("("):
            self.btn_action.setEnabled(True)
        else:
            self.btn_action.setEnabled(False)