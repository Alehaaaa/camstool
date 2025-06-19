import maya.cmds as cmds
import maya.mel as mel
import os
import shutil

import maya.OpenMayaUI as omui

try:
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QApplication,
        QMessageBox,
        QDialog,
        QInputDialog,
    )
    from PySide6.QtCore import Qt, QPoint  # type: ignore
    from PySide6.QtGui import QVector2D  # type: ignore

    from shiboken6 import wrapInstance  # type: ignore
except ImportError:
    from PySide2.QtWidgets import (
        QWidget,
        QApplication,
        QMessageBox,
        QDialog,
        QInputDialog,
    )
    from PySide2.QtCore import Qt, QPoint
    from PySide2.QtGui import QVector2D

    from shiboken2 import wrapInstance

import importlib

from .util import DPI, get_maya_qt, get_python_version


def check_for_updates(ui, warning=True, force=False):
    from . import updater

    importlib.reload(updater)
    return updater._check_for_updates(ui, warning, force)


def install_userSetup(uninstall=False):
    userSetupFile = os.path.join(os.getenv("MAYA_APP_DIR"), "scripts", "userSetup.py")

    cmds_import = "from maya import cmds\n"
    newUserSetup = ""
    startCode, endCode = "# start Cams", "# end Cams"

    try:
        with open(userSetupFile, "r") as input_file:
            lines = input_file.readlines()

            # Remove existing block between startCode and endCode
            inside_block = False
            for line in lines:
                if line == cmds_import:
                    cmds_import = ""
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

    CamsRunCode = (
        startCode
        + "\n\n"
        + cmds_import
        + 'if not cmds.about(batch=True):\n    cmds.evalDeferred(lambda: cmds.evalDeferred("import aleha_tools.cams as cams; cams.show()", lowestPriority=True))\n\n'
        + endCode
    )

    if not uninstall:
        newUserSetup += CamsRunCode

    # Write the updated userSetup file
    with open(userSetupFile, "w") as output_file:
        output_file.write(newUserSetup)


def unistall(ui):
    box = cmds.confirmDialog(
        title="About to Uninstall!",
        message="Uninstalling Cams will remove ALL settings.\nAre you sure you want to continue?",
        button=["Yes", "Cancel"],
        defaultButton="Cancel",
        cancelButton="Cancel",
        dismissString="Cancel",
    )

    if box == "Yes":
        install_userSetup(uninstall=True)

        toolsFolder = os.path.join(os.environ["MAYA_APP_DIR"], "scripts", "aleha_tools")
        # Remove tool files
        if os.path.isdir(toolsFolder):
            for filename in os.listdir(toolsFolder):
                f = os.path.join(toolsFolder, filename)
                if os.path.isfile(f):
                    os.remove(f)
                elif os.path.isdir(f):
                    shutil.rmtree(f)

        buttons = cmds.shelfLayout(
            cmds.tabLayout(mel.eval("$nul=$gShelfTopLevel"), q=1, st=1), q=True, ca=True
        )
        if buttons:
            for b in buttons:
                if (
                    cmds.shelfButton(b, exists=True)
                    and cmds.shelfButton(b, q=True, l=True) == ui.TOOL
                ):
                    cmds.deleteUI(b)

        close_UI(ui, confirm=False)
        if "cams_aleha_tool" in globals():
            try:
                del cams_aleha_tool  # noqa: F821
            except Exception:
                pass
            if ui:
                del ui


def get_camsDisplay_modeleditor():
    model_editor_cameras = {}
    panels = cmds.getPanel(type="modelPanel")
    for pl in panels:
        if cmds.modelEditor(pl, exists=True):
            cam = cmds.modelEditor(pl, q=True, camera=True)
            if cam:
                cam = cam.split("|")[-1]
                if cmds.objExists(cam + ".cams_display"):
                    model_editor_cameras[pl] = cam
    return model_editor_cameras


def get_preferences_display(cam):
    cam_attr = cam + ".cams_display"
    if cmds.objExists(cam_attr):
        attr_value = cmds.getAttr(cam_attr) or "{}"
        preferences = eval(attr_value)
    else:
        preferences = {}
        cmds.addAttr(cam, ln="cams_display", dt="string")
    return preferences


def save_display_to_cam(cam, commands=None):
    prefs = get_preferences_display(cam) or {}
    if commands:
        for attr, plugin, state in commands:
            prefs[attr] = (plugin, state)

    cmds.setAttr(f"{cam}.cams_display", str(prefs), type="string")


