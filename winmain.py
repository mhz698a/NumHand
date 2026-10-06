import os
import sys
import subprocess
import platform
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QMessageBox
)
from PyQt6.QtGui import QAction

from model import FileModel
from wfilelist_view import FileListView
from widget_filehand import FileDelegate
from sysfiles import FileUtils
from sysmove import move_selected_files, move_selected_to_trash, set_trash_folder
from wutils_foobar2000 import check_foobar2000_playing_file

class WMain(QMainWindow):

    BACKUP_FILENAME = ".__file_manager_backup__.json"

    def __init__(self, folder=None):
        super().__init__()

        self.folder = Path(folder) if folder else None
        self.model = FileModel()
        self.file_utils = FileUtils()
        
        if self.folder:
            self.file_utils.load_folder(self, self.model)

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

        ac_refresh_folder = QAction("&Refresh Loaded Folder", self)
        ac_refresh_folder.setShortcut("F5")
        ac_refresh_folder.triggered.connect(
            lambda: self.file_utils.load_folder(self, self.model)
        )
        menu_archivo.addAction(ac_refresh_folder)

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

        menu_editar = barra_menu.addMenu("&Edit")

        ac_select_all = QAction("Select All", self)
        ac_select_all.triggered.connect(
            lambda: self.model.set_all_checked(True)
        )
        menu_editar.addAction(ac_select_all)

        ac_unselect_all = QAction("Unselect All", self)
        ac_unselect_all.triggered.connect(
            lambda: self.model.set_all_checked(False)
        )
        menu_editar.addAction(ac_unselect_all)

        ac_invert_selection = QAction("Invert Selection", self)
        ac_invert_selection.triggered.connect(
            self.model.invert_selection
        )
        menu_editar.addAction(ac_invert_selection)

        menu_editar.addSeparator()

        # ----------------------------------------

        menu_utilidades = barra_menu.addMenu("&Utilidades")

        ac_desnum_folder = QAction("Reset Numeration Folder", self)
        ac_desnum_folder.setShortcut("Ctrl+F5")
        ac_desnum_folder.triggered.connect(
            lambda: self.file_utils.reset_numeration_folder(self, self.model)
        )
        menu_utilidades.addAction(ac_desnum_folder)

        ac_recover_failed = QAction("Recover failed renames", self)
        ac_recover_failed.setShortcut("Ctrl+Shift+R")
        ac_recover_failed.triggered.connect(
            lambda: self.file_utils.recover_failed_names(self, self.model)
        )
        menu_utilidades.addAction(ac_recover_failed)

        menu_utilidades.addSeparator()

        ac_format_hundreds = QAction("Convert to hundreds format", self)
        ac_format_hundreds.triggered.connect(
            lambda: self.file_utils.format_hundreds(self, self.model)
        )
        menu_utilidades.addAction(ac_format_hundreds)

        ac_integrate_files = QAction("Integrate Files", self)
        ac_integrate_files.triggered.connect(
            lambda: self.file_utils.integrate_files(self, self.model)
        )
        menu_utilidades.addAction(ac_integrate_files)

        ac_check_foobar2000 = QAction("Check foobar2000 playing file", self)
        ac_check_foobar2000.triggered.connect(
            lambda: check_foobar2000_playing_file(self)
        )
        menu_utilidades.addAction(ac_check_foobar2000)

        menu_utilidades.addSeparator()

        ac_move_selected = QAction(
            "Mover a otra carpeta los archivos seleccionados",
            self
        )
        ac_move_selected.triggered.connect(
            lambda: move_selected_files(self, self.model)
        )
        menu_utilidades.addAction(ac_move_selected)

        ac_set_trash = QAction("Establecer ruta de papelera", self)
        ac_set_trash.triggered.connect(lambda: set_trash_folder(self))
        menu_utilidades.addAction(ac_set_trash)

        ac_move_trash = QAction("Mover a papelera los seleccionados", self)
        ac_move_trash.triggered.connect(
            lambda: move_selected_to_trash(self, self.model)
        )
        menu_utilidades.addAction(ac_move_trash)

        menu_utilidades.addSeparator()

        ac_copy_paths = QAction("Copiar rutas de archivos seleccionados", self)
        ac_copy_paths.triggered.connect(self.copy_selected_paths)
        menu_utilidades.addAction(ac_copy_paths)

        ac_copy_names = QAction("Copiar nombres de archivos seleccionados", self)
        ac_copy_names.triggered.connect(self.copy_selected_names)
        menu_utilidades.addAction(ac_copy_names)


    def check_foobar2000_playing_file(self):
        from wutils_foobar2000 import is_file_from_list_playing

        try:
            is_playing = is_file_from_list_playing(
                file.path for file in self.model.files
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "foobar2000",
                f"Could not connect to foobar2000: {exc}"
            )
            return

        if is_playing:
            QMessageBox.information(
                self,
                "foobar2000",
                "foobar2000 is playing a file from the loaded folder."
            )
        else:
            QMessageBox.information(
                self,
                "foobar2000",
                "foobar2000 is not playing a file from the loaded folder."
            )

    def copy_selected_paths(self):
        selected_files = self.model.checked_files()
        QApplication.clipboard().setText(
            "\n".join(str(file.path) for file in selected_files)
        )

    def copy_selected_names(self):
        selected_files = self.model.checked_files()
        QApplication.clipboard().setText(
            "\n".join(file.path.name for file in selected_files)
        )

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
            "Exit the application",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if box_confirmacion == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()
