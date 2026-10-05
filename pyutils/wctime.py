# wctime.py
import ctypes
import time

kernel32 = ctypes.windll.kernel32

FILE_WRITE_ATTRIBUTES = 0x100
OPEN_EXISTING = 3
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4

class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_uint32),
        ("dwHighDateTime", ctypes.c_uint32),
    ]

def ts_to_filetime(ts: float) -> FILETIME:
    timestamp = int((ts + 11644473600) * 10_000_000)
    return FILETIME(timestamp & 0xFFFFFFFF, timestamp >> 32)

def _set_creation_time(path: str, ts: float):
    ft = ts_to_filetime(ts)

    handle = kernel32.CreateFileW(
        path,
        FILE_WRITE_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if handle == -1:
        raise OSError("Archivo ocupado")

    kernel32.SetFileTime(handle, ctypes.byref(ft), None, None)
    kernel32.CloseHandle(handle)

def setctime_blocking(path: str, ts: float, retry: float = 0.9):
    """
    Equivalente Windows a os.utime para Creation Time.
    Espera hasta que el archivo se libere.
    """
    while True:
        try:
            _set_creation_time(path, ts)
            return
        except OSError:
            time.sleep(retry)
