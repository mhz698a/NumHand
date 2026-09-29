import os
import sys
import subprocess
import platform
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget,
    QVBoxLayout, QMessageBox
)
from PyQt6.QtGui import QAction

from model import FileModel
from wfilelist_view import FileListView
from widget_filehand import FileDelegate
from sysfiles import FileUtils


class WMain(QMainWindow):

    BACKUP_FILENAME = ".__file_manager_backup__.json"

    def __init__(self, folder=None):
        super().__init__()

        self.folder = Path(folder) if folder else None
        self.model = FileModel()
        self.file_utils = FileUtils()

        self.setWindowTitle("Numeric Handler Files")
        self.resize(500, 700)
        self.build_ui()
        self.build_menubar()
        self.build_listview()

        if self.folder and self.folder.exists():
            self.file_utils.load_folder(self, self.model)

    def build_ui(self):
        l_central = QWidget()
        self.setCentralWidget(l_central)
        v_layout = QVBoxLayout(l_central)

        self.file_list = FileListView()
        v_layout.addWidget(self.file_list)

    def build_listview(self):
        self.file_list.setModel(
            self.model
        )

        self.file_list.setItemDelegate(
            FileDelegate(self.file_list, main_window=self)
        )

    def build_menubar(self):
        barra_menu = self.menuBar()

        menu_archivo = barra_menu.addMenu("&File")

        ac_abrir_folder = QAction("&Select Folder", self)
        ac_abrir_folder.setShortcut("Ctrl+O")
        ac_abrir_folder.triggered.connect(
            lambda: self.file_utils.select_folder(self, self.model)
        )
        menu_archivo.addAction(ac_abrir_folder)

        ac_opened_folder = QAction("&Open Selected Folder", self)
        ac_opened_folder.setShortcut("Ctrl+P")
        ac_opened_folder.triggered.connect(
            lambda: self.openFolderExplorer()
        )
        menu_archivo.addAction(ac_opened_folder)

        menu_archivo.addSeparator()

        ac_apply_changes = QAction("&Apply changes", self)
        ac_apply_changes.setShortcut("Ctrl+S")
        ac_apply_changes.triggered.connect(
            lambda: self.file_utils.apply_order(self, self.model)
        )
        menu_archivo.addAction(ac_apply_changes)

        menu_archivo.addSeparator()

        accion_salir = QAction("&Exit", self)
        accion_salir.setShortcut("Alt+F4")
        accion_salir.triggered.connect(self.close)
        menu_archivo.addAction(accion_salir)

        # ----------------------------------------

        menu_utilidades = barra_menu.addMenu("&Utilidades")

        ac_desnum_folder = QAction("Reset Numeration Folder", self)
        ac_desnum_folder.setShortcut("Ctrl+F5")
        ac_desnum_folder.triggered.connect(
            lambda: self.file_utils.reset_numeration_folder(self, self.model)
        )
        menu_utilidades.addAction(ac_desnum_folder)


    def openFolderExplorer(self):
        if self.folder and self.folder.exists():
            if platform.system() == "Windows":
                os.startfile(self.folder)
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(self.folder)])
            else:
                subprocess.run(["xdg-open", str(self.folder)])

    def closeEvent(self, event):
        box_confirmacion = QMessageBox.question(
            self,
            "Salir de la aplicación",
            "¿Estás seguro de que deseas salir?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if box_confirmacion == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
