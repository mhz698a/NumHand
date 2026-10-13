import uuid
import re
import time
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSlot

from wutils_sysfiles import rename_with_retry
from wconst import BACKUP_FILENAME, TEMP_PREFIX
from sysutils import WorkerSignals
from pyutils.foobar2000_api import Foobar2000Api


def build_apply_order_listfiles(files, folder_path, number_format):
    """Return only entries whose final path differs from their current path."""
    folder_path = Path(folder_path)
    plan = []
    for index, file in enumerate(files, start=1):
        final_path = folder_path / (number_format.format(index) + file.clean_name)
        if final_path != file.path:
            plan.append({
                "file": file,
                "temp_path": folder_path / (TEMP_PREFIX + uuid.uuid4().hex + file.path.suffix),
                "final_path": final_path,
            })
    return plan


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

            # Solo preparar archivos cuyo nombre final realmente cambia.
            # El índice sigue considerando todos los archivos para conservar la numeración.
            temp_files = build_apply_order_listfiles(
                self.files, self.folder_path, number_format
            )
            if not temp_files:
                self.signals.finished.emit(True)
                return

            # FASE 1/4: Respaldo
            def backup_cb(idx, total, orig_name):
                self.signals.progress.emit(
                    idx,
                    total,
                    f"Calculando hash y respaldando {idx}/{total}: {orig_name}",
                    1,
                    4,
                    "Respaldo (Etapa 1 de 4)"
                )

            self.file_utils.create_backup_sync(temp_files, self.folder_path, progress_callback=backup_cb)

            # FASE 2/4: Originales -> Temporales
            for idx, item in enumerate(temp_files, start=1):
                item["file"].path.rename(item["temp_path"])
                self.signals.progress.emit(
                    idx,
                    total_files,
                    f"Paso 1/2: renombrando {idx}/{total_files}",
                    2,
                    4,
                    "Renombrando a nombres temporales (Etapa 2 de 4)"
                )

            # FASE 3/4: Temporales -> Definitivos
            for idx, item in enumerate(temp_files, start=1):
                temp_path = item["temp_path"]
                final_path = item["final_path"]
                rename_with_retry(temp_path, final_path, max_attempts=10, delay=2.0)
                item["file"].path = final_path
                item["file"].clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", final_path.name)
                self.signals.progress.emit(
                    idx,
                    total_files,
                    f"Paso 2/2: aplicando numeración {idx}/{total_files}",
                    3,
                    4,
                    "Aplicando numeración final (Etapa 3 de 4)"
                )

            # FASE 4/4: Eliminar backup
            self.signals.progress.emit(
                1,
                1,
                "Eliminando archivo de respaldo...",
                4,
                4,
                "Finalizando operación (Etapa 4 de 4)"
            )
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
