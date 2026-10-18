import webbrowser
import requests
import re
import os
import time
import email.utils
from bs4 import BeautifulSoup
from dateutil import parser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

class NGError(Exception):
    pass

USE_NG_UPLOADED_DATE = False

VERBOSE = False

def ng_print(text):
    print(text if VERBOSE else "")

def sanitize_filename(name):
    """Limpia caracteres prohibidos por los sistemas operativos en nombres de archivo."""
    if not name:
        return "audio_unknown"
    # Reemplaza los caracteres no válidos con guiones bajos
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remueve espacios sobrantes o puntos al inicio/final
    return cleaned.strip().strip('.')

def parse_http_date(v):
    try:
        if not v:
            return None
        return email.utils.parsedate_to_datetime(v).timestamp()
    except Exception:
        return None

def extract_ng_uploaded_ts(soup):
    try:
        dl = soup.select_one("#sidestats dl.sidestats")
        if not dl:
            return None

        for dt in dl.find_all("dt"):
            if dt.get_text(strip=True) == "Uploaded":
                dd_date = dt.find_next_sibling("dd")
                dd_time = dd_date.find_next_sibling("dd") if dd_date else None

                if not dd_date or not dd_time:
                    return None

                raw = f"{dd_date.get_text(strip=True)} {dd_time.get_text(strip=True)}"
                return parser.parse(raw).timestamp()

    except Exception:
        pass

    return None

def extract_ng(song_id):
    """Devuelve dict: {title, url, content_length (int or None), last_modified_ts (float or None)}"""
    if not song_id or not song_id.isdigit():
        raise NGError("ID no numérico")

    url = f"https://www.newgrounds.com/audio/listen/{song_id}"
    
    try:
        r_obj = requests.get(url, headers=HEADERS, timeout=20)
    except requests.exceptions.Timeout:
        raise NGError("El servidor de Newgrounds tardó demasiado en responder (Timeout).")
    except requests.exceptions.RequestException as e:
        raise NGError(f"Error de red al conectar con Newgrounds: {e}")

    if r_obj.status_code != 200:
        raise NGError(f"HTTP {r_obj.status_code} al pedir la página NG")

    soup = BeautifulSoup(r_obj.text, "html.parser")

    if soup.find(id="pageerror"):
        raise NGError("Audio no existe o fue eliminado (pageerror)")

    title = soup.title.text.strip() if soup.title else f"newgrounds_{song_id}"
    
    # ---------- artista ----------
    artist = None
    try:
        a_obj = soup.select_one("div.authorlinks h4 a")
        if a_obj:
            artist = a_obj.get_text(strip=True)
    except Exception:
        artist = None

    # regex para URL mp3
    m = re.search(r'https?://audio\.ngfiles\.com/[^\s"\'<>]+?\.mp3', r_obj.text)
    if not m:
        # fallback: buscar con escapes
        m2 = re.search(r'audio\.ngfiles\.com\\?/[^"]+?\.mp3', r_obj.text)
        if m2:
            raw = m2.group(0).replace('\\/', '/')
            mp3_url = "https://" + raw if raw.startswith('audio.') else raw
        else:
            raise NGError("No se encontró enlace mp3 en HTML")
    else:
        mp3_url = m.group(0)

    # HEAD para metadata
    try:
        h = requests.head(mp3_url, headers=HEADERS, allow_redirects=True, timeout=15)
    except Exception:
        h = None

    content_length = None
    if h is not None:
        try:
            if 'Content-Length' in h.headers:
                content_length = int(h.headers['Content-Length'])
        except Exception:
            content_length = None
            
        lm = h.headers.get('Last-Modified') or h.headers.get('Date')
        file_ts = parse_http_date(lm) if lm else None

        uploaded_ts = None
        if USE_NG_UPLOADED_DATE:
            uploaded_ts = extract_ng_uploaded_ts(soup)

        final_ts = uploaded_ts if uploaded_ts is not None else file_ts

    return {
        "title": title,
        "artist": artist,
        "mp3_url": mp3_url,
        "content_length": content_length,
        "last_modified_ts": final_ts
    }

def download_ng_stream(mp3_url, dest_path, progress_callback=None, chunk_size=64*1024, stop_flag=None):
    """Descarga por streaming de forma robusta con manejo de errores, limpieza y reintentos para renombrar."""
    tmp = dest_path + ".part"
    downloaded = 0
    total = None
    success = False

    try:
        with requests.get(mp3_url, headers=HEADERS, stream=True, timeout=20) as r:
            r.raise_for_status()
            
            content_type = r.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                raise NGError("El enlace devolvió una página HTML en lugar de un archivo de audio válido.")
            
            total = int(r.headers.get("Content-Length", 0)) or None
            
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    # 1. Comprobar cancelación manual del usuario
                    if stop_flag is not None and stop_flag():
                        return {"cancelled": True, "downloaded": downloaded, "total": total}
                    
                    if not chunk:
                        continue
                        
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)
        
        # Si el bucle termina con éxito, marcamos la bandera
        success = True
        
        # --- REINTENTOS PARA EVITAR WINERROR 32 / 33 ---
        max_retries = 5
        delay = 4.5
        last_exception = None

        for attempt in range(max_retries):
            try:
                os.replace(tmp, dest_path)
                last_exception = None
                break
            except PermissionError as e:
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    raise NGError(f"No se pudo renombrar el archivo tras {max_retries} intentos por bloqueo de Windows: {e}")
            except Exception as e:
                raise NGError(f"Error inesperado al mover el archivo: {e}")

        if last_exception:
            raise NGError(f"Fallo al renombrar el archivo: {last_exception}")

        return {"cancelled": False, "downloaded": downloaded, "total": total}

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
        raise NGError(f"Fallo de red o conexión interrumpida durante la descarga: {e}")
    except Exception as e:
        if isinstance(e, NGError):
            raise
        raise NGError(f"Error inesperado durante la descarga: {e}")
        
    finally:
        # Limpieza automática: Si la descarga NO fue exitosa y el archivo temporal existe, lo borramos
        if not success and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
            
def get_song_information(id_string) -> dict:
    song_id = id_string.strip()
    if not song_id.isdigit():
        return {"Exception": "ID invalido"}
    try:
        data = extract_ng(song_id)
        raw_title = data.get("title") or f"song {song_id}"
        safe_filename = sanitize_filename(raw_title)
        
        title = data.get("title")
        if not title:
            title = f"song {song_id}"
            
        artist = data.get("artist")
        if not artist:
            artist = "Unknown Artist"
        
        return {
            "title": title,
            "artist": artist,
            "filename": safe_filename,
            "ng_id": song_id,
            "Exception": None
        }
        
    except NGError as e:
        return {"Exception": str(e)}
    except Exception as e:
        return {"Exception": f"Fallo inesperado:\n{e}"}

def open_id_page(idsong) -> None:
    webbrowser.open(f"https://newgrounds.com/audio/listen/{idsong}")