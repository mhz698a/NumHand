# tag_cover.py
import os
import contextlib
import mutagen
from pathlib import Path
from mutagen.id3 import APIC
from mutagen.mp4 import MP4Cover

from pyutils.wctime import setctime_blocking


SUPPORTED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".m4v"}

def read_cover_art(file_path: Path) -> bytes:
    """Extrae los bytes de la carátula frontal (APIC para MP3, covr para MP4)."""
    path = Path(file_path)
    if not path.exists():
        return None
    try:
        audio = mutagen.File(str(path))
        if audio is None or not hasattr(audio, "tags") or audio.tags is None:
            return None

        ext = path.suffix.lower()
        if ext == ".mp3":
            id3 = audio.tags
            for key in id3.keys():
                if key.startswith("APIC") or key == "APIC":
                    return id3[key].data
        elif ext in {".mp4", ".m4a", ".m4v"}:
            mp4 = audio.tags
            if "covr" in mp4 and mp4["covr"]:
                return bytes(mp4["covr"][0])
    except Exception:
        pass
    return None

def _preserve_times(path, callback):
    """Ejecuta una función respaldando y restaurando las fechas originales del archivo."""
    orig_atime = orig_mtime = orig_ctime = None
    with contextlib.suppress(OSError):
        st = path.stat()
        orig_atime = st.st_atime
        orig_mtime = st.st_mtime
        orig_ctime = st.st_ctime

    callback()

    with contextlib.suppress(OSError):
        if orig_atime is not None and orig_mtime is not None:
            os.utime(str(path), (orig_atime, orig_mtime))
        if orig_ctime is not None and setctime_blocking is not None:
            setctime_blocking(str(path), orig_ctime)

def write_cover_art_data(file_path: Path, data: bytes, mime_type: str = "image/jpeg") -> bool:
    """Escribe bytes de imagen como carátula preservando las fechas del sistema."""
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.exists():
        return False

    def _do_write():
        ext = path.suffix.lower()
        audio = mutagen.File(str(path))
        if audio is None:
            return

        if ext == ".mp3":
            if audio.tags is None:
                audio.add_tags()
            id3 = audio.tags
            keys_to_remove = [k for k in id3.keys() if k.startswith("APIC")]
            for k in keys_to_remove:
                del id3[k]
            
            id3.add(APIC(
                encoding=3,
                mime=mime_type,
                type=3,  # 3 = Front cover
                desc='Cover',
                data=data
            ))
            audio.save()

        elif ext in {".mp4", ".m4a", ".m4v"}:
            mp4 = audio.tags
            if mp4 is None:
                return
            cover_format = MP4Cover.FORMAT_PNG if "png" in mime_type.lower() else MP4Cover.FORMAT_JPEG
            mp4["covr"] = [MP4Cover(data, imageformat=cover_format)]
            audio.save()

    try:
        _preserve_times(path, _do_write)
        return True
    except Exception:
        return False

def write_cover_art(file_path: Path, image_path: Path) -> bool:
    """Lee un archivo de imagen en disco y lo escribe como carátula."""
    img_path = Path(image_path)
    if not img_path.exists():
        return False
    try:
        data = img_path.read_bytes()
        suffix = img_path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"
        return write_cover_art_data(file_path, data, mime)
    except Exception:
        return False

def export_cover_art(file_path: Path, export_path: Path) -> bool:
    """Exporta la carátula incrustada a un archivo en disco."""
    data = read_cover_art(file_path)
    if not data:
        return False
    try:
        Path(export_path).write_bytes(data)
        return True
    except Exception:
        return False
    
def get_common_cover(entries) -> bytes:
    """Compara mediante bytes crudos las carátulas de múltiples entradas.
    
    Devuelve los bytes si todos tienen exactamente la misma carátula.
    Devuelve b"" (vacío) si todos carecen de carátula.
    Devuelve None si las carátulas difieren entre los archivos seleccionados.
    """
    if not entries:
        return None

    first_bytes = read_cover_art(entries[0].path)

    for entry in entries[1:]:
        current_bytes = read_cover_art(entry.path)
        if current_bytes != first_bytes:
            return None  # Hay diferencias (valores múltiples)

    return first_bytes  # Retorna los bytes comunes (o None si todos están vacíos)

def remove_cover_art(file_path: Path) -> bool:
    """Elimina la carátula frontal preservando las fechas del sistema."""
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS or not path.exists():
        return False

    def _do_remove():
        ext = path.suffix.lower()
        audio = mutagen.File(str(path))
        if audio is None:
            return

        if ext == ".mp3":
            if audio.tags is not None:
                id3 = audio.tags
                keys_to_remove = [k for k in id3.keys() if k.startswith("APIC")]
                for k in keys_to_remove:
                    del id3[k]
                audio.save()

        elif ext in {".mp4", ".m4a", ".m4v"}:
            mp4 = audio.tags
            if mp4 is not None and "covr" in mp4:
                del mp4["covr"]
                audio.save()

    try:
        _preserve_times(path, _do_remove)
        return True
    except Exception:
        return False