import os
import logging
import subprocess
import platform
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QMessageBox, QDockWidget
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QItemSelectionModel

from model import FileModel
from wfilelist_view import FileListView
from widget_filehand import FileDelegate
from widget_right_p import IndividualTaggerPanel
from sys_non_enum import apply_changes_non_enum
from sysfiles import FileUtils
from sysmove import (
    check_folder_numbering,
    move_selected_files,
    move_selected_files_to_year_subfolder,
    move_selected_to_trash,
    set_trash_folder,
)
from wutils_foobar2000 import check_foobar2000_playing_file, select_foobar2000_playing_file
from tag_controller import apply_panel_tags_to_selection, update_tagger_panel
from wstatusbar import setup_status_bar, show_status_message
from widget_left_p import YearSubFolderPanel
from sub_controller import SubFolderController
from pyutils.foobar_settings import (
    get_foobar_interventions_enabled,
    set_foobar_interventions_enabled,
)

class WMain(QMainWindow):

    BACKUP_FILENAME = ".__file_manager_backup__.json"

    def __init__(self, folder=None, select_playing=True, initial_file=None):
        super().__init__()

        self.folder = Path(folder) if folder else None
        self.model = FileModel()
        self.file_utils = FileUtils()
        self.folder_cache = self.file_utils.folder_cache

        self.setWindowTitle("Numeric Handler Files")
        self.build_ui()
        self.build_menubar()
        self.build_listview()
        
        setup_status_bar(self)

        if self.folder and self.folder.exists():
            if initial_file:
                # Si se pasó un archivo directamente, se selecciona omitiendo foobar2000
                self.file_utils.load_folder(
                    self,
                    self.model,
                    on_loaded=lambda: select_foobar2000_playing_file(self, current_path=initial_file),
                )
            elif select_playing:
                # Comportamiento normal con foobar2000
                self.file_utils.load_folder(
                    self,
                    self.model,
                    on_loaded=lambda: select_foobar2000_playing_file(self),
                )
            else:
                self.file_utils.load_folder(self, self.model)

    def build_ui(self):
        l_central = QWidget()
        self.setCentralWidget(l_central)
        v_layout = QVBoxLayout(l_central)

        self.file_list = FileListView()
        v_layout.addWidget(self.file_list)
        
        # -------------------------------------------------------------
        self.left_dock = QDockWidget("Years And Subfolders Explorer", self)
        self.left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.left_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        self.left_dock.setTitleBarWidget(QWidget(self.left_dock))
        
        self.left_panel = YearSubFolderPanel(self.left_dock)
        self.left_dock.setWidget(self.left_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.left_dock)
        
        self.sub_controller = SubFolderController(self.left_panel, self)

        # -------------------------------------------------------------
        self.tagger_dock = QDockWidget("File Tags (Invididual)", self)
        self.tagger_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.tagger_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        
        self.tagger_dock.setTitleBarWidget(QWidget(self.tagger_dock))
        
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

    def select_first_file(self):
        """Selecciona visualmente el primer archivo de la lista, si existe."""
        if not self.model.files:
            return False

        first_index = self.model.index(0, 0)
        self.file_list.selectionModel().setCurrentIndex(
            first_index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.file_list.scrollTo(first_index)
        return True
    
    def _on_apply_tags_clicked(self):
        selected_indexes = self.file_list.selectionModel().selectedIndexes()
        selected_entries = [
            self.model.files[index.row()]
            for index in selected_indexes
            if index.isValid() and 0 <= index.row() < len(self.model.files)
        ]
        
        apply_panel_tags_to_selection(
            self.tagger_panel,  selected_entries, 
            status_callback=lambda msg: show_status_message(self, msg, 5000)
        )
        if self.folder and self.folder.is_dir():
            self.file_utils.sync_folder_cache(self.folder)
        
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
            ("&Load Custom Oring Folder", lambda: self.file_utils.select_folder(self, self.model), "Ctrl+O"),
            ("&Refresh Current Oring Folder", lambda: self.file_utils.load_folder(self, self.model, force_refresh=True), "F5"),
            ("&Open Current Oring Folder", self.openFolderExplorer, "Ctrl+P"),
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
            ("Current SubFolder Opened", lambda: self.sub_controller.sync_with_current_folder()),
            None,
            ("Quit Numeration Folder", lambda: self.file_utils.reset_numeration_folder(self, self.model), "Ctrl+F5"),
            ("Recover Failed Renames", lambda: self.file_utils.recover_failed_names(self, self.model), "Ctrl+Shift+R"),
            ("Convert to Hundreds Format", lambda: self.file_utils.format_hundreds(self, self.model)),
            None,
            ("Check Foobar2000 Playing File", lambda: check_foobar2000_playing_file(self)),
            ("Select Foobar2000 Playing File", lambda: select_foobar2000_playing_file(self)),
            ("Activar/Desactivar Intervenciones a Foobar2000", self.toggle_foobar_interventions),
            ("Clear cache from more of 30 days ago", self.clear_old_folder_cache),
            None,
            ("Integrate Files in This Folder", lambda: self.file_utils.integrate_files(self, self.model)),
            ("Move Selected to Other Folder", lambda: move_selected_files(self, self.model)),
            (
                "Move Selected to Year Subfolder",
                lambda: move_selected_files_to_year_subfolder(self, self.model),
            ),
            ("Check Folder Enumeration", lambda: check_folder_numbering(self, self.model)),
            ("Set Recicle Bin Folder", lambda: set_trash_folder(self)),
            ("Move Selected to Recicle Bin Folder", lambda: move_selected_to_trash(self, self.model)),
            None,
            ("Copy Paths of selecction", self.copy_selected_paths),
            ("Copy Filenames of selecction", self.copy_selected_names),
        ])

    def toggle_foobar_interventions(self):
        """Pregunta y persiste si las operaciones de archivos interactúan con Foobar2000."""
        state_flag = get_foobar_interventions_enabled()
        new_state = not state_flag
        answer = QMessageBox.information(
            self,
            "Intervenciones a Foobar2000",
            "El manejo de playlist y player de foobar2000 esta en "
            f"{state_flag} ¿Usted desea colocar el valor a {new_state}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        set_foobar_interventions_enabled(new_state)

    def clear_old_folder_cache(self):
        try:
            deleted = self.folder_cache.clear_older_than(30)
            QMessageBox.information(
                self,
                "Cache de carpetas",
                f"Se eliminaron {deleted} entradas de cache sin uso durante más de 30 días."
            )
        except Exception as error:
            QMessageBox.critical(self, "Error de cache", str(error))

    def _on_file_selection_changed(self, selected, deselected):
        """Actualiza el panel sin asumir que los índices sobreviven a un reset del modelo."""
        try:
            selected_indexes = self.file_list.selectionModel().selectedIndexes()
            selected_entries = [
                self.model.files[index.row()]
                for index in selected_indexes
                if index.isValid() and 0 <= index.row() < len(self.model.files)
            ]
            update_tagger_panel(self.tagger_panel, selected_entries)
        except Exception:
            # Las señales de Qt no deben propagar excepciones fuera de un slot:
            # según el entorno de ejecución, eso puede terminar el proceso sin traceback.
            logging.exception("Error al actualizar la selección de archivos de NumHand")

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
