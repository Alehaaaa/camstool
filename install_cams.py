import maya.cmds as cmds
import maya.mel as mel
import os
import shutil
import zipfile
import urllib.request
import urllib.error
import importlib
import traceback


class Installer:
    def install(
        self,
        tool="cams",
        url="https://raw.githubusercontent.com/Alehaaaa/camstool/main/versions/aleha_tools-latest.zip",
    ):
        """
        Downloads and installs the tool from the given URL using Maya's progress bar.
        Assumes the ZIP file contains a top-level 'aleha_tools' folder.

        Args:
            tool (str): The base name of the tool (used for cleaning old files).
            url (str): The direct download URL for the tool's ZIP archive.
        """
        # --- Progress Bar Setup ---
        gMainProgressBar = None
        try:
            gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
        except Exception:
            gMainProgressBar = None

        # Define progress steps
        max_progress = 10
        current_step = 0

        if gMainProgressBar:
            cmds.progressBar(
                gMainProgressBar,
                edit=True,
                beginProgress=True,
                isInterruptable=True,
                status="Starting Installation...",
                maxValue=max_progress,
            )
        else:
            print("Starting Installation...")

        mayaPath = os.environ.get("MAYA_APP_DIR")
        if not mayaPath or not os.path.isdir(mayaPath):
            cmds.error("Fatal: Could not determine MAYA_APP_DIR or path does not exist.")

        scriptPath = os.path.join(mayaPath, "scripts")
        toolsFolder = os.path.join(scriptPath, "aleha_tools")
        tmpZipFile = os.path.join(scriptPath, "tmp_install_aleha_tools.zip")

        try:  # Main try block for installation logic
            # --- Environment and Path Setup (Step 1) ---
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return  # Check for cancellation
            current_step += 1
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    step=1,
                    status="Checking Maya environment...",
                )
            else:
                print("Checking Maya environment...")

            # --- Clean up old specific files (Step 2) ---
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return
            current_step += 1
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    step=1,
                    status="Cleaning old tool files...",
                )
            else:
                print("Cleaning old tool files...")

            old_files = ["%s_pyside2.py" % tool, "%s_pyside2.pyc" % tool]
            for file_name in old_files:
                file_path = os.path.join(scriptPath, file_name)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        cmds.warning("Could not remove old file %s: %s" % (file_path, e))

            # --- Clean up temporary download file (Step 3) ---
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return
            current_step += 1
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    step=1,
                    status="Cleaning temporary files...",
                )
            else:
                print("Cleaning temporary files...")

            if os.path.isfile(tmpZipFile):
                try:
                    os.remove(tmpZipFile)
                except OSError as e:
                    cmds.warning("Could not remove existing temporary file %s: %s" % (tmpZipFile, e))

            # --- Clean up target tools folder (Step 4) ---
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return
            current_step += 1
            status_msg = "Cleaning target folder: %s..." % os.path.basename(toolsFolder)
            if gMainProgressBar:
                cmds.progressBar(gMainProgressBar, edit=True, step=1, status=status_msg)
            else:
                print(status_msg)

            if os.path.isdir(toolsFolder):
                for filename in os.listdir(toolsFolder):
                    if filename.lower() == "_prefs":
                        continue  # Skip prefs
                    item_path = os.path.join(toolsFolder, filename)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception as e:
                        cmds.warning("Could not remove item %s: %s" % (item_path, e))

            # --- Download (Step 5) ---
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return
            current_step += 1
            status_msg = "Downloading tool from %s..." % url
            if gMainProgressBar:
                cmds.progressBar(gMainProgressBar, edit=True, step=1, status=status_msg)
            else:
                print(status_msg)

            total_size = 0
            downloaded_size = 0

            try:
                request = urllib.request.Request(url)
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status == 200:
                        total_size_header = response.headers.get("Content-Length")
                        total_size = int(total_size_header) if total_size_header else 0

                        chunk_size = 8192
                        with open(tmpZipFile, "wb") as f:
                            while True:
                                chunk = response.read(chunk_size)
                                if not chunk:
                                    break

                                if gMainProgressBar and cmds.progressBar(
                                    gMainProgressBar, query=True, isCancelled=True
                                ):
                                    cmds.warning("Download cancelled by user.")
                                    f.close()
                                    if os.path.exists(tmpZipFile):
                                        os.remove(tmpZipFile)
                                    return

                                f.write(chunk)
                                downloaded_size += len(chunk)

                                if total_size > 0 and gMainProgressBar:
                                    progress_percent = int(100 * downloaded_size / total_size)
                                    current_progress_value = current_step + (progress_percent / 100.0)
                                    cmds.progressBar(
                                        gMainProgressBar,
                                        edit=True,
                                        progress=int(current_progress_value),
                                        status="Downloading... %s%%" % progress_percent,
                                    )
                                elif total_size == 0 and gMainProgressBar:
                                    cmds.progressBar(
                                        gMainProgressBar,
                                        edit=True,
                                        status="Downloading... %s KB" % (downloaded_size // 1024),
                                    )
                    else:
                        raise RuntimeError(
                            "Network error during download (HTTP Status: %s) from %s" % (response.status, url)
                        )

            except urllib.error.URLError as e:
                raise RuntimeError("Network error during download from %s: %s" % (url, e))
            except TimeoutError:
                raise RuntimeError("Network timeout during download from %s" % url)
            except Exception as e:
                raise RuntimeError("An unexpected error occurred during download: %s" % e)

            # Download complete (Step 6)
            current_step += 1
            status_msg = "Download complete (%s KB)." % (downloaded_size // 1024)
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    progress=current_step,
                    status=status_msg,
                )
            else:
                print(status_msg)

            # Extract (Step 7)
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return
            current_step += 1
            status_msg = "Extracting files to %s..." % os.path.basename(scriptPath)
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    progress=current_step,
                    status=status_msg,
                )
            else:
                print(status_msg)

            try:
                with zipfile.ZipFile(tmpZipFile, "r") as zfobj:
                    members_to_extract = []
                    for member_info in zfobj.infolist():
                        path_parts = member_info.filename.lower().split(os.sep)
                        if not member_info.is_dir() and "_prefs" not in path_parts:
                            members_to_extract.append(member_info.filename)

                    if not members_to_extract:
                        cmds.warning("No files found in the zip archive to extract (after filtering).")

                    zfobj.extractall(path=scriptPath, members=members_to_extract)

            except zipfile.BadZipFile:
                file_size = os.path.getsize(tmpZipFile) if os.path.exists(tmpZipFile) else 0
                raise RuntimeError(
                    "Downloaded file (%s, size: %s bytes) is not a valid ZIP archive."
                    % (tmpZipFile, file_size)
                )
            except (OSError, IOError) as e:
                raise RuntimeError("File system error during extraction: %s" % e)

            # Extraction complete (Step 8)
            current_step += 1
            status_msg = "Extraction complete (%s items)." % len(members_to_extract)
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    progress=current_step,
                    status=status_msg,
                )
            else:
                print(status_msg)

            # Load Tool (Step 9)
            if gMainProgressBar and cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                return
            current_step += 1
            status_msg = "Preparing to load tool..."
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    progress=current_step,
                    status=status_msg,
                )
            else:
                print(status_msg)

            cmds.evalDeferred(
                """
import sys
import os
import importlib
import traceback
import maya.cmds as cmds # Need cmds inside deferred for messages

# --- Define paths again within deferred execution context ---
mayaPath_deferred = os.environ.get("MAYA_APP_DIR")
scriptPath_deferred = os.path.join(mayaPath_deferred, "scripts") if mayaPath_deferred else None
toolsFolder_deferred = os.path.join(scriptPath_deferred, "aleha_tools") if scriptPath_deferred else None

print("Deferred execution: Loading tool...") # Print inside deferred

if toolsFolder_deferred and os.path.isdir(toolsFolder_deferred) and toolsFolder_deferred not in sys.path:
    print("Deferred: Adding %s to sys.path" % toolsFolder_deferred)
    sys.path.insert(0, toolsFolder_deferred)

module_name = 'aleha_tools.cams'
final_message = "Tool installation complete. Loading tool now..." # Default message

try:
    print("Deferred: Importing/reloading %s" % module_name)
    if module_name in sys.modules:
        cams_module = importlib.reload(sys.modules[module_name])
    else:
        if 'aleha_tools' not in sys.modules and toolsFolder_deferred:
             print("Deferred: Importing parent package 'aleha_tools'")
             __import__('aleha_tools')
        print("Deferred: Importing specific module: %s" % module_name)
        __import__(module_name)
        cams_module = sys.modules[module_name]

    cams_module.welcome()
    print("Deferred: Tool loaded successfully.")
    final_message = "<hl>Cams</hl> Tool successfully installed and loaded!"
    cmds.inViewMessage(amg=final_message, pos="midCenter", fade=True)

except ImportError as e:
    print("Deferred Error: Could not import tool module '%s': %s" % (module_name, e))
    print("Deferred sys.path: %s" % sys.path)
    traceback.print_exc()
    final_message = "Installation complete, but failed to import tool: %s. See Script Editor." % module_name
    cmds.error("Failed to import tool: %s. Check script editor for details." % module_name)
except AttributeError as e:
    print("Deferred Error: Could not find 'welcome' function in '%s': %s" % (module_name, e))
    traceback.print_exc()
    final_message = "Installation complete, but failed to find 'welcome' function in tool: %s." % module_name
    cmds.error("Failed to find 'welcome' function in tool: %s." % module_name)
except Exception as e:
    print("Deferred Error: An unexpected error occurred loading tool: %s" % e)
    traceback.print_exc()
    final_message = "Installation complete, but an unexpected error occurred loading tool. See Script Editor."
    cmds.error("An unexpected error occurred loading tool: %s" % e)

""",
                lowestPriority=True,
            )

            """# Step 11: Installing userScript
            userSetupFile = os.path.join(scriptPath, "userSetup.py")
            newUserSetup = ""
            startCode, endCode = "# start Cams", "# end Cams"

            try:
                with open(userSetupFile, 'r') as input_file:
                    lines = input_file.readlines()

                    # Remove existing block between startCode and endCode
                    inside_block = False
                    for line in lines:
                        if line.strip() == startCode:
                            inside_block = True
                        if not inside_block:
                            newUserSetup += line
                        if line.strip() == endCode:
                            inside_block = False

                    # Ensure there's always a two-line gap at the end
                    newUserSetup = newUserSetup.rstrip() + "\n\n"

            except IOError:
                newUserSetup = ""

            CamsRunCode = startCode + "\n\nimport aleha_tools.cams as cams\ncmds.evalDeferred(\"cams.show()\",lowestPriority=True)\n\n" + endCode
            newUserSetup += CamsRunCode

            # Write the updated userSetup file
            with open(userSetupFile, 'w') as output_file:
                output_file.write(newUserSetup)"""

            # Step 11: Installation process finished (loading deferred)
            current_step += 1
            status_msg = "Installation complete. Tool will load shortly."
            if gMainProgressBar:
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    progress=current_step,
                    status=status_msg,
                )
            else:
                print(status_msg)

        except RuntimeError as e:
            if gMainProgressBar:
                cmds.progressBar(gMainProgressBar, edit=True, status="Error: %s" % e)
            cmds.error("Installation failed: %s" % e)

        except Exception as e:
            if gMainProgressBar:
                cmds.progressBar(gMainProgressBar, edit=True, status="Unexpected Error: %s" % e)
            traceback.print_exc()
            cmds.error("An unexpected error occurred during installation: %s" % e)

        finally:
            # Final Cleanup
            if gMainProgressBar:
                cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)

            # Clean up temporary zip file (important to do this after potential errors too)
            if os.path.isfile(tmpZipFile):
                try:
                    os.remove(tmpZipFile)
                except OSError as e:
                    cmds.warning("Could not remove temporary file %s after process: %s" % (tmpZipFile, e))


# onMayaDroppedPythonFile function
def onMayaDroppedPythonFile(filePath=None):
    """
    Function called when the script is dragged and dropped into the Maya viewport.
    """

    """try:
        import aleha_tools.cams as cams
        return cmds.error("The cams tool is already installed. Please uninstall the tool and try again.")
    except ImportError:
        pass"""

    script_name = "install_cams"
    import sys

    if script_name in sys.modules:
        try:
            importlib.reload(sys.modules[script_name])
        except Exception as e:
            print("Warning: Could not reload installer script '%s': %s" % (script_name, e))

    installer = Installer()
    installer.install()


# if __name__ == "__main__":
#     print("Running installer directly (ensure Maya GUI is running)...")
#     # Need to be in Maya GUI context for progress bar
#     if not cmds.about(batch=True):
#         installer = Installer()
#         installer.install()
