import uuid
import re

import shutil
from pathlib import Path
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from wutils_sysfiles import rename_with_retry, clean_prefix
from wconst import BACKUP_FILENAME, TEMP_PREFIX


class WorkerSignals(QObject):
    # sub_current, sub_total, sub_msg, main_current, main_total, main_msg
    progress = pyqtSignal(int, int, str, int, int, str)
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
                self.signals.progress.emit(
                    0, 0, "Recuperando respaldo pendiente...",
                    0, 2, "Recuperación de respaldo"
                )
                recovered = self.file_utils.recover_backup_sync(self.folder_path)
                if not recovered:
                    self.signals.error.emit("No se pudo completar la recuperación del respaldo pendiente.")
                    return

            self.signals.progress.emit(
                0, 0, "Iniciando lectura de archivos...",
                0, 2, "Cargando carpeta"
            )
            all_entries = list(self.folder_path.iterdir())
            total = len(all_entries)
            
            files = []
            for idx, entry in enumerate(all_entries, start=1):
                if entry.is_file() and not entry.name.startswith(TEMP_PREFIX):
                    files.append(entry)
                if total > 0 and (idx % 10 == 0 or idx == total):
                    self.signals.progress.emit(
                        idx, total, f"Leyendo archivo {idx} de {total}: {entry.name}",
                        1, 2, "Leyendo archivos de la carpeta"
                    )

            self.signals.progress.emit(
                1, 1, "Ordenando lista de archivos...",
                2, 2, "Finalizando carga"
            )
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

            # Total de operaciones generales: Total archivos (Respaldo) + Total archivos (Temp) + Total archivos (Final)
            total_main_steps = total_files * 3

            # FASE 1: Plan
            temp_files = []
            for index, file in enumerate(self.files, start=1):
                temp_name = TEMP_PREFIX + uuid.uuid4().hex + file.path.suffix
                temp_path = self.folder_path / temp_name

                # Asegurar que clean_name incluye la extensión
                final_name = number_format.format(index) + file.clean_name
                final_path = self.folder_path / final_name

                temp_files.append({
                    "file": file,
                    "temp_path": temp_path,
                    "final_path": final_path
                })

            # FASE 2: Backup con progreso detallado
            def backup_progress_cb(sub_curr, sub_tot, filename):
                msg = f"Calculando hash y respaldando {sub_curr}/{sub_tot}: {filename}"
                main_msg = f"Etapa 1/3: Creando respaldo ({sub_curr}/{sub_tot})"
                self.signals.progress.emit(sub_curr, sub_tot, msg, sub_curr, total_main_steps, main_msg)

            self.file_utils.create_backup_sync(temp_files, self.folder_path, progress_callback=backup_progress_cb)

            # FASE 3: Originales -> Temporales
            for idx, item in enumerate(temp_files, start=1):
                item["file"].path.rename(item["temp_path"])
                sub_msg = f"Renombrando a temporal {idx}/{total_files}: {item['file'].original_name}"
                main_idx = total_files + idx
                main_msg = f"Etapa 2/3: Renombrado temporal ({idx}/{total_files})"
                self.signals.progress.emit(idx, total_files, sub_msg, main_idx, total_main_steps, main_msg)

            # FASE 4: Temporales -> Definitivos
            for idx, item in enumerate(temp_files, start=1):
                temp_path = item["temp_path"]
                final_path = item["final_path"]
                rename_with_retry(temp_path, final_path, max_attempts=10, delay=2.0)
                item["file"].path = final_path
                # El estado confirmado (original_path/original_name/original_row)
                # se actualiza en el hilo de interfaz solo después de finalizar
                # correctamente toda la operación.
                item["file"].clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", final_path.name)

                sub_msg = f"Aplicando numeración final {idx}/{total_files}: {final_path.name}"
                main_idx = (total_files * 2) + idx
                main_msg = f"Etapa 3/3: Aplicando numeración final ({idx}/{total_files})"
                self.signals.progress.emit(idx, total_files, sub_msg, main_idx, total_main_steps, main_msg)

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


