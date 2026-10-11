import re
from PyQt6.QtWidgets import QLineEdit, QTextEdit, QMenu, QCalendarWidget, QDialog, QVBoxLayout, QPushButton
from PyQt6.QtCore import QDate, Qt

class CalendarDialog(QDialog):
    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Fecha")
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget(self)
        
        if initial_text:
            parts = re.split(r'[-/\sT:]', initial_text.strip())
            numeric_parts = [p for p in parts if p.isdigit()]
            
            try:
                year = int(numeric_parts[0]) if len(numeric_parts) > 0 else QDate.currentDate().year()
                month = int(numeric_parts[1]) if len(numeric_parts) > 1 else 1
                day = int(numeric_parts[2]) if len(numeric_parts) > 2 else 1
                
                qdate = QDate(year, month, day)
                if qdate.isValid():
                    self.calendar.setSelectedDate(qdate)
            except ValueError:
                pass

        layout.addWidget(self.calendar)
        
        btn = QPushButton("Aceptar", self)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_date(self):
        return self.calendar.selectedDate().toString("yyyy/MM/dd")


class UtilityTextMixin:
    """Mixin que agrupa toda la lógica de utilidades de texto sin duplicar código."""
    
    def _get_text(self): raise NotImplementedError
    def _set_text(self, text): raise NotImplementedError
    def _has_selection(self): raise NotImplementedError
    def _get_selected_text(self): raise NotImplementedError
    def _remove_selection(self): raise NotImplementedError

    def _build_utility_menu(self, menu):
        util_menu = menu.addMenu("Utilidades de Texto")
        is_ro = self.isReadOnly()

        def preserve_eta_transform(text, func):
            eta_suffix = ""
            if " (η)" in text:
                parts = text.split(" (η)")
                text = parts[0]
                eta_suffix = " (η)" + "".join(parts[1:])
            return func(text) + eta_suffix

        # --- Opciones de Limpieza y Formato ---
        def clean_underscores():
            if not is_ro:
                self._set_text(' '.join(self._get_text().replace("(_)", "").replace("_", " ").strip().split()))

        def clean_hyphens():
            if not is_ro:
                self._set_text(' '.join(self._get_text().replace("(_)", "").replace("-", " ").strip().split()))

        def clean_both():
            if not is_ro:
                self._set_text(
                    ' '.join(
                        self._get_text().replace("(_)", "").replace("_", " ").replace("-", " ").strip().split()
                    )
                )

        def format_sentence():
            if not is_ro:
                text = self._get_text()
                self._set_text(preserve_eta_transform(text, lambda t: t.replace("_", " ").strip().capitalize() if t else ""))

        def format_lower():
            if not is_ro:
                text = self._get_text()
                self._set_text(preserve_eta_transform(text, lambda t: t.replace("_", " ").lower()))

        def format_upper():
            if not is_ro:
                text = self._get_text()
                self._set_text(preserve_eta_transform(text, lambda t: t.replace("_", " ").upper()))

        def format_title_case():
            if not is_ro:
                text = self._get_text()
                self._set_text(preserve_eta_transform(text, lambda t: t.replace("_", " ").title()))

        def add_eta():
            if not is_ro:
                text = self._get_text()
                if text.endswith("integerNG"):
                    self._set_text(
                        text.replace(" integerNG", "").replace("_integerNG", "").rstrip() + " (η)"
                    )
                    return
                if " (η)" not in text:
                    self._set_text(text.rstrip() + " (η)")

        # --- Opciones de Envío de Texto ---
        def send_to_title():
            if self.panel_ref and hasattr(self.panel_ref, 'title_edit'):
                if not self._has_selection():
                    return
                val = self._get_selected_text().strip()
                if not val:
                    return
                current = self.panel_ref.title_edit.text().rstrip()
                if current:
                    current += " "
                self.panel_ref.title_edit.setText(f"{current}{val}")
                if hasattr(self.panel_ref, 'title_check'):
                    self.panel_ref.title_check.setChecked(True)

        def send_to_artist():
            if self.panel_ref and hasattr(self.panel_ref, 'artist_edit'):
                if not self._has_selection():
                    return
                val = self._get_selected_text().strip()
                if not val:
                    return
                if not is_ro:
                    self._remove_selection()
                current = self.panel_ref.artist_edit.text().rstrip()
                if current:
                    if not current.endswith(";"):
                        current += "; "
                    else:
                        current += " "
                self.panel_ref.artist_edit.setText(f"{current}{val}")
                if hasattr(self.panel_ref, 'artist_check'):
                    self.panel_ref.artist_check.setChecked(True)

        def send_to_album():
            if self.panel_ref and hasattr(self.panel_ref, 'album_edit'):
                if not self._has_selection():
                    return
                val = self._get_selected_text().strip()
                if not val:
                    return
                current = self.panel_ref.album_edit.text().rstrip()
                if current:
                    current += " "
                self.panel_ref.album_edit.setText(f"{current}{val}")
                if hasattr(self.panel_ref, 'album_check'):
                    self.panel_ref.album_check.setChecked(True)
            
        def send_to_year():
            if self.panel_ref and hasattr(self.panel_ref, 'year_edit'):
                self.panel_ref.year_edit.setText(self._get_text())
                if hasattr(self.panel_ref, 'year_check'):
                    self.panel_ref.year_check.setChecked(True)

        def send_to_title_as_id():
            if self.panel_ref and hasattr(self.panel_ref, 'title_edit'):
                if not self._has_selection():
                    return
                val = self._get_selected_text().strip()
                if not val:
                    return
                if not is_ro:
                    self._remove_selection()
                current_title = self.panel_ref.title_edit.text().rstrip()
                if re.search(r"\(ID:\s*\d+\)$", current_title):
                    return
                if current_title.endswith("(ID: )"):
                    return
                if current_title:
                    current_title += " "
                self.panel_ref.title_edit.setText(f"{current_title}(ID: {val})")
                if hasattr(self.panel_ref, 'title_check'):
                    self.panel_ref.title_check.setChecked(True)

        def pick_date():
            if not is_ro:
                current_text = self._get_text()
                dlg = CalendarDialog(self, initial_text=current_text)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    self._set_text(dlg.get_date())

        # Construcción de acciones del menú
        act_clean_u = util_menu.addAction("Limpiar \"_\"")
        act_clean_u.setEnabled(not is_ro)
        act_clean_u.triggered.connect(clean_underscores)

        act_clean_h = util_menu.addAction("Limpiar \"-\"")
        act_clean_h.setEnabled(not is_ro)
        act_clean_h.triggered.connect(clean_hyphens)

        act_clean_both = util_menu.addAction("Limpiar \"_\" & \"-\"")
        act_clean_both.setEnabled(not is_ro)
        act_clean_both.triggered.connect(clean_both)
        
        util_menu.addSeparator()
        
        act_sent = util_menu.addAction("Formatear a Tipo Oracion \"Ab cd\"")
        act_sent.setEnabled(not is_ro)
        act_sent.triggered.connect(format_sentence)

        act_low = util_menu.addAction("Formatear a minusculas \"ab cd\"")
        act_low.setEnabled(not is_ro)
        act_low.triggered.connect(format_lower)

        act_up = util_menu.addAction("Formatear a mayusculas \"AB CD\"")
        act_up.setEnabled(not is_ro)
        act_up.triggered.connect(format_upper)

        act_tit = util_menu.addAction("Formatear a nombre unico \"Ab Cd\"")
        act_tit.setEnabled(not is_ro)
        act_tit.triggered.connect(format_title_case)
        
        util_menu.addSeparator()
        
        act_eta = util_menu.addAction("Agregar \" (η)\" al final")
        act_eta.setEnabled(not is_ro)
        act_eta.triggered.connect(add_eta)
        
        util_menu.addSeparator()
        
        util_menu.addAction("Enviar texto a Titulo").triggered.connect(send_to_title)
        util_menu.addAction("Enviar texto a Artista").triggered.connect(send_to_artist)
        util_menu.addAction("Enviar texto a Album").triggered.connect(send_to_album)
        util_menu.addAction("Enviar texto a Año").triggered.connect(send_to_year)
        util_menu.addAction("Enviar texto a titulo como (ID:)").triggered.connect(send_to_title_as_id)

        if getattr(self, "field_type", None) == "date":
            util_menu.addSeparator()
            act_date = util_menu.addAction("Colocar Fecha (YYYY/MM/DD)")
            act_date.setEnabled(not is_ro)
            act_date.triggered.connect(pick_date)


class UtilityLineEdit(QLineEdit, UtilityTextMixin):
    def __init__(self, parent=None, field_type=None, panel_ref=None):
        super().__init__(parent)
        self.field_type = field_type
        self.panel_ref = panel_ref

    def _get_text(self): return self.text()
    def _set_text(self, text): self.setText(text)
    def _has_selection(self): return self.hasSelectedText()
    def _get_selected_text(self): return self.selectedText()
    def _remove_selection(self): self.backspace()

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        self._build_utility_menu(menu)
        menu.exec(event.globalPos())


class UtilityTextEdit(QTextEdit, UtilityTextMixin):
    def __init__(self, parent=None, field_type=None, panel_ref=None):
        super().__init__(parent)
        self.field_type = field_type
        self.panel_ref = panel_ref

    def _get_text(self): return self.toPlainText()
    def _set_text(self, text): self.setPlainText(text)
    def _has_selection(self): return self.textCursor().hasSelection()
    def _get_selected_text(self): return self.textCursor().selectedText().replace('\u2029', '\n')
    def _remove_selection(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
            self.setTextCursor(cursor)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        self._build_utility_menu(menu)
        menu.exec(event.globalPos())