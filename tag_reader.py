from pathlib import Path
import mutagen

SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".m4v"}

DEFAULT_TAGS = {
    "title": "",
    "artist": "",
    "album": "",
    "year": "",
    "date": "",
    "track": "",
    "disc": "",
    "genre": "",
    "comment": ""
}

def _parse_track_disc(value):
    """Formatea valores de tuplas o cadenas como track/disc (ej. 1/12)."""
    if isinstance(value, (tuple, list)):
        if len(value) >= 2 and value[1]:
            return f"{value[0]}/{value[1]}"
        elif len(value) >= 1:
            return str(value[0])
    return str(value) if value else ""

def read_file_tags(file_path: Path) -> dict:
    """Lee y estandariza los 9 metadatos requeridos para MP3, MP4, M4A y M4V."""
    path = Path(file_path)
    tags = DEFAULT_TAGS.copy()

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.exists():
        return tags

    try:
        audio = mutagen.File(str(path))
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return tags

        ext = path.suffix.lower()

        if ext == ".mp3":
            # ID3 Tags
            id3 = audio.tags
            tags["title"] = str(id3.get("TIT2", ""))
            tags["artist"] = str(id3.get("TPE1", ""))
            tags["album"] = str(id3.get("TALB", ""))
            
            # Fecha y Año
            date_val = str(id3.get("TDRC", "")) or str(id3.get("TYER", ""))
            tags["date"] = date_val
            tags["year"] = date_val[:4] if len(date_val) >= 4 else ""

            tags["track"] = str(id3.get("TRCK", ""))
            tags["disc"] = str(id3.get("TPOS", ""))
            tags["genre"] = str(id3.get("TCON", ""))

            # Comentarios (COMM)
            comments = [v.text[0] for k, v in id3.items() if k.startswith("COMM") and v.text]
            tags["comment"] = comments[0] if comments else ""

        elif ext in {".mp4", ".m4a", ".m4v"}:
            # MP4 Atoms
            mp4 = audio.tags
            tags["title"] = str(mp4.get("\xa9nam", [""])[0])
            tags["artist"] = str(mp4.get("\xa9ART", [""])[0])
            tags["album"] = str(mp4.get("\xa9alb", [""])[0])
            
            date_val = str(mp4.get("\xa9day", [""])[0])
            tags["date"] = date_val
            tags["year"] = date_val[:4] if len(date_val) >= 4 else ""

            tags["track"] = _parse_track_disc(mp4.get("trkn", [()])[0])
            tags["disc"] = _parse_track_disc(mp4.get("disk", [()])[0])
            tags["genre"] = str(mp4.get("\xa9gen", [""])[0])
            tags["comment"] = str(mp4.get("\xa9cmt", [""])[0])

    except Exception:
        pass

    return tags