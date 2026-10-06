import re
import shutil
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QSettings, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

import syswall
from sysprog import DualProgressDialog
from wconst import BACKUP_FILENAME, TEMP_PREFIX


NUMBERING_RE = re.compile(r"^\d{2,3}\.\s")
TRASH_PATH_KEY = "trash/folder"
SETTINGS_ORGANIZATION = "EtudeTools"
SETTINGS_APPLICATION = "NumHand"


class MoveSignals(QObject):
    progress = pyqtSignal(int, int, str, int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)




def get_settings():
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def get_trash_folder():
    value = get_settings().value(TRASH_PATH_KEY, "", type=str)
    if not value:
        return None
    path = Path(value).expanduser().resolve()
    return path if path.is_dir() else None


class TrashFolderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Establecer ruta de papelera")
        self.resize(620, 130)

        self.path_edit = QLineEdit(self)
        self.path_edit.setReadOnly(True)
        current = get_settings().value(TRASH_PATH_KEY, "", type=str)
        if current:
            self.path_edit.setText(str(Path(current).expanduser().resolve()))

        select_button = QPushButton("Select Other Folder", self)
        select_button.clicked.connect(self.select_other_folder)

        open_button = QPushButton("Open Folder", self)
        open_button.clicked.connect(self.open_folder)

        accept_button = QPushButton("Accept", self)
        accept_button.clicked.connect(self.accept)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Ruta:"))
        path_layout.addWidget(self.path_edit)

        button_layout = QHBoxLayout()
        button_layout.addWidget(select_button)
        button_layout.addWidget(open_button)
        button_layout.addStretch()
        button_layout.addWidget(accept_button)

        layout = QVBoxLayout(self)
        layout.addLayout(path_layout)
        layout.addLayout(button_layout)

    def select_other_folder(self):
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Other Folder",
            self.path_edit.text() or str(Path.home()),
        )
        if selected:
            self.path_edit.setText(str(Path(selected).resolve()))

    def open_folder(self):
        folder = self.path_edit.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(
                self,
                "Ruta no válida",
                "Selecciona primero una carpeta válida.",
            )
            return

        path = Path(folder)
        try:
            import os
            import platform
            import subprocess

            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as error:
            QMessageBox.warning(
                self,
                "No se pudo abrir la carpeta",
                str(error),
            )

    def accept(self):
        folder = self.path_edit.text().strip()
        if not folder or not Path(folder).is_dir():
            QMessageBox.warning(
                self,
                "Ruta no válida",
                "Selecciona una carpeta válida antes de aceptar.",
            )
            return

        settings = get_settings()
        settings.setValue(TRASH_PATH_KEY, str(Path(folder).resolve()))
        settings.sync()
        super().accept()


def set_trash_folder(parent):
    dialog = TrashFolderDialog(parent)
    dialog.exec()


def build_trash_move_plan(selected_paths, remove_selected_numbering):
    return build_direct_move_plan(
        selected_paths,
        remove_selected_numbering,
    )


def detect_folder_numbering(paths):
    files = [Path(path) for path in paths if Path(path).is_file()]
    files = [
        path for path in files
        if not path.name.startswith(TEMP_PREFIX)
        and path.name != BACKUP_FILENAME
    ]
    if not files:
        return "sin numerar"
    two_digit = sum(bool(re.match(r"^\d{2}\.\s", path.name)) for path in files)
    three_digit = sum(bool(re.match(r"^\d{3}\.\s", path.name)) for path in files)
    if two_digit == len(files):
        return "00. "
    if three_digit == len(files):
        return "000. "
    if two_digit == 0 and three_digit == 0:
        return "sin numerar"
    return "mixta"


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
        (source, fmt.format(index) + clean_name)
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
        reorganize_source=True,
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
            source_plan = build_source_plan(source_remaining) if self.reorganize_source else []

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


def check_folder_numbering(parent, model):
    source_folder = getattr(parent, "folder", None)
    if not source_folder or not Path(source_folder).is_dir():
        QMessageBox.warning(parent, "Atención", "No hay ninguna carpeta cargada.")
        return
    paths = [
        path for path in Path(source_folder).resolve().iterdir()
        if path.is_file()
        and not path.name.startswith(TEMP_PREFIX)
        and path.name != BACKUP_FILENAME
    ]
    numbering = detect_folder_numbering(paths)
    messages = {
        "00. ": 'La carpeta está numerada en formato de dos dígitos: "00. ".',
        "000. ": 'La carpeta está numerada en formato de tres dígitos: "000. ".',
        "sin numerar": "La carpeta no está numerada.",
        "mixta": "La carpeta tiene una numeración mixta o incompleta.",
    }
    QMessageBox.information(
        parent,
        "Comprobar Numeración de esta carpeta",
        messages[numbering],
    )


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
    source_paths = [
        path for path in source_folder.iterdir()
        if path.is_file()
        and not path.name.startswith(TEMP_PREFIX)
        and path.name != BACKUP_FILENAME
    ]
    source_numbering = detect_folder_numbering(source_paths)
    reorganize_source = source_numbering in ("00. ", "000. ")

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
        reorganize_source,
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


