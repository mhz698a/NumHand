# wstatusbar.py
from PyQt6.QtWidgets import QStatusBar

def setup_status_bar(main_window) -> QStatusBar:
    """Configura e integra una QStatusBar limpia en la ventana principal."""
    status_bar = QStatusBar(main_window)
    main_window.setStatusBar(status_bar)
    return status_bar

def show_status_message(main_window, message: str, timeout_ms: int = 10000):
    """Muestra un mensaje en la barra de estado garantizando un mínimo de 10 segundos."""
    if hasattr(main_window, "statusBar") and main_window.statusBar():
        # Forzar un mínimo de 10000 ms (10 segundos)
        duration = max(timeout_ms, 10000)
        main_window.statusBar().showMessage(message, duration)