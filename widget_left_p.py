from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class IndividualTaggerPanel(QWidget):
    """Panel visual para edición individual de etiquetas.

    Este módulo contiene únicamente la interfaz. No implementa lectura,
    escritura, validación ni aplicación de etiquetas.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
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

        self.cover_widget = QFrame()
        self.cover_widget.setFixedSize(180, 180)
        self.cover_widget.setFrameShape(QFrame.Shape.Box)
        self.cover_widget.setFrameShadow(QFrame.Shadow.Plain)

        cover_layout = QHBoxLayout()
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.addWidget(self.cover_widget)
        cover_layout.addStretch()

        metadata_layout.addRow(self.cover_check, cover_layout)

        self.comment_edit = QTextEdit()
        metadata_layout.addRow(self.comment_check, self.comment_edit)

        main_layout.addLayout(metadata_layout)
        main_layout.addStretch()

        self.apply_tags = QPushButton("Apply Tags")

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)
        footer_layout.addStretch()
        footer_layout.addWidget(self.apply_tags)

        main_layout.addLayout(footer_layout)