from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QBuffer, QIODevice
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from wcoverlabel import CoverLabel
from tag_cover import read_cover_art, export_cover_art, get_common_cover

class IndividualTaggerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_entries = []
        self.pending_cover_bytes = None
        self.pending_cover_mime = "image/jpeg"
        self.pending_remove_cover = False
        self.common_cover_bytes = None
        self._build_ui()

    def _build_ui(self):
        def bind_chk_widget(chk, widget):
            widget.setEnabled(chk.isChecked())
            chk.toggled.connect(widget.setEnabled)
            
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        main_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("..."))
        header_layout.addStretch()

        self.newgrounds_button = QPushButton("Newgrounds")
        header_layout.addWidget(self.newgrounds_button)

        main_layout.addLayout(header_layout)

        metadata_layout = QFormLayout()
        metadata_layout.setSpacing(6)
        metadata_layout.setVerticalSpacing(8)

        # Checkboxes que actúan como etiquetas
        self.title_check = QCheckBox("Title:")
        self.artist_check = QCheckBox("Artist:")
        self.album_check = QCheckBox("Album:")
        self.year_check = QCheckBox("Year:")
        self.date_check = QCheckBox("Date:")
        self.track_check = QCheckBox("Track:")
        self.disc_check = QCheckBox("Disc:")
        self.genre_check = QCheckBox("Genre:")
        self.cover_check = QCheckBox("Cover:")
        self.comment_check = QCheckBox("Comment:")

        # Inputs
        self.title_edit = QLineEdit()
        title_layout = QHBoxLayout()
        title_layout.setSpacing(4)
        title_layout.addWidget(self.title_edit)

        self.artist_edit = QLineEdit()
        artist_layout = QHBoxLayout()
        artist_layout.addWidget(self.artist_edit)

        self.album_edit = QLineEdit()

        self.year_edit = QLineEdit()
        self.year_edit.setPlaceholderText("YYYY")

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD o YYYY-MM-DDTHH:MM:SSZ")

        self.track_edit = QLineEdit()
        self.track_edit.setPlaceholderText("00 o 00/00")

        self.disc_edit = QLineEdit()
        self.disc_edit.setPlaceholderText("00/00, 000/000 o 00/000")

        self.genre_line = QLineEdit()

        self.genre_stack = QStackedWidget()
        self.genre_stack.addWidget(self.genre_line)

        # Asignación directa al FormLayout
        metadata_layout.addRow(self.title_check, title_layout)
        metadata_layout.addRow(self.artist_check, artist_layout)
        metadata_layout.addRow(self.album_check, self.album_edit)
        metadata_layout.addRow(self.year_check, self.year_edit)
        metadata_layout.addRow(self.date_check, self.date_edit)
        metadata_layout.addRow(self.track_check, self.track_edit)
        metadata_layout.addRow(self.disc_check, self.disc_edit)
        metadata_layout.addRow(self.genre_check, self.genre_stack)

        self.cover_widget = CoverLabel()
        self.cover_widget.setFixedSize(180, 180)
        self.cover_widget.rightClicked.connect(self.show_cover_context_menu)
        
        cover_layout = QHBoxLayout()
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.addWidget(self.cover_widget)
        cover_layout.addStretch()
        
        metadata_layout.addRow(self.cover_check, cover_layout)

        self.comment_edit = QTextEdit()
        metadata_layout.addRow(self.comment_check, self.comment_edit)
        
        self.mtime_edit = QLineEdit()
        self.mtime_edit.setReadOnly(True)
        self.mtime_edit.setPlaceholderText("YYYY-MM-DD HH:MM:SS")

        self.ctime_edit = QLineEdit()
        self.ctime_edit.setReadOnly(True)
        self.ctime_edit.setPlaceholderText("YYYY-MM-DD HH:MM:SS")

        metadata_layout.addRow(QLabel("Last Time:"), self.mtime_edit)
        metadata_layout.addRow(QLabel("Created Time:"), self.ctime_edit)

        main_layout.addLayout(metadata_layout)
        main_layout.addStretch()

        self.apply_tags = QPushButton("Apply Tags")

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)
        footer_layout.addStretch()
        footer_layout.addWidget(self.apply_tags)

        bind_chk_widget(self.title_check, self.title_edit)
        bind_chk_widget(self.artist_check, self.artist_edit)
        bind_chk_widget(self.album_check, self.album_edit)
        bind_chk_widget(self.year_check, self.year_edit)
        bind_chk_widget(self.date_check, self.date_edit)
        bind_chk_widget(self.track_check, self.track_edit)
        bind_chk_widget(self.disc_check, self.disc_edit)
        bind_chk_widget(self.genre_check, self.genre_stack)
        bind_chk_widget(self.comment_check, self.comment_edit)

        main_layout.addLayout(footer_layout)
    
    def set_current_entries(self, entries):
        """Actualiza los archivos seleccionados y evalúa si comparten carátula o difieren."""
        self.current_entries = entries
        self.pending_cover_bytes = None
        self.pending_remove_cover = False
        self.common_cover_bytes = None

        if not entries:
            self.cover_widget.setPixmap(QPixmap())
            self.cover_widget.set_has_cover(False)
            return

        if len(entries) == 1:
            data = read_cover_art(entries[0].path)
            self.common_cover_bytes = data
            self.load_cover_from_bytes(data)
        else:
            # Comparación binaria de bytes crudos con get_common_cover
            common_bytes = get_common_cover(entries)
            
            if common_bytes is None:
                # Las carátulas difieren entre los archivos seleccionados
                self.cover_widget.setPixmap(QPixmap())
                self.cover_widget.set_has_cover(False)
                self.cover_widget.setText("(...valores multiples...)")
            elif common_bytes == b"":
                # Todos los archivos seleccionados carecen de carátula
                self.cover_widget.setPixmap(QPixmap())
                self.cover_widget.set_has_cover(False)
                self.cover_widget.setText("Agregar Carátula")
            else:
                # Todos comparten exactamente la misma carátula
                self.common_cover_bytes = common_bytes
                self.load_cover_from_bytes(common_bytes)
    
    def load_cover_from_bytes(self, data):
        """Helper para renderizar bytes de imagen en el CoverLabel."""
        if not data:
            self.cover_widget.setPixmap(QPixmap())
            self.cover_widget.set_has_cover(False)
            return

        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            self.cover_widget.setPixmap(QPixmap())
            self.cover_widget.set_has_cover(False)
            return

        self.cover_widget.set_has_cover(True)
        self.cover_widget.setText("")
        self.cover_widget.setPixmap(
            pixmap.scaled(
                self.cover_widget.width(),
                self.cover_widget.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
    
    def load_cover_for_path(self, path):
        data = read_cover_art(path)
        self.common_cover_bytes = data
        self.load_cover_from_bytes(data)
        
    def replace_cover_from_dialog(self):
        """Carga la imagen seleccionada en memoria y marca el checkbox de carátula."""
        if not self.current_entries:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar carátula",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )
        if not path:
            return

        img_path = Path(path)
        try:
            self.pending_cover_bytes = img_path.read_bytes()
            self.pending_remove_cover = False
            suffix = img_path.suffix.lower()
            self.pending_cover_mime = "image/png" if suffix == ".png" else "image/jpeg"

            pixmap = QPixmap()
            pixmap.loadFromData(self.pending_cover_bytes)
            if not pixmap.isNull():
                self.cover_widget.set_has_cover(True)
                self.cover_widget.setText("")
                self.cover_widget.setPixmap(
                    pixmap.scaled(
                        self.cover_widget.width(),
                        self.cover_widget.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )
                # Marcar automáticamente la casilla de carátula para aplicar al hacer click en Apply Tags
                self.cover_check.setChecked(True)
        except Exception:
            pass
            
    def export_cover_from_common(self):
        """Exporta la carátula común a un archivo en disco."""
        data = getattr(self, "common_cover_bytes", None)
        if not data:
            QMessageBox.information(self, "Carátula", "No hay una carátula común disponible para exportar.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar carátula",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )
        if not path:
            return

        try:
            Path(path).write_bytes(data)
        except Exception:
            pass
    
    def copy_cover_to_clipboard(self):
        """Copia la carátula común al portapapeles."""
        data = getattr(self, "common_cover_bytes", None)
        if not data:
            return

        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            return

        clipboard = QApplication.clipboard()
        clipboard.setPixmap(pixmap)
        clipboard.setImage(pixmap.toImage())
    
    def paste_cover_from_clipboard(self):
        """Carga la imagen del portapapeles en memoria y marca el checkbox."""
        if not self.current_entries:
            return
        clipboard = QApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            pixmap = clipboard.pixmap()
            if not pixmap.isNull():
                image = pixmap.toImage()

        if image.isNull():
            QMessageBox.information(self, "Carátula", "No hay una imagen válida en el portapapeles.")
            return

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            return

        self.pending_cover_bytes = bytes(buffer.data())
        self.pending_cover_mime = "image/png"
        self.pending_remove_cover = False
        
        pixmap = QPixmap()
        pixmap.loadFromData(self.pending_cover_bytes)
        if not pixmap.isNull():
            self.cover_widget.set_has_cover(True)
            self.cover_widget.setText("")
            self.cover_widget.setPixmap(
                pixmap.scaled(
                    self.cover_widget.width(),
                    self.cover_widget.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
            self.cover_check.setChecked(True)

    def remove_cover_from_selection(self):
        """Marca la eliminación de la carátula en memoria y activa el checkbox."""
        if not self.current_entries:
            return
        self.pending_cover_bytes = None
        self.pending_remove_cover = True

        self.cover_widget.setPixmap(QPixmap())
        self.cover_widget.set_has_cover(False)
        self.cover_widget.setText("Agregar Carátula")
        self.cover_check.setChecked(True)

    def show_cover_context_menu(self, pos):
        menu = QMenu(self)
        act_export = menu.addAction("Exportar imagen")
        act_replace = menu.addAction("Remplazar imagen")
        act_remove = menu.addAction("Eliminar Carátula")
        act_copy = menu.addAction("Copiar imagen al portapapeles")
        act_paste = menu.addAction("Pegar imagen del portapapeles")

        # Reglas de habilitación para selección múltiple / simple:
        # Exportar, Copiar y Eliminar requieren que exista una carátula común válida.
        has_valid_common = bool(getattr(self, "common_cover_bytes", None)) or self.cover_widget._has_cover
        act_export.setEnabled(has_valid_common)
        act_copy.setEnabled(has_valid_common)
        act_remove.setEnabled(has_valid_common)
        
        # Remplazar y Pegar siempre están habilitados (aplican al lote seleccionado o individual).
        act_replace.setEnabled(True)
        act_paste.setEnabled(True)

        action = menu.exec(pos)
        if action == act_export:
            self.export_cover_from_common()
        elif action == act_replace:
            self.replace_cover_from_dialog()
        elif action == act_remove:
            self.remove_cover_from_selection()
        elif action == act_copy:
            self.copy_cover_to_clipboard()
        elif action == act_paste:
            self.paste_cover_from_clipboard()