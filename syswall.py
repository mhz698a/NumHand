import platform
from pathlib import Path


def get_locking_processes(file_paths):
    """
    Comprueba si alguna de las rutas en file_paths está bloqueada por algún proceso en Windows
    usando Restart Manager (rstrtmgr.dll).

    Retorna una lista de nombres de aplicaciones o procesos que tienen archivos bloqueados.
    Si no hay archivos bloqueados o no estamos en Windows, retorna lista vacía.
    """
    if platform.system() != "Windows":
        return []

    existing_paths = []
    for p in file_paths:
        p_obj = Path(p)
        if p_obj.exists():
            existing_paths.append(str(p_obj.resolve()))

    if not existing_paths:
        return []

    try:
        import ctypes
        from ctypes import wintypes

        rstrtmgr = ctypes.windll.rstrtmgr

        CCH_RM_SESSION_KEY = 32
        CCH_RM_MAX_APP_NAME = 255
        CCH_RM_MAX_SVC_NAME = 63

        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        class RM_UNIQUE_PROCESS(ctypes.Structure):
            _fields_ = [
                ("dwProcessId", wintypes.DWORD),
                ("ProcessStartTime", FILETIME),
            ]

        class RM_PROCESS_INFO(ctypes.Structure):
            _fields_ = [
                ("Process", RM_UNIQUE_PROCESS),
                ("strAppName", ctypes.c_wchar * (CCH_RM_MAX_APP_NAME + 1)),
                ("strServiceShortName", ctypes.c_wchar * (CCH_RM_MAX_SVC_NAME + 1)),
                ("ApplicationType", ctypes.c_int),
                ("AppStatus", wintypes.DWORD),
                ("TSSessionId", wintypes.DWORD),
                ("bRestartable", wintypes.BOOL),
            ]

        session_handle = wintypes.DWORD()
        session_key = (ctypes.c_wchar * (CCH_RM_SESSION_KEY + 1))()

        res = rstrtmgr.RmStartSession(
            ctypes.byref(session_handle),
            0,
            session_key
        )
        if res != 0:
            return []

        try:
            file_array = (wintypes.LPCWSTR * len(existing_paths))()
            for i, p in enumerate(existing_paths):
                file_array[i] = p

            res = rstrtmgr.RmRegisterResources(
                session_handle,
                len(existing_paths),
                file_array,
                0, None,
                0, None
            )
            if res != 0:
                return []

            proc_info_needed = wintypes.UINT(0)
            proc_info_size = wintypes.UINT(0)
            reboot_reasons = wintypes.DWORD(0)

            res = rstrtmgr.RmGetList(
                session_handle,
                ctypes.byref(proc_info_needed),
                ctypes.byref(proc_info_size),
                None,
                ctypes.byref(reboot_reasons)
            )

            # ERROR_MORE_DATA = 234, ERROR_SUCCESS = 0
            if res not in (0, 234) or proc_info_needed.value == 0:
                return []

            proc_info_size.value = proc_info_needed.value
            proc_info_array = (RM_PROCESS_INFO * proc_info_size.value)()

            res = rstrtmgr.RmGetList(
                session_handle,
                ctypes.byref(proc_info_needed),
                ctypes.byref(proc_info_size),
                proc_info_array,
                ctypes.byref(reboot_reasons)
            )

            if res != 0:
                return []

            locking_apps = []
            for i in range(proc_info_size.value):
                app_name = proc_info_array[i].strAppName
                if not app_name:
                    pid = proc_info_array[i].Process.dwProcessId
                    app_name = f"PID {pid}"
                if app_name not in locking_apps:
                    locking_apps.append(app_name)

            return locking_apps

        finally:
            rstrtmgr.RmEndSession(session_handle)

    except Exception as e:
        print(f"Error checking locked files: {e}")
        return []
