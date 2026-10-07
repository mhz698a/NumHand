from PyQt6.QtWidgets import (
    QComboBox,
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

        metadata_layout.addRow(QLabel("Title:"), title_layout)
        metadata_layout.addRow(QLabel("Artist:"), artist_layout)
        metadata_layout.addRow(QLabel("Album:"), self.album_edit)
        metadata_layout.addRow(QLabel("Year:"), self.year_edit)
        metadata_layout.addRow(QLabel("Date:"), self.date_edit)
        metadata_layout.addRow(QLabel("Track:"), self.track_edit)
        metadata_layout.addRow(QLabel("Disc:"), self.disc_edit)
        metadata_layout.addRow(QLabel("Genre:"), self.genre_stack)

        self.cover_widget = QFrame()
        self.cover_widget.setFixedSize(180, 180)
        self.cover_widget.setFrameShape(QFrame.Shape.Box)
        self.cover_widget.setFrameShadow(QFrame.Shadow.Plain)

        cover_layout = QHBoxLayout()
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.addWidget(self.cover_widget)
        cover_layout.addStretch()

        metadata_layout.addRow(QLabel("Cover:"), cover_layout)

        self.comment_edit = QTextEdit()
        metadata_layout.addRow(QLabel("Comment:"), self.comment_edit)

        main_layout.addLayout(metadata_layout)
        main_layout.addStretch()
        
        self.apply_tags = QPushButton("Apply Tags")

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)
        footer_layout.addStretch()
        footer_layout.addWidget(self.apply_tags)

        main_layout.addLayout(footer_layout)