class FormatHundredsTask(QRunnable):
    def __init__(self, folder_path, files, file_utils):
        super().__init__()
        self.folder_path = Path(folder_path)
        self.files = files
        self.file_utils = file_utils
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            total_files = len(self.files)
            if total_files == 0:
                self.signals.finished.emit(True)
                return

            number_format = "{:03d}. "
            total_main_steps = total_files * 3

            # FASE 1: Plan
            temp_files = []
            for index, file in enumerate(self.files, start=1):
                temp_name = TEMP_PREFIX + uuid.uuid4().hex + file.path.suffix
                temp_path = self.folder_path / temp_name

                final_name = number_format.format(index) + file.clean_name
                final_path = self.folder_path / final_name

                temp_files.append({
                    "file": file,
                    "temp_path": temp_path,
                    "final_path": final_path
                })

            # FASE 2: Backup
            def backup_progress_cb(sub_curr, sub_tot, filename):
                msg = f"Calculando hash y respaldando {sub_curr}/{sub_tot}: {filename}"
                main_msg = f"Etapa 1/3: Creando respaldo ({sub_curr}/{sub_tot})"
                self.signals.progress.emit(sub_curr, sub_tot, msg, sub_curr, total_main_steps, main_msg)

            self.file_utils.create_backup_sync(temp_files, self.folder_path, progress_callback=backup_progress_cb)

            # FASE 3: Originales -> Temporales
            for idx, item in enumerate(temp_files, start=1):
                item["file"].path.rename(item["temp_path"])
                sub_msg = f"Renombrando a temporal {idx}/{total_files}: {item['file'].original_name}"
                main_idx = total_files + idx
                main_msg = f"Etapa 2/3: Renombrado temporal ({idx}/{total_files})"
                self.signals.progress.emit(idx, total_files, sub_msg, main_idx, total_main_steps, main_msg)

            # FASE 4: Temporales -> Definitivos
            for idx, item in enumerate(temp_files, start=1):
                temp_path = item["temp_path"]
                final_path = item["final_path"]
                rename_with_retry(temp_path, final_path, max_attempts=10, delay=2.0)
                item["file"].path = final_path
                item["file"].original_path = final_path
                item["file"].original_name = final_path.name
                item["file"].clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", final_path.name)

                sub_msg = f"Aplicando formato de centenas {idx}/{total_files}: {final_path.name}"
                main_idx = (total_files * 2) + idx
                main_msg = f"Etapa 3/3: Aplicando formato de centenas ({idx}/{total_files})"
                self.signals.progress.emit(idx, total_files, sub_msg, main_idx, total_main_steps, main_msg)

            # FASE 5: Eliminar backup
            backup_path = self.folder_path / BACKUP_FILENAME
            if backup_path.exists():
                backup_path.unlink()

            self.signals.finished.emit(True)
        except Exception as error:
            recovered = self.file_utils.recover_backup_sync(self.folder_path)
            if recovered:
                for file in self.files:
                    file.path = file.original_path
            self.signals.error.emit(f"Error durante el cambio a centenas: {error}")


