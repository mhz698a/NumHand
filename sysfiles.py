import uuid
import json
import re
from pathlib import Path
from PyQt6.QtWidgets import QFileDialog, QProgressDialog, QMessageBox
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, Qt

BACKUP_FILENAME = ".__file_manager_backup__.json"


class WorkerSignals(QObject):
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(object)         # result payload
    error = pyqtSignal(str)              # error message


class LoadFolderTask(QRunnable):
    def __init__(self, folder_path, file_utils):
        super().__init__()
        self.folder_path = Path(folder_path)
        self.file_utils = file_utils
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            # Check backup if exists
            backup_path = self.folder_path / BACKUP_FILENAME
            if backup_path.exists():
                self.signals.progress.emit(0, 0, "Recuperando respaldo pendiente...")
                recovered = self.file_utils.recover_backup_sync(self.folder_path)
                if not recovered:
                    self.signals.error.emit("No se pudo completar la recuperación del respaldo pendiente.")
                    return

            self.signals.progress.emit(0, 0, "Leyendo archivos...")
            all_entries = list(self.folder_path.iterdir())
            total = len(all_entries)

            files = []
            for idx, entry in enumerate(all_entries, start=1):
                if entry.is_file() and not entry.name.startswith(".__file_manager__"):
                    files.append(entry)
                if total > 0 and (idx % 10 == 0 or idx == total):
                    self.signals.progress.emit(idx, total, f"Leyendo archivo {idx} de {total}...")

            self.signals.progress.emit(total, total, "Ordenando archivos...")
            files.sort(key=lambda file: file.name.lower())

            self.signals.finished.emit(files)
        except Exception as e:
            self.signals.error.emit(str(e))


class ApplyOrderTask(QRunnable):
    def __init__(self, folder_path, files, file_utils):
        super().__init__()
        self.folder_path = Path(folder_path)
        self.files = files  # list of FileEntry
        self.file_utils = file_utils
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            total_files = len(self.files)
            if total_files == 0:
                self.signals.finished.emit(True)
                return

            if total_files < 100:
                number_format = "{:02d}. "
            elif total_files < 1000:
                number_format = "{:03d}. "
            else:
                number_format = "{:04d}. "

            # FASE 1: Plan
            temp_files = []
            for index, file in enumerate(self.files, start=1):
                temp_name = ".__file_manager__" + uuid.uuid4().hex + file.path.suffix
                temp_path = self.folder_path / temp_name

                final_name = number_format.format(index) + file.clean_name
                final_path = self.folder_path / final_name

                temp_files.append({
                    "file": file,
                    "temp_path": temp_path,
                    "final_path": final_path
                })

            # FASE 2: Backup
            self.signals.progress.emit(0, total_files * 2, "Creando respaldo...")
            self.file_utils.create_backup_sync(temp_files, self.folder_path)

            # FASE 3: Originales -> Temporales
            for idx, item in enumerate(temp_files, start=1):
                item["file"].path.rename(item["temp_path"])
                self.signals.progress.emit(idx, total_files * 2, f"Paso 1/2: renombrando {idx}/{total_files}")

            # FASE 4: Temporales -> Definitivos
            for idx, item in enumerate(temp_files, start=1):
                temp_path = item["temp_path"]
                final_path = item["final_path"]
                temp_path.rename(final_path)
                item["file"].path = final_path
                item["file"].original_path = final_path
                item["file"].original_name = final_path.name
                item["file"].clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", final_path.name)
                self.signals.progress.emit(total_files + idx, total_files * 2, f"Paso 2/2: aplicando numeración {idx}/{total_files}")

            # FASE 5: Eliminar backup
            backup_path = self.folder_path / BACKUP_FILENAME
            if backup_path.exists():
                backup_path.unlink()

            self.signals.finished.emit(True)
        except Exception as error:
            # Intentar recuperación
            recovered = self.file_utils.recover_backup_sync(self.folder_path)
            if recovered:
                for file in self.files:
                    file.path = file.original_path
            self.signals.error.emit(f"Error durante el renombrado: {error}")


