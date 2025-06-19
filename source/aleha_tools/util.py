import os
import sys
import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6.QtWidgets import (  # type: ignore
        QMainWindow,
    )
    from shiboken6 import wrapInstance  # type: ignore

    long = int
except ImportError:
    from PySide2.QtWidgets import (
        QMainWindow,
    )
    from shiboken2 import wrapInstance


def DPI(val):
    return omui.MQtUtil.dpiScale(val)


def return_icon_path(icon):
    script_directory = os.path.dirname(__file__)
    return os.path.join(script_directory, "_icons", icon)


def make_inViewMessage(message, icon="camera"):
    cmds.inViewMessage(
        amg='<div style="text-align:center"><img src='
        + return_icon_path(icon + ".png")
        + ">\n"
        + message
        + "\n",
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

    for cam in cmds.ls(type=("camera")):
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


def check_visible_layout(layout):
    try:
        try:
            s = cmds.workspaceControl(
                layout, q=True, visible=True
            ) and not cmds.workspaceControl(layout, q=True, collapse=True)
        except Exception:
            s = cmds.window(layout, q=True, visible=True)
    except Exception:
        s = False
    return s
