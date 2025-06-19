"""

Put this file in your scripts directory:
"%USERPROFILE%\Documents\maya\scripts"

or a speficic version:
"%USERPROFILE%\Documents\maya\####\scripts"


Run as a Dialog with:

import aleha_tools.spaceswitch as spaceswitch
spaceswitch.show()


Run as a Popup with:

import aleha_tools.spaceswitch as spaceswitch
spaceswitch.popup()


"""

try:
    from PySide6.QtWidgets import *  # type: ignore  # noqa: F403
    from PySide6.QtGui import *  # type: ignore  # noqa: F403
    from PySide6.QtCore import *  # type: ignore  # noqa: F403
    from shiboken6 import wrapInstance, isValid  # type: ignore

except ImportError:
    from PySide2.QtWidgets import (
        QMainWindow,
        QWidget,
        QDialog,
        QLabel,
        QVBoxLayout,
        QHBoxLayout,
        QMessageBox,
        QComboBox,
        QMenu,
        QMenuBar,
        QStyledItemDelegate,
    )
    from PySide2.QtGui import (
        QGuiApplication,
        QCursor,
        QPainter,
        QPen,
        QBrush,
        QImage,
        QPixmap,
        QColor,
    )
    from PySide2.QtCore import Qt, QPoint, QRectF, QSettings, QTimer, QEvent, QPointF
    from shiboken2 import wrapInstance, isValid

# from pprint import pprint

import maya.OpenMayaUI as omui
import maya.api.OpenMaya as om
import maya.cmds as cmds
import maya.mel as mel
import sys
import os
import math

try:
    from base64 import decodebytes
except ImportError:
    from base64 import decodestring

    decodebytes = decodestring


__version__ = "1.01beta"
TITLE = "SpaceSwitch"
ORG_NAME = "Aleha"


_MAIN_DICT = sys.modules["__main__"].__dict__  # the one place that survives reloads
MAINTENANCE = False


def get_maya_window():
    win_ptr = omui.MQtUtil.mainWindow()
    if sys.version_info.major < 3:
        return wrapInstance(long(win_ptr), QMainWindow)  # type: ignore  # noqa: F405
    else:
        return wrapInstance(int(win_ptr), QMainWindow)  # type: ignore  # noqa: F405


def show(_frameless=False):
    """Public entry point called from shelves or hotkeys."""
    SpaceSwitchManager.show(_frameless)


def popup(_frameless=True):
    """Public entry point called from hotkeys."""
    SpaceSwitchManager.show(_frameless)


def _instance_alive(widget: QWidget | None) -> bool:
    """Comprueba que *widget* siga siendo un QWidget válido."""
    return widget is not None and isValid(widget)


