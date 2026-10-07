from pathlib import Path
import mutagen

SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".m4v"}

def write_file_tags(file_path: Path, new_tags: dict) -> bool:
    """Escribe los metadatos indicados en el archivo según su extensión.
    
    new_tags es un diccionario que contiene solo los campos marcados/modificados.
    """
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.exists():
        return False

    try:
        ext = path.suffix.lower()
        if ext == ".mp3":
            audio = mutagen.File(str(path))
            if audio is None or audio.tags is None:
                audio.add_tags()

            id3 = audio.tags
            if "title" in new_tags: id3["TIT2"] = mutagen.id3.TIT2(encoding=3, text=new_tags["title"])
            if "artist" in new_tags: id3["TPE1"] = mutagen.id3.TPE1(encoding=3, text=new_tags["artist"])
            if "album" in new_tags: id3["TALB"] = mutagen.id3.TALB(encoding=3, text=new_tags["album"])
            if "year" in new_tags or "date" in new_tags:
                val = new_tags.get("date") or new_tags.get("year", "")
                id3["TDRC"] = mutagen.id3.TDRC(encoding=3, text=val)
            if "track" in new_tags: id3["TRCK"] = mutagen.id3.TRCK(encoding=3, text=new_tags["track"])
            if "disc" in new_tags: id3["TPOS"] = mutagen.id3.TPOS(encoding=3, text=new_tags["disc"])
            if "genre" in new_tags: id3["TCON"] = mutagen.id3.TCON(encoding=3, text=new_tags["genre"])
            if "comment" in new_tags: id3["COMM"] = mutagen.id3.COMM(encoding=3, lang="eng", desc="", text=new_tags["comment"])
            audio.save()

        elif ext in {".mp4", ".m4a", ".m4v"}:
            audio = mutagen.File(str(path))
            if audio is None or audio.tags is None:
                return False

            mp4 = audio.tags
            if "title" in new_tags: mp4["\xa9nam"] = [new_tags["title"]]
            if "artist" in new_tags: mp4["\xa9ART"] = [new_tags["artist"]]
            if "album" in new_tags: mp4["\xa9alb"] = [new_tags["album"]]
            if "date" in new_tags or "year" in new_tags: 
                mp4["\xa9day"] = [new_tags.get("date") or new_tags.get("year", "")]
            if "genre" in new_tags: mp4["\xa9gen"] = [new_tags["genre"]]
            if "comment" in new_tags: mp4["\xa9cmt"] = [new_tags["comment"]]
            audio.save()

        return True
    except Exception:
        return False