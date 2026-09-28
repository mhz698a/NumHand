import uuid
import json
from pathlib import Path
from natsort import natsort_keygen, ns
from pathlib import Path
from PyQt6.QtWidgets import (QFileDialog)

BACKUP_FILENAME = ".__file_manager_backup__.json"

class FileUtils:

    def select_folder(self, parent, model):
        folder = QFileDialog.getExistingDirectory(
            parent, "Seleccionar carpeta"
        )

        if not folder:
            return

        parent.folder = Path(folder)

        # --------------------------------
        # Comprobar backup pendiente
        # --------------------------------

        backup_path = (
            parent.folder
            / BACKUP_FILENAME
        )

        if backup_path.exists():
            print("Se encontró un respaldo pendiente.")
            recovered = self.recover_backup(parent)

            if recovered:
                print("Recuperación completada.")
            else:
                print(
                    "No se pudo completar "
                    "la recuperación."
                )

        # --------------------------------
        # Cargar archivos
        # --------------------------------

        files = [
            file
            for file in parent.folder.iterdir()
            if (
                file.is_file()
                and not file.name.startswith(
                    ".__file_manager__"
                )
            )
        ]

        files.sort(
            key=lambda file: file.name.lower()
        )

        model.set_files(files)
        

    def recover_backup(self, parent):

        backup_path = (
            parent.folder
            / BACKUP_FILENAME
        )

        if not backup_path.exists():
            return True

        # --------------------------------
        # Leer backup
        # --------------------------------

        try:

            with backup_path.open(
                "r",
                encoding="utf-8"
            ) as backup_file:

                backup = json.load(
                    backup_file
                )

        except Exception as error:

            print(
                "No se pudo leer el respaldo:",
                error
            )

            return False

        # --------------------------------
        # Validar backup
        # --------------------------------

        if backup.get("version") != 1:

            print(
                "Versión de respaldo no compatible."
            )

            return False

        files = backup.get(
            "files",
            []
        )

        if not files:

            print(
                "El respaldo no contiene archivos."
            )

            return False

        # --------------------------------
        # FASE 1
        # Determinar dónde está actualmente
        # cada archivo
        # --------------------------------

        recovery_plan = []

        for item in files:

            original_path = Path(
                item["original_path"]
            )

            temporary_path = Path(
                item["temporary_path"]
            )

            final_path = Path(
                item["final_path"]
            )

            current_path = None

            # 1. Todavía está como temporal
            if temporary_path.exists():
                current_path = temporary_path

            # 2. Ya fue renombrado al nombre final
            elif final_path.exists():
                current_path = final_path

            # 3. Ya está en el nombre original
            elif original_path.exists():
                current_path = original_path

            recovery_plan.append({
                "original_path": original_path,
                "temporary_path": temporary_path,
                "final_path": final_path,
                "current_path": current_path
            })

        # --------------------------------
        # Verificar que encontramos
        # todos los archivos
        # --------------------------------

        missing = [
            item
            for item in recovery_plan
            if item["current_path"] is None
        ]

        if missing:

            print(
                "No se pudieron localizar "
                "todos los archivos del respaldo."
            )

            for item in missing:

                print(
                    "No encontrado:",
                    item["original_path"]
                )

            return False

        # --------------------------------
        # FASE 2
        # Llevar todos los archivos a
        # nombres temporales de recuperación
        #
        # Esto evita colisiones entre
        # nombres originales.
        # --------------------------------

        recovery_temp_files = []

        try:

            for item in recovery_plan:

                current_path = (
                    item["current_path"]
                )

                original_path = (
                    item["original_path"]
                )

                # Ya está correctamente recuperado.
                if current_path == original_path:
                    continue

                recovery_name = (
                    ".__file_manager_recovery__"
                    + uuid.uuid4().hex
                    + current_path.suffix
                )

                recovery_path = (
                    parent.folder
                    / recovery_name
                )

                current_path.rename(
                    recovery_path
                )

                recovery_temp_files.append({
                    "recovery_path": recovery_path,
                    "original_path": original_path
                })

            # --------------------------------
            # FASE 3
            # Temporales de recuperación
            # → nombres originales
            # --------------------------------

            for item in recovery_temp_files:
                recovery_path = (item["recovery_path"])
                original_path = (item["original_path"])
                recovery_path.rename(original_path)

            # --------------------------------
            # FASE 4
            # Verificar recuperación
            # --------------------------------

            for item in recovery_plan:
                original_path = (item["original_path"])

                if not original_path.exists():
                    raise RuntimeError(
                        "No se pudo verificar "
                        f"{original_path.name}"
                    )

            # --------------------------------
            # FASE 5
            # Eliminar backup
            # --------------------------------

            backup_path.unlink()

            print("Recuperación completada correctamente.")
            return True

        except Exception as error:
            print("Error durante la recuperación:", error)
            return False
    
    
    def apply_order(self, parent, model):
        if not model.files:
            return

        # --------------------------------
        # Configuración del formato
        # --------------------------------

        total_files = len(model.files)

        if total_files < 100:
            number_format = "{:02d}. "
        elif total_files < 1000:
            number_format = "{:03d}. "
        else:
            number_format = "{:04d}. "

        # --------------------------------
        # FASE 1
        # Crear el plan completo
        # --------------------------------

        temp_files = []

        for index, file in enumerate(
            model.files,
            start=1
        ):

            # Nombre temporal único
            temp_name = (
                ".__file_manager__"
                + uuid.uuid4().hex
                + file.path.suffix
            )

            temp_path = (
                parent.folder
                / temp_name
            )

            # Nombre definitivo
            final_name = (
                number_format.format(index)
                + file.clean_name
            )

            final_path = (
                parent.folder
                / final_name
            )

            temp_files.append({
                "file": file,
                "temp_path": temp_path,
                "final_path": final_path
            })

        # --------------------------------
        # FASE 2
        # Crear backup
        #
        # TODAVÍA NO SE HA MODIFICADO
        # NINGÚN ARCHIVO.
        # --------------------------------

        self.create_backup(
            temp_files, parent
        )

        try:

            # --------------------------------
            # FASE 3
            # Originales → temporales
            # --------------------------------

            for item in temp_files:

                file = item["file"]
                temp_path = item["temp_path"]

                file.path.rename(
                    temp_path
                )

            # --------------------------------
            # FASE 4
            # Temporales → definitivos
            # --------------------------------

            for item in temp_files:

                file = item["file"]
                temp_path = item["temp_path"]
                final_path = item["final_path"]

                temp_path.rename(
                    final_path
                )

                file.path = final_path

            # --------------------------------
            # FASE 5
            # Todo terminó correctamente
            # --------------------------------

            backup_path = (
                parent.folder
                / BACKUP_FILENAME
            )

            if backup_path.exists():
                backup_path.unlink()

            model.layoutChanged.emit()

            print(
                "Renombrado completado correctamente."
            )

        except Exception as error:

            print(
                "Error durante el renombrado:",
                error
            )

            # --------------------------------
            # RECUPERACIÓN
            # --------------------------------

            recovered = (
                self.recover_backup()
            )

            if recovered:
                print("Archivos recuperados correctamente.")
                for file in model.files:
                    file.path = (
                        file.original_path
                    )

            else:

                print(
                    "La recuperación "
                    "no pudo completarse."
                )

            model.layoutChanged.emit()
            raise
    
    
    def create_backup(self, temp_files, parent):
        backup_path = (parent.folder / BACKUP_FILENAME)

        backup = {
            "version": 1,
            "status": "renaming",
            "folder": str(parent.folder),
            "files": []
        }

        for item in temp_files:
            file = item["file"]
            temp_path = item["temp_path"]
            final_path = item["final_path"]

            backup["files"].append({
                "original_name": file.original_name,
                "original_path": str(
                    file.original_path
                ),
                "temporary_name": temp_path.name,
                "temporary_path": str(temp_path),
                "final_name": final_path.name,
                "final_path": str(final_path)
            })

        temp_backup = (parent.folder / (BACKUP_FILENAME + ".tmp"))

        with temp_backup.open("w", encoding="utf-8") as backup_file:

            json.dump(
                backup,
                backup_file,
                indent=4,
                ensure_ascii=False
            )

            backup_file.flush()

        temp_backup.replace(backup_path)

        return backup_path