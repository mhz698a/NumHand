import os
import re
import shutil
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

def year_prefix(year) -> str:
    y = int(year)
    return f"{y - 2003:02d}."


def strip_year_prefix(name: str) -> str:
    name = str(name or "").strip()
    m = re.match(r"^\d+\.\s*(.*)$", name)
    return m.group(1).strip() if m else name


class FolderMoveSignals(QObject):
    progress = pyqtSignal(int, int, str, int, int, str)
    finished = pyqtSignal(str, str, Path)
    error = pyqtSignal(str)


class FolderMoveTask(QRunnable):
    def __init__(self, source_dir, dest_year, base_root):
        super().__init__()
        self.source_dir = Path(source_dir)
        self.dest_year = str(dest_year)
        self.base_root = Path(base_root)
        self.signals = FolderMoveSignals()

    def _count_files(self, root: Path) -> int:
        total = 0
        for _, _, files in os.walk(root):
            total += len(files)
        return max(total, 1)

    def run(self):
        try:
            if not self.source_dir.exists() or not self.source_dir.is_dir():
                raise FileNotFoundError(f"No existe la carpeta origen: {self.source_dir}")

            src_year = ""
            try:
                src_year = self.source_dir.parents[1].name
            except Exception:
                src_year = ""

            base_name = strip_year_prefix(self.source_dir.name)
            dst_prefix = year_prefix(self.dest_year)

            dest_dir = self.base_root / self.dest_year / f"{dst_prefix} music" / f"{dst_prefix} {base_name}"

            if self.source_dir.resolve() == dest_dir.resolve():
                self.signals.finished.emit(src_year, self.dest_year)
                return

            if dest_dir.exists():
                raise FileExistsError(f"Ya existe el destino: {dest_dir}")

            # Emitir progreso inicial
            self.signals.progress.emit(
                0, 100, "Moviendo carpeta...", 1, 1, f"Moviendo a {self.dest_year}..."
            )

            # Mover la carpeta de forma atómica y rápida al estar en la misma unidad
            shutil.move(str(self.source_dir), str(dest_dir))

            self.signals.progress.emit(
                100, 100, "Movimiento completado", 1, 1, "Operación finalizada con éxito."
            )

            self.signals.finished.emit(src_year, self.dest_year, dest_dir)

        except Exception as error:
            self.signals.error.emit(str(error))