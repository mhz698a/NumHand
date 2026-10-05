from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal


class DualProgressDialog(QDialog):
    """
    Diálogo personalizado que muestra dos barras de progreso:
    - Arriba: Progreso de la Subtarea / Paso actual.
    - Abajo: Progreso General de la operación.
    """
    canceled = pyqtSignal()

    def __init__(self, title="Procesando...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(450)
        
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Subtarea (Arriba) ---
        self.sub_label = QLabel("Iniciando subtarea...", self)
        self.sub_label.setWordWrap(True)
        layout.addWidget(self.sub_label)

        self.sub_bar = QProgressBar(self)
        self.sub_bar.setRange(0, 100)
        self.sub_bar.setValue(0)
        layout.addWidget(self.sub_bar)

        # --- General (Abajo) ---
        self.main_label = QLabel("Iniciando proceso general...", self)
        self.main_label.setWordWrap(True)
        layout.addWidget(self.main_label)

        self.main_bar = QProgressBar(self)
        self.main_bar.setRange(0, 100)
        self.main_bar.setValue(0)
        layout.addWidget(self.main_bar)

        # --- Botón Cancelar ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancelar", self)
        self.cancel_button.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_button)

        layout.addLayout(btn_layout)

    def set_progress(self, sub_current, sub_total, sub_message, main_current, main_total, main_message):
        """
        Actualiza el progreso de la subtarea y del proceso general.
        """
        # Actualizar Subtarea
        if sub_message:
            self.sub_label.setText(sub_message)
        if sub_total > 0:
            self.sub_bar.setMaximum(sub_total)
            self.sub_bar.setValue(sub_current)
        else:
            self.sub_bar.setMaximum(0)
            self.sub_bar.setValue(0)

        # Actualizar General
        if main_message:
            self.main_label.setText(main_message)
        if main_total > 0:
            self.main_bar.setMaximum(main_total)
            self.main_bar.setValue(main_current)
        else:
            self.main_bar.setMaximum(0)
            self.main_bar.setValue(0)

    def _on_cancel(self):
        self.canceled.emit()
        self.reject()
