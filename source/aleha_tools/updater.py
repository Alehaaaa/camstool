import os
import ssl
import json
import shutil
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from http.client import responses

try:
    from importlib import reload
except ImportError:
    pass

try:
    from PySide6.QtCore import QTimer
except ImportError:
    from PySide2.QtCore import QTimer

import maya.cmds as cmds
import maya.mel as mel

from . import funcs, util
from .util import compare_versions
from .base_widgets import QFlatConfirmDialog

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

    total_size = response.getheader("Content-Length")
    total_size = int(total_size) if total_size else 0
    block_size = 8192

    try:
        gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
        if total_size > 0 and gMainProgressBar:
            cmds.progressBar(
                gMainProgressBar,
                edit=True,
                beginProgress=True,
                isInterruptable=False,
                status="Downloading Update...",
                maxValue=total_size,
            )
    except Exception:
        gMainProgressBar = None

    downloaded = 0
    try:
        with open(saveFile, "wb") as output:
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                output.write(buffer)
                if gMainProgressBar and total_size > 0:
                    cmds.progressBar(gMainProgressBar, edit=True, progress=downloaded)
    finally:
        if gMainProgressBar and total_size > 0:
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)

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
            if filename.name != "_prefs":
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

        QFlatConfirmDialog.question(
            None,
            "Success",
            "Added a Button for %s to the current shelf." % tool.title(),
            buttons=QFlatConfirmDialog.Ok,
            highlight=QFlatConfirmDialog.Ok,
        )


def _fetch_repo_file(filename):
    sha = "main"
    if "raw.githubusercontent.com" in REPO:
        parts = str(REPO).split("raw.githubusercontent.com/")[-1].strip("/").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            branch = parts[2] if len(parts) > 2 else "main"
            api_url = "https://api.github.com/repos/%s/%s/commits/%s" % (owner, repo, branch)
            try:
                req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, context=unverified_ssl_context, timeout=10) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        if "sha" in data:
                            sha = data["sha"]
            except Exception:
                pass

    url = REPO.replace("/main/", "/%s/" % sha) + filename
    success, result = _download_text(url)

    if not success and sha != "main":
        success, result = _download_text(REPO + filename)

    return success, result


def _download_text(url):
    try:
        with urllib.request.urlopen(url, context=unverified_ssl_context, timeout=30) as response:
            if response.status == 200:
                text = response.read().decode("utf-8")
                if not text:
                    return False, NO_DATA_ERROR
                return True, text
            else:
                error_message = responses.get(response.status, "Unknown Error")
                return False, NO_SERVER_ERROR % (response.status, error_message)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        return False, "Network error: %s" % reason
    except TimeoutError:
        return False, "Connection timed out."
    except Exception as e:
        return False, "Unexpected error: %s" % e


def get_latest_version():
    success, result = _fetch_repo_file("version")
    if success:
        return True, result.strip()
    return False, result


def _get_changelog():
    success, result = _fetch_repo_file("release_notes.json")
    if success:
        try:
            return True, json.loads(result)
        except Exception:
            return False, "Error parsing changelog data."
    return False, result


# Check for Updates
def _check_for_updates(ui, warning=True, force=False):
    installed_verion = ui.VERSION

    success, latest_version = get_latest_version()
    if not success:
        if warning:
            util.make_inViewMessage(latest_version)
        return

    comp = compare_versions(latest_version, installed_verion)
    if not force:
        if comp == 0:
            if warning:
                util.make_inViewMessage("<hl>" + installed_verion + "</hl>\nYou are up-to-date.")
            return

        elif comp < 0:
            if warning:
                util.make_inViewMessage("You are using an unpublished\nversion <hl>" + installed_verion + "</hl></div>")
            return

    success, changelog = _get_changelog()
    if not success:
        if warning:
            util.make_inViewMessage(changelog)
        return

    is_blocked = bool(changelog.get("blocked", False))
    if is_blocked:
        if warning:
            util.make_inViewMessage(
                "<hl>Updates are blocked</hl>\nPlease wait until the problem is solved.",
                "warning.svg",
            )
        return

    last_release_notes = changelog.get("versions", {}).get(latest_version, [])
    formated_changelog = "\n".join(["- " + line for line in last_release_notes])

    update_available = QFlatConfirmDialog(
        window="Update for " + ui.TITLE,
        title="<b>Version %s available</b><br>(using %s)" % (latest_version, installed_verion),
        message=formated_changelog,
        icon=util.return_icon_path("update.svg"),
        buttons=[
            QFlatConfirmDialog.CustomButton("Install", positive=True, icon=util.return_icon_path("install")),
            QFlatConfirmDialog.CustomButton("Skip", positive=True, icon=util.return_icon_path("skip")),
        ],
        highlight="Install",
        exclusive=False,
        parent=ui,
    )
    update_available.title_label.setWordWrap(False)
    update_available.adjustSize()

    if update_available.confirm():
        funcs.install_userSetup()

        if update_available.clicked_button == "Install":
            from . import updater

            reload(updater)

            command = "import aleha_tools.cams as cams\ncams.show()"
            if not updater.install(ui.TITLE.lower(), command):
                return

            def _post_update():
                import aleha_tools.cams as cams
                from importlib import reload

                reload(cams)
                cams.show()
                QFlatConfirmDialog.question(
                    None,
                    "%s Update" % ui.TITLE,
                    "Update finished successfully to version <b>%s</b>."
                    % latest_version.replace("\n", "").replace("\r", ""),
                    buttons=["Ok"],
                    highlight=False,
                    title="Success",
                )

            QTimer.singleShot(0, _post_update)
            ui.process_prefs(skip_update=False)

        elif update_available.clicked_button == "Skip":
            ui.process_prefs(skip_update=True)
