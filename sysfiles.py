import uuid
import json
import re
import time

from pathlib import Path
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import QThreadPool

import syswall

from sysprog import DualProgressDialog
from wutils_sysfiles import compute_file_hash, is_folder_cleanly_numbered, classify_selected_files, rename_with_retry
from sysutils import LoadFolderTask, ApplyOrderTask, FormatHundredsTask, IntegrateFilesTask, ResetNumerationTask
from wconst import BACKUP_FILENAME, TEMP_PREFIX


class FileUtils:

    def __init__(self):
        self.thread_pool = QThreadPool.globalInstance()

    def select_folder(self, parent, model):
        folder = QFileDialog.getExistingDirectory(
            parent, "Seleccionar carpeta"
        )
        if not folder:
            return

        parent.folder = Path(folder)
        self.load_folder(parent, model)

    def load_folder(self, parent, model):
        if not parent.folder or not parent.folder.exists():
            return

        progress_dialog = DualProgressDialog("Cargando carpeta", parent)
        progress_dialog.show()

        task = LoadFolderTask(parent.folder, self)

        def on_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg):
            progress_dialog.set_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg)

        def on_finished(files):
            progress_dialog.close()
            model.set_files(files)

        def on_error(err_msg):
            progress_dialog.close()
            QMessageBox.critical(parent, "Error", err_msg)

        task.signals.progress.connect(on_progress)
        task.signals.finished.connect(on_finished)
        task.signals.error.connect(on_error)

        progress_dialog.canceled.connect(lambda: None)
        self.thread_pool.start(task)

    def check_files_locked(self, parent, file_paths):
        locking_apps = syswall.get_locking_processes(file_paths)
        if locking_apps:
            apps_str = "\n• ".join(locking_apps)
            QMessageBox.warning(
                parent,
                "Archivos en uso",
                f"Los siguientes programas están bloqueando archivos que se intentan modificar:\n\n• {apps_str}\n\nPor favor, cierra las aplicaciones manualmente antes de proceder."
            )
            return True
        return False

    def apply_order(self, parent, model):
        if not parent.folder or not model.files:
            return

        file_paths = [f.path for f in model.files]
        if self.check_files_locked(parent, file_paths):
            return

        progress_dialog = DualProgressDialog("Aplicando numeración", parent)
        progress_dialog.show()

        task = ApplyOrderTask(parent.folder, model.files, self)

        def on_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg):
            progress_dialog.set_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg)

        def on_finished(result):
            progress_dialog.close()
            model.layoutChanged.emit()

        def on_error(err_msg):
            progress_dialog.close()
            QMessageBox.critical(parent, "Error", err_msg)
            model.layoutChanged.emit()

        task.signals.progress.connect(on_progress)
        task.signals.finished.connect(on_finished)
        task.signals.error.connect(on_error)

        self.thread_pool.start(task)

    def recover_failed_names(self, parent, model):
        if not parent.folder or not parent.folder.exists():
            QMessageBox.warning(parent, "Atención", "No hay ninguna carpeta seleccionada.")
            return

        backup_path = parent.folder / BACKUP_FILENAME
        if not backup_path.exists():
            QMessageBox.information(
                parent,
                "Información",
                "No hay respaldos pendientes por aplicar."
            )
            return

        confirm = QMessageBox.question(
            parent,
            "Recuperar nombres fallidos",
            "Se ha detectado un respaldo pendiente. ¿Deseas intentar recuperar los nombres originales/fallidos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            success = self.recover_backup_sync(parent.folder)
            if success:
                QMessageBox.information(
                    parent,
                    "Éxito",
                    "Recuperación del respaldo completada correctamente."
                )
                self.load_folder(parent, model)
            else:
                QMessageBox.critical(
                    parent,
                    "Error",
                    "No se pudo completar la recuperación del respaldo."
                )

    def integrate_files(self, parent, model):
        if not parent.folder or not parent.folder.exists():
            QMessageBox.warning(parent, "Atención", "No hay ninguna carpeta seleccionada.")
            return

        folder_is_numbered = is_folder_cleanly_numbered(model.files)

        if not folder_is_numbered:
            QMessageBox.warning(
                parent,
                "Carpeta no numerada",
                "Esta carpeta no esta numerada, los archivos que se muevas aqui estarán en orden alfabético"
            )

        # Diálogo para seleccionar archivos a integrar
        selected_files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Seleccionar archivos a integrar"
        )

        if not selected_files:
            return

        selected_paths = [Path(p) for p in selected_files]

        # Comprobar bloqueos de archivos en seleccionados y en carpeta destino
        existing_entries = [
            f for f in parent.folder.iterdir()
            if f.is_file() and not f.name.startswith(TEMP_PREFIX)
        ]
        if self.check_files_locked(parent, selected_paths + existing_entries):
            return

        selected_case = classify_selected_files(selected_paths)

        if folder_is_numbered and selected_case == "CASE_3_STRANGE_OR_GAPS":
            confirm = QMessageBox.question(
                parent,
                "Formato no estándar o numeración incompleta",
                "Los archivos seleccionados tienen formatos extraños de numeración o saltos en la secuencia.\n\n"
                "Se limpiará su formato de inicio, se ordenarán alfabéticamente y se les añadirá numeración "
                "continua al final de la carpeta destino.\n\n¿Deseas continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        progress_dialog = DualProgressDialog("Integrar Archivos", parent)
        progress_dialog.show()

        task = IntegrateFilesTask(
            parent.folder,
            selected_paths,
            folder_is_numbered,
            selected_case,
            self
        )

        def on_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg):
            progress_dialog.set_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg)

        def on_finished(updated_files):
            progress_dialog.close()
            model.set_files(updated_files)
            QMessageBox.information(parent, "Éxito", "Archivos integrados correctamente.")

        def on_error(err_msg):
            progress_dialog.close()
            QMessageBox.critical(parent, "Error", err_msg)
            self.load_folder(parent, model)

        task.signals.progress.connect(on_progress)
        task.signals.finished.connect(on_finished)
        task.signals.error.connect(on_error)

        self.thread_pool.start(task)

    def format_hundreds(self, parent, model):
        if not parent.folder or not model.files:
            QMessageBox.warning(parent, "Atención", "No hay ninguna carpeta seleccionada o la carpeta está vacía.")
            return

        has_2digit_or_1digit = False
        for file in model.files:
            match = re.match(r"^(\d+)(?:_|\.\s*)", file.path.name)
            if match:
                digits_len = len(match.group(1))
                if digits_len < 3:
                    has_2digit_or_1digit = True
                    break

        if not has_2digit_or_1digit:
            QMessageBox.information(
                parent,
                "Información",
                "La carpeta ya se encuentra con el formato de centenas ('000. ')."
            )
            return

        file_paths = [f.path for f in model.files]
        if self.check_files_locked(parent, file_paths):
            return

        confirm = QMessageBox.question(
            parent,
            "Pasar a formato de centenas",
            "¿Deseas cambiar la numeración de los archivos en esta carpeta al formato de centenas ('001. ')?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress_dialog = DualProgressDialog("Formato de centenas", parent)
        progress_dialog.show()

        task = FormatHundredsTask(parent.folder, model.files, self)

        def on_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg):
            progress_dialog.set_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg)

        def on_finished(result):
            progress_dialog.close()
            model.layoutChanged.emit()

        def on_error(err_msg):
            progress_dialog.close()
            QMessageBox.critical(parent, "Error", err_msg)
            model.layoutChanged.emit()

        task.signals.progress.connect(on_progress)
        task.signals.finished.connect(on_finished)
        task.signals.error.connect(on_error)

        self.thread_pool.start(task)

    def reset_numeration_folder(self, parent, model):
        if not parent.folder:
            QMessageBox.warning(parent, "Atención", "No hay ninguna carpeta seleccionada.")
            return

        all_entries = [
            f for f in parent.folder.iterdir()
            if f.is_file() and not f.name.startswith(".__file_manager__")
        ]
        if self.check_files_locked(parent, all_entries):
            return

        confirm = QMessageBox.question(
            parent,
            "Confirmar des-enumeración",
            "¿Deseas eliminar los prefijos numéricos iniciales de todos los archivos en esta carpeta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress_dialog = DualProgressDialog("Des-enumerando carpeta", parent)
        progress_dialog.show()

        task = ResetNumerationTask(parent.folder, self)

        def on_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg):
            progress_dialog.set_progress(sub_curr, sub_tot, sub_msg, main_curr, main_tot, main_msg)

        def on_finished(updated_files):
            progress_dialog.close()
            model.set_files(updated_files)

        def on_error(err_msg):
            progress_dialog.close()
            QMessageBox.critical(parent, "Error", err_msg)

        task.signals.progress.connect(on_progress)
        task.signals.finished.connect(on_finished)
        task.signals.error.connect(on_error)

        self.thread_pool.start(task)

    def rename_single_file(self, parent, model, row, new_base_name):
        """
        Renombra un archivo individual sin perder su extensión.
        """
        if row < 0 or row >= len(model.files):
            return False

        file_entry = model.files[row]
        if not new_base_name:
            return False

        if self.check_files_locked(parent, [file_entry.path]):
            return False

        old_path = file_entry.path
        full_name = old_path.name
        
        ext_match = re.search(r"(\.[a-zA-Z0-9]{1,5})$", full_name)
        if ext_match:
            suffix = ext_match.group(1)
            name_body = full_name[:-len(suffix)]
        else:
            suffix = ""
            name_body = full_name
        
        old_prefix_match = re.match(r"^(\d+(?:_|\.\s*))", name_body)
        old_prefix = old_prefix_match.group(1) if old_prefix_match else ""
        
        new_prefix_match = re.match(r"^(\d+(?:_|\.\s*))", new_base_name)
        
        if new_prefix_match:
            user_prefix = new_prefix_match.group(1)
            clean_base = new_base_name[len(user_prefix):].strip()
            new_filename = f"{user_prefix}{clean_base}{suffix}"
            clean_base_for_model = clean_base
        else:
            new_filename = f"{old_prefix}{new_base_name}{suffix}"
            clean_base_for_model = new_base_name

        new_path = old_path.parent / new_filename

        if new_path.exists() and new_path != old_path:
            QMessageBox.warning(
                parent,
                "Error al renombrar",
                f"Ya existe un archivo con el nombre '{new_filename}'."
            )
            return False

        try:
            old_path.rename(new_path)
            file_entry.path = new_path
            file_entry.original_path = new_path
            file_entry.original_name = new_filename
            file_entry.clean_name = f"{clean_base_for_model}{suffix}"
            
            model.dataChanged.emit(model.index(row, 0), model.index(row, 0))
            return True
        
        except Exception as e:
            QMessageBox.critical(
                parent,
                "Error al renombrar",
                f"No se pudo renombrar el archivo: {e}"
            )
            return False

    @staticmethod
    def _is_retryable_backup_error(error):
        return (
            isinstance(error, PermissionError)
            or getattr(error, "errno", None) in {11, 13, 16}
            or getattr(error, "winerror", None) in {32, 33}
        )

    def _read_backup_with_retry(self, backup_path, max_attempts=10, delay=1.0):
        for attempt in range(1, max_attempts + 1):
            try:
                with backup_path.open("r", encoding="utf-8") as backup_file:
                    return json.load(backup_file)
            except json.JSONDecodeError as error:
                if attempt == max_attempts:
                    raise error
                time.sleep(delay)
            except OSError as error:
                if not self._is_retryable_backup_error(error) or attempt == max_attempts:
                    raise
                print(
                    f"El respaldo está ocupado; reintentando acceso "
                    f"({attempt + 1}/{max_attempts})..."
                )
                time.sleep(delay)

        raise RuntimeError("No se pudo acceder al respaldo.")

    def _unlink_backup_with_retry(self, backup_path, max_attempts=10, delay=1.0):
        for attempt in range(1, max_attempts + 1):
            try:
                backup_path.unlink()
                return
            except FileNotFoundError:
                return
            except OSError as error:
                if not self._is_retryable_backup_error(error) or attempt == max_attempts:
                    raise
                print(
                    f"El respaldo sigue ocupado; reintentando eliminación "
                    f"({attempt + 1}/{max_attempts})..."
                )
                time.sleep(delay)

    def recover_backup_sync(self, folder_path):
        backup_path = folder_path / BACKUP_FILENAME
        if not backup_path.exists():
            return True

        try:
            backup = self._read_backup_with_retry(backup_path)
        except Exception as error:
            print("No se pudo leer el respaldo:", error)
            return False

        if backup.get("version") != 1:
            print("Versión de respaldo no compatible.")
            return False

        files = backup.get("files", [])
        if not files:
            print("El respaldo no contiene archivos.")
            return False

        recovery_plan = []
        for item in files:
            original_path = Path(item["original_path"])
            temporary_path = Path(item["temporary_path"])
            final_path = Path(item["final_path"])
            sha256_hash = item.get("sha256")

            current_path = None
            if temporary_path.exists():
                current_path = temporary_path
            elif final_path.exists():
                current_path = final_path
            elif original_path.exists():
                current_path = original_path

            recovery_plan.append({
                "original_path": original_path,
                "temporary_path": temporary_path,
                "final_path": final_path,
                "current_path": current_path,
                "sha256": sha256_hash
            })

        claimed_paths = {item["current_path"].resolve() for item in recovery_plan if item["current_path"] is not None}
        missing_items = [item for item in recovery_plan if item["current_path"] is None]

        if missing_items:
            folder_files = [
                f for f in folder_path.iterdir()
                if f.is_file() and f.resolve() not in claimed_paths and not f.name.startswith(".__file_manager")
            ]

            file_hashes = {}
            for file_p in folder_files:
                h = compute_file_hash(file_p)
                if h:
                    file_hashes.setdefault(h, []).append(file_p)

            for item in missing_items:
                target_hash = item.get("sha256")
                if target_hash and target_hash in file_hashes and file_hashes[target_hash]:
                    candidate = file_hashes[target_hash].pop(0)
                    item["current_path"] = candidate
                    claimed_paths.add(candidate.resolve())

        missing = [item for item in recovery_plan if item["current_path"] is None]
        if missing:
            print("No se pudieron localizar todos los archivos del respaldo.")
            return False

        recovery_temp_files = []
        try:
            for item in recovery_plan:
                current_path = item["current_path"]
                original_path = item["original_path"]

                if current_path == original_path:
                    continue

                recovery_name = (
                    ".__file_manager_recovery__"
                    + uuid.uuid4().hex
                    + current_path.suffix
                )
                recovery_path = folder_path / recovery_name
                rename_with_retry(
                    current_path,
                    recovery_path,
                    max_attempts=10,
                    delay=1.0
                )

                recovery_temp_files.append({
                    "recovery_path": recovery_path,
                    "original_path": original_path
                })

            for item in recovery_temp_files:
                rename_with_retry(
                    item["recovery_path"],
                    item["original_path"],
                    max_attempts=10,
                    delay=1.0
                )

            for item in recovery_plan:
                if not item["original_path"].exists():
                    raise RuntimeError(f"No se pudo verificar {item['original_path'].name}")

            self._unlink_backup_with_retry(backup_path)
            print("Recuperación completada correctamente.")
            return True

        except Exception as error:
            for item in reversed(recovery_temp_files):
                recovery_path = item["recovery_path"]
                original_path = item["original_path"]
                if recovery_path.exists() and not original_path.exists():
                    try:
                        rename_with_retry(
                            recovery_path,
                            original_path,
                            max_attempts=10,
                            delay=1.0
                        )
                    except Exception:
                        pass

            print("Error durante la recuperación:", error)
            return False

    def create_backup_sync(self, temp_files, folder_path, progress_callback=None):
        backup_path = folder_path / BACKUP_FILENAME

        backup = {
            "version": 1,
            "status": "renaming",
            "folder": str(folder_path),
            "files": []
        }

        total_files = len(temp_files)
        for idx, item in enumerate(temp_files, start=1):
            file = item["file"]
            temp_path = item["temp_path"]
            final_path = item["final_path"]

            file_hash = compute_file_hash(file.path) if file.path.exists() else None

            backup["files"].append({
                "original_name": file.original_name,
                "original_path": str(file.original_path),
                "temporary_name": temp_path.name,
                "temporary_path": str(temp_path),
                "final_name": final_path.name,
                "final_path": str(final_path),
                "sha256": file_hash
            })

            if progress_callback:
                progress_callback(idx, total_files, file.original_name)

        temp_backup = folder_path / (BACKUP_FILENAME + ".tmp")
        with temp_backup.open("w", encoding="utf-8") as backup_file:
            json.dump(backup, backup_file, indent=4, ensure_ascii=False)
            backup_file.flush()

        temp_backup.replace(backup_path)
        return backup_path
