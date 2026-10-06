import re
import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import syswall
from sysprog import DualProgressDialog
from wconst import BACKUP_FILENAME, TEMP_PREFIX


NUMBERING_RE = re.compile(r"^\d{2,3}\.\s")


class MoveSignals(QObject):
    progress = pyqtSignal(int, int, str, int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)


def remove_standard_numbering(filename):
    return NUMBERING_RE.sub("", Path(filename).name, count=1)


def numbering_format(total):
    if total < 100:
        return "{:02d}. "
    if total < 1000:
        return "{:03d}. "
    return "{:04d}. "


def natural_sort_key(path):
    name = Path(path).name.lower()
    match = re.match(r"^(\d+)[._-]\s*", name)
    if match:
        return (0, int(match.group(1)), name)
    return (1, name)


def build_destination_plan(existing_paths, selected_paths, remove_selected_numbering):
    existing = sorted(existing_paths, key=natural_sort_key)
    selected = list(selected_paths)

    items = []
    for path in existing:
        clean_filename = remove_standard_numbering(path.name)
        items.append((Path(path), clean_filename))

    for path in selected:
        path = Path(path)
        name = remove_standard_numbering(path.name) if remove_selected_numbering else path.name
        items.append((path, name))

    fmt = numbering_format(len(items))
    return [
        (source, fmt.format(index) + clean_filename)
        for index, (source, clean_name) in enumerate(items, start=1)
    ]


def build_source_plan(existing_paths):
    existing = sorted(existing_paths, key=natural_sort_key)
    fmt = numbering_format(len(existing))
    return [
        (Path(path), fmt.format(index) + remove_standard_numbering(path.name))
        for index, path in enumerate(existing, start=1)
    ]


def build_direct_move_plan(selected_paths, remove_selected_numbering):
    plan = []
    for path in selected_paths:
        path = Path(path)
        name = remove_standard_numbering(path.name) if remove_selected_numbering else path.name
        plan.append((path, name))
    return plan


def _has_duplicate_destination_names(plan):
    names = [final_name.lower() for _, final_name in plan]
    return len(names) != len(set(names))