def display_menu_elements(commands=False):
    menu_elements = {
        "Curves": (
            ("NURBS Curves", "nurbsCurves", 0),
            ("NURBS Surfaces", "nurbsSurfaces", 0),
        ),
        "Surfaces": (
            ("Polygons", "polymeshes", 0),
            ("Textures", "displayTextures", 0),
        ),
        "Visualising": (
            ("Cameras", "cameras", 0),
            ("Hold-Outs", "holdOuts", 0),
            ("Image Planes", "imagePlane", 0),
            ("Motion Trails", "motionTrails", 0),
        ),
        "Rigging": (
            ("Locators", "locators", 0),
            ("IK Handles", "ikHandles", 0),
            ("Joints", "joints", 0),
            ("Deformers", "deformers", 0),
        ),
        "Viewport Utilities": (
            ("Grid", "grid", 0),
            ("Manipulators", "manipulators", 0),
            ("Selection Highlight", "selectionHiliteDisplay", 0),
        ),
        "Plugins": (
            ("GPU Cache", "gpuCacheDisplayFilter", 1),
            ("Blue Pencil", "bluePencil", 0),
        ),
    }
    if commands:
        return {
            item[1]: item[2] for values in menu_elements.values() for item in values
        }
    return menu_elements


def get_cam_display(cam_panels, command, plugin=False):
    if plugin:
        run_command = (
            "cmds.modelEditor('"
            + cam_panels[-1]
            + "', q=1, queryPluginObjects='"
            + command
            + "')"
        )
    else:
        run_command = (
            "cmds.modelEditor('" + cam_panels[-1] + "', q=1, " + command + "=1 )"
        )
    try:
        cleaned_run_command = "".join(c for c in run_command if c.isprintable())
        value = eval(cleaned_run_command)
        return value
    except Exception:
        return None


def set_cam_display(cam_panels, command, plugin=False, switch=None):
    var = get_cam_display(cam_panels, command, plugin) if switch is None else not switch
    for i in cam_panels:
        e_cmd = (
            "pluginObjects=('{}', {})".format(command, not var)
            if plugin
            else "{}={}".format(command, not var)
        )
        try:
            eval("cmds.modelEditor('{}', e=1, {})".format(i, e_cmd))
        except Exception:
            continue


def look_thru(cam, modelPane=None, ui=None):
    modelPane = modelPane or cmds.getPanel(wf=True)

    pane_widget = omui.MQtUtil.findControl(modelPane)
    if pane_widget:
        main_widget = get_maya_qt(pane_widget, QWidget).parent().parent().parent()
        if isinstance(main_widget, QWidget):
            try:
                cmds.workspaceControl(main_widget.objectName(), e=True, label=cam)
            except Exception:
                pass

    try:
        cmds.lookThru(modelPane, cam)
    except Exception:
        if ui:
            ui.reload_cams_UI()
        return
    preferences = get_preferences_display(cam)
    if preferences:
        for command, plugin_switch in preferences.items():
            plugin, switch = (
                plugin_switch if type(plugin_switch) is tuple else (plugin_switch, 0)
            )
            set_cam_display([modelPane], command, plugin=plugin, switch=switch)


def get_model_from_pos(pos):
    widget = QApplication.widgetAt(QPoint(*pos))
    """Check if a given QWidget == a model editor in Maya."""
    if isinstance(widget, QWidget):
        model_editor = widget.parent()
        if model_editor:
            return model_editor.objectName()
    return None


def get_panels_from_camera(cam):
    """Returns a set of model panels associated with a given camera transform or shape."""
    if cmds.objectType(cam, isType="transform"):
        cam_shape = cmds.listRelatives(cam, shapes=True)[0]
    else:
        cam_shape = cam

    return list(
        {
            p
            for p in cmds.getPanel(type="modelPanel")
            if cmds.modelPanel(p, q=True, camera=True) in {cam, cam_shape}
        }
    )


def drag_insert_camera(camera, parent, pos):
    button_pos, cursor_pos = pos

    cursor_x, cursor_y = cursor_pos.x(), cursor_pos.y()

    widget_name = get_model_from_pos((cursor_x, cursor_y))
    if widget_name and widget_name.startswith("modelPanel"):
        look_thru(camera, widget_name, parent)

    else:
        distance = QVector2D(button_pos - cursor_pos).length()
        if distance < DPI(120):  # Adjust the threshold as needed
            return

        tear_window = tear_off_cam(camera)
        cmds.workspaceControl(tear_window, e=True, rsh=600, rsw=900)
        window_widget = omui.MQtUtil.findControl(tear_window)
        floating_window = wrapInstance(int(window_widget), QWidget)

        # Get the parent widget of the floating window
        main_parent_widget = floating_window.parent().parent().parent().parent()

        # Set the initial position of the parent widget (floating window)
        main_parent_widget.move(
            cursor_x - main_parent_widget.geometry().width() / 2, cursor_y
        )

        main_parent_widget.raise_()
        main_parent_widget.activateWindow()  # Activates the window to gain focus


