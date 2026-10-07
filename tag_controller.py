from tag_writer import write_file_tags
from tag_reader import read_file_tags

MULTIPLE_VALUES = "(...valores multiples...)"

TAG_KEYS = [
    "title", "artist", "album", "year", "date",
    "track", "disc", "genre", "comment"
]

def aggregate_metadata(selected_entries: list) -> dict:
    """Compara y combina los metadatos de las entradas seleccionadas."""
    if not selected_entries:
        return {key: "" for key in TAG_KEYS}

    first_meta = selected_entries[0].metadata
    tags = {}
    
    for key in TAG_KEYS:
        first_val = first_meta.get(key, "")
        all_same = all(
            entry.metadata.get(key, "") == first_val 
            for entry in selected_entries
        )
        tags[key] = str(first_val) if all_same else MULTIPLE_VALUES

    return tags


def update_tagger_panel(panel, selected_entries: list):
    """Puebla la interfaz del IndividualTaggerPanel con los datos calculados."""
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
    

def apply_panel_tags_to_selection(panel, selected_entries: list):
    """Lee los datos del panel y actualiza los archivos seleccionados."""
    if not selected_entries:
        return

    # Recopilar solo las etiquetas cuyas casillas estén marcadas (o modificadas)
    tags_to_apply = {}
    
    if panel.title_check.isChecked():
        tags_to_apply["title"] = panel.title_edit.text()
    if panel.artist_check.isChecked():
        tags_to_apply["artist"] = panel.artist_edit.text()
    if panel.album_check.isChecked():
        tags_to_apply["album"] = panel.album_edit.text()
    if panel.year_check.isChecked():
        tags_to_apply["year"] = panel.year_edit.text()
    if panel.date_check.isChecked():
        tags_to_apply["date"] = panel.date_edit.text()
    if panel.track_check.isChecked():
        tags_to_apply["track"] = panel.track_edit.text()
    if panel.disc_check.isChecked():
        tags_to_apply["disc"] = panel.disc_edit.text()
    if panel.genre_check.isChecked():
        tags_to_apply["genre"] = panel.genre_line.text()
    if panel.comment_check.isChecked():
        tags_to_apply["comment"] = panel.comment_edit.toPlainText()

    if not tags_to_apply:
        return

    for entry in selected_entries:
        success = write_file_tags(entry.path, tags_to_apply)
        if success:
            # Re-leer metadatos para actualizar la memoria del modelo
            entry.metadata = read_file_tags(entry.path)