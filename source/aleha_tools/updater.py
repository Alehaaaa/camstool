import os
import ssl
import json
import shutil
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from http.client import responses
from importlib import reload

import maya.cmds as cmds
import maya.mel as mel

from . import funcs, util

# Constants
REPO = "https://raw.githubusercontent.com/Alehaaaa/camstool/main/"
NO_DATA_ERROR = "<hl>No Data</hl>\nCould not sync with the server."
NO_SERVER_ERROR = "<hl>%s %s</hl>\nCould not sync with the server."

# SSL Context
unverified_ssl_context = ssl.create_default_context()
unverified_ssl_context.check_hostname = False
unverified_ssl_context.verify_mode = ssl.CERT_NONE


def formatPath(path):
    path = str(path).replace("/", os.sep)
    path = path.replace("\\", os.sep)
    return path


def download(downloadUrl, saveFile):
    response = urllib.request.urlopen(downloadUrl, context=unverified_ssl_context, timeout=60)

    if response is None:
        cmds.warning("Error trying to install.")
        return

    with open(saveFile, "wb") as output:
        output.write(response.read())

    return True


def install(tool, command=None, file_path=None):
    scriptPath = Path(os.environ["MAYA_APP_DIR"]) / "scripts"
    tmpZipFile = scriptPath / "tmp.zip"

    if tmpZipFile.is_file():
        tmpZipFile.unlink()

    if file_path:
        shutil.copy(file_path, tmpZipFile)
    else:
        FileUrl = REPO + "/versions/aleha_tools-latest.zip"
        download(FileUrl, tmpZipFile)

    if not tmpZipFile.is_file():
        return cmds.error("Error trying to install.")

    zfobj = zipfile.ZipFile(tmpZipFile)
    fileList = zfobj.namelist()

    if not fileList:
        return cmds.error("Error trying to install.")

    toolsFolder = scriptPath / Path(fileList[0]).parts[0]

    # Remove old tool files
    if toolsFolder.is_dir():
        for filename in toolsFolder.iterdir():
            if ((tool in filename.name) or ("updater" in filename.name)) and (filename.name != "_pref"):
                if filename.is_file():
                    filename.unlink()
                elif filename.is_dir():
                    shutil.rmtree(filename)

    for name in fileList:
        uncompressed = zfobj.read(name)

        filename = scriptPath / name
        d = filename.parent

        if not d.exists():
            d.mkdir(parents=True)
        if str(filename).endswith(os.sep):
            continue

        with open(filename, "wb") as output:
            output.write(uncompressed)

    zfobj.close()
    if tmpZipFile.is_file():
        tmpZipFile.unlink()

    if not file_path:
        add_shelf_button(tool, command)

    return True


def add_shelf_button(tool, command):
    currentShelf = cmds.tabLayout(mel.eval("$nul=$gShelfTopLevel"), q=1, st=1)

    def find():
        buttons = cmds.shelfLayout(currentShelf, q=True, ca=True)
        if buttons:
            for b in buttons:
                if cmds.shelfButton(b, exists=True) and cmds.shelfButton(b, q=True, l=True) == tool:
                    return True
        return False

    if not find():
        icon_path = Path(os.environ["MAYA_APP_DIR"]) / "scripts" / "aleha_tools" / "_icons" / (tool + ".svg")
        cmds.shelfButton(
            parent=currentShelf,
            i=str(icon_path),
            label=tool,
            c=command or "import aleha_tools." + tool + " as " + tool + ";" + tool + ".show()",
            annotation=tool.title() + " by Aleha",
        )
        cmds.confirmDialog(
            title="Added Shelf Button",
            message="Added a Button for " + tool.title() + " to the current shelf.",
            button=["Ok"],
            defaultButton="Ok",
        )


def get_latest_version():
    current_version_url = REPO + "version"
    try:
        with urllib.request.urlopen(
            current_version_url, context=unverified_ssl_context, timeout=30
        ) as response:
            if response.status != 200:
                error_message = responses.get(response.status, "Unknown Error")
                util.make_inViewMessage(NO_SERVER_ERROR % (response.status, error_message))
                return None

            text = response.read().decode("utf-8")
            if not text:
                util.make_inViewMessage(NO_DATA_ERROR)
                return None

            return text

    except urllib.error.URLError as e:
        util.make_inViewMessage("Network error: %s" % e)
    except TimeoutError:
        util.make_inViewMessage("Connection timed out.")
    except Exception as e:
        util.make_inViewMessage("Unexpected error: %s" % e)

    return None


def _get_changelog():
    current_version_url = REPO + "release_notes.json"
    try:
        with urllib.request.urlopen(
            current_version_url, context=unverified_ssl_context, timeout=30
        ) as response:
            if response.status == 200:
                text = response.read().decode("utf-8")
                if not text:
                    data = {}
                    util.make_inViewMessage(NO_DATA_ERROR)
                else:
                    data = json.loads(text)
                return data
            else:
                error_message = responses.get(response.status, "Unknown Error")
                util.make_inViewMessage(NO_SERVER_ERROR % (response.status, error_message))
                return None
    except urllib.error.URLError as e:
        util.make_inViewMessage("Network error: %s" % e)
        return None
    except TimeoutError:
        util.make_inViewMessage("Connection timed out.")
        return None


# Check for Updates
def _check_for_updates(ui, warning=True, force=False):
    installed_verion = ui.VERSION

    latest_version = get_latest_version()
    if not latest_version:
        return

    if not force and installed_verion == latest_version:
        if warning:
            util.make_inViewMessage("<hl>" + installed_verion + "</hl>\nYou are up-to-date.")
        return

    elif latest_version < installed_verion:
        if warning:
            util.make_inViewMessage(
                "You are using an unpublished\nversion <hl>" + installed_verion + "</hl></div>"
            )

    else:
        changelog = _get_changelog()
        is_blocked = bool(changelog.get("blocked", False))
        if is_blocked:
            if warning:
                util.make_inViewMessage(
                    "<hl>Updates are blocked</hl>\nPlease wait until the problem == solved.",
                    "warning",
                )
            return

        last_release_notes = changelog["versions"][latest_version]
        formated_changelog = "\n".join(["- " + line for line in last_release_notes])

        funcs.install_userSetup()

        update_available = cmds.confirmDialog(
            title="New update for " + ui.TITLE + "!",
            message="Version %s available, you are using %s\n\n%s"
            % (latest_version, installed_verion, formated_changelog),
            messageAlign="center",
            button=["Install", "Skip", "Close"],
            defaultButton="Install",
            cancelButton="Close",
        )
        if update_available == "Install":
            from . import updater

            try:
                reload(updater)
            except ImportError:
                pass

            command = "import aleha_tools.cams as cams\ncams.show()"
            if not install(ui.TITLE.lower(), command):
                return

            reload_command = command.replace(
                "\n",
                "\ntry: from importlib import reload\nexcept ImportError: pass\nreload(cams)\n",
            )
            cmds.evalDeferred(reload_command)

            cmds.evalDeferred(
                'from aleha_tools import util\nutil.make_inViewMessage("Update finished successfully<hl>'
                + latest_version
                + "</hl></div>)",
                lowestPriority=True,
            )
            ui.process_prefs(skip_update=False)

        elif update_available == "Skip":
            ui.process_prefs(skip_update=True)
