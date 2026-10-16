import time
import hashlib
import re
from pathlib import Path


def rename_with_retry(src_path, dst_path, max_attempts=10, delay=2.0):
    """Reintenta renombrar un archivo hasta max_attempts veces con una pausa de delay segundos."""
    for attempt in range(1, max_attempts + 1):
        try:
            src_path.rename(dst_path)
            return
        except Exception as e:
            if attempt == max_attempts:
                raise e
            time.sleep(delay)


def compute_file_hash(file_path, chunk_size=65536):
    """Calcula el hash SHA-256 de un archivo."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


def clean_prefix(filename):
    p = Path(filename)
    stem = p.stem
    suffix = p.suffix
    cleaned_stem = re.sub(r"^(?:[a-zA-Z]{1,5}[-_.\s]*)?\d+[:._\s-]*", "", stem)
    cleaned_stem = cleaned_stem.strip()
    return f"{cleaned_stem}{suffix}" if cleaned_stem else filename


def is_folder_cleanly_numbered(files):
    if not files:
        return False

    for idx, file in enumerate(files, start=1):
        name = file.path.name if hasattr(file, "path") else Path(file).name
        m = re.match(r"^(\d+)(?:_|\.\s*|-+\s*)", name)
        if not m:
            return False
        if int(m.group(1)) != idx:
            return False
    return True


def is_folder_cleanly_enumerated(paths):
    """Comprueba la enumeración continua independientemente del orden visual de los archivos."""
    files = []
    for item in paths:
        path = Path(item.path if hasattr(item, "path") else item)
        if path.is_file():
            files.append(path)

    if not files:
        return False

    total = len(files)
    expected_width = 2 if total < 100 else 3 if total < 1000 else 4
    numbers = []

    for path in files:
        match = re.match(r"^(\\d+)\\.\\s", path.name)
        if not match or len(match.group(1)) != expected_width:
            return False
        numbers.append(int(match.group(1)))

    return sorted(numbers) == list(range(1, total + 1))


def classify_selected_files(selected_paths):
    std_matches = []
    has_any_prefix = False

    for path_obj in selected_paths:
        name = path_obj.name
        m_std = re.match(r"^(\d{2,4})(?:_|\.\s*|-+\s*)", name)
        if m_std:
            std_matches.append(int(m_std.group(1)))

        if re.match(r"^(?:[a-zA-Z]{1,5}[-_.\s]*)?\d+[:._\s-]*", name):
            has_any_prefix = True

    if len(std_matches) == len(selected_paths):
        if std_matches == list(range(1, len(selected_paths) + 1)):
            return "CASE_2_CLEAN"
        else:
            return "CASE_3_STRANGE_OR_GAPS"

    if has_any_prefix:
        return "CASE_3_STRANGE_OR_GAPS"

    return "CASE_1_NO_NUMERATION"

