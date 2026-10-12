from datetime import datetime
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QTextEdit
from tag_writer import write_file_tags
from tag_reader import read_file_tags
from syswall import get_locking_processes


MULTIPLE_VALUES = "(...valores multiples...)"

from tag_reader import DEFAULT_TAGS
from tag_cover import write_cover_art_data, remove_cover_art


def aggregate_metadata(selected_entries: list) -> dict:
    """Compara y combina los metadatos de las entradas seleccionadas."""
    if not selected_entries:
        return {key: "" for key in DEFAULT_TAGS}

    first_meta = selected_entries[0].metadata
    tags = {}
    
    for key in DEFAULT_TAGS:
        first_val = first_meta.get(key, "")
        all_same = all(
            entry.metadata.get(key, "") == first_val 
            for entry in selected_entries
        )
        tags[key] = str(first_val) if all_same else MULTIPLE_VALUES

    return tags


def update_tagger_panel(panel, selected_entries: list):
    """Puebla la interfaz del IndividualTaggerPanel con los datos calculados."""
    panel.set_current_entries(selected_entries)    
    tags = aggregate_metadata(selected_entries)

    panel.title_edit.setText(tags["title"])
    panel.artist_edit.setText(tags["artist"])
    panel.album_edit.setText(tags["album"])
    panel.year_edit.setText(tags["year"])
    panel.date_edit.setText(tags["date"])
    panel.track_edit.setText(tags["track"])
    panel.disc_edit.setText(tags["disc"])
    panel.genre_line.setText(tags["genre"])
    panel.comment_edit.setPlainText(tags["comment"])
    panel.mtime_edit.setText(tags["mtime"])
    panel.ctime_edit.setText(tags["ctime"])

    
def _flash_widget(widget):
    """Aplica un fondo verde #056b38 temporalmente durante 3 segundos."""
    original_style = widget.styleSheet()
    widget.setStyleSheet("background-color: #056b38; color: white;")
    QTimer.singleShot(3000, lambda: widget.setStyleSheet(original_style))

def _flash_cover_widget(widget):
    """Aplica un borde verde #056b38 temporalmente a la carátula durante 3 segundos."""
    original_style = widget.styleSheet()
    widget.setStyleSheet("""
        QLabel {
            border: 3px solid #056b38;
            background-color: #232323;
            color: #dddddd;
        }
    """)
    QTimer.singleShot(3000, lambda: widget.setStyleSheet(original_style))
    
def apply_panel_tags_to_selection(panel, selected_entries: list, status_callback=None):
    if not selected_entries:
        return

    # Mapeo estructurado de (Checkbox, InputWidget, ClaveDeTag)
    fields_map = [
        (panel.title_check, panel.title_edit, "title"),
        (panel.artist_check, panel.artist_edit, "artist"),
        (panel.album_check, panel.album_edit, "album"),
        (panel.year_check, panel.year_edit, "year"),
        (panel.date_check, panel.date_edit, "date"),
        (panel.track_check, panel.track_edit, "track"),
        (panel.disc_check, panel.disc_edit, "disc"),
        (panel.genre_check, panel.genre_line, "genre"),
        (panel.comment_check, panel.comment_edit, "comment"),
    ]

    tags_to_apply = {}
    active_fields = []

    for chk, widget, key in fields_map:
        if chk.isChecked():
            val = widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text()
            tags_to_apply[key] = val
            active_fields.append((chk, widget))

    apply_cover = panel.cover_check.isChecked() and (
        getattr(panel, "pending_cover_bytes", None) is not None or 
        getattr(panel, "pending_remove_cover", False)
    )

    if not tags_to_apply and not apply_cover:
        return

    success_count = 0
    for entry in selected_entries:
        locking_apps = get_locking_processes([str(entry.path)])
        if locking_apps:
            apps_str = ", ".join(locking_apps)
            if status_callback:
                status_callback(f"Archivo bloqueado: '{entry.path.name}' está ocupado por [{apps_str}].")
            continue
        
        success = True
        if tags_to_apply:
            success = write_file_tags(entry.path, tags_to_apply)
            
        if success and apply_cover:
            if getattr(panel, "pending_remove_cover", False):
                cover_success = remove_cover_art(entry.path)
            else:
                cover_success = write_cover_art_data(entry.path, panel.pending_cover_bytes, panel.pending_cover_mime)
            
            if not cover_success:
                success = False
        
        if success:
            success_count += 1
            entry.metadata = read_file_tags(entry.path)
            try:
                st = entry.path.stat()
                entry.metadata["mtime"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                entry.metadata["ctime"] = datetime.fromtimestamp(st.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    if success_count > 0:
        for chk, widget in active_fields:
            chk.setChecked(False)
            _flash_widget(widget)

        if apply_cover:
            panel.cover_check.setChecked(False)
            panel.pending_cover_bytes = None
            panel.pending_remove_cover = False
            _flash_cover_widget(panel.cover_widget)

        if status_callback:
            status_callback(
                f"Se actualizaron exitosamente las etiquetas/carátula de {success_count} archivo(s). Fechas de sistema preservadas."
            )