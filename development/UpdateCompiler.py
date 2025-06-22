import maya.cmds as cmds
import maya.mel as mel

import os
import sys
import json
import zipfile
import logging
import shutil
import importlib


class CompileCams:
    def __init__(self, source_path, cams_version=None) -> None:
        if not cams_version:
            import aleha_tools  # type: ignore

            cams_version = aleha_tools.DATA["VERSION"]

        self.cams_version = cams_version

        self.source_path = source_path
        self.destination = r"\\HKEY\temp\from_alejandro\cams_tool"

        self.saved_source_path = os.path.join(self.destination, "source")

        self.zip_file = "aleha_tools-%s.zip"
        self.zip_destination_path = os.path.join(
            self.destination, "versions", self.zip_file % self.cams_version
        )

        self.json_notes = r"\\HKEY\temp\from_alejandro\cams_tool\release_notes.json"

    @staticmethod
    def create_progressbar(mainBar, filename):
        message = "Saving file: %s" % filename

        cmds.progressBar(
            mainBar,
            edit=True,
            beginProgress=True,
            isInterruptable=False,
            status=message,
        )

    @staticmethod
    def prompt_for_notes(version):
        notes = cmds.promptDialog(
            title="Cams Release Notes",
            message="Enter %s release notes:" % version,
            button=["OK", "Cancel"],
            defaultButton="OK",
            cancelButton="Cancel",
            dismissString="Cancel",
        )

        if notes == "OK":
            return cmds.promptDialog(query=True, text=True)

        return False

    def main(self):
        all_notes = self.read_version_notes(self.cams_version, self.json_notes)

        if not all_notes:

            def _load_module(path, name):
                spec = importlib.util.spec_from_file_location(name, path)
                if not spec:
                    raise ImportError(f"No module at '{path}'")
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    raise ImportError(f"Error in '{path}': {e}")
                return module

            def _run_method(module, cls_name, method="main", *args):
                if not hasattr(module, cls_name):
                    raise AttributeError(
                        f"No class '{cls_name}' in '{module.__name__}'"
                    )

                instance = getattr(module, cls_name)(*args)

                if not hasattr(instance, method) or not callable(
                    getattr(instance, method)
                ):
                    raise AttributeError(
                        f"No callable method '{method}' in '{cls_name}'"
                    )
                return getattr(instance, method)()

            path = (
                r"\\HKEY\temp\from_alejandro\cams_tool\development\ChangesCompiler.py"
            )
            name = "generate_changes_cams"
            cls = "CamsToolUpdater"
            method = "run"
            all_notes = _run_method(_load_module(path, name), cls, method)

            logging.info(f"Automatically made the changelog: {str(all_notes)}")
            if sys.platform == "win32":
                os.startfile(self.json_notes)
            """try:
                pass
            except:
                all_notes = []
                while True:
                    notes = self.prompt_for_notes(self.cams_version)
                    if notes:
                        all_notes.append(notes)
                    elif not all_notes:
                        if notes != False:
                            logging.warning("No notes provided. Exiting.")
                        return
                    else:
                        break
                if all_notes:
                    logging.info(f"Version updated to {self.cams_version}.")"""

            if all_notes:
                self.update_release_notes(self.cams_version, all_notes, self.json_notes)
            else:
                logging.info("No notes provided. Exiting.")
                return

        self.zip_directory(self.source_path)

        self.copy_all_files(
            self.source_path,
            os.path.join(self.saved_source_path, os.path.basename(self.source_path)),
        )

        logging.info(
            "Saved Version %s in: %s" % (self.cams_version, self.zip_destination_path)
        )

        cmds.evalDeferred(
            lambda: "from importlib import reload;import aleha_tools.cams as cams;reload(cams); cams.show()",
            lowestPriority=True,
        )

    def read_version_notes(self, version, json_file):
        with open(json_file, "r") as file:
            data = json.load(file)

        return data["versions"].get(version)

    def update_release_notes(self, version, notes, json_file):
        with open(json_file, "r") as file:
            data = json.load(file)

        data["versions"][version] = notes

        ordered_versions = sorted(
            data["versions"].items(), key=lambda x: x[0], reverse=True
        )
        data["versions"] = dict(ordered_versions)

        with open(json_file, "w") as file:
            json.dump(data, file, indent=4)

    def copy_all_files(self, source_path, saved_path):
        # Crear la carpeta de destino si no existe
        if not os.path.exists(saved_path):
            os.makedirs(saved_path)

        for item in os.listdir(source_path):
            src = os.path.join(source_path, item)
            dst = os.path.join(saved_path, item)

            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

    def zip_directory(self, source_path):
        data_file = os.path.join(source_path, "__init__.py")
        if os.path.isfile(data_file):
            version_match = "'VERSION':"

            with open(data_file, "r") as file:
                data = file.read()
                newData = ""
                for line in data.split("\n"):
                    if version_match in line:
                        line = (
                            line.split(version_match)[0]
                            + f"'VERSION': '{self.cams_version}',"
                        )
                    newData += line + "\n"
            with open(data_file, "w") as file:
                file.write(newData)

        mainBar = mel.eval("$tmp = $gMainProgressBar")

        with zipfile.ZipFile(
            self.zip_destination_path, "w", zipfile.ZIP_DEFLATED
        ) as zipf:
            for root, dirs, files in os.walk(source_path):
                for ex in ("_prefs", "__pycache__"):
                    if ex in dirs:
                        dirs.remove(ex)
                for file in files:
                    self.create_progressbar(mainBar, file)

                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, source_path)
                    zipf.write(file_path, arcname=os.path.join("aleha_tools", arc_name))

        with open(os.path.join(self.destination, "version"), "w") as f:
            f.write(self.cams_version)

        latest_path = os.path.join(
            self.destination, "versions", self.zip_file % "latest"
        )
        if os.path.isfile(latest_path):
            os.remove(latest_path)
        shutil.copy(self.zip_destination_path, latest_path)

        cmds.progressBar(mainBar, edit=True, endProgress=True)


if __name__ == "__main__":
    compiler = CompileCams()
    compiler.main()
