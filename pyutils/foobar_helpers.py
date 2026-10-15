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
    normalized = os.path.normcase(
        os.path.normpath(os.path.abspath(os.fspath(path)))
    )
    return normalized.casefold()


def capture_foobar_file_move_state(
    foobar_api,
    old_to_new_paths,
    source_folder=None,
):
    """
    Captura el contexto de foobar2000 antes de un movimiento.

    La playlist activa solo se sincronizará con NumHand cuando el directorio
    del primer elemento de esa playlist coincida con source_folder. Si no
    coincide, la playlist original se conserva intacta; únicamente se usa una
    playlist auxiliar cuando uno de los archivos movidos es el que se reproduce.
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
        "source_folder": str(source_folder) if source_folder is not None else None,
        "playlist_matches_source_folder": False,
        "should_sync_source_playlist": False,
        "playback_state_captured": False,
        "capture_error": None,
    }
    if foobar_api is None:
        return state

    try:
        playlists = foobar_api.playlists()
        current_playlist = next(
            (playlist for playlist in playlists if playlist.get("isCurrent") is True),
            None,
        )
        if current_playlist is None or current_playlist.get("id") is None:
            state["capture_error"] = "No se pudo determinar la playlist activa."
            return state

        active_playlist_id = current_playlist.get("id")
        state["active_playlist_id"] = active_playlist_id

        # Una playlist vacía o un error al consultar su primer elemento no se
        # consideran coincidencia: en ese caso nunca la modificamos.
        if source_folder is not None:
            try:
                first_item_path = foobar_api.first_playlist_item_path(active_playlist_id)
                if first_item_path:
                    first_item_parent = str(Path(first_item_path).parent)
                    state["playlist_matches_source_folder"] = (
                        _normalize_move_path(first_item_parent)
                        == _normalize_move_path(source_folder)
                    )
            except Exception as playlist_error:
                state["playlist_match_error"] = str(playlist_error)

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
        state["playback_state_captured"] = True
        # No sincronizar si no se pudo leer el estado completo del reproductor:
        # en ese caso no podemos descartar que la pista activa vaya a moverse.
        state["should_sync_source_playlist"] = bool(
            state["playlist_matches_source_folder"]
        )
        if not playing_path:
            return state

        normalized_mapping = {
            _normalize_move_path(old_path): str(new_path)
            for old_path, new_path in old_to_new_paths.items()
        }
        new_path = normalized_mapping.get(_normalize_move_path(playing_path))
        if not new_path:
            # No hay ninguna canción afectada. No enviamos órdenes de playback.
            return state

        state["playback_affected"] = True
        state["new_path"] = new_path

        # Detener solo si el archivo que se mueve es el que está reproduciéndose.
        foobar_api.stop()
        state["player_stopped"] = True
        time.sleep(0.5)

        # No limpiar nunca la playlist original, incluso si su título es
        # "auxiliar". En ese caso se usa una lista temporal con otro nombre.
        auxiliary = next(
            (
                playlist for playlist in playlists
                if str(playlist.get("title", "")).strip().casefold() == "auxiliar"
            ),
            None,
        )
        if (
            auxiliary is not None
            and str(auxiliary.get("id")) == str(active_playlist_id)
        ):
            state["auxiliary_playlist_title"] = "auxiliar (NumHand playback)"
            auxiliary = next(
                (
                    playlist for playlist in playlists
                    if str(playlist.get("title", "")).strip().casefold()
                    == state["auxiliary_playlist_title"].casefold()
                    and str(playlist.get("id")) != str(active_playlist_id)
                ),
                None,
            )

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
                        and str(playlist.get("id")) != str(active_playlist_id)
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
        # No bloqueamos el movimiento por una excepción de Beefweb. Si el
        # playback ya fue detenido, el estado parcial permite intentar restaurarlo.
        state["capture_error"] = str(error)
        print(f"No se pudo preparar la restauración de playback de foobar2000: {error}")

    return state


def restore_foobar_after_file_move(state, source_folder, successful=True):
    """
    Restaura playback si se movió la canción activa y sincroniza la playlist
    original únicamente cuando esta corresponde a la carpeta de NumHand.
    """
    if not state or not state.get("fb_api"):
        return

    fb_api = state["fb_api"]
    active_playlist_id = state.get("active_playlist_id")
    auxiliary_playlist_id = state.get("auxiliary_playlist_id")
    playback_affected = bool(state.get("playback_affected"))
    should_sync_source_playlist = bool(state.get("should_sync_source_playlist"))

    # Si la playlist abierta en foobar2000 pertenece a otra carpeta y no se
    # movió la canción activa, no enviamos ningún POST a foobar2000.
    if not playback_affected and not should_sync_source_playlist:
        return

    playback_restored_successfully = False
    if playback_affected:
        original_path = state.get("playing_path")
        target_path = state.get("new_path") if successful else original_path
        if not target_path or not Path(target_path).is_file():
            target_path = (
                original_path
                if original_path and Path(original_path).is_file()
                else None
            )

        volume_restore_pending = False
        try:
            if target_path:
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
                    raise RuntimeError(
                        "No se pudo localizar la playlist auxiliar para restaurar playback."
                    )

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
                playback_restored_successfully = True
            else:
                print(
                    "No se encontró una ruta válida para restaurar la canción "
                    "de foobar2000 después del movimiento."
                )

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

    # Volver a seleccionar la playlist anterior. Si no pertenece a la carpeta
    # abierta en NumHand, se preserva su contenido y no se reconstruye.
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

        if not should_sync_source_playlist:
            return
        if playback_affected and not playback_restored_successfully:
            print(
                "Se omitió la sincronización de la playlist original porque no "
                "se pudo confirmar la restauración segura del playback."
            )
            return

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

        old_timeout = fb_api.timeout
        fb_api.timeout = max(3.0, 3.0 + len(remaining_audio_paths) * 0.099)
        try:
            fb_api.clear_playlist(active_playlist_id)
            if remaining_audio_paths:
                fb_api.add_playlist_items(active_playlist_id, remaining_audio_paths)
                time.sleep(0.8 + len(remaining_audio_paths) * 0.001)
        finally:
            fb_api.timeout = old_timeout
    except Exception as error:
        print(f"No se pudo sincronizar la playlist de foobar2000: {error}")
