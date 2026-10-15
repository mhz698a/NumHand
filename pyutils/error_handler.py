import sys
import traceback
from PyQt6.QtWidgets import QMessageBox, QApplication

def show_exception_box(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_text = "".join(tb_lines)

    # Imprimir también en consola / stderr
    sys.stderr.write(tb_text)

    app = QApplication.instance()
    if app:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Error inesperado")
        msg.setText(f"Ocurrió un error en la aplicación:\n\n{exc_value}")
        msg.setDetailedText(tb_text)
        msg.exec()

def setup_exception_hook():
    """Configura el manejador global de excepciones para la aplicación."""
    sys.excepthook = show_exception_box