class MoveSelectedTask(QRunnable):
    def __init__(
        self,
        source_folder,
        target_folder,
        selected_paths,
        remove_selected_numbering,
        reorganize_destination,
    ):
        super().__init__()
        self.source_folder = Path(source_folder)
        self.target_folder = Path(target_folder)
        self.selected_paths = [Path(path) for path in selected_paths]
        self.remove_selected_numbering = remove_selected_numbering
        self.reorganize_destination = reorganize_destination
        self.signals = MoveSignals()

    def _emit_progress(self, current, total, label, phase, phase_total, phase_label):
        self.signals.progress.emit(
            current, total, label, phase, phase_total, phase_label
        )

    def run(self):
        selected_staged = []
        target_staged = []
        source_staged = []
        finalized = []

        try:
            destination_existing = [
                path
                for path in self.target_folder.iterdir()
                if path.is_file()
                and not path.name.startswith(TEMP_PREFIX)
                and path.name != BACKUP_FILENAME
            ]

            if self.reorganize_destination:
                destination_plan = build_destination_plan(
                    destination_existing,
                    self.selected_paths,
                    self.remove_selected_numbering,
                )
            else:
                destination_plan = build_direct_move_plan(
                    self.selected_paths,
                    self.remove_selected_numbering,
                )

                existing_names = {path.name.lower() for path in destination_existing}
                planned_names = {final_name.lower() for _, final_name in destination_plan}

                if _has_duplicate_destination_names(destination_plan):
                    raise FileExistsError(
                        "Los archivos seleccionados producirían nombres duplicados "
                        "en la carpeta de destino."
                    )

                conflicts = sorted(existing_names & planned_names)
                if conflicts:
                    raise FileExistsError(
                        "Ya existen en la carpeta de destino los siguientes archivos: "
                        + ", ".join(conflicts)
                    )

            source_remaining = [
                path
                for path in self.source_folder.iterdir()
                if path.is_file()
                and path not in self.selected_paths
                and not path.name.startswith(TEMP_PREFIX)
                and path.name != BACKUP_FILENAME
            ]
            source_plan = build_source_plan(source_remaining)

            total_move = len(self.selected_paths)
            total_destination = len(destination_plan)
            total_source = len(source_plan)
            total_work = max(total_move + total_destination + total_source, 1)

            self._emit_progress(
                0,
                total_work,
                "Preparando movimiento...",
                1,
                4,
                "Moviendo archivos seleccionados (Etapa 1 de 4)",
            )

            for index, source_path in enumerate(self.selected_paths, start=1):
                temp_name = f"{TEMP_PREFIX}move_{uuid.uuid4().hex}{source_path.suffix}"
                temp_path = self.target_folder / temp_name
                shutil.move(str(source_path), str(temp_path))
                selected_staged.append((temp_path, source_path))
                self._emit_progress(
                    index,
                    total_work,
                    f"Moviendo seleccionado {index}/{total_move}",
                    1,
                    4,
                    "Moviendo archivos seleccionados (Etapa 1 de 4)",
                )

            self._emit_progress(
                total_move,
                total_work,
                "Preparando renombrado...",
                2,
                4,
                "Preparando destino y origen (Etapa 2 de 4)",
            )

            if self.reorganize_destination:
                selected_temp_paths = {temp_path for temp_path, _ in selected_staged}
                existing_for_stage = [
                    source
                    for source, _ in destination_plan
                    if source not in self.selected_paths
                    and source not in selected_temp_paths
                ]

                for index, source_path in enumerate(existing_for_stage, start=1):
                    temp_name = f"{TEMP_PREFIX}move_{uuid.uuid4().hex}{source_path.suffix}"
                    temp_path = self.target_folder / temp_name
                    source_path.rename(temp_path)
                    target_staged.append((temp_path, source_path))
                    self._emit_progress(
                        total_move + index,
                        total_work,
                        f"Preparando destino {index}/{len(existing_for_stage)}",
                        2,
                        4,
                        "Preparando destino y origen (Etapa 2 de 4)",
                    )

            source_for_stage = [source for source, _ in source_plan]
            for index, source_path in enumerate(source_for_stage, start=1):
                temp_name = f"{TEMP_PREFIX}source_{uuid.uuid4().hex}{source_path.suffix}"
                temp_path = self.source_folder / temp_name
                source_path.rename(temp_path)
                source_staged.append((temp_path, source_path))
                self._emit_progress(
                    total_move + index,
                    total_work,
                    f"Preparando origen {index}/{total_source}",
                    2,
                    4,
                    "Preparando destino y origen (Etapa 2 de 4)",
                )

            destination_lookup = {
                original: temp for temp, original in target_staged
            }
            destination_lookup.update(
                {original: temp for temp, original in selected_staged}
            )

            source_lookup = {
                original: temp for temp, original in source_staged
            }

            self._emit_progress(
                0,
                total_work,
                "Aplicando cambios...",
                3,
                4,
                "Aplicando nombres definitivos (Etapa 3 de 4)",
            )

            for index, (original_source, final_name) in enumerate(
                destination_plan, start=1
            ):
                temp_source = destination_lookup.get(original_source)
                if temp_source is None:
                    raise FileNotFoundError(
                        f"No se encontró el archivo preparado: {original_source}"
                    )

                final_path = self.target_folder / final_name
                temp_source.rename(final_path)
                finalized.append((final_path, temp_source))
                self._emit_progress(
                    total_move + index,
                    total_work,
                    f"Actualizando destino {index}/{total_destination}",
                    3,
                    4,
                    "Aplicando nombres definitivos (Etapa 3 de 4)",
                )

            for index, (original_source, final_name) in enumerate(
                source_plan, start=1
            ):
                temp_source = source_lookup.get(original_source)
                if temp_source is None:
                    raise FileNotFoundError(
                        f"No se encontró el archivo preparado: {original_source}"
                    )

                final_path = self.source_folder / final_name
                temp_source.rename(final_path)
                finalized.append((final_path, temp_source))
                self._emit_progress(
                    total_move + total_destination + index,
                    total_work,
                    f"Reorganizando origen {index}/{total_source}",
                    4,
                    4,
                    "Cerrando huecos en la carpeta de origen (Etapa 4 de 4)",
                )

            self.signals.finished.emit()

        except Exception as error:
            for final_path, temp_path in reversed(finalized):
                try:
                    if final_path.exists():
                        final_path.rename(temp_path)
                except Exception:
                    pass

            for temp_path, original_path in reversed(source_staged):
                try:
                    if temp_path.exists():
                        temp_path.rename(original_path)
                except Exception:
                    pass

            for temp_path, original_path in reversed(target_staged):
                try:
                    if temp_path.exists():
                        temp_path.rename(original_path)
                except Exception:
                    pass

            for temp_path, original_path in reversed(selected_staged):
                try:
                    if temp_path.exists():
                        shutil.move(str(temp_path), str(original_path))
                except Exception:
                    pass

            self.signals.error.emit(f"Error durante el movimiento de archivos: {error}")


