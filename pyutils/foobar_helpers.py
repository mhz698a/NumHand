import os
from pathlib import Path
import time
from wconst import EXTENSION_FILES, BACKUP_FILENAME, TEMP_PREFIX

def capture_foobar_playback_state(foobar_api, target_dir, new_dir=None):
    """
    Captura el estado de reproducción si el archivo activo está dentro de target_dir.
    Si se proporciona new_dir, calcula de una vez la ruta equivalente que tendrá tras la operación.
    """
    state = {
        "fb_api": foobar_api,
        "have_been_playing": False,
        "saved_playlist_id": None,
        "saved_position": 0.0,
        "playing_path": None,
        "new_path_for_playing": None,
        "saved_volume": None,
        "saved_is_muted": False,
    }
    try:
        player_data = foobar_api.player()
        player_info = player_data.get("player", {})
        
        volume_info = player_info.get("volume", {})
        state["saved_volume"] = volume_info.get("value")
        state["saved_is_muted"] = volume_info.get("isMuted", False)

        active_item = player_info.get("activeItem")
        if not active_item:
            return state

        state["saved_playlist_id"] = active_item.get("playlistId")
        state["saved_position"] = active_item.get("position", 0.0)
        playing_path = foobar_api.current_path()
        state["playing_path"] = playing_path

        if playing_path:
            target_resolved = Path(target_dir).resolve()
            play_p = Path(playing_path).resolve()
            if target_resolved == play_p or target_resolved in play_p.parents:
                state["have_been_playing"] = True
                if new_dir:
                    rel_subpath = play_p.relative_to(target_resolved)
                    state["new_path_for_playing"] = str(Path(new_dir).resolve() / rel_subpath)
                foobar_api.stop()
                # La playlist se limpia después de completar el cambio físico, no durante la captura.
                time.sleep(0.7)
    except Exception:
        pass
    return state

def restore_and_sync_foobar_playlist(state, new_dir, file_entries=None, source_dir=None):
    """Reconstruye la playlist con la lista completa de archivos capturada antes del cambio."""
    if (
        not state.get("fb_api")
        or state.get("saved_playlist_id") is None
        or not state.get("have_been_playing")
    ):
        return

    # No reconstruir una playlist con una lista parcial o desconocida.
    if file_entries is None:
        print("No se sincronizó Foobar2000: falta la lista completa de archivos de origen.")
        return

    fb_api = state["fb_api"]
    playlist_id = state["saved_playlist_id"]
    saved_volume = state.get("saved_volume")

    try:
        audio_extensions = EXTENSION_FILES
        source_root = Path(source_dir).resolve() if source_dir is not None else None
        destination_root = Path(new_dir).resolve()
        new_audio_paths = []

        for item in file_entries:
            raw_path = item.path if hasattr(item, "path") else item
            original_path = Path(raw_path).resolve()
            if original_path.suffix.lower() not in audio_extensions:
                continue

            if source_root is not None:
                try:
                    relative_path = original_path.relative_to(source_root)
                except ValueError:
                    # Ignorar entradas ajenas a la carpeta que se está moviendo.
                    continue
            else:
                relative_path = Path(original_path.name)

            new_audio_paths.append(str((destination_root / relative_path).resolve()))

        if not new_audio_paths:
            return

        target_new_path = state.get("new_path_for_playing")
        if target_new_path:
            normalized_target = Path(target_new_path).resolve().as_posix().casefold()
            if not any(
                Path(path).resolve().as_posix().casefold() == normalized_target
                for path in new_audio_paths
            ):
                target_new_path = None

        # La playlist se conserva si la operación previa falla o se cancela.
        fb_api.set_muted()
        time.sleep(0.8)
        fb_api.clear_playlist(playlist_id)
        time.sleep(0.2)
        fb_api.reload_and_restore_playlist(
            playlist_id=playlist_id,
            new_paths=new_audio_paths,
            target_file_path=target_new_path,
            position_seconds=state.get("saved_position", 0.0)
        )
        time.sleep(0.8)
        fb_api.set_volume_non_muted(saved_volume)

    except Exception as fb_err:
        print(f"Error sincronizando playlist de Foobar2000 tras cambio de carpeta: {fb_err}")

