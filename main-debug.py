from pathlib import Path
import sys
import argparse
import ctypes
import platform
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from winmain import WMain
from pyutils.mutex import SingleInstanceMutex
from pyutils.error_handler import setup_exception_hook

if platform.system() == "Windows":
    my_app_id = 'EtudeTools.NumHand.Numhand.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reordenador numerico de archivos y renombrador")
    parser.add_argument("folder_path", nargs="?", type=str, help="La carpeta a enumerar")
    parser.add_argument(
        "--no-select-playing",
        action="store_true",
        help="No seleccionar automáticamente el archivo que se reproduce en foobar2000",
    )
    
    # Si quieres que coja una ruta fija cuando lo ejecutes sin parámetros (en debug):
    # Simplemente reemplaza r"C:\Tu\Ruta\Fija" por la ruta de prueba que uses habitualmente.
    DEBUG_FOLDER = r"E:\_Internal\2015\12. music\12. b.t.over_the_stars_and_the_flames"
    
    # Comprobamos si se pasaron argumentos por la línea de comandos
    if len(sys.argv) == 1 and DEBUG_FOLDER:
        folder_path_value = DEBUG_FOLDER
    else:
        args = parser.parse_args()
        folder_path_value = args.folder_path

    path_obj = Path(folder_path_value)

    if path_obj.is_dir():
        path_input = str(path_obj)
        initial_file = None
        no_select_playing = False # o args.no_select_playing si manejas flags
    else:
        path_input = str(path_obj.parent)
        initial_file = str(path_obj)
        no_select_playing = True

    APP_DIR = Path(__file__).resolve().parent.as_posix()
    ICON_PATH = f"{APP_DIR}/assets/handicon.png"

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(ICON_PATH))
    setup_exception_hook()

    mutex = SingleInstanceMutex()
    if not mutex.try_lock():
        QMessageBox.warning(
            None,
            "Aplicación ya en ejecución",
            "La aplicación NumHand ya se encuentra ejecutándose."
        )
        sys.exit(0)
    
    # Nota: Asegúrate de adaptar no_select_playing según si usas o no el argumento `--no-select-playing` en debug.
    _wmain = WMain(path_input, select_playing=not no_select_playing)
    _wmain.showMaximized()
    sys.exit(app.exec())