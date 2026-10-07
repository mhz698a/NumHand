import re
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from sysprog import DualProgressDialog
from wconst import TEMP_PREFIX


class ApplyNonEnumSignals(QObject):
    progress = pyqtSignal(int, int, str, int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class ApplyNonEnumTask(QRunnable):
    def __init__(self, files):
        super().__init__()
        self.files = list(files)
        self.signals = ApplyNonEnumSignals()

    @pyqtSlot()
    def run(self):
        staged = []
        finalized = []

        try:
            changes = []
            for file in self.files:
                if file.clean_name == file.original_clean_name:
                    continue

                final_name = file.pending_name
                if not final_name:
                    current_name = file.path.name
                    suffix = Path(current_name).suffix
                    stem = current_name[:-len(suffix)] if suffix else current_name
                    prefix_match = re.match(r"^(\d+(?:_|\.\s*))", stem)
                    prefix = prefix_match.group(1) if prefix_match else ""
                    final_name = f"{prefix}{file.clean_name}"

                final_path = file.path.parent / final_name
                if final_path != file.path:
                    changes.append((file, final_path))

            if not changes:
                self.signals.finished.emit()
                return

            target_names = [path.name.lower() for _, path in changes]
            if len(target_names) != len(set(target_names)):
                raise FileExistsError(
                    "Los renombrados individuales producirían nombres duplicados."
                )

            change_sources = {file.path.resolve() for file, _ in changes}
            for file, final_path in changes:
                if final_path.exists() and final_path.resolve() not in change_sources:
                    raise FileExistsError(
                        f"Ya existe un archivo con el nombre '{final_path.name}'."
                    )

            total = len(changes)
            self.signals.progress.emit(
                0, total, "Preparando renombrados individuales...",
                1, 2, "Renombrados individuales (Etapa 1 de 2)"
            )

            for index, (file, final_path) in enumerate(changes, start=1):
                temp_path = file.path.parent / (
                    f"{TEMP_PREFIX}non_enum_{uuid.uuid4().hex}{file.path.suffix}"
                )
                file.path.rename(temp_path)
                staged.append((file, temp_path, final_path))
                self.signals.progress.emit(
                    index, total, f"Preparando {index}/{total}",
                    1, 2, "Renombrados individuales (Etapa 1 de 2)"
                )

            for index, (file, temp_path, final_path) in enumerate(staged, start=1):
                temp_path.rename(final_path)
                finalized.append((file, final_path))
                self.signals.progress.emit(
                    index, total, f"Aplicando {index}/{total}",
                    2, 2, "Renombrados individuales (Etapa 2 de 2)"
                )

            for file, final_path in finalized:
                file.path = final_path
                file.original_path = final_path
                file.original_name = final_path.name
                file.original_clean_name = file.clean_name
                file.pending_name = None

            self.signals.finished.emit()

        except Exception as error:
            for file, final_path in reversed(finalized):
                try:
                    if final_path.exists():
                        final_path.rename(file.path)
                except Exception:
                    pass

            for file, temp_path, final_path in reversed(staged):
                try:
                    if temp_path.exists():
                        temp_path.rename(file.path)
                except Exception:
                    pass

            self.signals.error.emit(
                f"Error durante los renombrados individuales: {error}"
            )


def _is_cleanly_enumerated(paths):
    files = [Path(path) for path in paths if Path(path).is_file()]
    if not files:
        return False

    matches = []
    for path in files:
        match = re.match(r"^(\d{2}|\d{3})\.\s", path.name)
        if not match:
            return False
        matches.append((int(match.group(1)), len(match.group(1))))

    widths = {width for _, width in matches}
    if len(widths) != 1:
        return False

    numbers = sorted(number for number, _ in matches)
    return numbers == list(range(1, len(numbers) + 1))


def apply_changes_non_enum(parent, model):
    if not parent.folder or not parent.folder.exists() or not model.files:
        QMessageBox.warning(
            parent,
            "Atención",
            "No hay ninguna carpeta cargada o la carpeta está vacía.",
        )
        return

    paths = [
        file.path
        for file in model.files
        if file.path.exists()
    ]
    if _is_cleanly_enumerated(paths):
        confirmation = QMessageBox.question(
            parent,
            "Carpeta enumerada",
            "Esta carpeta ya esta enumerada, ¿Desea aplicar los cambios normalmente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmation == QMessageBox.StandardButton.Yes:
            parent.file_utils.apply_order(parent, model)
        return

    confirmation = QMessageBox.question(
        parent,
        "Aplicar cambios sin enumerar",
        "Esta carpeta no esta numerada o tiene numeración extraña y solo se habrá cambios de nombre ¿Desea continuar?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirmation != QMessageBox.StandardButton.Yes:
        return

    changes = [
        file for file in model.files
        if file.clean_name != file.original_clean_name
    ]
    if not changes:
        QMessageBox.information(
            parent,
            "Sin cambios",
            "No hay cambios de nombre individuales pendientes.",
        )
        return

    if parent.file_utils.check_files_locked(parent, [file.path for file in changes]):
        return

    progress_dialog = DualProgressDialog(
        "Aplicando cambios sin enumerar",
        parent,
    )
    progress_dialog.show()

    task = ApplyNonEnumTask(changes)

    def on_finished():
        progress_dialog.close()
        model.layoutChanged.emit()

    def on_error(message):
        progress_dialog.close()
        QMessageBox.critical(parent, "Error", message)
        model.layoutChanged.emit()

    task.signals.progress.connect(progress_dialog.update_progress)
    task.signals.error.connect(on_error)
    task.signals.finished.connect(on_finished)

    QThreadPool.globalInstance().start(task)