def _normalize_move_path(path):
    """Normaliza rutas para compararlas sin depender de mayúsculas o separadores."""
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def capture_foobar_file_move_state(foobar_api, old_to_new_paths):
    """
    Guarda el estado de foobar2000 antes de mover archivos seleccionados.

    Si el archivo reproducido está entre los seleccionados, lo deja preparado
    para reanudarlo desde una playlist auxiliar después del movimiento.
    old_to_new_paths relaciona cada ruta de origen con su ruta final prevista.
    """
    state = {
        "fb_api": foobar_api,
        "active_playlist_id": None,
        "playing_playlist_id": None,
        "playing_path": None,
        "new_path": None,
        "saved_position": 0.0,
        "saved_duration": 0.0,
        "saved_playback_state": "stopped",
        "saved_volume": None,
        "saved_is_muted": False,
        "playback_affected": False,
        "auxiliary_playlist_id": None,
        "auxiliary_playlist_title": "auxiliar",
        "player_stopped": False,
    }
    if foobar_api is None:
        return state

    try:
        playlists = foobar_api.playlists()
        current_playlist = next(
            (playlist for playlist in playlists if playlist.get("isCurrent") is True),
            None,
        )
        if current_playlist is not None:
            state["active_playlist_id"] = current_playlist.get("id")

        player_info = foobar_api.player().get("player", {})
        active_item = player_info.get("activeItem") or {}
        volume_info = player_info.get("volume") or {}
        state["saved_playback_state"] = player_info.get("playbackState", "stopped")
        state["saved_position"] = float(active_item.get("position") or 0.0)
        state["saved_duration"] = float(active_item.get("duration") or 0.0)
        state["playing_playlist_id"] = active_item.get("playlistId")
        state["saved_volume"] = volume_info.get("value")
        state["saved_is_muted"] = bool(volume_info.get("isMuted", False))

        playing_path = foobar_api.current_path_playbackState()
        if not playing_path:
            playing_path = foobar_api.current_path()
        state["playing_path"] = playing_path
        if not playing_path:
            return state

        normalized_mapping = {
            _normalize_move_path(old_path): new_path
            for old_path, new_path in old_to_new_paths.items()
        }
        new_path = normalized_mapping.get(_normalize_move_path(playing_path))
        if not new_path:
            return state

        state["playback_affected"] = True
        state["new_path"] = str(new_path)

        # No tocar la playlist original si ya se llama "auxiliar": en ese caso
        # se necesita una lista temporal distinta para conservar su contenido.
        auxiliary = next(
            (
                playlist for playlist in playlists
                if str(playlist.get("title", "")).strip().casefold() == "auxiliar"
            ),
            None,
        )
        if (
            auxiliary is not None
            and str(auxiliary.get("id")) == str(state["active_playlist_id"])
        ):
            state["auxiliary_playlist_title"] = "auxiliar (NumHand playback)"
            auxiliary = next(
                (
                    playlist for playlist in playlists
                    if str(playlist.get("title", "")).strip().casefold()
                    == state["auxiliary_playlist_title"].casefold()
                ),
                None,
            )

        # Detener antes de que el sistema de archivos intente mover el archivo abierto.
        foobar_api.stop()
        state["player_stopped"] = True

        if auxiliary is None:
            created = foobar_api.add_playlist(
                state["auxiliary_playlist_title"],
                set_current=True,
            )
            auxiliary_id = created.get("id")
            if auxiliary_id is None:
                refreshed = foobar_api.playlists()
                auxiliary = next(
                    (
                        playlist for playlist in refreshed
                        if str(playlist.get("title", "")).strip().casefold()
                        == state["auxiliary_playlist_title"].casefold()
                    ),
                    None,
                )
                auxiliary_id = auxiliary.get("id") if auxiliary else None
        else:
            auxiliary_id = auxiliary.get("id")
            foobar_api.select_playlist(auxiliary_id)

        if auxiliary_id is None:
            raise RuntimeError("No se pudo crear o localizar la playlist auxiliar.")

        state["auxiliary_playlist_id"] = auxiliary_id
        foobar_api.clear_playlist(auxiliary_id)

    except Exception as error:
        # El movimiento de archivos no debe quedar bloqueado si Beefweb falla.
        state["capture_error"] = str(error)
        print(f"No se pudo preparar la restauración de playback de foobar2000: {error}")

    return state


