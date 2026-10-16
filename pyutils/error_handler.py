import logging
import os
import sys
import tempfile
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox, QApplication


_LOGGING_CONFIGURED = False


def _configure_file_logging():
    """Write diagnostics to a persistent log even when NumHand has no console."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    candidates = []
    for environment_key in ("LOCALAPPDATA", "APPDATA"):
        root = os.environ.get(environment_key)
        if root:
            candidates.append(Path(root) / "NumHand" / "logs")
    candidates.append(Path(tempfile.gettempdir()) / "NumHand" / "logs")

    for log_dir in candidates:
        handler = None
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                log_dir / "numhand.log",
                maxBytes=4 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
                errors="backslashreplace",
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"
            ))
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(handler)
            _LOGGING_CONFIGURED = True
            logging.info("Registro de diagnóstico inicializado en %s", log_dir / "numhand.log")
            return
        except Exception:
            if handler is not None:
                try:
                    handler.close()
                except Exception:
                    pass

    # Last resort: keep stderr diagnostics when all persistent locations fail.
    logging.basicConfig(level=logging.INFO)


def show_exception_box(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_text = "".join(tb_lines)

    logging.critical(
        "Excepción no controlada en el hilo principal",
        exc_info=(exc_type, exc_value, exc_tb),
    )

    # Keep stderr output for console/debug runs.
    try:
        sys.stderr.write(tb_text)
    except Exception:
        pass

    app = QApplication.instance()
    if app:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Error inesperado")
        msg.setText(f"Ocurrió un error en la aplicación:\n\n{exc_value}")
        msg.setDetailedText(tb_text)
        msg.exec()


def setup_exception_hook():
    """Configure persistent diagnostics and the global Python exception hook."""
    _configure_file_logging()
    sys.excepthook = show_exception_box
