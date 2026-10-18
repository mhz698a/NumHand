import uuid
import re
import time
import ntpath
import os
from pathlib import Path
import webbrowser
from PyQt6.QtCore import QRunnable, pyqtSlot

from wutils_sysfiles import rename_with_retry
from wconst import BACKUP_FILENAME, TEMP_PREFIX
from sysutils import WorkerSignals
from pyutils.foobar2000_api import Foobar2000Api


def build_apply_order_listfiles(files, folder_path, number_format):
    """Return only entries whose final path differs from their current path."""
    folder_path = Path(folder_path)
    plan = []
    for index, file in enumerate(files, start=1):
        final_path = folder_path / (number_format.format(index) + file.clean_name)
        if final_path != file.path:
            plan.append({
                "file": file,
                "temp_path": folder_path / (TEMP_PREFIX + uuid.uuid4().hex + file.path.suffix),
                "final_path": final_path,
            })
    return plan


class ApplyOrderTask(QRunnable):
    def __init__(self, folder_path, files, file_utils, integrate_foobar=True):
        super().__init__()
        self.folder_path = Path(folder_path)
        self.files = files
        self.file_utils = file_utils
        self.integrate_foobar = integrate_foobar
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            total_files = len(self.files)
            if total_files == 0:
                self.signals.finished.emit(True)
                return

            if total_files < 100:
                number_format = "{:02d}. "
            elif total_files < 1000:
                number_format = "{:03d}. "
            else:
                number_format = "{:04d}. "

            temp_files = build_apply_order_listfiles(
                self.files, self.folder_path, number_format
            )
            if not temp_files:
                self.signals.finished.emit(True)
                return

            # --- 1. PRE-VERIFICACIÓN Y ESTADO DE FOOBAR2000 ---
            fb_api = None
            have_been_playing = False
            saved_playlist_id = None
            saved_position = 0.0
            playing_path = None
            new_path_for_playing = None

            if self.integrate_foobar:
                try:
                    fb_api = Foobar2000Api()
                    player_data = fb_api.player()
                    player_info = player_data.get("player", {})
                    active_item = player_info.get("activeItem")
                    
                    if active_item:
                        saved_playlist_id = active_item.get("playlistId")
                        saved_position = active_item.get("position", 0.0)
                        playing_path = fb_api.current_path()
                except Exception:
                    # Si foobar2000 no está abierto o no responde, se continúa sin interrumpir el renombrado
                    fb_api = None

            # Mapeo de archivos que van a cambiar (old_path -> new_path)
            target_changes = {}
            for item in temp_files:
                old_str = os.fspath(item["file"].path)
                new_str = os.fspath(item["final_path"])
                target_changes[ntpath.normcase(ntpath.normpath(old_str))] = new_str

            # Detectar si la canción en reproducción actual será modificada
            if playing_path and saved_playlist_id is not None:
                norm_playing = ntpath.normcase(ntpath.normpath(playing_path))
                if norm_playing in target_changes:
                    have_been_playing = True
                    new_path_for_playing = target_changes[norm_playing]
                    if fb_api:
                        try:
                            fb_api.stop()  # Detener playback para liberar el bloqueo de archivo en Windows
                        except Exception:
                            pass

            # FASE 1/4: Respaldo
            def backup_cb(idx, total, orig_name):
                self.signals.progress.emit(
                    idx,
                    total,
                    f"Calculando hash y respaldando {idx}/{total}: {orig_name}",
                    1,
                    4,
                    "Respaldo (Etapa 1 de 4)"
                )

            self.file_utils.create_backup_sync(temp_files, self.folder_path, progress_callback=backup_cb)

            # FASE 2/4: Originales -> Temporales
            for idx, item in enumerate(temp_files, start=1):
                item["file"].path.rename(item["temp_path"])
                self.signals.progress.emit(
                    idx,
                    total_files,
                    f"Paso 1/2: renombrando {idx}/{total_files}",
                    2,
                    4,
                    "Renombrando a nombres temporales (Etapa 2 de 4)"
                )

            # FASE 3/4: Temporales -> Definitivos
            for idx, item in enumerate(temp_files, start=1):
                temp_path = item["temp_path"]
                final_path = item["final_path"]
                rename_with_retry(temp_path, final_path, max_attempts=10, delay=3.0)
                item["file"].path = final_path
                item["file"].clean_name = re.sub(r"^\d+(?:_|\.\s*)", "", final_path.name)
                self.signals.progress.emit(
                    idx,
                    total_files,
                    f"Paso 2/2: aplicando numeración {idx}/{total_files}",
                    3,
                    4,
                    "Aplicando numeración final (Etapa 3 de 4)"
                )

            # FASE 4/4: Eliminar backup
            self.signals.progress.emit(
                1,
                1,
                "Eliminando archivo de respaldo...",
                4,
                4,
                "Finalizando operación (Etapa 4 de 4)"
            )
            backup_path = self.folder_path / BACKUP_FILENAME
            if backup_path.exists():
                backup_path.unlink()

            # --- 2. SINCRONIZACIÓN POST-RENOMBRADO CON FOOBAR2000 ---
            if fb_api and saved_playlist_id is not None and target_changes:
                try:
                    # Obtener ítems actuales de la playlist activa
                    playlist_items = fb_api.playlist_items(saved_playlist_id, start=0, end=20000, columns=["%path%"])
                    
                    indices_to_remove = []
                    for idx, pitem in enumerate(playlist_items):
                        cols = pitem.get("columns", [])
                        if cols:
                            norm_item_path = ntpath.normcase(ntpath.normpath(cols[0]))
                            if norm_item_path in target_changes:
                                indices_to_remove.append(idx)

                    # Eliminar índices de mayor a menor para evitar desplazamientos incorrectos
                    if indices_to_remove:
                        indices_to_remove.sort(reverse=True)
                        fb_api.remove_playlist_items(saved_playlist_id, indices_to_remove)

                    # Agregar las nuevas rutas físicas
                    new_paths_to_add = list(target_changes.values())
                    if new_paths_to_add:
                        fb_api.add_playlist_items(saved_playlist_id, new_paths_to_add)

                    # Ordenar la playlist alfabéticamente / numéricamente por ruta
                    fb_api.sort_playlist(saved_playlist_id, expression="%path%")

                    # Reanudar reproducción y posición si estaba sonando un archivo modificado
                    if have_been_playing and new_path_for_playing:
                        updated_items = fb_api.playlist_items(saved_playlist_id, start=0, end=20000, columns=["%path%"])
                        norm_new_playing = ntpath.normcase(ntpath.normpath(new_path_for_playing))
                        
                        new_index = None
                        for idx, pitem in enumerate(updated_items):
                            cols = pitem.get("columns", [])
                            if cols and ntpath.normcase(ntpath.normpath(cols[0])) == norm_new_playing:
                                new_index = idx
                                break
                                                
                        if new_index is not None:
                            fb_api.play_item_but_pause(saved_playlist_id, new_index)
                            if saved_position > 0:
                                time.sleep(0.5)  # Breve pausa para asegurar que el reproductor inicie antes del seek
                                fb_api.set_position_but_come(saved_position)

                except Exception as fb_err:
                    print(f"Error al actualizar la playlist en foobar2000: {fb_err}")

            self.signals.finished.emit(True)
        except Exception as error:
            # Recuperación en caso de fallo general de archivos
            recovered = self.file_utils.recover_backup_sync(self.folder_path)
            if recovered:
                for file in self.files:
                    file.path = file.original_path
            self.signals.error.emit(f"Error durante el renombrado: {error}")