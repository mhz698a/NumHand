import os
from pathlib import Path
import time

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
                foobar_api.clear_playlist(state["saved_playlist_id"])
                
    except Exception:
        pass
    return state

def restore_and_sync_foobar_playlist(state, new_dir, file_entries=None):
    """Reconstruye la playlist con las nuevas rutas de new_dir (tras cambio de carpeta) 
    y reanuda la reproducción localizando el archivo por su nombre sin usar glob/rglob."""
    if not state.get("fb_api") or state.get("saved_playlist_id") is None:
        return
    
    fb_api = state["fb_api"]
    playlist_id = state["saved_playlist_id"]
    saved_volume = state.get("saved_volume")
    
    try:
        audio_extensions = (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".mp4", ".aac", ".opus")
        new_audio_paths = []

        if file_entries:
            for item in file_entries:
                p = Path(item.path if hasattr(item, "path") else item)
                if p.suffix.lower() in audio_extensions:
                    new_p = Path(new_dir) / p.name
                    new_audio_paths.append(str(new_p.resolve()))
        else:
            saved_playing = state.get("saved_file_path") or state.get("new_path_for_playing")
            if saved_playing:
                new_audio_paths.append(str(Path(saved_playing).resolve()))

        if not new_audio_paths:
            return

        # 2. Identificar el archivo activo anterior y deducir su nueva ruta basada en el nombre
        target_new_path = None
        saved_playing_path = state.get("saved_file_path") or state.get("new_path_for_playing")
        
        if state.get("have_been_playing") and saved_playing_path:
            old_filename = Path(saved_playing_path).name
            # Buscar dentro de las nuevas rutas aquella que comparta exactamente el nombre de archivo
            for new_path in new_audio_paths:
                if Path(new_path).name.lower() == old_filename.lower():
                    target_new_path = new_path
                    break

        # 3. Delegar la recarga masiva y el posicionamiento inteligente a la API
        fb_api.set_muted()
        time.sleep(0.8)
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
