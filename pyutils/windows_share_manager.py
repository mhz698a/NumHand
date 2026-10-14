# windows_share_manager.py
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from shutil import which
from typing import Any, Iterable, Sequence


class WindowsShareError(Exception):
    """Base para errores del motor de compartición."""


class WindowsAdminRequiredError(WindowsShareError):
    """La operación requiere privilegios elevados."""


class WindowsShareValidationError(WindowsShareError):
    """La entrada no cumple con lo esperado."""


class WindowsShareExecutionError(WindowsShareError):
    """Falló la ejecución de un comando de Windows."""


class ShareAccessRight(str, Enum):
    READ = "Read"
    CHANGE = "Change"
    FULL = "Full"


@dataclass(frozen=True)
class SharePermissionSummary:
    puede: tuple[str, ...]
    no_puede: tuple[str, ...]


class WindowsShareManager:
    """
    Motor lógico para crear, eliminar, consultar y administrar recursos SMB locales en Windows.

    Diseñado para ser importado en PyQt6.
    La UI no debe llamar operaciones largas en el hilo principal: mover una instancia
    de esta clase a un QThread o encapsularla en un QObject trabajador.

    Nota práctica para PyQt6:
    - el slot de la UI dispara una señal al worker
    - el worker ejecuta la operación aquí
    - el worker emite resultado/error al terminar
    """

    PAYLOAD_ENV = "WSM_PAYLOAD_JSON"
    _INVALID_SHARE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
    _SAFE_NAME_RE = re.compile(r"^[^\\/:*?\"<>|\x00-\x1F]{1,80}$")

    def __init__(self) -> None:
        self._ps_exe = self._detect_powershell()

    @staticmethod
    def es_administrador() -> bool:
        if os.name != "nt":
            return False
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def _detect_powershell() -> str | None:
        for candidate in ("powershell.exe", "pwsh.exe"):
            if which(candidate):
                return candidate
        return None

    @classmethod
    def _ensure_windows(cls) -> None:
        if os.name != "nt":
            raise WindowsShareValidationError("Esta clase solo funciona en Windows.")

    @classmethod
    def normalizar_share_name(cls, share_name: str) -> str:
        if not isinstance(share_name, str):
            raise WindowsShareValidationError("El nombre del recurso debe ser texto.")

        name = share_name.strip()
        if not name:
            raise WindowsShareValidationError("El nombre del recurso no puede estar vacío.")

        # Sanitización conservadora: evita caracteres problemáticos en Windows.
        name = cls._INVALID_SHARE_CHARS.sub("_", name)
        name = re.sub(r"\s+", " ", name).strip(" .")

        if not name:
            raise WindowsShareValidationError("El nombre del recurso quedó vacío tras la sanitización.")

        if name.upper() in {"CON", "PRN", "AUX", "NUL"}:
            raise WindowsShareValidationError("Ese nombre no es válido como recurso compartido.")

        if not cls._SAFE_NAME_RE.fullmatch(name):
            raise WindowsShareValidationError("El nombre del recurso contiene caracteres no permitidos.")

        return name

    @staticmethod
    def _validar_folder_path(folder_path: str) -> Path:
        if not isinstance(folder_path, str):
            raise WindowsShareValidationError("La ruta debe ser texto.")

        raw = folder_path.strip()
        if not raw:
            raise WindowsShareValidationError("La ruta no puede estar vacía.")

        path = Path(raw)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise WindowsShareValidationError(f"La carpeta no existe: {raw}") from exc
        except OSError as exc:
            raise WindowsShareValidationError(f"No se pudo validar la ruta: {exc}") from exc

        if not resolved.is_dir():
            raise WindowsShareValidationError(f"La ruta no corresponde a una carpeta: {raw}")

        return resolved

    @staticmethod
    def _validar_descripcion(description: str | None) -> str:
        if description is None:
            return ""
        if not isinstance(description, str):
            raise WindowsShareValidationError("La descripción debe ser texto.")
        desc = description.strip()
        if len(desc) > 256:
            raise WindowsShareValidationError("La descripción no puede exceder 256 caracteres.")
        return desc

    @staticmethod
    def _validar_lista_cuentas(values: Iterable[str] | None, field_name: str) -> list[str]:
        if values is None:
            return []
        out: list[str] = []
        for item in values:
            if not isinstance(item, str):
                raise WindowsShareValidationError(f"'{field_name}' debe contener solo texto.")
            cleaned = item.strip()
            if not cleaned:
                continue
            out.append(cleaned)
        return out

    @staticmethod
    def _validar_limite_usuarios(limit: int | None) -> int | None:
        if limit is None:
            return None
        if not isinstance(limit, int):
            raise WindowsShareValidationError("El límite de usuarios debe ser un entero.")
        if limit < 0:
            raise WindowsShareValidationError("El límite de usuarios no puede ser negativo.")
        return limit

    def _run_powershell_json(self, script: str, payload: dict[str, Any] | None = None) -> Any:
        if not self._ps_exe:
            raise WindowsShareExecutionError("No se encontró PowerShell en este sistema.")

        env = os.environ.copy()
        if payload is not None:
            env[self.PAYLOAD_ENV] = json.dumps(payload, ensure_ascii=False)

        extra_args = {}
        if os.name == "nt":
            # CREATE_NO_WINDOW (0x08000000) evita que el subproceso herede o cree una consola visible
            extra_args["creationflags"] = 0x08000000
        
        proc = subprocess.run(
            [self._ps_exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            shell=False,
            env=env,
            **extra_args # Inyecta de forma segura el flag de ocultación si estás en Windows
        )

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if proc.returncode != 0:
            raise WindowsShareExecutionError(self._traducir_error(stderr, stdout, proc.returncode))

        if not stdout:
            return None

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise WindowsShareExecutionError(f"Salida no JSON inesperada: {stdout}") from exc

    def _run_net_share(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["net", *args],
            capture_output=True,
            text=True,
            shell=False,
        )
        return proc

    @staticmethod
    def _traducir_error(stderr: str, stdout: str = "", returncode: int = 1) -> str:
        blob = f"{stdout}\n{stderr}".lower()

        patterns = [
            ("access is denied", "Acceso denegado. Ejecuta la aplicación como administrador."),
            ("acceso denegado", "Acceso denegado. Ejecuta la aplicación como administrador."),
            ("system error 5", "Acceso denegado. Ejecuta la aplicación como administrador."),
            ("already exists", "El recurso compartido ya existe."),
            ("ya existe", "El recurso compartido ya existe."),
            ("system error 85", "Ya existe un nombre en conflicto para ese recurso."),
            ("cannot find the file specified", "No se encontró la ruta o el recurso solicitado."),
            ("no se puede encontrar el archivo especificado", "No se encontró la ruta o el recurso solicitado."),
            ("not recognized as the name of a cmdlet", "PowerShell no tiene disponible el módulo o cmdlet necesario."),
            ("the term", "PowerShell no tiene disponible el módulo o cmdlet necesario."),
            ("share does not exist", "No existe un recurso compartido con ese nombre."),
            ("no existe", "No existe un recurso compartido con ese nombre."),
            ("system error 2310", "No existe un recurso compartido con ese nombre."),
            ("system error 2312", "Ya existe un recurso con ese nombre."),
        ]

        for needle, message in patterns:
            if needle in blob:
                return message

        detail = stderr.strip() or stdout.strip() or "sin detalle"
        return f"El comando falló con código {returncode}. Detalle: {detail}"

    @staticmethod
    def resumen_permiso(right: ShareAccessRight | str) -> SharePermissionSummary:
        value = right.value if isinstance(right, ShareAccessRight) else str(right).strip().title()
        if value == "Read":
            return SharePermissionSummary(
                puede=("leer", "listar", "abrir archivos"),
                no_puede=("crear", "modificar", "borrar", "cambiar permisos"),
            )
        if value == "Change":
            return SharePermissionSummary(
                puede=("leer", "listar", "abrir", "crear", "modificar", "borrar"),
                no_puede=("cambiar permisos"),
            )
        return SharePermissionSummary(
            puede=("leer", "listar", "abrir", "crear", "modificar", "borrar", "cambiar permisos"),
            no_puede=(),
        )

    @staticmethod
    def _normalizar_resultado_json(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    @staticmethod
    def _normalizar_share_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "nombre": row.get("Name"),
            "ruta": row.get("Path"),
            "descripcion": row.get("Description"),
            "maximo_usuarios": row.get("MaximumAllowed"),
            "allow_maximum": row.get("AllowMaximum"),
            "estado": row.get("Status"),
            "tipo": row.get("Type"),
        }

    @staticmethod
    def _normalizar_access_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "share_name": row.get("Name"),
            "scope_name": row.get("ScopeName"),
            "account_name": row.get("AccountName"),
            "access_control_type": row.get("AccessControlType"),
            "access_right": row.get("AccessRight"),
        }

    @staticmethod
    def _normalizar_session_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": row.get("SessionId"),
            "client_computer_name": row.get("ClientComputerName"),
            "client_user_name": row.get("ClientUserName"),
            "num_opens": row.get("NumOpens"),
            "dialect": row.get("Dialect"),
            "seconds_exists": row.get("SecondsExists"),
            "seconds_idle": row.get("SecondsIdle"),
            "scope_name": row.get("ScopeName"),
        }

    @staticmethod
    def _normalizar_open_file_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_id": row.get("FileId"),
            "session_id": row.get("SessionId"),
            "path": row.get("Path"),
            "client_computer_name": row.get("ClientComputerName"),
            "client_user_name": row.get("ClientUserName"),
            "share_relative_path": row.get("ShareRelativePath"),
        }

    def compartir_carpeta(
        self,
        folder_path: str,
        share_name: str,
        description: str | None = None,
        full_access: Iterable[str] | None = None,
        change_access: Iterable[str] | None = None,
        read_access: Iterable[str] | None = None,
        no_access: Iterable[str] | None = None,
        concurrent_user_limit: int | None = None,
        continuously_available: bool | None = None,
    ) -> bool:
        """
        Crea un recurso SMB.
        Primero intenta SMBShare. Si el módulo no está disponible, usa net share.
        """
        self._ensure_windows()
        if not self.es_administrador():
            raise WindowsAdminRequiredError("La operación requiere privilegios de administrador.")

        carpeta = self._validar_folder_path(folder_path)
        nombre = self.normalizar_share_name(share_name)
        desc = self._validar_descripcion(description)
        full = self._validar_lista_cuentas(full_access, "full_access")
        change = self._validar_lista_cuentas(change_access, "change_access")
        read = self._validar_lista_cuentas(read_access, "read_access")
        deny = self._validar_lista_cuentas(no_access, "no_access")
        limit = self._validar_limite_usuarios(concurrent_user_limit)

        if self._ps_exe:
            script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json

