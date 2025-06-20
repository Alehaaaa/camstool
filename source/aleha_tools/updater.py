import os
import ssl
import json
import maya.cmds as cmds
import urllib.request
import urllib.error
from importlib import reload

# from pprint import pprint

from http.client import responses
from . import funcs, util

reload(funcs)
reload(util)

ssl_context = ssl._create_unverified_context()

REPO = "https://raw.githubusercontent.com/Alehaaaa/camstool/main/"

NO_DATA_ERROR = "<hl>No Data</hl>\nCould not sync with the server."
NO_SERVER_ERROR = "<hl>%s %s</hl>\nCould not sync with the server."


def formatPath(path):
    path = path.replace("/", os.sep)
    path = path.replace("\\", os.sep)
    return path


def download(downloadUrl, saveFile):
    response = urllib.request.urlopen(downloadUrl, context=ssl_context, timeout=60)

    if response is None:
        cmds.warning("Error trying to install.")
        return

    output = open(saveFile, "wb")
    output.write(response.read())
    output.close()
    return output


def install(tool, command=None, file_path=None):
    import os
    import shutil
    import zipfile

    scriptPath = os.path.join(os.environ["MAYA_APP_DIR"], "scripts")
    tmpZipFile = os.path.join(scriptPath, "tmp.zip")

    if os.path.isfile(tmpZipFile):
        os.remove(tmpZipFile)

    if file_path:
        output = shutil.copy(file_path, tmpZipFile)
    else:
        FileUrl = REPO + "/versions/aleha_tools-latest.zip"
        output = download(FileUrl, tmpZipFile)

    if not os.path.isfile(tmpZipFile):
        return cmds.error("Error trying to install.")

    zfobj = zipfile.ZipFile(tmpZipFile)
    fileList = zfobj.namelist()

    if not fileList:
        return cmds.error("Error trying to install.")

    toolsFolder = os.path.join(scriptPath, os.path.dirname(fileList[0]))

    # Remove old tool files
    if os.path.isdir(toolsFolder):
        for filename in os.listdir(toolsFolder):
            f = os.path.join(toolsFolder, filename)
            if ((tool in f) or ("updater" in f)) and (f != "_pref"):
                if os.path.isfile(f):
                    os.remove(f)
                elif os.path.isdir(f):
                    shutil.rmtree(f)

    for name in fileList:
        uncompressed = zfobj.read(name)

        filename = formatPath(os.path.join(scriptPath, name))
        d = os.path.dirname(filename)

        if not os.path.exists(d):
            os.makedirs(d)
        if filename.endswith(os.sep):
            continue

        output = open(filename, "wb")
        output.write(uncompressed)
        output.close()

    zfobj.close()
    if os.path.isfile(tmpZipFile):
        os.remove(tmpZipFile)

    if not file_path:
        add_shelf_button(tool, command)

    return True


def add_shelf_button(tool, command):
    import maya.cmds as cmds
    import maya.mel as mel
    import os

    currentShelf = cmds.tabLayout(mel.eval("$nul=$gShelfTopLevel"), q=1, st=1)

    def find():
        buttons = cmds.shelfLayout(currentShelf, q=True, ca=True)
        if buttons:
            for b in buttons:
                if (
                    cmds.shelfButton(b, exists=True)
                    and cmds.shelfButton(b, q=True, l=True) == tool
                ):
                    return True
        return False

    if not find():
        cmds.shelfButton(
            parent=currentShelf,
            i=os.path.join(
                os.environ["MAYA_APP_DIR"],
                "scripts",
                "aleha_tools",
                "_icons",
                tool + ".svg",
            ),
            label=tool,
            c=command
            or "import aleha_tools." + tool + " as " + tool + ";" + tool + ".show()",
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
            current_version_url, context=ssl_context, timeout=30
        ) as response:
            if response.status != 200:
                error_message = responses.get(response.status, "Unknown Error")
                funcs.make_inViewMessage(
                    NO_SERVER_ERROR % (response.status, error_message)
                )
                return None

            text = response.read().decode("utf-8")
            if not text:
                funcs.make_inViewMessage(NO_DATA_ERROR)
                return None

            return text

    except urllib.error.URLError as e:
        funcs.make_inViewMessage(f"Network error: {e}")
    except TimeoutError:
        funcs.make_inViewMessage("Connection timed out.")
    except Exception as e:
        funcs.make_inViewMessage(f"Unexpected error: {e}")

    return None


def _get_changelog():
    current_version_url = REPO + "release_notes.json"
    try:
        with urllib.request.urlopen(
            current_version_url, context=ssl_context, timeout=30
        ) as response:
            if response.status == 200:
                text = response.read().decode("utf-8")
                if not text:
                    data = {}
                    funcs.make_inViewMessage(NO_DATA_ERROR)
                else:
                    data = json.loads(text)
                return data
            else:
                error_message = responses.get(response.status, "Unknown Error")
                funcs.make_inViewMessage(
                    NO_SERVER_ERROR % (response.status, error_message)
                )
                return None
    except urllib.error.URLError as e:
        funcs.make_inViewMessage(f"Network error: {e}")
        return None
    except TimeoutError:
        funcs.make_inViewMessage("Connection timed out.")
        return None


# Check for Updates
def _check_for_updates(ui, warning=True, force=False):
    installed_verion = ui.VERSION

    latest_version = get_latest_version()
    if not latest_version:
        return

    if not force and installed_verion == latest_version:
        if warning:
            funcs.make_inViewMessage(
                "<hl>" + installed_verion + "</hl>\nYou are up-to-date."
            )
        return

    elif latest_version < installed_verion:
        if warning:
            funcs.make_inViewMessage(
                "You are using an unpublished\nversion <hl>"
                + installed_verion
                + "</hl></div>"
            )

    else:
        changelog = _get_changelog()
        is_blocked = bool(changelog.get("blocked", False))
        if is_blocked:
            if warning:
                funcs.make_inViewMessage(
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
                from importlib import reload
            except ImportError:
                pass
            reload(updater)

            command = "import aleha_tools.cams as cams\ncams.show()"
            if not install(ui.TITLE.lower(), command):
                return

            reload_command = command.replace(
                "\n",
                "\ntry: from importlib import reload\nexcept ImportError: pass\nreload(cams)\n",
            )
            cmds.evalDeferred(reload_command)

            funcs.make_inViewMessage(
                "Update finished successfully\ncurrent version == now <hl>"
                + latest_version
                + "</hl></div>"
            )
            ui.process_prefs(skip_update=False)

        elif update_available == "Skip":
            ui.process_prefs(skip_update=True)