def move_selected_files(parent, model):
    selected_files = model.checked_files()
    if not selected_files:
        return

    source_folder = getattr(parent, "folder", None)
    if not source_folder or not Path(source_folder).exists():
        QMessageBox.warning(
            parent,
            "Atención",
            "No hay ninguna carpeta cargada.",
        )
        return

    source_folder = Path(source_folder).resolve()

    target_folder = QFileDialog.getExistingDirectory(
        parent,
        "Seleccionar carpeta de destino",
    )
    if not target_folder:
        return

    target_folder = Path(target_folder).resolve()

    if target_folder == source_folder:
        QMessageBox.warning(
            parent,
            "Carpeta no válida",
            "La carpeta de destino debe ser diferente de la carpeta cargada.",
        )
        return

    selected_paths = [file.path for file in selected_files]
    existing_paths = [
        path
        for path in target_folder.iterdir()
        if path.is_file()
        and not path.name.startswith(TEMP_PREFIX)
        and path.name != BACKUP_FILENAME
    ]

    answer = QMessageBox.question(
        parent,
        "Quitar numeración",
        "¿Deseas quitar de los archivos seleccionados las numeraciones iniciales "
        "\"00. \" o \"000. \" antes de moverlos?",
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Yes,
    )

    if answer == QMessageBox.StandardButton.Cancel:
        return

    remove_selected_numbering = answer == QMessageBox.StandardButton.Yes

    reorganize_answer = QMessageBox.question(
        parent,
        "Reorganizar carpeta de destino",
        "¿Deseas reorganizar y renumerar también los archivos de la carpeta de destino?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    reorganize_destination = (
        reorganize_answer == QMessageBox.StandardButton.Yes
    )

    locking_paths = selected_paths + (existing_paths if reorganize_destination else [])
    locking_apps = syswall.get_locking_processes(locking_paths)
    if locking_apps:
        apps_str = "\n• ".join(locking_apps)
        QMessageBox.warning(
            parent,
            "Archivos en uso",
            "Los siguientes programas están bloqueando archivos que se intentan modificar:"
            f"\n\n• {apps_str}"
            "\n\nCierra las aplicaciones manualmente antes de proceder.",
        )
        return

    progress_dialog = DualProgressDialog("Mover archivos seleccionados", parent)
    progress_dialog.show()

    task = MoveSelectedTask(
        source_folder,
        target_folder,
        selected_paths,
        remove_selected_numbering,
        reorganize_destination,
    )

    def on_finished():
        progress_dialog.close()
        model.set_all_checked(False)
        parent.file_utils.load_folder(parent, model)
        if reorganize_destination:
            message = (
                "Los archivos seleccionados fueron movidos y la numeración de las "
                "carpetas de origen y destino fue reorganizada correctamente."
            )
        else:
            message = (
                "Los archivos seleccionados fueron movidos. La carpeta de origen "
                "fue reorganizada y la carpeta de destino existente no fue modificada."
            )
        QMessageBox.information(parent, "Éxito", message)

    def on_error(message):
        progress_dialog.close()
        QMessageBox.critical(parent, "Error", message)
        parent.file_utils.load_folder(parent, model)

    task.signals.progress.connect(progress_dialog.update_progress)
    task.signals.finished.connect(on_finished)
    task.signals.error.connect(on_error)

    QThreadPool.globalInstance().start(task)