$params = @{
    Name = $payload.share_name
    Path = $payload.folder_path
}

if ($payload.description) { $params.Description = $payload.description }
if ($null -ne $payload.concurrent_user_limit) { $params.ConcurrentUserLimit = [uint32]$payload.concurrent_user_limit }
if ($null -ne $payload.continuously_available) { $params.ContinuouslyAvailable = [bool]$payload.continuously_available }

if ($payload.full_access -and $payload.full_access.Count -gt 0) { $params.FullAccess = @($payload.full_access) }
if ($payload.change_access -and $payload.change_access.Count -gt 0) { $params.ChangeAccess = @($payload.change_access) }
if ($payload.read_access -and $payload.read_access.Count -gt 0) { $params.ReadAccess = @($payload.read_access) }
if ($payload.no_access -and $payload.no_access.Count -gt 0) { $params.NoAccess = @($payload.no_access) }

New-SmbShare @params -ErrorAction Stop | Select-Object * | ConvertTo-Json -Depth 8 -Compress
"""
            try:
                self._run_powershell_json(
                    script,
                    {
                        "share_name": nombre,
                        "folder_path": str(carpeta),
                        "description": desc,
                        "full_access": full,
                        "change_access": change,
                        "read_access": read,
                        "no_access": deny,
                        "concurrent_user_limit": limit,
                        "continuously_available": continuously_available,
                    },
                )
                return True
            except WindowsShareExecutionError as exc:
                # Fallback a net share si el módulo SMBShare no está disponible.
                msg = str(exc).lower()
                if "not recognized" not in msg and "módulo" not in msg and "cmdlet" not in msg:
                    raise

        # Fallback clásico: net share
        args = [f"share", f"{nombre}={str(carpeta)}"]
        for account in full:
            args.append(f"/grant:{account},FULL")
        for account in change:
            args.append(f"/grant:{account},CHANGE")
        for account in read:
            args.append(f"/grant:{account},READ")
        if deny:
            raise WindowsShareValidationError("net share no admite NoAccess en el fallback clásico.")
        if limit is not None and limit > 0:
            args.append(f"/users:{limit}")
        if desc:
            args.append(f"/remark:{desc}")

        proc = self._run_net_share(args)
        if proc.returncode != 0:
            raise WindowsShareExecutionError(self._traducir_error(proc.stderr, proc.stdout, proc.returncode))
        return True

    def descompartir_carpeta(self, share_name: str, force: bool = True) -> bool:
        self._ensure_windows()
        if not self.es_administrador():
            raise WindowsAdminRequiredError("La operación requiere privilegios de administrador.")

        nombre = self.normalizar_share_name(share_name)

        if self._ps_exe:
            script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json
if ($payload.force) {
    Remove-SmbShare -Name $payload.share_name -Force -Confirm:$false -ErrorAction Stop | Out-Null
} else {
    Remove-SmbShare -Name $payload.share_name -Confirm:$false -ErrorAction Stop | Out-Null
}
[pscustomobject]@{
    ok = $true
    share_name = $payload.share_name
} | ConvertTo-Json -Compress
"""
            try:
                self._run_powershell_json(script, {"share_name": nombre, "force": force})
                return True
            except WindowsShareExecutionError as exc:
                msg = str(exc).lower()
                if "not recognized" not in msg and "módulo" not in msg and "cmdlet" not in msg:
                    raise

        proc = self._run_net_share(["share", nombre, "/delete"])
        if proc.returncode != 0:
            raise WindowsShareExecutionError(self._traducir_error(proc.stderr, proc.stdout, proc.returncode))
        return True

    def obtener_carpetas_compartidas(self) -> list[dict[str, Any]]:
        """
        Devuelve los shares visibles en el sistema.
        Fuente principal: Win32_Share vía CIM/WMI.
        """
        self._ensure_windows()
        script = r"""
$ErrorActionPreference = 'Stop'
Get-CimInstance -ClassName Win32_Share |
    Select-Object Name, Path, Description, MaximumAllowed, AllowMaximum, Status, Type |
    ConvertTo-Json -Depth 6 -Compress
"""
        items = self._normalizar_resultado_json(self._run_powershell_json(script))
        return [self._normalizar_share_row(item) for item in items]

    def existe_carpeta_compartida(self, share_name: str) -> bool:
        nombre = self.normalizar_share_name(share_name)
        for share in self.obtener_carpetas_compartidas():
            if share.get("nombre") == nombre:
                return True
        return False

    def obtener_detalles_carpeta_compartida(self, share_name: str) -> dict[str, Any]:
        """
        Devuelve:
        - detalle WMI/CIM del share
        - ACL del share
        """
        self._ensure_windows()
        nombre = self.normalizar_share_name(share_name)

        script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json

