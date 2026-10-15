import os
import sys
import tempfile
import platform
from PyQt6.QtCore import QLockFile

class SingleInstanceMutex:
    """
    Mutex para garantizar que solo una instancia de la aplicación se ejecute a la vez.
    Usa el Mutex nombrado de Windows si está en Windows, o QLockFile como alternativa.
    """
    def __init__(self, mutex_name="NumHand_SingleInstance_Mutex"):
        self.mutex_name = mutex_name
        self._lock_file = None
        self._win_mutex = None
        self._is_locked = False

    def try_lock(self) -> bool:
        """
        Intenta adquirir el mutex de instancia única.
        Retorna True si se adquirió con éxito (es la única instancia),
        o False si ya hay otra instancia ejecutándose.
        """
        if platform.system() == "Windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                mutex_name_w = f"Local\\{self.mutex_name}"
                # CreateMutexW(lpMutexAttributes, bInitialOwner, lpName)
                self._win_mutex = kernel32.CreateMutexW(None, True, mutex_name_w)
                last_error = kernel32.GetLastError()
                ERROR_ALREADY_EXISTS = 183
                if last_error == ERROR_ALREADY_EXISTS:
                    self._is_locked = False
                    return False
                self._is_locked = True
                return True
            except Exception:
                pass

        # Alternativa multiplataforma con QLockFile
        lock_path = os.path.join(tempfile.gettempdir(), f"{self.mutex_name}.lock")
        self._lock_file = QLockFile(lock_path)
        self._lock_file.setStaleLockTime(0)
        if self._lock_file.tryLock(100):
            self._is_locked = True
            return True
        else:
            self._is_locked = False
            return False

    def unlock(self):
        """Libera el mutex de la instancia actual."""
        if self._lock_file and self._is_locked:
            try:
                self._lock_file.unlock()
            except Exception:
                pass
        if self._win_mutex and platform.system() == "Windows":
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self._win_mutex)
            except Exception:
                pass
        self._is_locked = False
