import os
import subprocess
import platform
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QMessageBox, QDockWidget
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from model import FileModel
from wfilelist_view import FileListView
from widget_filehand import FileDelegate
from widget_left_p import IndividualTaggerPanel
from sys_non_enum import apply_changes_non_enum
from sysfiles import FileUtils
from sysmove import (
    check_folder_numbering,
    move_selected_files,
    move_selected_to_trash,
    set_trash_folder,
)
from wutils_foobar2000 import check_foobar2000_playing_file
from tag_controller import apply_panel_tags_to_selection, update_tagger_panel


class WMain(QMainWindow):

    BACKUP_FILENAME = ".__file_manager_backup__.json"

    def __init__(self, folder=None):
        super().__init__()

        self.folder = Path(folder) if folder else None
        self.model = FileModel()
        self.file_utils = FileUtils()

        self.setWindowTitle("Numeric Handler Files")
        self.resize(1000, 700)
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

        self.tagger_dock = QDockWidget("File Tags (Invididual)", self)
        self.tagger_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.tagger_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        self.tagger_panel = IndividualTaggerPanel(self.tagger_dock)
        self.tagger_dock.setWidget(self.tagger_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.tagger_dock)
        
        self.tagger_panel.apply_tags.clicked.connect(self._on_apply_tags_clicked)

    def build_listview(self):
        self.file_list.setModel(self.model)
        self.file_list.setItemDelegate(
            FileDelegate(self.file_list, main_window=self)
        )
        self.file_list.selectionModel().selectionChanged.connect(
            self._on_file_selection_changed
        )
    
    def _on_apply_tags_clicked(self):
        selected_indexes = self.file_list.selectionModel().selectedIndexes()
        selected_entries = [self.model.files[idx.row()] for idx in selected_indexes]
        
        apply_panel_tags_to_selection(self.tagger_panel, selected_entries)
        
        # Refrescar vista del panel derecho
        update_tagger_panel(self.tagger_panel, selected_entries)

    def build_menubar(self):
        def add_menu_items(menu, items):
            for item in items:
                if item is None:
                    menu.addSeparator()
                    continue
                
                text, slot, *shortcut = item
                action = QAction(text, self)
                if shortcut:
                    action.setShortcut(shortcut[0])
                action.triggered.connect(slot)
                menu.addAction(action)

        barra_menu = self.menuBar()

        # ----------------------------------------
        # Menú Archivo
        # ----------------------------------------
        add_menu_items(barra_menu.addMenu("&File"), [
            ("&Open Oring Folder", lambda: self.file_utils.select_folder(self, self.model), "Ctrl+O"),
            ("&Refresh Oring Folder", lambda: self.file_utils.load_folder(self, self.model), "F5"),
            ("&Open Oring Folder", self.openFolderExplorer, "Ctrl+P"),
            None,
            ("&Apply changes", lambda: self.file_utils.apply_order(self, self.model), "Ctrl+S"),
            ("Apply changes (Non-Enum)", lambda: apply_changes_non_enum(self, self.model)),
            None,
            ("&Exit", self.close, "Alt+F4"),
        ])

        # ----------------------------------------
        # Menú Editar
        # ----------------------------------------
        add_menu_items(barra_menu.addMenu("&Edit"), [
            ("Select All", lambda: self.model.set_all_checked(True)),
            ("Unselect All", lambda: self.model.set_all_checked(False)),
            ("Invert Selection", self.model.invert_selection),
            None,
        ])

        # ----------------------------------------
        # Menú Utilidades
        # ----------------------------------------
        add_menu_items(barra_menu.addMenu("&Utilidades"), [
            ("Quit Numeration Folder", lambda: self.file_utils.reset_numeration_folder(self, self.model), "Ctrl+F5"),
            ("Recover Failed Renames", lambda: self.file_utils.recover_failed_names(self, self.model), "Ctrl+Shift+R"),
            None,
            ("Convert to Hundreds Format", lambda: self.file_utils.format_hundreds(self, self.model)),
            ("Integrate Files", lambda: self.file_utils.integrate_files(self, self.model)),
            ("Check Foobar2000 Playing File", lambda: check_foobar2000_playing_file(self)),
            None,
            ("Move Selected to Other Folder", lambda: move_selected_files(self, self.model)),
            ("Check Folder Enumeration", lambda: check_folder_numbering(self, self.model)),
            ("Set Recicle Bin Folder", lambda: set_trash_folder(self)),
            ("Move Selected to Recicle Bin Folder", lambda: move_selected_to_trash(self, self.model)),
            None,
            ("Copy Paths of selecction", self.copy_selected_paths),
            ("Copy Filenames of selecction", self.copy_selected_names),
        ])

    def _on_file_selection_changed(self, selected, deselected):
        """Se ejecuta cada vez que el usuario selecciona o desselecciona items en la lista."""
        selected_indexes = self.file_list.selectionModel().selectedIndexes()
        selected_entries = [self.model.files[idx.row()] for idx in selected_indexes]
        update_tagger_panel(self.tagger_panel, selected_entries)

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
