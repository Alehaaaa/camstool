import sys
from pathlib import Path
import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6.QtWidgets import (  # type: ignore
        QMainWindow,
    )
    from shiboken6 import wrapInstance, isValid  # type: ignore

except ImportError:
    from PySide2.QtWidgets import (
        QMainWindow,
    )
    from shiboken2 import wrapInstance, isValid

long = int


def DPI(val):
    return omui.MQtUtil.dpiScale(val)


def return_icon_path(icon):
    if "." not in icon:
        icon = icon + ".png"
    return str(Path(__file__).parent / "_icons" / icon)


def make_inViewMessage(message, icon="camera"):
    cmds.inViewMessage(
        amg='<div style="text-align:center"><img src=' + return_icon_path(icon) + ">\n" + message + "\n",
        pos="midCenter",
        a=0.9,
        fade=True,
    )


def getcolor(camera):
    min_v = 100
    max_v = 170

    # Convert the UUID to a hexadecimal string
    hex_string = cmds.ls(camera, uuid=1)[0].split("-")

    # Extract RGB values from parts of the hexadecimal string
    r = int(hex_string[1], 16)
    g = int(hex_string[2], 16)
    b = int(hex_string[3], 16)

    max_range = max(r, g, b)
    default_color = []
    for i in [r, g, b]:
        i = int(min_v + (i / max_range) * (max_v - min_v))
        default_color.append(i)

    return default_color


def get_cameras(default=False):
    # Get all custom cameras in scene and the default ones
    non_startup_cameras = []
    startup_cameras = []

    for cam in cmds.ls(type=("camera")) or []:
        kcam = cmds.listRelatives(cam, type="transform", p=True)[0]
        if not cmds.camera(kcam, q=1, sc=True):
            non_startup_cameras.append(kcam)
        else:
            startup_cameras.append(kcam)
    return non_startup_cameras if not default else startup_cameras


def get_python_version():
    return sys.version_info.major


def get_maya_qt(ptr=omui.MQtUtil.mainWindow(), qt=QMainWindow):
    return wrapInstance(long(ptr), qt)


def is_valid_widget(widget, expected_type=None):
    if widget is None:
        return False
    if expected_type is not None and not isinstance(widget, expected_type):
        return False
    if isValid(widget):
        return True
    return False


def check_visible_layout(layout):
    try:
        try:
            s = cmds.workspaceControl(layout, q=True, visible=True) and not cmds.workspaceControl(
                layout, q=True, collapse=True
            )
        except Exception:
            s = cmds.window(layout, q=True, visible=True)
    except Exception:
        s = False
    return s


def get_root_path():
    """Returns the root path of the project (parent of source directory)."""
    return Path(__file__).resolve().parents[2]


def compare_versions(v1, v2):
    """
    Compares two version strings.
    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    import re

    def tokenize(v):
        return [int(s) if s.isdigit() else s.lower() for s in re.split(r"(\d+)", str(v)) if s]

    t1, t2 = tokenize(v1), tokenize(v2)

    for p1, p2 in zip(t1, t2):
        if p1 == p2:
            continue
        if type(p1) is not type(p2):
            p1, p2 = str(p1), str(p2)
        return (p1 > p2) - (p1 < p2)

    return (len(t1) > len(t2)) - (len(t1) < len(t2))
