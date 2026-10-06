from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QHBoxLayout
)


class DualProgressDialog(QDialog):
    canceled = pyqtSignal()

    def __init__(self, title="Progreso", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Barra Superior: Subtarea
        self.sub_label = QLabel("Iniciando subtarea...", self)
        self.sub_label.setWordWrap(True)
        self.sub_bar = QProgressBar(self)
        self.sub_bar.setRange(0, 0)  # Indeterminado por defecto

        # Barra Inferior: Progreso General
        self.main_label = QLabel("Iniciando proceso general...", self)
        self.main_label.setWordWrap(True)
        self.main_bar = QProgressBar(self)
        self.main_bar.setRange(0, 0)  # Indeterminado por defecto

        # Botón Cancelar
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton("Cancelar", self)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)

        # Ensamblado del layout
        layout.addWidget(self.sub_label)
        layout.addWidget(self.sub_bar)
        layout.addSpacing(10)
        layout.addWidget(self.main_label)
        layout.addWidget(self.main_bar)
        layout.addSpacing(10)
        layout.addLayout(button_layout)

    def _on_cancel_clicked(self):
        self.canceled.emit()
        self.reject()

    def reject(self):
        super().reject()

    def closeEvent(self, event):
        self.canceled.emit()
        super().closeEvent(event)

    @pyqtSlot(int, int, str, int, int, str)
    def update_progress(self, sub_current, sub_total, sub_label, main_current, main_total, main_label):
        if sub_label:
            self.sub_label.setText(sub_label)
        if sub_total > 0:
            self.sub_bar.setRange(0, sub_total)
            self.sub_bar.setValue(sub_current)
        else:
            self.sub_bar.setRange(0, 0)

        if main_label:
            self.main_label.setText(main_label)
        if main_total > 0:
            self.main_bar.setRange(0, main_total)
            self.main_bar.setValue(main_current)
        else:
            self.main_bar.setRange(0, 0)