$name = $payload.share_name.Replace("'", "''")
$wmi = Get-CimInstance -ClassName Win32_Share -Filter "Name='$name'" |
    Select-Object Name, Path, Description, MaximumAllowed, AllowMaximum, Status, Type

$access = @()
try {
    $access = (Get-SmbShare -Name $payload.share_name -ErrorAction Stop | Get-SmbShareAccess -ErrorAction Stop |
        Select-Object Name, ScopeName, AccountName, AccessControlType, AccessRight)
} catch {
    $access = @()
}

[pscustomobject]@{
    wmi_share = $wmi
    access    = $access
} | ConvertTo-Json -Depth 8 -Compress
"""
        raw = self._run_powershell_json(script, {"share_name": nombre})

        if not isinstance(raw, dict):
            raise WindowsShareExecutionError("No se pudo obtener el detalle del recurso compartido.")

        wmi_share = raw.get("wmi_share")
        access = raw.get("access")

        if isinstance(wmi_share, list):
            wmi_share = wmi_share[0] if wmi_share else None

        if isinstance(access, list):
            normalized_access = [self._normalizar_access_row(x) for x in access if isinstance(x, dict)]
        elif isinstance(access, dict):
            normalized_access = [self._normalizar_access_row(access)]
        else:
            normalized_access = []

        return {
            "share": self._normalizar_share_row(wmi_share) if isinstance(wmi_share, dict) else None,
            "access": normalized_access,
        }

    def obtener_permisos_carpeta_compartida(self, share_name: str) -> list[dict[str, Any]]:
        self._ensure_windows()
        nombre = self.normalizar_share_name(share_name)

        script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json
Get-SmbShare -Name $payload.share_name -ErrorAction Stop |
    Get-SmbShareAccess -ErrorAction Stop |
    Select-Object Name, ScopeName, AccountName, AccessControlType, AccessRight |
    ConvertTo-Json -Depth 6 -Compress
"""
        items = self._normalizar_resultado_json(self._run_powershell_json(script, {"share_name": nombre}))
        return [self._normalizar_access_row(item) for item in items]

    def otorgar_permiso_carpeta_compartida(self, share_name: str, account_name: str, right: ShareAccessRight | str) -> bool:
        self._ensure_windows()
        if not self.es_administrador():
            raise WindowsAdminRequiredError("La operación requiere privilegios de administrador.")

        nombre = self.normalizar_share_name(share_name)
        account = account_name.strip()
        if not account:
            raise WindowsShareValidationError("El nombre de cuenta no puede estar vacío.")
        access_right = right.value if isinstance(right, ShareAccessRight) else str(right).strip().title()
        if access_right not in {"Read", "Change", "Full"}:
            raise WindowsShareValidationError("Permiso inválido. Use Read, Change o Full.")

        script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json
