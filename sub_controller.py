import traceback
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, QSize, QThreadPool
from PyQt6.QtWidgets import QListWidgetItem, QMenu, QMessageBox
from sysprog import DualProgressDialog
from wconst import EXTENSION_FILES
from widget_left_p import SubfolderListItemWidget
from pyutils.verbose_folders import VerboseRenameDialog, split_prefixed_name
from pyutils.year_picker import YearPickerDialog
from pyutils.folder_move import FolderMoveTask, strip_year_prefix
from pyutils.foobar2000_api import Foobar2000Api
from syswall import get_locking_processes
from wutils_foobar2000 import select_foobar2000_playing_file
from pyutils.foobar_helpers import capture_foobar_playback_state, restore_and_sync_foobar_playlist

BASE_ROOT = r"E:\_Internal"

def is_dir_empty(p: Path) -> bool:
    try:
        return not any(p.iterdir())
    except Exception:
        return False

class SubFolderController(QObject):
    subfolders_loaded = pyqtSignal(str, list)

    def __init__(self, panel_widget, main_window, parent=None):
        super().__init__(parent)
        self.panel = panel_widget
        self.main_window = main_window
        self.foobar = Foobar2000Api()
        
        self.load_timer = QTimer(self)
        self.load_timer.setSingleShot(True)
        self.load_timer.setInterval(150)
        self.pending_year = None
        self.last_valid_year = None

        self.move_thread = None
        self.move_worker = None

        self.load_timer.timeout.connect(self._execute_load)
        
        self._connect_signals()
        self.init_selection_from_folder()

    def _connect_signals(self):
        self.panel.YearSelectorCells.itemSelectionChanged.connect(self._on_year_selection_changed)
        self.panel.SubFolderYearList.currentItemChanged.connect(self._on_subfolder_changed)
        self.panel.SubFolderYearList.customContextMenuRequested.connect(self._show_context_menu)

    def init_selection_from_folder(self):
        folder_path = getattr(self.main_window, "folder", None)
        target_year = None
        target_subfolder = None

        if folder_path:
            try:
                p = Path(folder_path).resolve()
                base_p = Path(BASE_ROOT).resolve()
                if p == base_p or base_p in p.parents:
                    rel = p.relative_to(base_p)
                    rel_parts = rel.parts
                    if len(rel_parts) >= 1:
                        target_year = rel_parts[0]
                    if len(rel_parts) >= 3:
                        target_subfolder = rel_parts[2]
                    elif len(rel_parts) == 2 and not p.name.endswith(EXTENSION_FILES):
                        target_subfolder = rel_parts[1]
            except Exception:
                pass

        if not target_year:
            target_year = str(datetime.now().year)

        self._select_year_in_table(target_year)
        subfolders = self.fetch_subfolders_for_year(target_year)
        self._populate_subfolders_ui(subfolders, select_subfolder=target_subfolder)

    def _select_year_in_table(self, year_str):
        table = self.panel.YearSelectorCells
        table.blockSignals(True)
        target_cell = None
        max_year = -1

        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                it = table.item(r, c)
                if it:
                    val_str = it.text()
                    if val_str == year_str:
                        target_cell = (r, c)
                    if val_str.isdigit() and int(val_str) > max_year:
                        max_year = int(val_str)

        if not target_cell and max_year != -1:
            year_str = str(max_year)
            for r in range(table.rowCount()):
                for c in range(table.columnCount()):
                    it = table.item(r, c)
                    if it and it.text() == year_str:
                        target_cell = (r, c)
                        break

        if target_cell:
            table.setCurrentCell(target_cell[0], target_cell[1])
            self.last_valid_year = year_str

        table.blockSignals(False)

    def _on_year_selection_changed(self):
        current_item = self.panel.YearSelectorCells.currentItem()
        if not current_item or not current_item.text().strip():
            self.panel.YearSelectorCells.clearSelection()
            if self.last_valid_year:
                self._select_year_cell_silent(self.last_valid_year)
            return

        year_str = current_item.text()
        self.last_valid_year = year_str
        self.pending_year = year_str
        self.load_timer.start()

    def _select_year_cell_silent(self, year_str):
        table = self.panel.YearSelectorCells
        table.blockSignals(True)
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                it = table.item(r, c)
                if it and it.text() == year_str:
                    table.setCurrentCell(r, c)
                    table.blockSignals(False)
                    return
        table.blockSignals(False)

    def _execute_load(self):
        if not self.pending_year:
            return
        year = self.pending_year
        subfolders = self.fetch_subfolders_for_year(year)
        self._populate_subfolders_ui(subfolders)

    def _populate_subfolders_ui(self, subfolders, select_subfolder=None):
        list_widget = self.panel.SubFolderYearList
        list_widget.clear()
        
        target_row = 0
        if not subfolders:
            item = QListWidgetItem(list_widget)
            item.setSizeHint(QSize(0, 36))
            widget = SubfolderListItemWidget("(no hay subcarpetas)")
            list_widget.setItemWidget(item, widget)
        else:
            for idx, name in enumerate(subfolders):
                item = QListWidgetItem(list_widget)
                item.setSizeHint(QSize(0, 36))
                widget = SubfolderListItemWidget(name)
                
                widget.btn_arrow.clicked.connect(lambda checked, n=name: self._on_action_button_clicked(n))
                list_widget.setItemWidget(item, widget)
                
                if select_subfolder:
                    # Limpiar prefijos de ambos lados (ej: "23. sample" -> "sample")
                    clean_select = strip_year_prefix(select_subfolder).lower().strip()
                    clean_name = strip_year_prefix(name).lower().strip()
                    
                    if clean_name == clean_select or clean_select in clean_name or clean_name in clean_select:
                        target_row = idx

            list_widget.setCurrentRow(target_row)

    def _on_action_button_clicked(self, subfolder_name):
        year_item = self.panel.YearSelectorCells.currentItem()
        if not year_item:
            return

        target_folder = self.build_music_ahead_path(year_item.text()) / subfolder_name
        self._load_subfolder(target_folder)

    def _load_subfolder(self, target_folder: Path, on_loaded=None):
        """Hace lo mismo que el botón de una subcarpeta, con callback opcional al terminar."""
        target_folder = Path(target_folder)
        if not target_folder.exists() or not target_folder.is_dir():
            return

        if hasattr(self.main_window, "file_list"):
            self.main_window.file_list.clearSelection()

        self.main_window.folder = target_folder
        self.main_window.file_utils.load_folder(
            self.main_window,
            self.main_window.model,
            on_loaded=on_loaded,
        )

    def _load_and_play_subfolder(self, target_folder: Path):
        """Carga una subcarpeta y después reemplaza la playlist para reproducir desde el primer audio."""
        target_folder = Path(target_folder).resolve()
        self._load_subfolder(
            target_folder,
            on_loaded=lambda folder=target_folder: self._play_loaded_subfolder(folder),
        )

    def _play_loaded_subfolder(self, target_folder: Path):
        """Reemplaza la playlist de Foobar2000 por los audios cargados y reproduce el primer elemento."""
        try:
            # La carga es asíncrona: verificar que el modelo siga representando esta carpeta.
            current_folder = getattr(self.main_window, "folder", None)
            if not current_folder or Path(current_folder).resolve() != Path(target_folder).resolve():
                print("Esta subcarpeta requiere estar cargada para enviarla a Foobar2000")
                QMessageBox.warning(
                    self.main_window,
                    "NumHand",
                    "Esta subcarpeta requiere estar cargada para enviarla a Foobar2000",
                )
                return
                
            audio_paths = [
                str(Path(entry.path).resolve())
                for entry in self.main_window.model.files
                if Path(entry.path).suffix.lower() in EXTENSION_FILES
            ]
            if not audio_paths:
                QMessageBox.information(
                    self.main_window,
                    "Foobar2000",
                    "La carpeta cargada no contiene archivos de audio compatibles.",
                )
                return

            player_info = self.foobar.playlists()
            playlist_id = self.foobar.match_playlist(player_info)
            
            if playlist_id is None or playlist_id == "":
                raise RuntimeError("Foobar2000 No esta abierto")

            self.foobar.stop()
            self.foobar.clear_playlist(playlist_id)
            self.foobar.reload_and_restore_playlist(playlist_id, audio_paths, audio_paths[0], 0.0, is_recover_playback=False)
            select_foobar2000_playing_file(self.main_window, current_path=audio_paths[0])
            
        except Exception as exc:
            self.msg = QMessageBox(self.main_window)
            self.msg.setIcon(QMessageBox.Icon.Warning)
            self.msg.setWindowTitle("Foobar2000")
            self.msg.setText("La carpeta se cargó en NumHand, pero no se pudo iniciar la reproducción")
            self.msg.setInformativeText(f"Detalle: {exc}")            
            self.msg.setDetailedText(traceback.format_exc())
            self.msg.exec()

    def _on_subfolder_changed(self, current, previous):
        if previous:
            prev_widget = self.panel.SubFolderYearList.itemWidget(previous)
            if isinstance(prev_widget, SubfolderListItemWidget):
                prev_widget.set_active(False)

        if current:
            curr_widget = self.panel.SubFolderYearList.itemWidget(current)
            if isinstance(curr_widget, SubfolderListItemWidget):
                is_valid = not current.text().startswith("(") and not curr_widget.label.text().startswith("(")
                curr_widget.set_active(is_valid)

    def _check_and_stop_playback_if_needed(self, target_dir: Path) -> bool:
        """Comprueba si el archivo en reproducción pertenece a la carpeta y detiene el playback."""
        try:
            current_playing = self.foobar.current_path_playbackState()
            if current_playing:
                curr_path = Path(current_playing)
                # Verificar si el archivo actual está dentro de la carpeta a modificar
                if target_dir in curr_path.parents or target_dir == curr_path:
                    self.foobar.stop()
                    return True
        except Exception:
            pass
        return False

    def _check_files_in_use(self, target_dir: Path) -> bool:
        """Verifica si la carpeta o archivos internos están en uso usando syswall."""
        try:
            files_to_check = [str(target_dir)]
            if target_dir.is_dir():
                current_folder = getattr(self.main_window, "folder", None)
                same_folder_is_loaded = (
                    current_folder is not None
                    and Path(current_folder).resolve() == Path(target_dir).resolve()
                )
                if same_folder_is_loaded and hasattr(self.main_window, "model"):
                    for file_entry in self.main_window.model.files:
                        files_to_check.append(str(file_entry.path))
                else:
                    for p in target_dir.iterdir():
                        if p.is_file():
                            files_to_check.append(str(p))
                            if len(files_to_check) > 50: # Limitar para rendimiento
                                break
            
            locking_apps = get_locking_processes(files_to_check, omit_fb=True)
            if locking_apps:
                apps_str = ", ".join(locking_apps)
                res = QMessageBox.warning(
                    self.main_window,
                    "Archivos en uso",
                    f"La carpeta o algunos de sus archivos están siendo utilizados por los siguientes procesos:\n\n{apps_str}\n\n¿Deseas continuar de todas formas?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                return res == QMessageBox.StandardButton.Yes
        except Exception:
            pass
        return True

    def _show_context_menu(self, pos):
        item = self.panel.SubFolderYearList.itemAt(pos)
        if not item:
            return

        widget = self.panel.SubFolderYearList.itemWidget(item)
        sub_name = widget.label.text() if widget else item.text()
        if sub_name.startswith("("):
            return

        year_item = self.panel.YearSelectorCells.currentItem()
        if not year_item:
            return

        year = year_item.text()
        base = self.build_music_ahead_path(year)
        target_dir = base / sub_name

        menu = QMenu(self.main_window)
        act_load = menu.addAction("Load This SubFolder")
        act_load_play = menu.addAction("Load and Play this SubFolder")
        menu.addSeparator()

        act_new = menu.addAction("Crear Subcarpeta Aqui")
        act_rename = menu.addAction("Renombrar esta Subcarpeta")
        act_del = menu.addAction("Eliminar esta subcarpeta")
        is_empty = target_dir.exists() and is_dir_empty(target_dir)
        act_del.setEnabled(is_empty)

        act_move = menu.addAction("Mover Carpeta a otro año")

        action = menu.exec(self.panel.SubFolderYearList.mapToGlobal(pos))
        if not action:
            return

        # Las dos primeras acciones cargan la carpeta seleccionada por el menú contextual.
        if action == act_load:
            self._load_subfolder(target_dir)
        elif action == act_load_play:
            self._load_and_play_subfolder(target_dir)
        elif action == act_new:
            self._create_subfolder(year, base)
        elif action == act_rename:
            self.rename_selected_subfolder(sub_name, target_dir, year)
        elif action == act_del:
            self._delete_subfolder(target_dir, year)
        elif action == act_move:
            self.move_subfolder_to_another_year(target_dir, year)

    def _create_subfolder(self, year, base):
        """Maneja la lógica de interfaz y creación física de una nueva subcarpeta."""
        dlg = VerboseRenameDialog("", "", self.main_window, title="Crear subcarpeta nueva")
        if dlg.exec() != QMessageBox.DialogCode.Accepted:
            return

        raw = dlg.selected_raw()
        suffix = dlg.selected_suffix()
        if not raw:
            return

        prefix_num = int(year) - 2003
        final_name = f"{prefix_num:02d}. {raw}"
        if suffix:
            final_name = f"{final_name}.{suffix}"

        new_dir = base / final_name
        try:
            new_dir.mkdir(parents=True, exist_ok=False)
            self.refresh_subfolders(year)
        except FileExistsError:
            QMessageBox.warning(self.main_window, "Ya existe", "La carpeta ya existe.")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"No se pudo crear la carpeta:\n{e}")

    def _delete_subfolder(self, target_dir: Path, year: str):
        """Maneja la confirmación y eliminación física de una subcarpeta vacía."""
        if not target_dir.exists() or not is_dir_empty(target_dir):
            return
        
        confirm = QMessageBox.question(
            self.main_window,
            "Eliminar carpeta",
            f"¿Eliminar la carpeta?\n\n{target_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                target_dir.rmdir()
                self.refresh_subfolders(year)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"No se pudo eliminar:\n{e}")

    def _snapshot_file_entries_for_folder(self, target_dir: Path):
        """Obtiene una instantánea completa de los archivos directos antes de mutar la carpeta."""
        target_dir = Path(target_dir).resolve()
        current_folder = getattr(self.main_window, "folder", None)
        model = getattr(self.main_window, "model", None)

        # Solo reutilizar el modelo cuando corresponde exactamente a la carpeta origen.
        if current_folder and model is not None:
            try:
                if Path(current_folder).resolve() == target_dir:
                    return list(model.files)
            except (OSError, TypeError, ValueError):
                pass

        # Si la carpeta no está cargada en el panel, consultar el índice de archivos
        # de esa carpeta; no se debe tomar model.files de una carpeta distinta.
        file_utils = getattr(self.main_window, "file_utils", None)
        folder_cache = getattr(file_utils, "folder_cache", None)
        if folder_cache is not None:
            return list(folder_cache.list_files(target_dir))

        return [path for path in target_dir.iterdir() if path.is_file()]

    def _is_folder_currently_open(self, target_dir: Path) -> bool:
        """Verifica si la carpeta o alguna superior está abierta en NumHand."""
        if hasattr(self.main_window, "folder") and self.main_window.folder:
            try:
                curr_f = Path(self.main_window.folder).resolve()
                t_f = Path(target_dir).resolve()
                return curr_f == t_f or t_f in curr_f.parents
            except Exception:
                pass
        return False

    def rename_selected_subfolder(self, sub_name, target_dir, year):
        if not target_dir.exists():
            return
        
        prefix, raw_value, suffix_value = split_prefixed_name(sub_name)
        dlg = VerboseRenameDialog(raw_value, suffix_value, self.main_window)
        if dlg.exec() != QMessageBox.DialogCode.Accepted:
            return

        new_raw = dlg.selected_raw()
        new_suffix = dlg.selected_suffix()
        if not new_raw:
            return

        final_name = new_raw
        if new_suffix:
            final_name = f"{final_name}.{new_suffix}"
        if prefix:
            final_name = f"{prefix}{final_name}"

        if final_name == sub_name:
            return

        new_dir = target_dir.parent / final_name
        if new_dir.exists():
            QMessageBox.warning(self.main_window, "Ya existe", "Ya existe una carpeta con ese nombre.")
            return

        # 1. Verificar si la carpeta está abierta actualmente en la interfaz
        is_current_folder_open = self._is_folder_currently_open(target_dir)

        # Guardar la lista antes del cambio de ruta y antes de cualquier recarga asíncrona.
        try:
            file_entries = self._snapshot_file_entries_for_folder(target_dir)
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error",
                f"No se pudo obtener la lista de archivos de origen:\n{e}"
            )
            return

        # 2. Capturar estado de reproducción de Foobar2000 antes de mover/renombrar
        fb_api = None
        try:
            fb_api = Foobar2000Api()
        except Exception:
            pass

        # 3. Comprobar archivos en uso antes de detener la reproducción.
        if not self._check_files_in_use(target_dir):
            return

        # Capturar el estado y calcular la nueva ruta de reproducción.
        temp_new_dir_for_calc = target_dir.parent / final_name
        foobar_state = capture_foobar_playback_state(fb_api, target_dir, temp_new_dir_for_calc)

        try:
            # Renombrar carpeta física
            target_dir.rename(new_dir)

            # 4. Sincronizar Foobar2000 con la instantánea de archivos del directorio origen
            restore_and_sync_foobar_playlist(
                foobar_state, new_dir,
                file_entries=file_entries, source_dir=target_dir
            )

            # 5. Si la carpeta estaba abierta en la app, actualizar ruta y recargar vista
            if is_current_folder_open:
                self.main_window.folder = new_dir
                if hasattr(self.main_window, "file_list"):
                    self.main_window.file_list.clearSelection()
                
                if foobar_state["have_been_playing"] and foobar_state["new_path_for_playing"]:
                    self.main_window.file_utils.load_folder(
                        self.main_window, 
                        self.main_window.model, 
                        on_loaded=lambda: select_foobar2000_playing_file(self.main_window, current_path=foobar_state["new_path_for_playing"])
                    )
                else:
                    self.main_window.file_utils.load_folder(self.main_window, self.main_window.model)

            # 6. Actualizar UI de subcarpetas
            subfolders = self.fetch_subfolders_for_year(year)
            self._populate_subfolders_ui(subfolders, select_subfolder=new_dir.name)

        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"No se pudo renombrar la carpeta:\n{e}")

    def move_subfolder_to_another_year(self, src_dir, src_year):
        dlg = YearPickerDialog(self.main_window)
        if dlg.exec() != QMessageBox.DialogCode.Accepted:
            return

        dest_year = dlg.selected_year()
        if not dest_year:
            return
        
        if str(dest_year) == str(src_year):
            QMessageBox.warning(
                self.main_window,
                "Acción no permitida",
                f"La carpeta ya se encuentra en el año {dest_year}."
            )
            return

        is_current_folder_open = self._is_folder_currently_open(src_dir)

        fb_api = None
        try:
            fb_api = Foobar2000Api()
        except Exception:
            pass

        # FolderMoveTask cambia el prefijo al del año destino; calcular exactamente esa ruta
        # para que la ruta de reproducción guardada coincida con real_dest_dir.
        dest_base_path = self.build_music_ahead_path(dest_year)
        dest_prefix = f"{int(dest_year) - 2003:02d}."
        dest_folder_name = f"{dest_prefix} {strip_year_prefix(src_dir.name)}"
        new_dir = dest_base_path / dest_folder_name
        
        # Capturar los archivos de origen antes de mover y antes de iniciar una recarga asíncrona.
        try:
            file_entries = self._snapshot_file_entries_for_folder(src_dir)
        except Exception as e:
            QMessageBox.critical(
                self.main_window, "Error",
                f"No se pudo obtener la lista de archivos de origen:\n{e}"
            )
            return

        # Comprobar bloqueos antes de detener la reproducción.
        if not self._check_files_in_use(src_dir):
            return

        # Capturar el estado de reproducción usando la nueva ruta correcta.
        foobar_state = capture_foobar_playback_state(fb_api, src_dir, new_dir)

        self.progress_dialog = DualProgressDialog("Mover carpeta a otro año", self.main_window)
        self.progress_dialog.show()

        task = FolderMoveTask(src_dir, dest_year, BASE_ROOT)

        def on_finished(sy, dy, real_dest_dir):
            self.progress_dialog.close()
            
            # Seleccionar el año destino en la interfaz de manera silenciosa
            table = self.panel.YearSelectorCells
            table.blockSignals(True)
            self._select_year_in_table(dest_year)
            table.blockSignals(False)
            self.last_valid_year = str(dest_year)      

            # Si la carpeta estaba abierta, actualizar ruta y recargar vista
            if is_current_folder_open:
                self.main_window.folder = real_dest_dir
                self.main_window.file_list.clearSelection()
                
                if foobar_state.get("have_been_playing") and foobar_state.get("new_path_for_playing"):
                    self.main_window.file_utils.load_folder(
                        self.main_window, 
                        self.main_window.model, 
                        on_loaded=lambda: select_foobar2000_playing_file(
                            self.main_window, current_path=foobar_state["new_path_for_playing"]
                        )
                    )
                else:
                    self.main_window.file_utils.load_folder(self.main_window, self.main_window.model)
            
            subfolders = self.fetch_subfolders_for_year(dest_year)
            self._populate_subfolders_ui(subfolders, select_subfolder=real_dest_dir.name)
            
            restore_and_sync_foobar_playlist(
                foobar_state, str(real_dest_dir),
                file_entries=file_entries, source_dir=src_dir
            )
            
        def on_error(err_msg):
            self.progress_dialog.close()
            QMessageBox.critical(self.main_window, "Error", f"No se pudo mover la carpeta:\n{err_msg}")

        task.signals.progress.connect(self.progress_dialog.update_progress)
        task.signals.finished.connect(on_finished)
        task.signals.error.connect(on_error)

        QThreadPool.globalInstance().start(task)


    def refresh_subfolders(self, year):
        subfolders = self.fetch_subfolders_for_year(year)
        self._populate_subfolders_ui(subfolders)

    def build_music_ahead_path(self, year) -> Path:
        try:
            y = int(year)
        except ValueError:
            y = datetime.now().year
        prefix_num = y - 2003
        prefix = f"{prefix_num:02d}."
        folder_name = f"{prefix} music"
        return Path(BASE_ROOT) / str(y) / folder_name

    def fetch_subfolders_for_year(self, year_str) -> list:
        base_path = self.build_music_ahead_path(year_str)
        if base_path.exists() and base_path.is_dir():
            try:
                return sorted(p.name for p in base_path.iterdir() if p.is_dir())
            except Exception:
                return []
        return []

    def sync_with_current_folder(self):
        self.init_selection_from_folder()