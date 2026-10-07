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