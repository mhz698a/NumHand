from pathlib import Path
import sys
import argparse
import ctypes
import platform
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from winmain import WMain

if platform.system() == "Windows":
    my_app_id = 'EtudeTools.NumHand.Numhand.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reordenador numerico de archivos y renombrador")
    parser.add_argument("folder_path", type=str, help="La carpeta a enumerar")
    parser.add_argument(
        "--no-select-playing",
        action="store_true",
        help="No seleccionar automáticamente el archivo que se reproduce en foobar2000",
    )
    args = parser.parse_args()

    folder_path_into = args.folder_path
    path_obj = Path(args.folder_path)

    if path_obj.is_dir():
        path_input = str(path_obj)
    else:
        path_input = str(path_obj.parent)

    APP_DIR = Path(__file__).resolve().parent.as_posix()
    ICON_PATH = f"{APP_DIR}/assets/handicon.png"

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(ICON_PATH))
    _wmain = WMain(path_input, select_playing=not args.no_select_playing)
    _wmain.show()
    sys.exit(app.exec())
