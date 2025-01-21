import maya.cmds as cmds
import os
import shutil
import zipfile

class Installer:

    def install(self, tool='cams', file_path=r"\\HKEY\temp\from_alejandro\cams_tool"):
        mayaPath = os.environ["MAYA_APP_DIR"]
        scriptPath = mayaPath + os.sep + "scripts"
        toolsFolder = scriptPath + os.sep + "aleha_tools" + os.sep
        tmpZipFile = f"{scriptPath}{os.sep}tmp.zip"

        old_files = [f"{tool}_pyside2.py", f"{tool}_pyside2.pyc"]

        for file in old_files:
            if os.path.isfile(f"{scriptPath}{os.sep}{file}"):
                os.remove(f"{scriptPath}{os.sep}{file}")

        if os.path.isfile(tmpZipFile):
            os.remove(tmpZipFile)
        
        if not os.path.isdir(toolsFolder):
            os.mkdir(toolsFolder)

        # Remove old tool files
        for filename in os.listdir(toolsFolder):
            if filename == "_prefs":
                continue
            f = os.path.join(toolsFolder, filename)
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

        versions_folder = os.path.join(file_path, "versions")
        latest_file = [v for v in os.listdir(versions_folder)][-1]
        latest_file_path = os.path.join(versions_folder, latest_file)

        shutil.copy(latest_file_path, tmpZipFile)

        with zipfile.ZipFile(tmpZipFile) as zfobj:
            files = [f for f in zfobj.namelist() if "_pref" not in f]

            for name in files:
                uncompressed = zfobj.read(name)
                filename = os.path.join(scriptPath, name)

                if os.path.isdir(filename):
                    continue
                d = os.path.dirname(filename)

                if not os.path.exists(d):
                    os.mkdir(d)

                with open(filename, "wb") as output:
                    output.write(uncompressed)

        if os.path.isfile(tmpZipFile):
            os.remove(tmpZipFile)

        cmds.evalDeferred("""
import aleha_tools.cams as cams
try: from importlib import reload
except: pass
reload(cams)
cams.show()
""")


def onMayaDroppedPythonFile(filePath):
    """
    Function called when the script is dragged and dropped into the Maya viewport.
    Maya passes the file path of the dropped script as an argument.
    """

    import sys
    if 'install_cams' in sys.modules:
        import importlib
        importlib.reload(sys.modules['install_cams'])
        
    installer = Installer()
    installer.install()
    cmds.inViewMessage(amg="Tool successfully installed and loaded!", pos="topCenter", fade=True)