Get-SmbShare -Name $payload.share_name -ErrorAction Stop |
    Grant-SmbShareAccess -AccountName $payload.account_name -AccessRight $payload.access_right -Force -ErrorAction Stop |
    Out-Null
"OK"
"""
        self._run_powershell_json(
            script,
            {"share_name": nombre, "account_name": account, "access_right": access_right},
        )
        return True

    def revocar_permiso_carpeta_compartida(self, share_name: str, account_name: str) -> bool:
        self._ensure_windows()
        if not self.es_administrador():
            raise WindowsAdminRequiredError("La operación requiere privilegios de administrador.")

        nombre = self.normalizar_share_name(share_name)
        account = account_name.strip()
        if not account:
            raise WindowsShareValidationError("El nombre de cuenta no puede estar vacío.")

        script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json
Get-SmbShare -Name $payload.share_name -ErrorAction Stop |
    Revoke-SmbShareAccess -AccountName $payload.account_name -Force -ErrorAction Stop |
    Out-Null
"OK"
"""
        self._run_powershell_json(script, {"share_name": nombre, "account_name": account})
        return True

    def establecer_permisos_carpeta_compartida(
        self,
        share_name: str,
        full_access: Iterable[str] | None = None,
        change_access: Iterable[str] | None = None,
        read_access: Iterable[str] | None = None,
        remove_existing: bool = False,
    ) -> bool:
        """
        Ajusta permisos del share.
        Si remove_existing=True, revoca primero los trustees actuales.
        """
        self._ensure_windows()
        if not self.es_administrador():
            raise WindowsAdminRequiredError("La operación requiere privilegios de administrador.")

        nombre = self.normalizar_share_name(share_name)
        full = self._validar_lista_cuentas(full_access, "full_access")
        change = self._validar_lista_cuentas(change_access, "change_access")
        read = self._validar_lista_cuentas(read_access, "read_access")

        if remove_existing:
            actuales = self.obtener_permisos_carpeta_compartida(nombre)
            for row in actuales:
                account = row.get("account_name")
                if account:
                    self.revocar_permiso_carpeta_compartida(nombre, account)

        for account in full:
            self.otorgar_permiso_carpeta_compartida(nombre, account, ShareAccessRight.FULL)
        for account in change:
            self.otorgar_permiso_carpeta_compartida(nombre, account, ShareAccessRight.CHANGE)
        for account in read:
            self.otorgar_permiso_carpeta_compartida(nombre, account, ShareAccessRight.READ)

        return True

    def obtener_sesiones_smb(self) -> list[dict[str, Any]]:
        self._ensure_windows()
        script = r"""
$ErrorActionPreference = 'Stop'
Get-SmbSession |
    Select-Object SessionId, ClientComputerName, ClientUserName, NumOpens, Dialect, SecondsExists, SecondsIdle, ScopeName |
    ConvertTo-Json -Depth 6 -Compress
"""
        items = self._normalizar_resultado_json(self._run_powershell_json(script))
        return [self._normalizar_session_row(item) for item in items]

    def obtener_archivos_abiertos_smb(self) -> list[dict[str, Any]]:
        self._ensure_windows()
        script = r"""
$ErrorActionPreference = 'Stop'
Get-SmbOpenFile |
    Select-Object FileId, SessionId, Path, ClientComputerName, ClientUserName, ShareRelativePath |
    ConvertTo-Json -Depth 6 -Compress
"""
        items = self._normalizar_resultado_json(self._run_powershell_json(script))
        return [self._normalizar_open_file_row(item) for item in items]

    def cerrar_sesion_smb(self, session_id: int) -> bool:
        self._ensure_windows()
        if not self.es_administrador():
            raise WindowsAdminRequiredError("La operación requiere privilegios de administrador.")
        if not isinstance(session_id, int) or session_id < 0:
            raise WindowsShareValidationError("SessionId inválido.")

        script = r"""
$ErrorActionPreference = 'Stop'
$payload = $env:WSM_PAYLOAD_JSON | ConvertFrom-Json
Close-SmbSession -SessionId ([UInt64]$payload.session_id) -Force -ErrorAction Stop | Out-Null
"OK"
"""
        self._run_powershell_json(script, {"session_id": session_id})
        return True

    def resumen_detallado_carpeta_compartida(self, share_name: str) -> dict[str, Any]:
        """
        Atajo para UI:
        - detalles del share
        - permisos
        - resumen humano de acceso
        """
        nombre = self.normalizar_share_name(share_name)
        detalle = self.obtener_detalles_carpeta_compartida(nombre)
        permisos = detalle.get("access", [])

        return {
            "share_name": nombre,
            "details": detalle.get("share"),
            "access": permisos,
            "permissions_summary": {
                "Read": {
                    "puede": list(self.resumen_permiso(ShareAccessRight.READ).puede),
                    "no_puede": list(self.resumen_permiso(ShareAccessRight.READ).no_puede),
                },
                "Change": {
                    "puede": list(self.resumen_permiso(ShareAccessRight.CHANGE).puede),
                    "no_puede": list(self.resumen_permiso(ShareAccessRight.CHANGE).no_puede),
                },
                "Full": {
                    "puede": list(self.resumen_permiso(ShareAccessRight.FULL).puede),
                    "no_puede": list(self.resumen_permiso(ShareAccessRight.FULL).no_puede),
                },
            },
        }


# ---------------------------------------------------------------------
# Integración mínima con PyQt6:
#
# class ShareWorker(QtCore.QObject):
#     finished = QtCore.pyqtSignal(object)
#     error = QtCore.pyqtSignal(str)
#
#     @QtCore.pyqtSlot(str, str)
#     def create_share(self, folder_path: str, share_name: str):
#         try:
#             manager = WindowsShareManager()
#             manager.compartir_carpeta(folder_path, share_name)
#             self.finished.emit(True)
#         except Exception as exc:
#             self.error.emit(str(exc))
#
# El worker se mueve a un QThread. La UI solo recibe señales.
# ---------------------------------------------------------------------


if __name__ == "__main__":
    mgr = WindowsShareManager()

    print("Administrador:", mgr.es_administrador())    
    print("Shares:")
    for s in mgr.obtener_carpetas_compartidas():
        print(s)