def _place_next_to_cursor(dlg: QDialog) -> None:
    """Coloca el diálogo a la derecha del cursor, centrado verticalmente."""
    dlg.adjustSize()
    w, h = dlg.width(), dlg.height()

    cur_pos = QCursor.pos()
    screen = QGuiApplication.screenAt(cur_pos) or QGuiApplication.primaryScreen()
    geom = screen.availableGeometry()  # respeta la barra de tareas

    x = max(geom.left(), min(cur_pos.x(), geom.right() - w))
    y = max(geom.top(), min(cur_pos.y() - h // 2, geom.bottom() - h))
    dlg.move(x, y)


class SpaceSwitchManager:
    """Create or reuse the single, persistent SpaceSwitch dialog."""

    @classmethod
    def show(cls, frameless=False) -> None:
        if MAINTENANCE and os.getenv("USERNAME") != "alejandro":
            cmds.error(f"{TITLE} under maintenance")
            return

        dlg: SpaceSwitchDialog | None = _MAIN_DICT.get("_SPACESWITCH_INSTANCE")  # type: ignore
        if _instance_alive(dlg) and dlg.isHidden():
            try:
                dlg.close()  # triggers closeEvent - clean-up
            finally:
                dlg = None  # drop the stale pointer

        if not _instance_alive(dlg):
            dlg = SpaceSwitchDialog(frameless, parent=get_maya_window())
            _MAIN_DICT["_SPACESWITCH_INSTANCE"] = dlg

        if frameless:
            _place_next_to_cursor(dlg)
        dlg.refresh()
        dlg._add_script_jobs()  # keep the original camelCase

        if dlg.isHidden():  # will only be True on first creation
            dlg.show()
        else:
            dlg.raise_()
            dlg.activateWindow()


class SpaceSwitchDialog(QDialog):
    """
    Messages:
    """

    NO_INTERNET = "Could not establish a connection to the server."
    WORKING_ON_IT = "Still working on this feature!"

    AUTO_CLOSE_DIST = 10  # píxeles – ajusta a tu gusto
    AUTO_CLOSE_PERIOD = 300  # ms     – frecuencia de chequeo

    def __init__(self, frameless=False, parent=None):
        super(SpaceSwitchDialog, self).__init__(parent=get_maya_window())

        if sys.platform == "darwin":
            self._base_flags = Qt.Tool
        else:
            self._base_flags = Qt.Window | Qt.WindowCloseButtonHint
        self._frameless_flags = (
            Qt.Window
            | Qt.WindowCloseButtonHint
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )

        self._frameless = frameless
        if self._frameless:
            _flags = self._frameless_flags
        else:
            _flags = self._base_flags

        self.setWindowFlags(_flags)

        self.setWindowTitle(("{} {}").format(TITLE, __version__))
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setModal(False)

        self.settings = QSettings(ORG_NAME, TITLE)
        self.instance_settings()

        self.analyzer = GimbalAnalyzer()

        self.object_selection = []

        self.create_layouts()
        self.create_widgets()
        self.create_connections()

        self.setMaximumSize(self.size())

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(self.AUTO_CLOSE_PERIOD)
        self._auto_timer.timeout.connect(self._check_mouse_distance)
        if self._frameless:
            self._auto_timer.start()

        self._auto_timer_enabled = self._frameless
        self._timer_was_paused = False

        self._dragging = False
        self._drag_start_pos = None
        self._drag_pos = QPoint()

        self._drag_threshold = 10

        # self.check_for_updates(warning=False)

    def instance_settings(self):
        self.namespace_display = self.settings.value(
            "namespace_display", False, type=bool
        )
        self.all_frames = self.settings.value("all_frames", False, type=bool)

        self.euler_filter = self.settings.value("euler_filter", True, type=bool)
        self.show_rotate_order = self.settings.value(
            "show_rotate_order", True, type=bool
        )

    def create_layouts(self):
        self.main_layout = QVBoxLayout(self)

        # Menu bar
        self.menu_bar = QMenuBar()
        settings_menu = QMenu("Settings", self)
        settings_menu.aboutToShow.connect(self._pause_auto_timer)
        settings_menu.aboutToHide.connect(self._resume_auto_timer)

        self.menu_bar.addMenu(settings_menu)

        self.toggle_namespaces_action = settings_menu.addAction("Show namespaces")
        self.toggle_namespaces_action.setCheckable(True)
        self.toggle_namespaces_action.setChecked(self.namespace_display)

        self.show_rotate_order_action = settings_menu.addAction("Enable Rotate Order")
        self.show_rotate_order_action.setCheckable(True)
        self.show_rotate_order_action.setChecked(self.show_rotate_order)

        settings_menu.addSeparator()

        self.euler_filter_action = settings_menu.addAction("Auto Euler Filter")
        self.euler_filter_action.setCheckable(True)
        self.euler_filter_action.setChecked(self.euler_filter)

        self.all_frames_action = settings_menu.addAction("Apply to all frames")
        self.all_frames_action.setCheckable(True)
        self.all_frames_action.setChecked(self.all_frames)

        about_menu = QMenu("About", self)
        about_menu.aboutToShow.connect(self._pause_auto_timer)
        about_menu.aboutToHide.connect(self._resume_auto_timer)

        self.menu_bar.addMenu(about_menu)

        self.check_updates_action = about_menu.addAction("Check for updates")
        self.check_updates_action.setVisible(False)
        about_menu.addSeparator()
        self.credits_action = about_menu.addAction("Credits")

        self.main_layout.setMenuBar(self.menu_bar)

        self.enums_layout = QVBoxLayout()
        self.button_layout = QHBoxLayout()
        self.main_layout.addLayout(self.enums_layout)
        self.main_layout.addLayout(self.button_layout)

        self.menu_bar.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Permite arrastrar haciendo clic en la zona vacía del QMenuBar."""
        if obj == self.menu_bar:
            t = event.type()
            if t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if self.menu_bar.actionAt(event.pos()) is None:  # fuera de menus
                    self._dragging = True
                    self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                    if self._auto_timer_enabled:  # apaga timer
                        self._auto_timer.stop()
                        self._auto_timer_enabled = False
                    return True  # consumir evento

            elif (
                t == QEvent.MouseMove
                and self._dragging
                and event.buttons() & Qt.LeftButton
            ):
                self.move(event.globalPos() - self._drag_pos)
                return True

            elif (
                t == QEvent.MouseButtonRelease
                and self._dragging
                and event.button() == Qt.LeftButton
            ):
                self._dragging = False
                if self._frameless:
                    self.setWindowFlags(self._base_flags)
                    self.show()
                    self._frameless = False
                return True

        # para todo lo demás, comportamiento normal
        return super().eventFilter(obj, event)

    def create_widgets(self):
        self.selection_label = QLabel("No valid switches selected.")
        self.selection_label.setStyleSheet(
            "QLabel {background-color: #333333;border-radius: 3px;}"
        )
        self.selection_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.selection_label.setFixedHeight(21)
        self.main_layout.insertWidget(0, self.selection_label)

    def create_connections(self):
        self.check_updates_action.triggered.connect(self.check_for_updates)
        self.credits_action.triggered.connect(self.coffee)

        self.show_rotate_order_action.toggled.connect(
            lambda state: self.set_setting("show_rotate_order", state, True)
        )
        self.toggle_namespaces_action.toggled.connect(
            lambda state: self.set_setting("namespace_display", state, True)
        )
        self.euler_filter_action.toggled.connect(
            lambda state: self.set_setting("euler_filter", state)
        )
        self.all_frames_action.toggled.connect(
            lambda state: self.set_setting("all_frames", state)
        )

    def set_setting(self, setting, state, refresh=False):
        self.settings.setValue(setting, state)
        setattr(self, setting, state)

        if refresh:
            self.refresh(force=True)

    def getSelectedObj(self, long=False):
        return cmds.ls(selection=True, long=long)

    def _pause_auto_timer(self):
        if self._auto_timer.isActive():
            self._auto_timer.stop()
            self._timer_was_paused = True
        else:
            self._timer_was_paused = False

    def _resume_auto_timer(self):
        if self._timer_was_paused and self._frameless:
            self._auto_timer.start()

    # Main Function to Set the ComboBox
    def set_combobox(self, enum_objects):
        combobox = AutoPauseComboBox(
            self._pause_auto_timer, self._resume_auto_timer, parent=self
        )
        combobox.setMaxVisibleItems(60)
        combobox.setItemDelegate(RightIconDelegate(combobox))

        seen = set()
        marked = {
            item for obj in enum_objects.values() for item in obj.get("marked", [])
        }
        currents = [obj.get("current") for obj in enum_objects.values()]

        any_object = next(iter(enum_objects.values()), {})
        gimbal_info = any_object.get("gimbal", {})

        real_enum_values = []

        for i, enum_value in enumerate(
            [
                enum
                for obj in enum_objects.values()
                for enum in obj["enum"]
                if not (enum in seen or seen.add(enum))
            ]
        ):
            label = gimbal_info.get(enum_value, {}).get("label", "")
            display_text = f"{enum_value} ({label})" if label else enum_value

            combobox.addItem(display_text)
            real_enum_values.append(enum_value)

            if i not in marked:
                combobox.setItemData(i, True, Qt.UserRole + 1)
            else:
                combobox.setItemData(i, enum_value, Qt.UserRole)

            if i in currents:
                combobox.setCurrentIndex(i)

        """
        #Multiple Frames
        combobox.insertSeparator(combobox.count())

        seen = set()

        for i, op in enumerate([enum for obj in enum_objects.values() for enum in obj['enum'] if not (enum in seen or seen.add(enum))]):
            combobox.addItem(op)
            # Set Qt.UserRole to mark current options
            if i in marked:
                combobox.setItemData(combobox.count() - 1, True, Qt.UserRole)
                combobox.setCurrentText(op)"""

        return combobox

    def getEnums(self):
        spaceswitch_enum_dictionary = {}

        for object in self.object_selection:
            if object in spaceswitch_enum_dictionary.keys():
                continue

            locked = cmds.listAttr(object, cb=1) or []
            animatable = cmds.listAnimatable(object)
            if animatable:
                orderedAttrs = [
                    i.rsplit(".", 1)[-1] for i in animatable if i and i not in locked
                ]

                if orderedAttrs:
                    if self.show_rotate_order:
                        orderedAttrs.extend(["rotateOrder"])
                    for enum_attr in orderedAttrs:
                        try:
                            attrType = cmds.attributeQuery(
                                enum_attr, node=object, attributeType=True
                            )
                        except Exception:
                            continue
                        if attrType == "enum":
                            enum_values = cmds.attributeQuery(
                                enum_attr, node=object, listEnum=True
                            )[0].split(":")
                            long_name = cmds.attributeQuery(
                                enum_attr, node=object, niceName=True
                            )
                            if any(c.isalnum() for c in enum_values):
                                if enum_attr not in spaceswitch_enum_dictionary.keys():
                                    spaceswitch_enum_dictionary[enum_attr] = {
                                        "objects": {},
                                        "long": long_name,
                                    }
                                if (
                                    object
                                    not in spaceswitch_enum_dictionary[enum_attr].keys()
                                ):
                                    spaceswitch_enum_dictionary[enum_attr]["objects"][
                                        object
                                    ] = {"enum": [], "marked": [], "current": []}
                                for value in enum_values:
                                    spaceswitch_enum_dictionary[enum_attr]["objects"][
                                        object
                                    ]["enum"].append(value)
                                keys = (
                                    cmds.keyframe(
                                        f"{object}.{enum_attr}",
                                        query=True,
                                        valueChange=True,
                                    )
                                    or []
                                )
                                spaceswitch_enum_dictionary[enum_attr]["objects"][
                                    object
                                ]["marked"] = list(set([int(x) for x in keys])) or [
                                    cmds.getAttr(f"{object}.{enum_attr}")
                                ]
                                spaceswitch_enum_dictionary[enum_attr]["objects"][
                                    object
                                ]["current"] = cmds.getAttr(f"{object}.{enum_attr}")

                        # Si es rotateOrder, analizamos gimbal
                        if enum_attr == "rotateOrder" and self.show_rotate_order:
                            gimbal_data = self.analyzer.analyze(object)
                            spaceswitch_enum_dictionary[enum_attr]["objects"][object][
                                "gimbal"
                            ] = gimbal_data

        return spaceswitch_enum_dictionary

    def refresh(self, timeChange=False, force=False, *args):
        if timeChange:
            return

        sel = self.getSelectedObj(long=False)
        if sorted(sel) != sorted(self.object_selection) or force:
            self.object_selection = sel
            self.selection_label.setHidden(False)

            try:
                self.clearlayout(self.enums_layout)
                if self.object_selection:
                    self.spaceswitch_enum_dictionary = self.getEnums()
                    if self.spaceswitch_enum_dictionary:
                        self.selection_label.setHidden(True)

                        for (
                            enum,
                            enum_objects_current,
                        ) in self.spaceswitch_enum_dictionary.items():
                            combobox_layout = QHBoxLayout()
                            unique_controls = list(
                                set(enum_objects_current["objects"].keys())
                            )
                            if len(unique_controls) == 1:
                                combobox_name = unique_controls[0]
                                combobox_name = combobox_name.split("|")[-1]
                                if ":" in combobox_name and not self.namespace_display:
                                    combobox_name = combobox_name.split(":")[-1]
                                if len(combobox_name) > 50:
                                    combobox_name = "..." + combobox_name[:50]
                            else:
                                combobox_name = f"({len(unique_controls)})"

                            control_target = QLabel(
                                "%s %s"
                                % (combobox_name, enum_objects_current["long"].title())
                            )
                            combobox_layout.addWidget(control_target)

                            combobox = self.set_combobox(
                                enum_objects_current["objects"]
                            )
                            combobox_layout.addWidget(combobox)

                            options_and_objects = {}
                            for obj, option in enum_objects_current["objects"].items():
                                for i, o in enumerate(option["enum"]):
                                    if o not in options_and_objects.keys():
                                        options_and_objects[o] = {"objects": []}
                                    options_and_objects[o]["objects"].append(obj)
                                    options_and_objects[o]["index"] = i

                            combobox.textActivated.connect(
                                lambda x,
                                enum=enum,
                                oo=options_and_objects: self.apply_changes(x, enum, oo)
                            )
                            self.enums_layout.insertLayout(0, combobox_layout)
            finally:
                self.adjustSize()

    def clearlayout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            if child.layout():
                self.clearlayout(child.layout())

    @staticmethod
    def do_xform(target, enum_attr, enum_value, xform=None):
        xform = xform or cmds.xform(target, q=True, ws=True, matrix=True)
        cmds.setAttr(("{}.{}").format(target, enum_attr), enum_value)
        cmds.xform(target, ws=True, matrix=xform)

    def multiple_frames(self, enum_attr, enum_value, keyframes):
        marker_widget = None

        try:
            # Color timeline
            timerange = [list(keyframes.keys())[0], list(keyframes.keys())[-1] + 1]
            if cmds.timeControl("timeControl1", q=1, rv=1):
                timerange = [
                    int(f) for f in cmds.timeControl("timeControl1", ra=1, q=True)
                ]

            if int(cmds.about(v=1)) >= 2024:
                cmds.playbackOptions(sv=False)

            marker_widget = Timeline(timerange)

            # Start Progress Bar
            gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
            bar_value = 1
            max_bar_value = len(keyframes.keys())
            cmds.progressBar(gMainProgressBar, e=True, bp=True, max=max_bar_value)

            dictionary_xforms = {}
            current_time = cmds.currentTime(q=True)
            for frame, targets in keyframes.items():
                cmds.currentTime(frame)
                dictionary_xforms[frame] = {}
                for t in targets:
                    dictionary_xforms[frame][t] = cmds.xform(
                        t, q=True, ws=True, matrix=True
                    )
                cmds.progressBar(
                    gMainProgressBar,
                    edit=True,
                    status="Saving Positions (%s/%s)..." % (bar_value, max_bar_value),
                    step=1,
                )
                bar_value += 1
            bar_value = 1
            cmds.progressBar(gMainProgressBar, e=True, ep=True)
            cmds.progressBar(gMainProgressBar, e=True, bp=True, max=max_bar_value)
            for frame, targets in dictionary_xforms.items():
                for target, xform in targets.items():
                    cmds.currentTime(frame)
                    self.do_xform(target, enum_attr, enum_value, xform)
                    cmds.progressBar(
                        gMainProgressBar,
                        edit=True,
                        status="Applying Positions (%s/%s)..."
                        % (bar_value, max_bar_value),
                        step=1,
                    )
                    bar_value += 1

            cmds.currentTime(current_time)
            cmds.progressBar(gMainProgressBar, e=True, ep=True)

        finally:
            if marker_widget:
                marker_widget.delete_marker()

    def apply_euler_filter(self, targets):
        anim_curves = []

        for target in targets:
            for attr in ["rx", "ry", "rz"]:
                attribute = f"{target}.{attr}"
                if cmds.objExists(attribute):
                    anim_curve = cmds.listConnections(
                        attribute, source=True, type="animCurve"
                    )
                    if anim_curve:
                        anim_curve = anim_curve[0]
                        if cmds.objExists(anim_curve):
                            anim_curves.append(anim_curve)

        anim_curves = list(set(anim_curves))
        cmds.filterCurve(*anim_curves)

    def apply_changes(self, enum_value, enum_attr, options_and_objects):
        all_frames_setting = self.all_frames
        if enum_attr == "rotateOrder":
            if " " in enum_value.strip():
                enum_value = enum_value.split(" ")[0]
            # Ignore all_frames = False when using rotateOrder, apply always to all frames
            all_frames_setting = True

        targets = options_and_objects[enum_value]["objects"]
        enum_index = options_and_objects[enum_value]["index"]

        cmds.undoInfo(openChunk=True)
        self._kill_script_jobs()

        cmds.refresh(suspend=True)

        timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
        current_frames = cmds.timeControl("timeControl1", q=True, ra=True)

        if not timeline_selection and not all_frames_setting:
            targets_with_keys = targets
            keyframes = current_frames
        else:
            keyframes = {
                k: [t for t in targets if k in cmds.keyframe(t, query=True) or []]
                for k in sorted(
                    set(sum([cmds.keyframe(t, query=True) or [] for t in targets], []))
                )
            }
            if timeline_selection:
                keyframes = {
                    k: v
                    for k, v in keyframes.items()
                    if current_frames[0] <= k <= current_frames[1]
                }

            targets_with_keys = list(
                set([object for _list in keyframes.values() for object in _list])
            )

        sorted_targets_with_keys = sorted(
            targets_with_keys, key=lambda x: x.count("|"), reverse=True
        )
        try:
            # Check if there == a timeline selection.
            if sorted_targets_with_keys:
                if type(keyframes) is dict:
                    self.multiple_frames(enum_attr, enum_index, keyframes)
                elif type(keyframes) is list:
                    cmds.currentTime(keyframes[0])
                    for target in sorted_targets_with_keys:
                        self.do_xform(target, enum_attr, enum_index)
            else:
                for target in sorted_targets_with_keys:
                    self.do_xform(target, enum_attr, enum_index)

            if self.euler_filter:
                self.apply_euler_filter(sorted_targets_with_keys)

        finally:
            cmds.refresh(suspend=False)
            self._add_script_jobs()
            self.refresh(force=True)

            cmds.undoInfo(closeChunk=True)

        cmds.showWindow("MayaWindow")

    # Check for Updates
    def check_for_updates(self, warning=True, *args):
        import json

        script_name = TITLE.lower()

        url = "https://raw.githubusercontent.com/Alehaaaa/mayascripts/main/version.json"

        if sys.version_info.major < 3:
            from urllib2 import urlopen  # type: ignore
        else:
            from urllib.request import urlopen

        try:
            response = urlopen(url, timeout=1)
        except Exception:
            if warning:
                om.MGlobal.displayWarning(SpaceSwitchDialog.NO_INTERNET)
            return
        content = response.read()

        if content:
            data = json.loads(content)
            script = data[script_name]

            version = str(script["version"])
            changelog = script["changelog"]

        def convert_list_to_string():
            result, sublst = [], []
            for item in changelog:
                if item:
                    sublst.append(str(item))
                else:
                    if sublst:
                        result.append(sublst)
                        sublst = []
            if sublst:
                result.append(sublst)
            result = result[:4]
            result.append(["is And more is"])
            return "\n\n".join(["\n".join(x) for x in result])

        if version > __version__:
            update_available = cmds.confirmDialog(
                title="New update for {0}!".format(TITLE),
                message="Version {0} available, you are using {1}\n\nChangelog:\n{2}".format(
                    version, self.VERSION, convert_list_to_string()
                ),
                messageAlign="center",
                button=["Install", "Close"],
                defaultButton="Install",
                cancelButton="Close",
            )
            if update_available == "Install":
                self._kill_script_jobs()
                self.deleteLater()
                cmds.evalDeferred(
                    "import aleha_tools.{} as spaceswitch;try:from importlib import reload;except ImportError:pass;reload(spaceswitch);spaceswitch.SpaceSwitchDialog.show();".format(
                        script_name
                    )
                )
        else:
            if warning:
                om.MGlobal.displayWarning("All up-to-date.")

    def coffee(self):
        credits_dialog = QMessageBox()
        # credits_dialog.setWindowFlags(self.windowFlags() & Qt.FramelessWindowHint)

        base64Data = "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"
        image_64_decode = decodebytes(base64Data.encode("utf-8"))
        image = QImage()
        image.loadFromData(image_64_decode, "JPG")
        pixmap = QPixmap(image).scaledToHeight(56, Qt.SmoothTransformation)
        credits_dialog.setIconPixmap(pixmap)
        credits_dialog.setWindowTitle("About")
        credits_dialog.setText(
            "Created by @" + ORG_NAME + "<br>"
            # ' - <a href=https://www.instagram.com/alejandro_anim><font color="white">Instagram</a><br>'
            'Visit my website - <a href=https://alehaaaa.github.io><font color="white">alehaaaa.github.io</a>'
            "<br><br>"
            "If you liked this tool,<br>"
            "you can send me some love!"
        )
        credits_dialog.setFixedSize(400, 300)
        credits_dialog.exec_()

    def rebuild_script_jobs(self, *args, **kwargs):
        # Close the dialog when a new scene == opened in Maya to avoid callback errors
        self._kill_script_jobs()
        self._add_script_jobs()

    def _add_script_jobs(self):
        cmds.scriptJob(event=["SelectionChanged", self.refresh])
        cmds.scriptJob(event=["timeChanged", self.refresh])

        cmds.scriptJob(event=["SceneOpened", self.rebuild_script_jobs])
        cmds.scriptJob(event=["Undo", self.refresh])

    def _kill_script_jobs(self):
        for j in cmds.scriptJob(listJobs=True):
            if "aleha_tools.spaceswitch" in j:
                if ":" not in j:
                    continue
                id = int(j.split(":")[0])
                cmds.scriptJob(kill=int(id))

    # ────────────────────────────────────────────────────────────────
    def _check_mouse_distance(self) -> None:
        if not self.isVisible() or not self._auto_timer_enabled:
            return

        cur_pos = QCursor.pos()
        rect = self.frameGeometry()

        dx = max(rect.left() - cur_pos.x(), 0, cur_pos.x() - rect.right())
        dy = max(rect.top() - cur_pos.y(), 0, cur_pos.y() - rect.bottom())

        if dx * dx + dy * dy > self.AUTO_CLOSE_DIST**2:
            self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.globalPos()
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

            if self._auto_timer_enabled:
                self._auto_timer.stop()
                self._auto_timer_enabled = False

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if not self._dragging:
                if (
                    event.globalPos() - self._drag_start_pos
                ).manhattanLength() > self._drag_threshold:
                    self._dragging = True

            if self._dragging:
                self.move(event.globalPos() - self._drag_pos)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_start_pos = None
            self._drag_pos = QPoint(0, 0)

            if self._frameless:
                self.setWindowFlags(self._base_flags)
                self.show()
                self._frameless = False

        super().mouseReleaseEvent(event)

    # ─────────────────────────  CLEAN-UP  ─────────────────────────────
    def closeEvent(self, event):
        if self._auto_timer.isActive():
            self._auto_timer.stop()
        self._kill_script_jobs()
        _MAIN_DICT["_SPACESWITCH_INSTANCE"] = None
        super().closeEvent(event)

        # self.deleteLater()
        # event.accept()  # Ensure the window closes properly


class GimbalAnalyzer:
    def __init__(self):
        self.rotation_orders = {
            "xyz": om.MEulerRotation.kXYZ,
            "yzx": om.MEulerRotation.kYZX,
            "zxy": om.MEulerRotation.kZXY,
            "xzy": om.MEulerRotation.kXZY,
            "yxz": om.MEulerRotation.kYXZ,
            "zyx": om.MEulerRotation.kZYX,
        }

    def radians_to_degrees(self, radians):
        return radians * (180 / math.pi)

    def get_middle_axis_value(self, rotation):
        return {
            om.MEulerRotation.kZXY: rotation.x,
            om.MEulerRotation.kZYX: rotation.y,
            om.MEulerRotation.kXZY: rotation.z,
            om.MEulerRotation.kXYZ: rotation.y,
            om.MEulerRotation.kYZX: rotation.z,
            om.MEulerRotation.kYXZ: rotation.x,
        }[rotation.order]

    def compute_gimbal_percentage(self, rotation):
        mid = self.radians_to_degrees(self.get_middle_axis_value(rotation))
        return int(abs(((mid + 90) % 180) - 90) / 90 * 100)

    def convert_order_string(self, s):
        return self.rotation_orders.get(s, om.MEulerRotation.kZYX)

    def get_rotation(self, obj):
        selectionList = om.MSelectionList()
        selectionList.add(obj)
        dagPath = selectionList.getDagPath(0)

        transform = om.MFnTransform(dagPath)
        return transform.rotation()

    def get_rotation_order_list(self, obj):
        if cmds.attributeQuery("rotateOrder", node=obj, exists=True):
            return cmds.attributeQuery("rotateOrder", node=obj, listEnum=True)[0].split(
                ":"
            )
        return []

    def compute_all_percentages(self, obj, order_list):
        rot = self.get_rotation(obj)
        percentages = []
        for order_str in order_list:
            reordered = om.MEulerRotation(rot.x, rot.y, rot.z)
            reordered.reorderIt(self.convert_order_string(order_str))
            percentages.append(self.compute_gimbal_percentage(reordered))
        return percentages

    def classify_percentages(self, percentages):
        labels = [""] * len(percentages)
        if not percentages:
            return labels

        if len(set(percentages)) == 1:
            return labels

        best = min(percentages)
        for i, val in enumerate(percentages):
            diff = val - best
            if diff == 0:
                labels[i] = "Best"
            elif diff <= 2:
                labels[i] = "Good"
            elif diff <= 6:
                labels[i] = "OK"
        return labels

    def analyze(self, obj):
        order_list = self.get_rotation_order_list(obj)
        if not order_list:
            return {}

        percentages = self.compute_all_percentages(obj, order_list)
        labels = self.classify_percentages(percentages)

        result = {}
        for i, order in enumerate(order_list):
            result[order] = {"percentage": percentages[i], "label": labels[i]}
        return result


class AutoPauseComboBox(QComboBox):
    """
    Combobox que pausa el temporizador de auto-cierre al abrir el popup
    y lo reanuda al cerrarlo (salvo que ya se hubiera desactivado para siempre
    porque el usuario movió la ventana).
    """

    def __init__(self, pause_cb, resume_cb, parent=None):
        super().__init__(parent)
        self._pause_cb = pause_cb
        self._resume_cb = resume_cb

    # -- se ejecuta justo antes de que Qt cree y muestre el popup -----
    def showPopup(self):
        if callable(self._pause_cb):
            self._pause_cb()
        super().showPopup()

    # -- se ejecuta cuando el popup desaparece ------------------------
    def hidePopup(self):
        super().hidePopup()
        if callable(self._resume_cb):
            self._resume_cb()


# Custom Delegate Class
class RightIconDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)  # Draw default text

        if index.data(Qt.UserRole):  # Check if current option
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(255, 255, 255, 170))
            painter.setPen(Qt.NoPen)

            size = 5  # Dot size
            x = option.rect.right() - size * 2  # Position far right
            y = option.rect.center().y() - size // 2  # Center vertically

            painter.drawEllipse(x, y, size, size)  # Draw round dot


class Timeline(QWidget):
    def __init__(
        self, timerange=None, color=(200, 120, 200), autodestroy=300, parent=None
    ):
        """
        Initializes the timeline marker.

        :param timerange: Tuple (start_frame, end_frame).
        :param color: Tuple (R, G, B | 0-255) default: purple.
        :param autodestroy: milliseconds before the marker == removed.
        """
        parent = parent or self.get_timeline()
        if not parent:
            return
        super().__init__(parent)

        self.timerange = timerange or [
            int(f) for f in cmds.timeControl("timeControl1", ra=1, q=True)
        ]
        if not self.timerange:
            return

        self.color = QColor(*color, 70)  # Adding alpha internally

        if parent:
            self.setGeometry(parent.rect())
            self.show()

            if autodestroy is not None:
                # Set up a timer to remove the marker after a autodestroy
                self.timer = QTimer(self)
                self.timer.setSingleShot(True)
                self.timer.timeout.connect(self.delete_marker)
                self.timer.start(autodestroy)  # Remove after `autodestroy` milliseconds

    @classmethod
    def get_timeline(cls):
        """Fetches the Maya timeline widget."""
        tline = mel.eval("$tmpVar=$gPlayBackSlider")
        ptr = (
            omui.MQtUtil.findControl(tline)
            or omui.MQtUtil.findLayout(tline)
            or omui.MQtUtil.findMenuItem(tline)
        )
        if ptr:
            return wrapInstance(int(ptr), QWidget)
        return None

    def paintEvent(self, event):
        """Handles painting the timeline marker on the playback slider."""
        if not self.timerange:
            return

        start = cmds.playbackOptions(q=True, minTime=True)
        end = cmds.playbackOptions(q=True, maxTime=True)
        total_width = self.width()
        step = (total_width - (total_width * 0.01)) / (end - start + 1)

        sframe, eframe = self.timerange
        eframe -= 1  # Adjust to be within range

        pos_start = (sframe - start) * step + (total_width * 0.005)
        pos_end = (eframe + 1 - start) * step + (total_width * 0.005)
        rect = QRectF(QPointF(pos_start, 0), QPointF(pos_end, self.height()))

        painter = QPainter(self)
        pen = QPen(self.color)
        pen.setWidth(step + step * 0.005)

        painter.setPen(pen)
        painter.fillRect(rect, QBrush(self.color))

    def delete_marker(self):
        """Removes the marker safely."""
        try:
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass


if __name__ == "__main__":
    SpaceSwitchDialog().showUI()