class IntegrateFilesTask(QRunnable):
    def __init__(self, target_folder, selected_file_paths, folder_is_numbered, selected_case, file_utils):
        super().__init__()
        self.target_folder = Path(target_folder)
        self.selected_file_paths = [Path(p) for p in selected_file_paths]
        self.folder_is_numbered = folder_is_numbered
        self.selected_case = selected_case
        self.file_utils = file_utils
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            from natsort import natsorted
            self.signals.progress.emit(
                0, 0, "Analizando archivos a integrar...",
                0, 2, "Etapa 1/2: Análisis de archivos"
            )

            existing_files = [
                f for f in self.target_folder.iterdir()
                if f.is_file() and not f.name.startswith(TEMP_PREFIX)
            ]

            if not self.folder_is_numbered:
                all_items = []
                for ef in existing_files:
                    cname = clean_prefix(ef.name)
                    all_items.append({
                        "is_selected": False,
                        "source_path": ef,
                        "clean_name": cname
                    })

                for sf in self.selected_file_paths:
                    cname = clean_prefix(sf.name)
                    temp_dest = self.target_folder / (f"{TEMP_PREFIX}import_{uuid.uuid4().hex}{sf.suffix}")
                    shutil.move(sf, temp_dest)
                    all_items.append({
                        "is_selected": True,
                        "source_path": temp_dest,
                        "clean_name": cname
                    })

                all_items = natsorted(all_items, key=lambda x: x["clean_name"].lower())

                total_count = len(all_items)
                if total_count < 100:
                    fmt = "{:02d}. "
                elif total_count < 1000:
                    fmt = "{:03d}. "
                else:
                    fmt = "{:04d}. "

                temp_plan = []
                for idx, item in enumerate(all_items, start=1):
                    final_name = fmt.format(idx) + item["clean_name"]
                    final_path = self.target_folder / final_name
                    temp_name = TEMP_PREFIX + uuid.uuid4().hex + item["source_path"].suffix
                    temp_path = self.target_folder / temp_name

                    temp_plan.append({
                        "source_path": item["source_path"],
                        "temp_path": temp_path,
                        "final_path": final_path,
                        "clean_name": item["clean_name"]
                    })

                total_steps = len(temp_plan) * 2

                # Mover todos a temp
                for idx, tp in enumerate(temp_plan, start=1):
                    tp["source_path"].rename(tp["temp_path"])
                    sub_msg = f"Renombrado temporal {idx}/{len(temp_plan)}: {tp['clean_name']}"
                    main_msg = f"Etapa 1/2: Moviendo a ubicación temporal ({idx}/{len(temp_plan)})"
                    self.signals.progress.emit(idx, len(temp_plan), sub_msg, idx, total_steps, main_msg)

                # Mover todos de temp a final
                for idx, tp in enumerate(temp_plan, start=1):
                    rename_with_retry(tp["temp_path"], tp["final_path"], max_attempts=10, delay=2.0)
                    sub_msg = f"Aplicando nombre final {idx}/{len(temp_plan)}: {tp['final_path'].name}"
                    main_idx = len(temp_plan) + idx
                    main_msg = f"Etapa 2/2: Aplicando nombres finales ({idx}/{len(temp_plan)})"
                    self.signals.progress.emit(idx, len(temp_plan), sub_msg, main_idx, total_steps, main_msg)

            else:
                existing_files = natsorted(existing_files, key=lambda f: f.name.lower())
                last_num = len(existing_files)
                total_new_count = last_num + len(self.selected_file_paths)

                if total_new_count < 100:
                    fmt = "{:02d}. "
                elif total_new_count < 1000:
                    fmt = "{:03d}. "
                else:
                    fmt = "{:04d}. "

                items_plan = []
                for idx, ef in enumerate(existing_files, start=1):
                    cname = re.sub(r"^\d+(?:_|\.\s*)", "", ef.name)
                    final_name = fmt.format(idx) + cname
                    items_plan.append({
                        "source_path": ef,
                        "final_name": final_name
                    })

                selected_processed = []
                if self.selected_case == "CASE_2_CLEAN":
                    sorted_selected = natsorted(self.selected_file_paths, key=lambda f: f.name.lower())
                    for idx, sf in enumerate(sorted_selected, start=1):
                        num = last_num + idx
                        cname = re.sub(r"^\d+(?:_|\.\s*)", "", sf.name)
                        final_name = fmt.format(num) + cname
                        selected_processed.append((sf, final_name))

                elif self.selected_case == "CASE_1_NO_NUMERATION":
                    for idx, sf in enumerate(self.selected_file_paths, start=1):
                        num = last_num + idx
                        cname = sf.name
                        final_name = fmt.format(num) + cname
                        selected_processed.append((sf, final_name))

                else:  # CASE_3_STRANGE_OR_GAPS
                    cleaned_files = []
                    for sf in self.selected_file_paths:
                        cname = clean_prefix(sf.name)
                        cleaned_files.append((sf, cname))

                    cleaned_files = natsorted(cleaned_files, key=lambda x: x[1].lower())

                    for idx, (sf, cname) in enumerate(cleaned_files, start=1):
                        num = last_num + idx
                        final_name = fmt.format(num) + cname
                        selected_processed.append((sf, final_name))

                for sf, final_name in selected_processed:
                    temp_dest = self.target_folder / (f"{TEMP_PREFIX}import_{uuid.uuid4().hex}{sf.suffix}")
                    shutil.move(sf, temp_dest)
                    items_plan.append({
                        "source_path": temp_dest,
                        "final_name": final_name
                    })

                temp_plan = []
                for item in items_plan:
                    temp_name = TEMP_PREFIX + uuid.uuid4().hex + item["source_path"].suffix
                    temp_path = self.target_folder / temp_name
                    final_path = self.target_folder / item["final_name"]
                    temp_plan.append({
                        "source_path": item["source_path"],
                        "temp_path": temp_path,
                        "final_path": final_path,
                        "final_name": item["final_name"]
                    })

                total_steps = len(temp_plan) * 2

                for idx, tp in enumerate(temp_plan, start=1):
                    tp["source_path"].rename(tp["temp_path"])
                    sub_msg = f"Preparando temporal {idx}/{len(temp_plan)}: {tp['final_name']}"
                    main_msg = f"Etapa 1/2: Moviendo a ubicación temporal ({idx}/{len(temp_plan)})"
                    self.signals.progress.emit(idx, len(temp_plan), sub_msg, idx, total_steps, main_msg)

                for idx, tp in enumerate(temp_plan, start=1):
                    rename_with_retry(tp["temp_path"], tp["final_path"], max_attempts=10, delay=2.0)
                    sub_msg = f"Integrando archivo {idx}/{len(temp_plan)}: {tp['final_name']}"
                    main_idx = len(temp_plan) + idx
                    main_msg = f"Etapa 2/2: Aplicando nombres finales ({idx}/{len(temp_plan)})"
                    self.signals.progress.emit(idx, len(temp_plan), sub_msg, main_idx, total_steps, main_msg)

            updated_files = [
                f for f in self.target_folder.iterdir()
                if f.is_file() and not f.name.startswith(TEMP_PREFIX)
            ]
            updated_files.sort(key=lambda file: file.name.lower())

            self.signals.finished.emit(updated_files)

        except Exception as error:
            try:
                for item in self.target_folder.iterdir():
                    if item.is_file() and item.name.startswith(TEMP_PREFIX):
                        try:
                            item.unlink()
                        except Exception:
                            pass
            except Exception:
                pass
            self.signals.error.emit(f"Error durante la integración de archivos: {error}")


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
                if f.is_file() and not f.name.startswith(TEMP_PREFIX)
            ]
            total_files = len(all_entries)
            if total_files == 0:
                self.signals.finished.emit([])
                return

            temp_plan = []
            for file in all_entries:
                original_name = file.name
                clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", original_name)
                if clean_name != original_name:
                    temp_name = TEMP_PREFIX + uuid.uuid4().hex + file.suffix
                    temp_path = self.folder_path / temp_name
                    final_path = self.folder_path / clean_name
                    temp_plan.append({
                        "original_path": file,
                        "temp_path": temp_path,
                        "final_path": final_path,
                        "clean_name": clean_name
                    })

            if temp_plan:
                total_steps = len(temp_plan) * 2
                for idx, item in enumerate(temp_plan, start=1):
                    item["original_path"].rename(item["temp_path"])
                    sub_msg = f"Renombrando a temporal {idx}/{len(temp_plan)}: {item['clean_name']}"
                    main_msg = f"Etapa 1/2: Moviendo a ubicación temporal ({idx}/{len(temp_plan)})"
                    self.signals.progress.emit(idx, len(temp_plan), sub_msg, idx, total_steps, main_msg)

                for idx, item in enumerate(temp_plan, start=1):
                    item["temp_path"].rename(item["final_path"])
                    sub_msg = f"Quitando numeración {idx}/{len(temp_plan)}: {item['clean_name']}"
                    main_idx = len(temp_plan) + idx
                    main_msg = f"Etapa 2/2: Removiendo prefijos numéricos ({idx}/{len(temp_plan)})"
                    self.signals.progress.emit(idx, len(temp_plan), sub_msg, main_idx, total_steps, main_msg)

            updated_files = [
                f for f in self.folder_path.iterdir()
                if f.is_file() and not f.name.startswith(TEMP_PREFIX)
            ]
            updated_files.sort(key=lambda file: file.name.lower())

            self.signals.finished.emit(updated_files)
        except Exception as error:
            self.signals.error.emit(f"Error durante la des-enumeración: {error}")
