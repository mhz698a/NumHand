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
        items.append((Path(path), remove_standard_numbering(path.name)))

    for path in selected:
        path = Path(path)
        name = remove_standard_numbering(path.name) if remove_selected_numbering else path.name
        items.append((path, name))

    fmt = numbering_format(len(items))
    return [
        (source, fmt.format(index) + clean_name)
        for index, (source, clean_name) in enumerate(items, start=1)
    ]


class MoveSelectedTask(QRunnable):
    def __init__(self, source_folder, target_folder, selected_paths, remove_selected_numbering):
        super().__init__()
        self.source_folder = Path(source_folder)
        self.target_folder = Path(target_folder)
        self.selected_paths = [Path(path) for path in selected_paths]
        self.remove_selected_numbering = remove_selected_numbering
        self.signals = MoveSignals()

    def _emit_progress(self, current, total, label, phase, phase_total, phase_label):
        self.signals.progress.emit(
            current, total, label, phase, phase_total, phase_label
        )

    def run(self):
        selected_staged = []
        target_staged = []
        finalized = []

        try:
            existing_paths = [
                path for path in self.target_folder.iterdir()
                if path.is_file() and not path.name.startswith(TEMP_PREFIX) and path.name != BACKUP_FILENAME
            ]

            plan = build_destination_plan(
                existing_paths,
                self.selected_paths,
                self.remove_selected_numbering,
            )

            total = len(plan)
            self._emit_progress(
                0, total, "Preparando movimiento...", 1, 3,
                "Preparando archivos (Etapa 1 de 3)"
            )

            for index, source_path in enumerate(self.selected_paths, start=1):
                temp_name = f"{TEMP_PREFIX}move_{uuid.uuid4().hex}{source_path.suffix}"
                temp_path = self.target_folder / temp_name
                shutil.move(str(source_path), str(temp_path))
                selected_staged.append((temp_path, source_path))
                self._emit_progress(
                    index,
                    len(self.selected_paths),
                    f"Moviendo seleccionado {index}/{len(self.selected_paths)}",
                    1,
                    3,
                    "Moviendo archivos seleccionados (Etapa 1 de 3)",
                )

            self._emit_progress(
                0, total, "Evitando colisiones de nombres...", 2, 3,
                "Preparando renombrado (Etapa 2 de 3)"
            )

            staged_sources = {temp_path for temp_path, _ in selected_staged}
            existing_for_stage = [
                source for source, _ in plan
                if source not in self.selected_paths
                and source not in staged_sources
            ]

            for index, source_path in enumerate(existing_for_stage, start=1):
                temp_name = f"{TEMP_PREFIX}move_{uuid.uuid4().hex}{source_path.suffix}"
                temp_path = self.target_folder / temp_name
                source_path.rename(temp_path)
                target_staged.append((temp_path, source_path))
                self._emit_progress(
                    index,
                    len(existing_for_stage),
                    f"Preparando destino {index}/{len(existing_for_stage)}",
                    2,
                    3,
                    "Preparando renombrado (Etapa 2 de 3)",
                )

            staged_lookup = {
                original: temp for temp, original in target_staged
            }
            staged_lookup.update({
                original: temp for temp, original in selected_staged
            })

            self._emit_progress(
                0, total, "Aplicando numeración secuencial...", 3, 3,
                "Aplicando nombres definitivos (Etapa 3 de 3)"
            )

            for index, (original_source, final_name) in enumerate(plan, start=1):
                temp_source = staged_lookup.get(original_source)
                if temp_source is None:
                    raise FileNotFoundError(
                        f"No se encontró el archivo preparado: {original_source}"
                    )

                final_path = self.target_folder / final_name
                temp_source.rename(final_path)
                finalized.append((final_path, temp_source))
                self._emit_progress(
                    index,
                    total,
                    f"Renumerando {index}/{total}",
                    3,
                    3,
                    "Aplicando nombres definitivos (Etapa 3 de 3)",
                )

            self.signals.finished.emit()

        except Exception as error:
            for final_path, temp_path in reversed(finalized):
                try:
                    if final_path.exists():
                        final_path.rename(temp_path)
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
        path for path in target_folder.iterdir()
        if path.is_file() and not path.name.startswith(TEMP_PREFIX)
    ]

    locking_paths = selected_paths + existing_paths
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

    progress_dialog = DualProgressDialog("Mover archivos seleccionados", parent)
    progress_dialog.show()

    task = MoveSelectedTask(
        source_folder,
        target_folder,
        selected_paths,
        remove_selected_numbering,
    )

    def on_finished():
        progress_dialog.close()
        model.set_all_checked(False)
        parent.file_utils.load_folder(parent, model)
        QMessageBox.information(
            parent,
            "Éxito",
            "Los archivos seleccionados fueron movidos y la numeración de la carpeta "
            "de destino fue reorganizada correctamente.",
        )

    def on_error(message):
        progress_dialog.close()
        QMessageBox.critical(parent, "Error", message)
        parent.file_utils.load_folder(parent, model)

    task.signals.progress.connect(progress_dialog.update_progress)
    task.signals.finished.connect(on_finished)
    task.signals.error.connect(on_error)

    QThreadPool.globalInstance().start(task)
