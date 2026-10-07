from PyQt6.QtWidgets import (
    QCheckBox,
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
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Tagger Individual"))
        header_layout.addStretch()

        self.newgrounds_button = QPushButton("Newgrounds")
        self.newgrounds_button.setFixedHeight(36)
        header_layout.addWidget(self.newgrounds_button)

        main_layout.addLayout(header_layout)

        metadata_layout = QFormLayout()
        metadata_layout.setSpacing(6)
        metadata_layout.setVerticalSpacing(8)

        self.title_edit = QLineEdit()
        self.title_edit.setFixedHeight(38)

        self.title_id_button = QPushButton("(ID:)")
        self.title_id_button.setFixedSize(90, 38)
        self.title_id_button.setToolTip("Añadir (ID:) al título")

        self.title_paste_button = QPushButton("[ T ]")
        self.title_paste_button.setFixedSize(90, 38)
        self.title_paste_button.setToolTip("Mover el título al campo de título")

        title_layout = QHBoxLayout()
        title_layout.setSpacing(4)
        title_layout.addWidget(self.title_edit)
        title_layout.addWidget(self.title_id_button)
        title_layout.addWidget(self.title_paste_button)

        self.artist_edit = QLineEdit()
        self.artist_edit.setFixedHeight(38)

        self.artist_paste_button = QPushButton("[ A ]")
        self.artist_paste_button.setFixedSize(90, 38)
        self.artist_paste_button.setToolTip("Mover el artista al campo de artistas")

        artist_layout = QHBoxLayout()
        artist_layout.setSpacing(4)
        artist_layout.addWidget(self.artist_edit)
        artist_layout.addWidget(self.artist_paste_button)

        self.album_edit = QLineEdit()
        self.album_edit.setFixedHeight(38)

        self.year_edit = QLineEdit()
        self.year_edit.setFixedHeight(38)
        self.year_edit.setPlaceholderText("YYYY")

        self.date_edit = QLineEdit()
        self.date_edit.setFixedHeight(38)
        self.date_edit.setPlaceholderText("YYYY-MM-DD o YYYY-MM-DDTHH:MM:SSZ")

        self.track_edit = QLineEdit()
        self.track_edit.setFixedHeight(38)
        self.track_edit.setPlaceholderText("00 o 00/00")

        self.disc_edit = QLineEdit()
        self.disc_edit.setFixedHeight(38)
        self.disc_edit.setPlaceholderText("00/00, 000/000 o 00/000")

        self.genre_line = QLineEdit()
        self.genre_line.setFixedHeight(38)

        self.genre_combo = QComboBox()
        self.genre_combo.setFixedHeight(38)
        self.genre_combo.addItems(["", "Episode", "Movie", "Short", "Soundtrack"])

        self.genre_stack = QStackedWidget()
        self.genre_stack.addWidget(self.genre_line)
        self.genre_stack.addWidget(self.genre_combo)

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
        self.comment_edit.setFixedHeight(160)
        metadata_layout.addRow(QLabel("Comment:"), self.comment_edit)

        main_layout.addLayout(metadata_layout)
        main_layout.addStretch()

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(8)

        self.always_on_top_checkbox = QCheckBox("Siempre visible")
        self.always_on_top_checkbox.setChecked(True)

        self.overwrite_checkbox = QCheckBox("Es Sobrescritor")
        self.overwrite_checkbox.setChecked(False)

        footer_layout.addWidget(self.always_on_top_checkbox)
        footer_layout.addWidget(self.overwrite_checkbox)
        footer_layout.addStretch()

        main_layout.addLayout(footer_layout)