def select_cam(cam, button=None):
    if button:
        button.select_action.setVisible(False)
        button.deselect_action.setVisible(True)

    cmds.select(cam, add=True)


def deselect_cam(cam, button=None):
    if button:
        button.deselect_action.setVisible(False)
        button.select_action.setVisible(True)

    cmds.select(cam, deselect=True)


def duplicate_cam(cam, ui):
    cmds.undoInfo(openChunk=True)
    dup_cam = cmds.duplicate(cam)
    dup_cam = dup_cam[0]
    if cmds.listRelatives(dup_cam, parent=True):
        cmds.parent(dup_cam, w=1)
    cmds.showHidden(dup_cam)
    cmds.setAttr(cmds.listRelatives(dup_cam, shapes=True)[0] + ".renderable", False)

    type_attr = dup_cam + ".cams_type"
    if cmds.objExists(type_attr):
        cmds.deleteAttr(type_attr)

    cmds.select(dup_cam)

    cmds.undoInfo(closeChunk=True)

    ui.parentUI.reload_cams_UI()
    try:
        ui.context_menu.close()
    except Exception:
        pass


def check_if_valid_camera(cam, status=None):
    check_passed = True
    message = None

    if cmds.camera(cam, q=1, sc=True):
        check_passed = False
        message = "Default camera '" + cam + "' cannot be %s."

    elif cmds.referenceQuery(cam, isNodeReferenced=True):
        check_passed = False
        message = "Referenced camera '" + cam + "' cannot be %s."

    if check_passed:
        return True
    else:
        if status and message:
            cmds.warning(message % status)
        return False