def move_selected_to_trash(parent, model):
    selected_files = model.checked_files()
    if not selected_files:
        return

    source_folder = getattr(parent, "folder", None)
    if not source_folder or not Path(source_folder).is_dir():
        QMessageBox.warning(parent, "Atención", "No hay ninguna carpeta cargada.")
        return

    trash_folder = get_trash_folder()
    if trash_folder is None:
        QMessageBox.warning(
            parent,
            "Papelera no configurada",
            "Establece primero una ruta válida mediante "
            '"Establecer ruta de papelera".',
        )
        return

    source_folder = Path(source_folder).resolve()
    trash_folder = trash_folder.resolve()

    if source_folder == trash_folder:
        QMessageBox.warning(
            parent,
            "Ruta no válida",
            "La papelera no puede ser la misma carpeta que la carpeta cargada.",
        )
        return

    confirmation = QMessageBox.question(
        parent,
        "Mover a papelera",
        "¿Deseas continuar con el movimiento de los archivos seleccionados a la papelera?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirmation != QMessageBox.StandardButton.Yes:
        return

    numbering_answer = QMessageBox.question(
        parent,
        "Quitar numeración",
        "¿Deseas quitar de los archivos seleccionados las numeraciones iniciales "
        '"00. " o "000. " antes de moverlos a la papelera?',
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Yes,
    )
    if numbering_answer == QMessageBox.StandardButton.Cancel:
        return

    remove_selected_numbering = (
        numbering_answer == QMessageBox.StandardButton.Yes
    )
    selected_paths = [Path(file.path) for file in selected_files]
    source_paths = [
        path for path in source_folder.iterdir()
        if path.is_file()
        and not path.name.startswith(TEMP_PREFIX)
        and path.name != BACKUP_FILENAME
    ]
    source_numbering = detect_folder_numbering(source_paths)
    reorganize_source = source_numbering in ("00. ", "000. ")

    trash_existing = [
        path
        for path in trash_folder.iterdir()
        if path.is_file()
        and not path.name.startswith(TEMP_PREFIX)
        and path.name != BACKUP_FILENAME
    ]
    trash_plan = build_trash_move_plan(
        selected_paths,
        remove_selected_numbering,
    )
    existing_names = {path.name.lower() for path in trash_existing}
    planned_names = {final_name.lower() for _, final_name in trash_plan}

    if len(planned_names) != len(trash_plan):
        QMessageBox.critical(
            parent,
            "Nombres duplicados",
            "Los archivos seleccionados producirían nombres duplicados en la papelera.",
        )
        return

    conflicts = sorted(existing_names & planned_names)
    if conflicts:
        QMessageBox.warning(
            parent,
            "Archivo ya existente",
            "Ya existen en la papelera los siguientes archivos:\n\n"
            + "\n".join(conflicts),
        )
        return

    locking_apps = syswall.get_locking_processes(selected_paths)
    if locking_apps:
        apps_str = "\n• ".join(locking_apps)
        QMessageBox.warning(
            parent,
            "Archivos en uso",
            "Los siguientes programas están bloqueando archivos que se intentan mover:"
            f"\n\n• {apps_str}\n\nCierra las aplicaciones manualmente antes de proceder.",
        )
        return

    progress_dialog = DualProgressDialog("Mover archivos a papelera", parent)
    progress_dialog.show()

    task = MoveSelectedTask(
        source_folder,
        trash_folder,
        selected_paths,
        remove_selected_numbering,
        False,
        reorganize_source,
    )

    def on_finished():
        progress_dialog.close()
        model.set_all_checked(False)
        parent.file_utils.load_folder(parent, model)
        QMessageBox.information(
            parent,
            "Éxito",
            "Los archivos seleccionados fueron movidos al destino guardado en QSettings. "
            + (
                "La carpeta de origen fue reorganizada."
                if reorganize_source
                else "La carpeta de origen no estaba numerada y no fue alterada."
            ),
        )

    def on_error(message):
        progress_dialog.close()
        QMessageBox.critical(parent, "Error", message)
        parent.file_utils.load_folder(parent, model)

    task.signals.progress.connect(progress_dialog.update_progress)
    task.signals.finished.connect(on_finished)
    task.signals.error.connect(on_error)
    QThreadPool.globalInstance().start(task)
