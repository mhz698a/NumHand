"""Small reusable client for the foobar2000 Web API used by NumHand.

This module contains transport concerns only. Decisions about file selection
and UI behavior belong to the caller.
"""
from __future__ import annotations

from pathlib import Path
import time
from typing import Dict, Any, Optional
import requests
from requests.exceptions import HTTPError, Timeout, RequestException

BASE_URL = "http://localhost:8880"

class Foobar2000Api:
    def __init__(self, base_url:str = BASE_URL, timeout:float = 1.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, **kwargs) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Realiza una petición POST específica para la API de Beefweb.
        
        Args:
            path: Ruta del endpoint (ej. '/api/playback/next').
            **kwargs: Argumentos adicionales para requests.post (json, headers, etc.).
            
        Returns:
            Dict con la respuesta JSON si existe contenido, o None si es 204 No Content.
            
        Raises:
            HTTPError: Si el servidor responde con un código de error (4xx o 5xx).
            Timeout: Si la petición excede el tiempo límite configurado.
        """
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        
        try:
            response = requests.post(
                url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            
            # 204 No Content o cuerpo vacío
            if response.status_code == 204 or not response.content:
                return None
                
            return response.json()

        except HTTPError as http_err:
            # Aquí puedes loggear o personalizar el error según lo que devuelva Beefweb
            print(f"Error HTTP en POST {path}: {http_err} - Respuesta: {response.text}")
            raise
        except Timeout as timeout_err:
            print(f"Timeout agotado ({self.timeout}s) en POST {path}")
            raise
        except RequestException as req_err:
            print(f"Error de red inesperado en POST {path}: {req_err}")
            raise

    def player(self) -> dict[str, Any]:
        """Consulta específica para seleccionar el archivo en reproducción."""
        return self._get("/api/player")

    def player_col_parm(self, columns: list[str] | None = None) -> dict[str, Any]:
        params = {"columns": columns} if columns else {}
        return self._get("/api/player", params=params)


    def playlist_items(self, playlist_id: int, start: int = 0, end: int = 20000,
                       columns: list[str] | None = None,) -> list[dict[str, Any]]:
        payload = self._get(
            f"/api/playlists/{playlist_id}/items/{start}:{end}",
            params={"columns": columns or ["%path%"]},
        )
        playlist_items = payload.get("playlistItems", {})
        if isinstance(playlist_items, dict) and "items" in playlist_items:
            return playlist_items["items"]
        return payload.get("items", [])

    def current_path(self) -> str | None:
        player = self.player().get("player", {})
        if player.get("playbackState") not in ("playing", "paused", "pause"):
            return None

        item = player.get("activeItem")
        if not item:
            return None

        playlist_id = item.get("playlistId")
        index = item.get("index")
        if playlist_id is None or index is None:
            return None

        items = self.playlist_items(
            playlist_id,
            start=index,
            end=index + 1,
            columns=["%path%"],
        )
        if not items:
            return None

        columns = items[0].get("columns", [])
        return columns[0] if columns else None

    def current_path_playbackState(self) -> str | None:
        """Consulta específica para seleccionar el archivo en reproducción."""
        player = self.player_col_parm(columns=["%path%"]).get("player", {})
        if player.get("playbackState") not in ("playing", "paused", "pause"):
            return None

        active_item = player.get("activeItem") or {}
        columns = active_item.get("columns") or []
        return columns[0] if columns and columns[0] else None

    def stop(self) -> None:
      """Detiene la reproducción actual."""
      self._post("/api/player/stop")

    def remove_playlist_items(self, playlist_id: str | int, indices: list[int]) -> None:
      """Elimina ítems específicos de una playlist según sus índices."""
      self._post(
          f"/api/playlists/{playlist_id}/items/remove",
          json={"items": indices},
      )

    def add_playlist_items(self, playlist_id: str | int, paths: list[str]) -> None:
      """Agrega nuevos archivos a una playlist."""
      self._post(
          f"/api/playlists/{playlist_id}/items/add",
          json={"items": paths},
      )

    def sort_playlist(self, playlist_id: str | int, expression: str = "%path%") -> None:
      """Ordena los elementos de la playlist según una expresión (ej. '%path%')."""
      self._post(
          f"/api/playlists/{playlist_id}/items/sort",
          json={"by": expression},
      )

    def play_item_but_pause(self, playlist_id: str | int, index: int) -> None:
        """Reproduce un elemento específico de una playlist por su índice.
        Pero dejandolo en pause.
        """
        self._post(f"/api/player/play/{playlist_id}/{index}")
        self._post("/api/player", json={"playback": "pause"})

    def set_position_but_come(self, position_seconds: float) -> None:
        """Establece la posición actual de reproducción en segundos (Seeking).
        Asumiendo pausa y luego darle playing.
        """
        self._post("/api/player", json={"position": position_seconds},)
        self._post("/api/player", json={"playback": "playing"})
    
    def set_player_state_atomic(self, state: dict[str, Any]) -> None:
        """Establece el estado completo del reproductor (playback, activeItem, position, etc.) de forma atómica."""
        self._post("/api/player", json=state)
        
    def play_item_single(self, playlist_id: str | int, index: int) -> None:
        """Reproduce un elemento específico de una playlist por su índice."""
        self._post(f"/api/player/play/{playlist_id}/{index}")

    def set_position_single(self, position_seconds: float) -> None:
        """Establece la posición actual de reproducción en segundos (Seeking)."""
        self._post("/api/player", json={"position": position_seconds},)

    def clear_playlist(self, playlist_id: str | int) -> None:
        """Borra todos los elementos de una playlist."""
        self._post(f"/api/playlists/{playlist_id}/clear")
        
    def play_item_with_position(self, playlist_id: str | int, 
                                index: int, position_seconds: float = 0.0) -> None:
        """Reproduce un ítem específico y restaura su posición con pausas transitorias."""
        self._post(f"/api/player/play/{playlist_id}/{index}")
        time.sleep(0.6)
        self._post("/api/player", json={"position": position_seconds, "playbackState": "paused"})
        time.sleep(0.2)
        self._post("/api/player", json={"playbackState": "playing"})
    
    def reload_and_restore_playlist(self, playlist_id: str | int, 
                                    new_paths: list[str], target_file_path: str | None = None, position_seconds: float = 0.0) -> None:
        """Flujo completo: detiene, limpia la playlist, reañade los paths y reanuda el archivo activo en su posición."""
        self.stop()
        self.clear_playlist(playlist_id)
        
        if new_paths:
            self.add_playlist_items(playlist_id, new_paths)
            # Darle un respiro a foobar2000 para que indexe masivamente los elementos insertados
            time.sleep(0.4 + (len(new_paths) * 0.001)) # Pequeño factor dinámico según el tamaño
        
        if target_file_path:
            # Reintentar la búsqueda del índice por si la playlist aún se está procesando
            target_index = None
            for intento in range(3):
                items = self.playlist_items(playlist_id, start=0, end=20000, columns=["%path%"])
                norm_target = Path(target_file_path).resolve().as_posix().lower()
                
                for idx, pitem in enumerate(items):
                    cols = pitem.get("columns", [])
                    if cols and Path(cols[0]).resolve().as_posix().lower() == norm_target:
                        target_index = idx
                        break
                
                if target_index is not None:
                    break
                time.sleep(0.3) # Esperar un poco más si todavía no aparece el ítem
            
            if target_index is not None:
                time.sleep(0.3)
                self.play_item_with_position(playlist_id, target_index, position_seconds)