def rename_cam(cam, rename_input=None, ui=None):
    if not check_if_valid_camera(cam, status="renamed"):
        return

    if not rename_input or not str(rename_input).strip():
        re_win = QInputDialog()
        re_win.setWindowTitle("Rename " + cam)
        re_win.setLabelText("New name:")
        re_win.setTextValue(cam)

        re_win.setWindowFlags(re_win.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        result = re_win.exec_()

        if result == QDialog.Accepted:
            rename_input = re_win.textValue()
        else:
            return

    if cmds.objExists(cam + ".cams_type"):
        _parent = cmds.listRelatives(cam, parent=True)
        all_descendants = cmds.listRelatives(_parent, allDescendents=True) + _parent

        cmds.undoInfo(openChunk=True)

        name = cmds.rename(cam, rename_input)
        for descendant in all_descendants:
            try:
                cmds.rename(descendant, name + descendant[len(cam) : :])
            except Exception:
                pass

        cmds.undoInfo(closeChunk=True)
    else:
        name = cmds.rename(cam, rename_input)

    if ui:
        ui.reload_cams_UI()
    return name


def delete_cam(cam, ui):
    if not check_if_valid_camera(cam, status="deleted"):
        return

    if cmds.objExists(cam):
        delete = QMessageBox()
        response = delete.warning(
            None,
            "Delete " + cam,
            "Are you sure you want to delete " + cam + "?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,  # Uso de StandardButton
            QMessageBox.StandardButton.No,  # Botón por defecto
        )

        if response == QMessageBox.StandardButton.Yes:
            if cmds.objExists(cam + ".cams_type"):
                try:
                    delete_target = cmds.listRelatives(cam, allParents=True)[0]
                except Exception:
                    delete_target = cam

                if cmds.nodeType(delete_target) != "dagContainer":
                    try:
                        delete_target = cmds.listRelatives(
                            delete_target, allParents=True
                        )[0]
                    except Exception:
                        pass
            else:
                delete_target = cam
            cmds.undoInfo(openChunk=True)
            cmds.delete(cam, inputConnectionsAndNodes=True)
            cmds.delete(delete_target, hierarchy="both")
            cmds.undoInfo(closeChunk=True)
    ui.reload_cams_UI()


def tear_off_cam(cam):
    tear_off_window = None
    for i in range(10):
        try:
            name = cam + "_WorkspaceControl" + (str(i) if i != 0 else "")
            tear_off_window = cmds.workspaceControl(name, label=cam, retain=False)
            break
        except Exception:
            pass
    if tear_off_window is None:
        cmds.warning("Error making panel or too many Tear Off panels already made!")
        return

    cmds.paneLayout()
    new_pane = cmds.modelPanel()
    cmds.showWindow(tear_off_window)

    look_thru(cam, new_pane)
    cmds.modelEditor(new_pane, e=1, displayAppearance="smoothShaded")

    cmds.workspaceControl(tear_off_window, e=1, rsh=600, rsw=900)
    return tear_off_window


def delete_maya_UI(ui="CamsWorkspaceControl"):
    try:
        cmds.deleteUI(ui)
        cmds.workspaceControl(ui, e=True, close=True)
    except Exception:
        pass


def close_all_Windows(ui):
    for window_ui in ["MultiCams", ui.workspace_control_name]:
        if cmds.workspaceControl(window_ui, exists=True):
            try:
                delete_maya_UI(window_ui)
            except Exception:
                pass
    try:
        ui.kill_all_scriptJobs()
        ui.close()
        ui.deleteLater()
    except Exception:
        pass


def close_UI(ui, confirm=True):
    if not ui:
        return
    elif confirm and ui.confirm_exit:
        currentShelf = cmds.tabLayout(mel.eval("$nul=$gShelfTopLevel"), q=1, st=1)
        tool = ui.TITLE.lower()

        def find():
            buttons = cmds.shelfLayout(currentShelf, q=True, ca=True)
            if buttons is None:
                return False
            else:
                for b in buttons:
                    if (
                        cmds.shelfButton(b, exists=True)
                        and cmds.shelfButton(b, q=True, l=True) == tool
                    ):
                        return True
            return False

        if not find():
            box = cmds.confirmDialog(
                title="About to close Cams!",
                message="Closing Cams will NOT reopen the UI on Maya's next launch.\nYou will have to use a Shelf button or run Cams launch script.\n\nAre you sure you want to continue?",
                button=["Yes", "Add to Shelf", "Cancel"],
                defaultButton="Cancel",
                cancelButton="Cancel",
                dismissString="Cancel",
            )

            if box == "Yes" or box == "Add to Shelf":
                if box == "Add to Shelf":
                    cmds.shelfButton(
                        parent=currentShelf,
                        i=os.path.join(
                            os.path.dirname(__file__),
                            "_icons",
                            tool + ".svg",
                        ),
                        label=tool,
                        c="import aleha_tools.%s as %s;from importlib import reload;reload(%s);%s.show()"
                        % (tool, tool, tool, tool),
                        annotation=tool.title() + " by Aleha",
                    )
            else:
                return
    close_all_Windows(ui)


# Open Tools
def run_tools(tool, ui=None):
    if get_python_version() > 2:
        try:
            import importlib

            tool_module = importlib.import_module("aleha_tools._tools." + tool)
            importlib.reload(tool_module)
        except ImportError:
            cmds.error("Error importing module " + tool)
            return

        if ui:
            tool_instance = getattr(tool_module, tool)()
            tool_instance.show_dialog(ui)
        else:
            getattr(tool_module, tool)()

    else:
        cmds.warning("Work in Progress")


def check_author():
    import base64 as b

    return os.getenv("USER", os.getenv("USERNAME")).lower() in [
        b.b64decode(x).decode() for x in [b"YWxlamFuZHJv", b"YWxlaGE="]
    ]


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
        raise AttributeError(f"No class '{cls_name}' in '{module.__name__}'")

    instance = getattr(module, cls_name)(os.path.dirname(__file__), *args)

    if not hasattr(instance, method) or not callable(getattr(instance, method)):
        raise AttributeError(f"No callable method '{method}' in '{cls_name}'")
    return getattr(instance, method)()


def compile_version():
    if not check_author():
        return

    import aleha_tools  # type: ignore

    importlib.reload(aleha_tools)
    local_version = aleha_tools.DATA.get("VERSION")

    version_input = cmds.promptDialog(
        title="New Version",
        message="Enter the new version number:",
        text=local_version,
        button=["OK", "Cancel"],
        defaultButton="OK",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if version_input == "OK":
        new_version = cmds.promptDialog(query=True, text=True)
        if new_version < local_version:
            cmds.warning("New version must be greater than current version.")
            return

        path = r"\\HKEY\temp\from_alejandro\cams_tool\development\UpdateCompiler.py"
        name = "compiler_cams"
        cls = "CompileCams"
        method = "main"

        try:
            # Pass new_version as a positional argument
            _run_method(_load_module(path, name), cls, method, new_version)

        except (ImportError, AttributeError) as e:
            print(f"Compile Error: {e}")


def changes_compiler():
    if not check_author():
        return
    path = r"\\HKEY\temp\from_alejandro\cams_tool\development\ChangesCompiler.py"
    name = "generate_changes_cams"
    cls = "CamsToolUpdater"
    method = "run"
    try:
        changelog = _run_method(_load_module(path, name), cls, method)
        if changelog:
            cmds.confirmDialog(m="- " + "\n- ".join(changelog))
    except (ImportError, AttributeError) as e:
        print(f"Changelog Error: {e}")
