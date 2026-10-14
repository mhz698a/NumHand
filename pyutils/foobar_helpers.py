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
        "new_path_for_playing": None
    }
    try:
        player_data = foobar_api.player()
        active_item = player_data.get("player", {}).get("activeItem")
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
    except Exception:
        pass
    return state

def restore_and_sync_foobar_playlist(state, old_dir, new_dir):
    """Limpia las rutas viejas de la playlist, agrega las nuevas y restaura la reproducción."""
    if not state["fb_api"] or state["saved_playlist_id"] is None:
        return
    
    fb_api = state["fb_api"]
    playlist_id = state["saved_playlist_id"]
    
    try:
        playlist_items = fb_api.playlist_items(playlist_id, start=0, end=20000, columns=["%path%"])
        indices_to_remove = []
        old_dir_str = str(Path(old_dir).resolve()).lower()

        for idx, pitem in enumerate(playlist_items):
            cols = pitem.get("columns", [])
            if cols:
                item_p_str = Path(cols[0]).resolve().as_posix().lower()
                if item_p_str.startswith(old_dir_str.replace("\\", "/")):
                    indices_to_remove.append(idx)

        if indices_to_remove:
            indices_to_remove.sort(reverse=True)
            fb_api.remove_playlist_items(playlist_id, indices_to_remove)

        new_audio_paths = [
            str(f) for f in Path(new_dir).rglob("*") 
            if f.is_file() and f.suffix.lower() in (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac")
        ]

        if new_audio_paths:
            fb_api.add_playlist_items(playlist_id, new_audio_paths)
            fb_api.sort_playlist(playlist_id, expression="%path%")

        if state["have_been_playing"] and state["new_path_for_playing"]:
            updated_items = fb_api.playlist_items(playlist_id, start=0, end=20000, columns=["%path%"])
            norm_new_playing = Path(state["new_path_for_playing"]).resolve().as_posix().lower()
            
            new_index = None
            for idx, pitem in enumerate(updated_items):
                cols = pitem.get("columns", [])
                if cols and Path(cols[0]).resolve().as_posix().lower() == norm_new_playing:
                    new_index = idx
                    break

            if new_index is not None:
                time.sleep(0.8)
                fb_api.play_item_but_pause(playlist_id, new_index)
                if state["saved_position"] > 0:
                    time.sleep(0.5)
                    fb_api.set_position_but_come(state["saved_position"])

    except Exception as fb_err:
        print(f"Error actualizando playlist de Foobar2000: {fb_err}")