class ResetNumerationTask(QRunnable):
    def __init__(self, folder_path, file_utils):
        super().__init__()
        self.folder_path = Path(folder_path)
        self.file_utils = file_utils
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            all_entries = [
                f for f in self.folder_path.iterdir()
                if f.is_file() and not f.name.startswith(".__file_manager__")
            ]
            total_files = len(all_entries)
            if total_files == 0:
                self.signals.finished.emit([])
                return

            # Renombrar removiendo el prefijo numérico
            temp_plan = []
            for file in all_entries:
                original_name = file.name
                clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", original_name)
                if clean_name != original_name:
                    temp_name = ".__file_manager__" + uuid.uuid4().hex + file.suffix
                    temp_path = self.folder_path / temp_name
                    final_path = self.folder_path / clean_name
                    temp_plan.append({
                        "original_path": file,
                        "temp_path": temp_path,
                        "final_path": final_path
                    })

            if temp_plan:
                # Renombrar a temp primero para evitar colisiones
                total_steps = len(temp_plan) * 2
                for idx, item in enumerate(temp_plan, start=1):
                    item["original_path"].rename(item["temp_path"])
                    self.signals.progress.emit(idx, total_steps, f"Des-enumerando (fase 1) {idx}/{len(temp_plan)}")

                for idx, item in enumerate(temp_plan, start=1):
                    item["temp_path"].rename(item["final_path"])
                    self.signals.progress.emit(len(temp_plan) + idx, total_steps, f"Des-enumerando (fase 2) {idx}/{len(temp_plan)}")

            # Volver a leer la carpeta de archivos actualizada
            updated_files = [
                f for f in self.folder_path.iterdir()
                if f.is_file() and not f.name.startswith(".__file_manager__")
            ]
            updated_files.sort(key=lambda file: file.name.lower())

            self.signals.finished.emit(updated_files)
        except Exception as error:
            self.signals.error.emit(f"Error durante la des-enumeración: {error}")


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

        progress_dialog = QProgressDialog("Cargando carpeta...", "Cancelar", 0, 0, parent)
        progress_dialog.setWindowTitle("Cargando carpeta")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        progress_dialog.show()

        task = LoadFolderTask(parent.folder, self)

        def on_progress(current, total, message):
            progress_dialog.setLabelText(message)
            if total > 0:
                progress_dialog.setMaximum(total)
                progress_dialog.setValue(current)

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

    def apply_order(self, parent, model):
        if not parent.folder or not model.files:
            return

        progress_dialog = QProgressDialog("Aplicando numeración...", "Cancelar", 0, 0, parent)
        progress_dialog.setWindowTitle("Aplicando numeración")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        progress_dialog.show()

        task = ApplyOrderTask(parent.folder, model.files, self)

        def on_progress(current, total, message):
            progress_dialog.setLabelText(message)
            if total > 0:
                progress_dialog.setMaximum(total)
                progress_dialog.setValue(current)

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

        confirm = QMessageBox.question(
            parent,
            "Confirmar des-enumeración",
            "¿Deseas eliminar los prefijos numéricos iniciales de todos los archivos en esta carpeta?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        progress_dialog = QProgressDialog("Des-enumerando carpeta...", "Cancelar", 0, 0, parent)
        progress_dialog.setWindowTitle("Des-enumerando carpeta")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)
        progress_dialog.show()

        task = ResetNumerationTask(parent.folder, self)

        def on_progress(current, total, message):
            progress_dialog.setLabelText(message)
            if total > 0:
                progress_dialog.setMaximum(total)
                progress_dialog.setValue(current)

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
        if row < 0 or row >= len(model.files):
            return False

        file_entry = model.files[row]
        clean_stem = Path(file_entry.clean_name).stem
        if not new_base_name or new_base_name == clean_stem:
            return False

        old_path = file_entry.path
        suffix = old_path.suffix

        # Mantener el prefijo numérico si existe en el nombre actual del archivo en disco
        prefix_match = re.match(r"^(\d+(?:_|\.\s*))", old_path.name)
        prefix = prefix_match.group(1) if prefix_match else ""

        new_filename = f"{prefix}{new_base_name}{suffix}"
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
            file_entry.clean_name = f"{new_base_name}{suffix}"
            model.dataChanged.emit(model.index(row, 0), model.index(row, 0))
            return True
        except Exception as e:
            QMessageBox.critical(
                parent,
                "Error al renombrar",
                f"No se pudo renombrar el archivo: {e}"
            )
            return False

    def recover_backup_sync(self, folder_path):
        backup_path = folder_path / BACKUP_FILENAME
        if not backup_path.exists():
            return True

        try:
            with backup_path.open("r", encoding="utf-8") as backup_file:
                backup = json.load(backup_file)
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
                "current_path": current_path
            })

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
                current_path.rename(recovery_path)

                recovery_temp_files.append({
                    "recovery_path": recovery_path,
                    "original_path": original_path
                })

            for item in recovery_temp_files:
                item["recovery_path"].rename(item["original_path"])

            for item in recovery_plan:
                if not item["original_path"].exists():
                    raise RuntimeError(f"No se pudo verificar {item['original_path'].name}")

            backup_path.unlink()
            print("Recuperación completada correctamente.")
            return True

        except Exception as error:
            print("Error durante la recuperación:", error)
            return False

    def create_backup_sync(self, temp_files, folder_path):
        backup_path = folder_path / BACKUP_FILENAME

        backup = {
            "version": 1,
            "status": "renaming",
            "folder": str(folder_path),
            "files": []
        }

        for item in temp_files:
            file = item["file"]
            temp_path = item["temp_path"]
            final_path = item["final_path"]

            backup["files"].append({
                "original_name": file.original_name,
                "original_path": str(file.original_path),
                "temporary_name": temp_path.name,
                "temporary_path": str(temp_path),
                "final_name": final_path.name,
                "final_path": str(final_path)
            })

        temp_backup = folder_path / (BACKUP_FILENAME + ".tmp")
        with temp_backup.open("w", encoding="utf-8") as backup_file:
            json.dump(backup, backup_file, indent=4, ensure_ascii=False)
            backup_file.flush()

        temp_backup.replace(backup_path)
        return backup_path
