import maya.OpenMayaUI as omui
import maya.cmds as cmds
from importlib import reload

# Attempt to import PySide2, fallback to PySide6 if unavailable

try:
    from PySide6.QtWidgets import QMainWindow, QWidget  # type: ignore
    from PySide6.QtGui import QIcon, QAction  # type: ignore
except ImportError:
    from PySide2.QtWidgets import QAction, QMainWindow, QWidget
    from PySide2.QtGui import QIcon


# Import and reload necessary modules
from . import settings, widgets, funcs, util

reload(settings)
reload(widgets)
reload(funcs)
reload(util)


def on_show(self):
    menu = self.debug_menu
    """Populates the debug menu with debugging tools."""
    if menu is None or not hasattr(menu, "clear"):
        return

    menu.clear()

    debug_tools = [
        ("Print Widget Hierarchy", print_widget_hierarchy),
        ("Log UI Structure", log_ui_structure),
        ("Force Refresh Viewport", refresh_viewport),
    ]

    for name, function in debug_tools:
        action = QAction(QIcon(util.return_icon_path("debug.png")), name)
        action.triggered.connect(function)
        menu.addAction(action)


def print_widget_hierarchy():
    print("Widget hierarchy debug tool activated.")


def log_ui_structure():
    print("Logging UI structure...")


def refresh_viewport():
    cmds.refresh()
    print("Viewport refreshed.")


def debug(ui):
    cams_widget = omui.MQtUtil.findControl(ui.workspace_control_name)
    cams_ui = util.get_maya_qt(cams_widget, QWidget)

    topmost_parent = []
    while True:
        parent_widget = cams_ui.parent()
        topmost_parent.append(parent_widget)
        if isinstance(parent_widget, QMainWindow):
            break
        cams_ui = parent_widget

    for w in topmost_parent:
        print(w)

    if cmds.workspaceControl(ui.workspace_control_name, q=True, floating=True):
        topmost_parent = topmost_parent[-2]
        topmost_parent.resize(ui.width(), util.DPI(15))

    else:
        topmost_parent = topmost_parent[2]
        topmost_parent.setSizes([54, topmost_parent.sizes()[1]])
