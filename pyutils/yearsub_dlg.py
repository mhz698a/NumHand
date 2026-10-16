from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


DEFAULT_BASE_ROOT = Path(r"E:\_Internal")


class YearSubDialog(QDialog):
    """Dialog modal para elegir una subcarpeta de destino organizada por año."""

    def __init__(
        self,
        parent=None,
        selected_files=None,
        music_path_for_year=None,
        base_root=DEFAULT_BASE_ROOT,
    ):
        super().__init__(parent)
        self.setWindowTitle("Mover archivos a subcarpeta por año")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setModal(True)

        self._music_path_for_year = music_path_for_year
        self._base_root = Path(base_root)
        self._destination = None

        self.YearSelectorCells = self._build_year_selector()
        self.SubFolderYearList = QListWidget(self)
        self.SubFolderYearList.setObjectName("SubFolderYearList")
        self.SubFolderYearList.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.SubFolderYearList.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.SubFolderYearList.setMinimumWidth(300)
        self.SubFolderYearList.currentItemChanged.connect(
            self._update_move_button
        )

        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(8)
        selection_layout.addWidget(self.YearSelectorCells)
        selection_layout.addWidget(self.SubFolderYearList, stretch=1)

        self.FileList = QListWidget(self)
        self.FileList.setObjectName("FilesToMoveList")
        self.FileList.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.FileList.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.FileList.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.FileList.setMinimumHeight(108)
        self.FileList.setUniformItemSizes(True)
        self._populate_files(selected_files or [])

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        self.move_button = QPushButton("Mover", self)
        self.move_button.setEnabled(False)
        self.move_button.clicked.connect(self._accept_destination)
        self.cancel_button = QPushButton("Cancelar", self)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.move_button)
        buttons_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(selection_layout)
        layout.addWidget(QLabel("Archivos a mover:", self))
        layout.addWidget(self.FileList, stretch=1)
        layout.addLayout(buttons_layout)

        self.resize(680, 620)
        current_year = str(datetime.now().year)
        self._select_year(current_year)
        self._populate_subfolders_for_year(current_year)

    def _build_year_selector(self):
        current_year = datetime.now().year
        years = [str(year) for year in range(2004, current_year + 1)]
        rows = (len(years) + 1) // 2

        table = QTableWidget(rows, 2, self)
        table.setObjectName("YearSelectorCells")
        table.setFixedWidth(98)
        table.setFixedHeight(rows * 26 + 2)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setShowGrid(False)
        table.setStyleSheet(
            """
            QTableWidget::item:selected {
                background-color: #2a82da;
                color: white;
            }
            """
        )

        for index, year in enumerate(years):
            row, column = divmod(index, 2)
            item = QTableWidgetItem(year)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, column, item)
            table.setRowHeight(row, 26)

        table.setColumnWidth(0, 45)
        table.setColumnWidth(1, 45)
        table.currentItemChanged.connect(
            self._on_year_selection_changed
        )
        return table

    def _select_year(self, year):
        for row in range(self.YearSelectorCells.rowCount()):
            for column in range(self.YearSelectorCells.columnCount()):
                item = self.YearSelectorCells.item(row, column)
                if item and item.text() == str(year):
                    self.YearSelectorCells.setCurrentCell(row, column)
                    return

    def _music_directory_for_year(self, year):
        if callable(self._music_path_for_year):
            return Path(self._music_path_for_year(year))
        try:
            numeric_year = int(year)
        except (TypeError, ValueError):
            return self._base_root / str(year)
        prefix = f"{numeric_year - 2003:02d}."
        return self._base_root / str(numeric_year) / f"{prefix} music"

    def _on_year_selection_changed(self, current=None, previous=None):
        if current is not None and current.text().strip():
            self._populate_subfolders_for_year(current.text())
        else:
            self._populate_subfolders_for_year(None)

    def _populate_subfolders_for_year(self, year):
        self.SubFolderYearList.clear()
        self.move_button.setEnabled(False)
        if not year:
            return

        music_directory = self._music_directory_for_year(year)
        try:
            subfolders = sorted(
                (path for path in music_directory.iterdir() if path.is_dir()),
                key=lambda path: path.name.casefold(),
            ) if music_directory.is_dir() else []
        except OSError:
            subfolders = []

        if not subfolders:
            item = QListWidgetItem("(no hay subcarpetas)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, 36))
            self.SubFolderYearList.addItem(item)
            return

        for folder in subfolders:
            item = QListWidgetItem(folder.name)
            item.setData(Qt.ItemDataRole.UserRole, str(folder.resolve()))
            item.setSizeHint(QSize(0, 36))
            self.SubFolderYearList.addItem(item)

    def _populate_files(self, selected_files):
        for entry in selected_files:
            path = Path(getattr(entry, "path", entry))
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setSizeHint(QSize(0, 36))
            self.FileList.addItem(item)

    def destination_path(self):
        """Devuelve la ruta elegida o None si no hay una subcarpeta válida."""
        item = self.SubFolderYearList.currentItem()
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            return None

        path_value = item.data(Qt.ItemDataRole.UserRole)
        if not path_value:
            return None

        path = Path(path_value)
        return path.resolve() if path.is_dir() else None

    def _update_move_button(self, current=None, previous=None):
        self.move_button.setEnabled(self.destination_path() is not None)

    def _accept_destination(self):
        destination = self.destination_path()
        if destination is None:
            return
        self._destination = destination
        self.accept()

    @classmethod
    def get_destination_path(
        cls,
        parent=None,
        selected_files=None,
        music_path_for_year=None,
        base_root=DEFAULT_BASE_ROOT,
    ):
        """Muestra el diálogo y retorna la ruta destino o None si se cancela."""
        dialog = cls(
            parent=parent,
            selected_files=selected_files,
            music_path_for_year=music_path_for_year,
            base_root=base_root,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog._destination or dialog.destination_path()