def restore_foobar_after_file_move(state, source_folder, successful=True):
    """
    Reanuda el tema afectado desde la playlist auxiliar y sincroniza la playlist
    que estaba activa con los archivos de audio que siguen en la carpeta origen.
    Es reutilizable en futuras operaciones de movimiento.
    """
    if not state or not state.get("fb_api"):
        return

    fb_api = state["fb_api"]
    active_playlist_id = state.get("active_playlist_id")
    auxiliary_playlist_id = state.get("auxiliary_playlist_id")
    volume_restore_pending = False

    if state.get("playback_affected"):
        original_path = state.get("playing_path")
        target_path = state.get("new_path") if successful else original_path
        if not target_path or not Path(target_path).is_file():
            target_path = original_path if original_path and Path(original_path).is_file() else None

        try:
            # Si la preparación inicial falló después de detener el player,
            # recuperar o crear una playlist auxiliar de forma segura aquí.
            playlists = fb_api.playlists()
            if auxiliary_playlist_id is None:
                aux_title = state.get("auxiliary_playlist_title", "auxiliar")
                auxiliary = next(
                    (
                        playlist for playlist in playlists
                        if str(playlist.get("title", "")).strip().casefold()
                        == str(aux_title).casefold()
                        and str(playlist.get("id")) != str(active_playlist_id)
                    ),
                    None,
                )
                if auxiliary is None:
                    created = fb_api.add_playlist(aux_title, set_current=True)
                    auxiliary_playlist_id = created.get("id")
                else:
                    auxiliary_playlist_id = auxiliary.get("id")
                state["auxiliary_playlist_id"] = auxiliary_playlist_id

            if auxiliary_playlist_id is None:
                raise RuntimeError("No se pudo localizar la playlist auxiliar para restaurar playback.")

            if target_path:
                fb_api.select_playlist(auxiliary_playlist_id)
                fb_api.clear_playlist(auxiliary_playlist_id)
                fb_api.add_playlist_items(auxiliary_playlist_id, [str(target_path)])
                time.sleep(0.35)

                fb_api.set_muted()
                volume_restore_pending = True
                fb_api.play_item_single(auxiliary_playlist_id, 0)
                time.sleep(0.45)
                fb_api.pause()

                position = max(0.0, float(state.get("saved_position") or 0.0))
                duration = float(state.get("saved_duration") or 0.0)
                if duration > 0:
                    position = min(position, max(0.0, duration - 0.1))
                fb_api.set_position_single(position)

                fb_api.restore_volume_state(
                    state.get("saved_volume"),
                    state.get("saved_is_muted", False),
                )
                volume_restore_pending = False

                if state.get("saved_playback_state") == "playing":
                    fb_api.play()
            else:
                print("No se encontró la ruta del tema para restaurar playback de foobar2000.")

        except Exception as error:
            print(f"Error al restaurar playback de foobar2000 tras mover archivos: {error}")
        finally:
            if volume_restore_pending:
                try:
                    fb_api.restore_volume_state(
                        state.get("saved_volume"),
                        state.get("saved_is_muted", False),
                    )
                except Exception as volume_error:
                    print(f"No se pudo restaurar el volumen de foobar2000: {volume_error}")

    # Volver a la playlist seleccionada originalmente y reconstruirla solo con
    # los archivos de audio que permanezcan en la carpeta abierta en NumHand.
    if active_playlist_id is None:
        return

    try:
        playlists = fb_api.playlists()
        current_playlist = next(
            (playlist for playlist in playlists if playlist.get("isCurrent") is True),
            None,
        )
        if current_playlist is None or str(current_playlist.get("id")) != str(active_playlist_id):
            fb_api.select_playlist(active_playlist_id)

        source_path = Path(source_folder)
        audio_extensions = {extension.casefold() for extension in EXTENSION_FILES}
        remaining_audio_paths = []
        if source_path.is_dir():
            remaining_audio_paths = [
                str(path.resolve())
                for path in sorted(source_path.iterdir(), key=lambda item: item.name.casefold())
                if path.is_file()
                and path.suffix.casefold() in audio_extensions
                and not path.name.startswith(TEMP_PREFIX)
                and path.name != BACKUP_FILENAME
            ]

        fb_api.clear_playlist(active_playlist_id)
        if remaining_audio_paths:
            fb_api.add_playlist_items(active_playlist_id, remaining_audio_paths)
            time.sleep(min(1.0, 0.25 + len(remaining_audio_paths) * 0.001))
    except Exception as error:
        print(f"No se pudo sincronizar la playlist activa de foobar2000: {error}")

