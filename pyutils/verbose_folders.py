from pathlib import Path
import re
import json
from PyQt6 import QtGui, QtWidgets
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, 
    QDialogButtonBox
)

enviroment = "architecture" # business

PREFIX_RE = re.compile(r"^(\d+\.\s*)(.*)$")
BASE_DIR = Path(__file__).resolve().parent.parent

if enviroment == "architecture":        
    VERBOSE_FOLDERS_JSON = BASE_DIR / "__structure__" / "verbose_architecture.json"
elif enviroment == "business":
    VERBOSE_FOLDERS_JSON = BASE_DIR / "__structure__" / "verbose_business.json"

with open(VERBOSE_FOLDERS_JSON, 'r', encoding='utf-8') as archivo:
    VERBOSE_MAP = json.load(archivo)


DISPLAY_TO_RAW = {v: k for k, v in VERBOSE_MAP.items()}
RAW_KEYS = sorted(VERBOSE_MAP.keys(), key=len, reverse=True)

def split_prefixed_name(name: str):
    name = str(name or "").strip()

    prefix = ""
    body = name

    m = PREFIX_RE.match(name)
    if m:
        prefix = m.group(1)
        body = m.group(2).strip()

    raw = ""
    suffix = ""

    for candidate in RAW_KEYS:
        if body == candidate:
            raw = candidate
            break
        if body.startswith(candidate + "."):
            raw = candidate
            suffix = body[len(candidate) + 1:].strip()
            break

    if not raw:
        if "." in body:
            raw, suffix = body.rsplit(".", 1)
            raw = raw.strip()
            suffix = suffix.strip()
        else:
            raw = body

    return prefix, raw, suffix

class VerboseRenameDialog(QtWidgets.QDialog):
    def __init__(self, raw_value="", suffix_value="", parent=None, title="Renombrar subcarpeta"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(450, 80)

        layout = QVBoxLayout(self)

        row = QHBoxLayout()

        self.combo = QComboBox()
        for display, raw in DISPLAY_TO_RAW.items():
            self.combo.addItem(display, raw)

        idx = self.combo.findData(raw_value)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

        self.edit_suffix = QLineEdit()
        self.edit_suffix.setText(suffix_value)
        self.edit_suffix.setPlaceholderText("Nombre final opcional")

        row.addWidget(self.combo, stretch=2)
        row.addWidget(self.edit_suffix, stretch=3)

        layout.addLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_raw(self):
        return self.combo.currentData()

    def selected_suffix(self):
        return self.edit_suffix.text().strip()