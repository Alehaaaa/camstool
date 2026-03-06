#
#
#  Copy this file in your scripts directory:
#     %USERPROFILE%\Documents\maya\scripts
#
#  or in a speficic version:
#     %USERPROFILE%\Documents\maya\XXXX\scripts
#
#
#  Run as a DIALOG with:
#
#    import aleha_tools.spaceswitch as spaceswitch
#    spaceswitch.show()
#
#
#  Run as a POPUP with:
#
#    import aleha_tools.spaceswitch as spaceswitch
#    spaceswitch.popup()
#
#


# -*- coding: utf-8 -*-


import sys
import math

from maya import cmds
from maya import mel
from maya import OpenMaya as om
from maya import OpenMayaUI as omui

try:
    PYSIDE_VERSION = 2
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    from PySide2.QtCore import QSettings
    from shiboken2 import wrapInstance, isValid
except ImportError:
    PYSIDE_VERSION = 6
    from PySide6.QtCore import *  # type: ignore
    from PySide6.QtGui import *  # type: ignore
    from PySide6.QtWidgets import *  # type: ignore
    from PySide6.QtCore import QSettings  # type: ignore
    from shiboken6 import wrapInstance, isValid  # type: ignore

from aleha_tools import base_widgets
from aleha_tools import util
from aleha_tools import widgets

from importlib import reload

reload(base_widgets)
reload(util)
reload(widgets)

CONTEXTUAL_CURSOR = QCursor(QPixmap(":/rmbMenu.png"), hotX=11, hotY=8)
_MAIN_DICT = sys.modules["__main__"].__dict__


APPCONFIG = {
    "title": "SpaceSwitch",
    "version": "1.3.1",
    "org_name": "Alehaaaa",
}


# =================================================================================
# %% UI BASE CLASSES (MODULAR WRAPPER)
# =================================================================================


class Grip(QSizeGrip):
    """
    A custom QSizeGrip that signals the parent to pause auto-closing on resizing.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._parent_widget = parent
        self._start_geom = None

    def mousePressEvent(self, e):
        self._start_geom = self._parent_widget.geometry()
        self._parent_widget._pause_timer()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self._start_geom and self._parent_widget.geometry() != self._start_geom:
            self._parent_widget.showBottomBar()
        self._start_geom = None

    def eventFilter(self, obj, event):
        return False


class FloatingWidget(base_widgets.QFlatDialog):
    """
    A draggable, frameless, rounded widget wrapper.
    Can be instantiated as a temporary popup or a pinned window.
    """

    BORDER_RADIUS = 5
    AUTO_CLOSE_DIST = 10
    AUTO_CLOSE_PERIOD_MS = 300
    TEXT_COLOR = "#bbbbbb"

    def __init__(self, popup=False, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.FramelessWindowHint)

        self.setMinimumWidth(util.DPI(220))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._is_dragging = False
        self._drag_offset = QPoint()

        self._setup_ui()

        self._timer_enabled = popup
        self._timer_paused = False
        if self._timer_enabled:
            self._setup_timer()

    def _setup_ui(self):
        self.mainContent = QWidget(self)
        self.mainLayout = QVBoxLayout(self.mainContent)
        self.mainLayout.setContentsMargins(util.DPI(10), util.DPI(14), util.DPI(10), 0)
        self.mainLayout.setSpacing(4)

        self.root_layout.insertWidget(0, self.mainContent, 1)

        self.grip = Grip(self)
        self.grip.setCursor(Qt.SizeBDiagCursor)

    def paintEvent(self, event):
        if not self.isVisible():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#333333"))

        # Use drawRoundedRect for clean, all-around rounded corners
        rect = self.rect().adjusted(0, 0, 1, -2)
        r = self.BORDER_RADIUS
        p.drawRoundedRect(rect, r, r)

    def setBottomBar(self, *args, **kwargs):
        """Overrides QFlatDialog to manage bottom bar while allowing popup timer to persist."""
        super().setBottomBar(*args, **kwargs)

    def showBottomBar(self):
        """Disables auto-kill and adds a default close button if no bar exists."""
        if hasattr(self, "_refresh_footer"):
            self._refresh_footer()
        elif not self.bottomBar:
            self.setBottomBar(closeButton=True)
        self._disable_auto_kill()

    def place_near_cursor(self):
        self.resize(self.sizeHint())
        w, h = self.width(), self.height()
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        x = max(geo.left(), min(cursor_pos.x(), geo.right() - w))
        y = max(geo.top(), min(cursor_pos.y() - h // 2, geo.bottom() - h))
        self.move(x, y)

    def _check_mouse_distance_and_close(self):
        if not self._timer_enabled or not self.isVisible():
            return
        p, r = QCursor.pos(), self.frameGeometry()
        dx = max(r.left() - p.x(), 0, p.x() - r.right())
        dy = max(r.top() - p.y(), 0, p.y() - r.bottom())
        if (dx * dx + dy * dy) > (self.AUTO_CLOSE_DIST * self.AUTO_CLOSE_DIST):
            self.close()

    def resizeEvent(self, event):
        s = self.grip.sizeHint()
        self.grip.setFixedSize(s)
        self.grip.move(self.width() - s.width(), 0)
        self.grip.raise_()
        super().resizeEvent(event)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._is_dragging = True
            if PYSIDE_VERSION < 6:
                global_position = e.globalPos()
            else:
                global_position = e.globalPosition().toPoint()
            self._drag_offset = global_position - self.frameGeometry().topLeft()
            self._pause_timer()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._is_dragging and (e.buttons() & Qt.LeftButton):
            if PYSIDE_VERSION < 6:
                global_position = e.globalPos()
            else:
                global_position = e.globalPosition().toPoint()
            self.move(global_position - self._drag_offset)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            self.showBottomBar()
        super().mouseReleaseEvent(e)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.setInterval(self.AUTO_CLOSE_PERIOD_MS)
        self._timer.timeout.connect(self._check_mouse_distance_and_close)
        self._timer.start()

    def _enable_timer(self):
        if hasattr(self, "_timer") and self._timer:
            self._timer.start()
            self._timer_enabled = True

    def _pause_timer(self):
        if hasattr(self, "_timer") and self._timer:
            self._timer.stop()
            self._timer_enabled = False

    def _disable_auto_kill(self):
        if hasattr(self, "_timer") and self._timer:
            self._timer.stop()
            self._timer = None
        self._timer_enabled = None

    def closeEvent(self, e):
        self._disable_auto_kill()
        super().closeEvent(e)


class SetupTargetsDialog(FloatingWidget):
    def __init__(self, parent, objects_dict, on_close):
        super().__init__(popup=False, parent=parent)
        self.on_close = on_close

        if parent and hasattr(parent, "_pause_timer"):
            parent._pause_timer()

        self.objects_dict = objects_dict
        self._create_layouts()
        self.setBottomBar(
            [
                base_widgets.DialogButton(
                    "Add", callback=self._add_target, icon=util.return_icon_path("add"), highlight=True
                )
            ],
            closeButton=True,
        )

    def _add_target(self):
        for obj in cmds.ls(selection=True):
            self.targets_list.add_target(obj)

    def _create_layouts(self):
        title = QLabel("Xform targets")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 4px;")

        self.targets_list = TargetsList(self)
        self.targets_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        for target in list(self.objects_dict.keys()):
            self.targets_list.add_target(target)

        self.mainLayout.addWidget(title)
        self.mainLayout.addWidget(self.targets_list)

    def closeEvent(self, event):
        new_order = self.targets_list.backing_store

        new_dict = {}
        for t in new_order:
            new_dict[t] = self.objects_dict.get(t) or list(self.objects_dict.values())[0]

        self.objects_dict.clear()
        self.objects_dict.update(new_dict)

        if callable(self.on_close):
            self.on_close(self.objects_dict.keys())

        parent = self.parent()
        if parent and hasattr(parent, "_enable_timer"):
            parent._enable_timer()

        super().closeEvent(event)


class TargetItemWidget(QWidget):
    def __init__(self, name, list_ref):
        super().__init__()
        self.name = name
        self.list_ref = list_ref

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        label = QLabel(name.split(":")[-1])
        close_btn = QPushButton()
        base_widgets.HoverableIcon.apply(close_btn, util.return_icon_path("close"))

        close_btn.setIconSize(QSize(15, 15))
        close_btn.setFixedSize(10, 10)
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.clicked.connect(self._remove)
        close_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:pressed {
                background: #101010;
            }
            """)

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(close_btn)

    def _remove(self):
        self.list_ref.remove_target(self.name)


class TargetsList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.backing_store = []
        self.setStyleSheet("""
            QListWidget:focus {
                outline: none;
                border: none;
        }
        """)

    def add_target(self, name):
        if not cmds.objExists(name) or name in self.backing_store:
            return

        self.backing_store.append(name)

        item = QListWidgetItem()
        # item.setFlags(Qt.NoItemFlags)
        widget = TargetItemWidget(name, self)

        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

    def remove_target(self, name):
        if name in self.backing_store:
            self.backing_store.remove(name)

        for i in range(self.count()):
            if self.itemWidget(self.item(i)).name == name:
                self.takeItem(i)
                break


class AutoPauseComboBox(QComboBox):
    """
    A ComboBox that pauses the auto-close timer when the popup is opened
    """

    def __init__(self, pause_cb, resume_cb, parent=None):
        super().__init__(parent)
        self._pause_cb = pause_cb
        self._resume_cb = resume_cb

    def showPopup(self):
        if callable(self._pause_cb):
            self._pause_cb()
        super().showPopup()

    def hidePopup(self):
        super().hidePopup()
        if callable(self._resume_cb):
            self._resume_cb()


# Custom Delegate Class
class RightIconDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        if index.data(Qt.UserRole):
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(255, 255, 255, 170))
            painter.setPen(Qt.NoPen)

            dot_size = 5  # Dot size
            x = option.rect.right() - dot_size * 2
            y = option.rect.center().y() - dot_size // 2

            painter.drawEllipse(x, y, dot_size, dot_size)


class Timeline(QWidget):
    def __init__(self, timerange=None, color=(200, 120, 200), autodestroy=300, parent=None):
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

        self.timerange = timerange or [int(f) for f in cmds.timeControl("timeControl1", ra=1, q=True)]
        if not self.timerange:
            return

        args = list(color) + [70]
        self.color = QColor(*args)

        if parent:
            self.setGeometry(parent.rect())
            self.show()

            if autodestroy is not None:
                # Set up a timer to remove the marker
                self.timer = QTimer(self)
                self.timer.setSingleShot(True)
                self.timer.timeout.connect(self.delete_marker)
                self.timer.start(autodestroy)

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


# =================================================================================
# %% APPLICATION IMPLEMENTATION (SPACE SWITCH)
# =================================================================================


def get_maya_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    if not main_window_ptr:
        return None
    return wrapInstance(int(main_window_ptr), QMainWindow)


class CallbackManager:
    def __init__(self):
        self.ids = []

    def add(self, cb_id):
        self.ids.append(cb_id)

    def clear(self):
        for i in self.ids:
            try:
                om.MMessage.removeCallback(i)
            except Exception:
                pass
        del self.ids[:]


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
        return radians * (180.0 / math.pi)

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

    def _safe_get_depend_node(self, sel_list, index=0):
        """Supports API 2.0 and classic API calling styles."""
        try:
            # API 2.0
            return sel_list.getDependNode(index)
        except TypeError:
            # Classic API signature: getDependNode(index, MObject)
            mobj = om.MObject()
            sel_list.getDependNode(index, mobj)  # type: ignore[arg-type]
            return mobj

    def get_rotation(self, obj):
        sel = om.MSelectionList()
        sel.add(obj)
        node = self._safe_get_depend_node(sel, 0)
        tfm = om.MFnTransform(node)
        return tfm.rotation()  # MEulerRotation (radians)

    def get_rotation_order_list(self, obj):
        if cmds.attributeQuery("rotateOrder", node=obj, exists=True):
            return cmds.attributeQuery("rotateOrder", node=obj, listEnum=True)[0].split(":")
        return []

    def _rotation_at_time(self, obj, t, order_list):
        """Get MEulerRotation at time t WITHOUT changing current time or UI."""
        rx = cmds.getAttr("%s.rotateX" % obj, time=t)
        ry = cmds.getAttr("%s.rotateY" % obj, time=t)
        rz = cmds.getAttr("%s.rotateZ" % obj, time=t)
        idx = int(cmds.getAttr("%s.rotateOrder" % obj, time=t))
        idx = max(0, min(idx, len(order_list) - 1)) if order_list else 0
        current_order_str = order_list[idx] if order_list else "xyz"

        return om.MEulerRotation(
            math.radians(rx or 0.0),
            math.radians(ry or 0.0),
            math.radians(rz or 0.0),
            self.convert_order_string(current_order_str),
        )

    def compute_all_percentages(self, obj, order_list):
        """
        Worst-case gimbal % per order across ALL keyed frames (or current time if unkeyed),
        without pausing OGS or touching the timeline.
        """
        key_times = set()
        for attr in ("rotateX", "rotateY", "rotateZ"):
            k = cmds.keyframe(obj, attribute=attr, query=True, timeChange=True)
            if k:
                key_times.update(k)
        if not key_times:
            key_times = {cmds.currentTime(query=True)}

        key_times = sorted(key_times)

        percentages = []
        for target_order_str in order_list:
            target_order = self.convert_order_string(target_order_str)
            worst = 0
            for t in key_times:
                rot_t = self._rotation_at_time(obj, t, order_list)
                # copy before reordering
                reordered = om.MEulerRotation(rot_t.x, rot_t.y, rot_t.z, rot_t.order)
                reordered.reorderIt(target_order)
                g = self.compute_gimbal_percentage(reordered)
                if g > worst:
                    worst = g
            percentages.append(worst)
        return percentages

    def classify_percentages(self, percentages):
        labels = [""] * len(percentages)
        if not percentages or len(set(percentages)) == 1:
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
        """
        Returns:
          {
            "xyz": {"percentage": 12, "label": "Good"},
            "yzx": {"percentage": 10, "label": "Best"},
            ...
          }
        """
        order_list = self.get_rotation_order_list(obj)
        if not order_list:
            return {}

        percentages = self.compute_all_percentages(obj, order_list)
        labels = self.classify_percentages(percentages)

        result = {}
        for i, order in enumerate(order_list):
            result[order] = {"percentage": percentages[i], "label": labels[i]}
        return result


class SpaceSwitchAlehaWidget(FloatingWidget):
    """
    Messages:
    """

    NO_INTERNET = "Could not establish a connection to the server."
    WORKING_ON_IT = "Still working on this feature!"

    """
    The main widget for the Space Switch tool, now with configurable modes.
    """

    def __init__(self, popup=False, parent=get_maya_window()):
        super().__init__(popup=popup, parent=parent)

        self.setWindowTitle("%s %s" % (APPCONFIG.get("title"), APPCONFIG.get("version")))

        self.settings = QSettings(APPCONFIG.get("org_name"), APPCONFIG.get("title"))
        self.instance_settings()

        self.analyzer = GimbalAnalyzer()
        self._cb = CallbackManager()

        self._create_layouts()
        self._create_selection_layout()
        self._add_callbacks()

        self.comboboxes = {}
        self.last_selection = []

        self.refresh()

    def _refresh_footer(self):
        """Updates the interaction bar based on whether valid switches exist."""
        buttons = []
        if self.comboboxes:
            buttons.append(
                base_widgets.DialogButton(
                    "Apply",
                    callback=self.apply,
                    icon=util.return_icon_path("apply"),
                    highlight=True,
                )
            )

        # Show Close only if not in popup mode (pinned)
        should_close = not self._timer_enabled
        self.setBottomBar(buttons=buttons, closeButton=should_close)

    def apply(self):
        """Commits all currently selected enum values to the scene."""
        for (enum_attr, _), (combobox, options_and_objects) in self.comboboxes.items():
            enum_value = combobox.currentText().split(" (")[0]
            self.apply_changes(enum_value, enum_attr, options_and_objects)

    def instance_settings(self):
        self.namespace_display = self.__fix_setting(self.settings.value("namespace_display", False))
        self.all_frames = self.__fix_setting(self.settings.value("all_frames", False))

        self.euler_filter = self.__fix_setting(self.settings.value("euler_filter", True))
        self.show_rotate_order = self.__fix_setting(self.settings.value("show_rotate_order", True))

    @staticmethod
    def __fix_setting(setting):
        if isinstance(setting, bool):
            return setting
        elif isinstance(setting, int):
            return bool(setting)
        elif isinstance(setting, str):
            return setting.lower() == "true"
        else:
            return False

    def _show_context_menu(self, pos):
        self.context_menu = QMenu(self)
        self.context_menu.aboutToShow.connect(self._pause_timer)
        self.context_menu.aboutToHide.connect(self._enable_timer)

        self.toggle_namespaces_action = self.context_menu.addAction("Show namespaces")
        self.toggle_namespaces_action.setCheckable(True)
        self.toggle_namespaces_action.setChecked(self.namespace_display)

        self.show_rotate_order_action = self.context_menu.addAction("Enable Rotate Order")
        self.show_rotate_order_action.setCheckable(True)
        self.show_rotate_order_action.setChecked(self.show_rotate_order)

        self.context_menu.addSeparator()

        self.euler_filter_action = self.context_menu.addAction("Auto Euler Filter")
        self.euler_filter_action.setCheckable(True)
        self.euler_filter_action.setChecked(self.euler_filter)

        self.all_frames_action = self.context_menu.addAction("Apply to all frames")
        self.all_frames_action.setCheckable(True)
        self.all_frames_action.setChecked(self.all_frames)

        self.context_menu.addSeparator()

        self.check_updates_action = self.context_menu.addAction("Check for updates")
        self.check_updates_action.setVisible(False)
        self.context_menu.addSeparator()
        self.credits_action = self.context_menu.addAction("Credits")

        self.check_updates_action.triggered.connect(self.check_for_updates)
        self.credits_action.triggered.connect(self.coffee)

        self.show_rotate_order_action.toggled.connect(
            lambda state: self.set_setting("show_rotate_order", state, refresh=True)
        )
        self.toggle_namespaces_action.toggled.connect(
            lambda state: self.set_setting("namespace_display", state, refresh=True)
        )
        self.euler_filter_action.toggled.connect(lambda state: self.set_setting("euler_filter", state))
        self.all_frames_action.toggled.connect(lambda state: self.set_setting("all_frames", state))

        exec_fn = getattr(self.context_menu, "exec", None) or getattr(self.context_menu, "exec_", None)
        exec_fn(QCursor.pos())

    def set_setting(self, setting, state, refresh=False):
        self.settings.setValue(setting, state)
        setattr(self, setting, state)

        if refresh:
            self.refresh(force=True)

    def _create_layouts(self):
        # Main content widget that holds layouts
        self.mainContent.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mainContent.customContextMenuRequested.connect(self._show_context_menu)

        self.enums_layout = QVBoxLayout()
        self.enums_layout.setSpacing(2)
        self.mainLayout.addLayout(self.enums_layout)

    def _create_selection_layout(self):
        selection_layout = QVBoxLayout()
        selection_layout.setSpacing(0)

        selection_title = QLabel("Selection")
        selection_title.setStyleSheet(
            "font-size: %spx; color: %s; font-weight: bold; background: transparent;"
            % (util.DPI(18), self.TEXT_COLOR)
        )
        selection_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        selection_title.setWordWrap(False)
        selection_title.setFixedHeight(selection_title.fontMetrics().height() + 2)

        self.selection_label = QLabel("No switches for selection")
        self.selection_label.setFixedHeight(util.DPI(30))
        self.selection_label.setStyleSheet("color: %s; background: transparent;" % self.TEXT_COLOR)

        selection_layout.addWidget(selection_title)
        selection_layout.addWidget(self.selection_label)

        self.mainLayout.insertLayout(0, selection_layout)

    def _add_callbacks(self):
        try:
            self._cb.add(om.MEventMessage.addEventCallback("SelectionChanged", self.refresh))
            self._cb.add(om.MEventMessage.addEventCallback("timeChanged", self.refresh))
            self._cb.add(om.MEventMessage.addEventCallback("Undo", self.refresh))

            self._cb.add(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, self._refresh_callbacks))
        except Exception as e:
            cmds.warning("Could not add Maya callbacks: %s" % e)

    def _remove_callbacks(self):
        try:
            self._cb.clear()
        except Exception as e:
            cmds.warning("Could not remove Maya callbacks: %s" % e)

    def _refresh_callbacks(self, *args):
        self._remove_callbacks()
        self._add_callbacks()

    def getSelectedObj(self, long=False):
        return cmds.ls(selection=True, long=long)

    # Main Function to Set the ComboBox
    def set_combobox(self, enum_objects):
        combobox = AutoPauseComboBox(self._pause_timer, self._enable_timer, parent=self)
        combobox.setMaxVisibleItems(60)
        combobox.setItemDelegate(RightIconDelegate(combobox))

        seen = set()
        marked = {item for obj in enum_objects.values() for item in obj.get("marked", [])}
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
            display_text = "%s (%s)" % (enum_value, label) if label else enum_value

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

        def _is_connected(node, attr):
            plug = "%s.%s" % (node, attr)
            try:
                if cmds.connectionInfo(plug, isDestination=True) or cmds.connectionInfo(plug, isSource=True):
                    return True
                return bool(cmds.listConnections(plug, s=True, d=True, plugs=True) or [])
            except Exception:
                return False

        for object in self.last_selection:
            if object in spaceswitch_enum_dictionary.keys():
                continue

            # Only user-defined attrs (excludes Maya defaults), but allow rotateOrder if requested
            orderedAttrs = cmds.listAttr(object, ud=True) or []
            if self.show_rotate_order and cmds.attributeQuery("rotateOrder", node=object, exists=True):
                if "rotateOrder" not in orderedAttrs:
                    orderedAttrs.append("rotateOrder")

            if orderedAttrs:
                for enum_attr in orderedAttrs:
                    try:
                        attrType = cmds.attributeQuery(enum_attr, node=object, attributeType=True)
                    except Exception:
                        continue
                    if attrType != "enum":
                        continue

                    raw = cmds.attributeQuery(enum_attr, node=object, listEnum=True) or []
                    if not raw:
                        continue

                    # Clean labels: strip '=NNN', trim, drop placeholders (no alphanumerics)
                    enum_values_raw = raw[0].split(":")
                    enum_values_clean = []
                    for v in enum_values_raw:
                        label = v.split("=", 1)[0].strip()
                        if any(c.isalnum() for c in label):
                            enum_values_clean.append(label)

                    # Keep only enums with multiple meaningful options
                    if len(set(enum_values_clean)) < 2:
                        continue

                    # Must be connected to something (unless it's rotateOrder)
                    if enum_attr != "rotateOrder" and not _is_connected(object, enum_attr):
                        continue

                    long_name = cmds.attributeQuery(enum_attr, node=object, niceName=True)

                    if enum_attr not in spaceswitch_enum_dictionary.keys():
                        spaceswitch_enum_dictionary[enum_attr] = {
                            "objects": {},
                            "long": long_name,
                        }

                    if object not in spaceswitch_enum_dictionary[enum_attr]["objects"].keys():
                        spaceswitch_enum_dictionary[enum_attr]["objects"][object] = {
                            "enum": [],
                            "marked": [],
                            "current": [],
                        }

                    # Save options
                    spaceswitch_enum_dictionary[enum_attr]["objects"][object]["enum"].extend(
                        enum_values_clean
                    )

                    # Keyed values and current
                    keys = cmds.keyframe("%s.%s" % (object, enum_attr), query=True, valueChange=True) or []
                    spaceswitch_enum_dictionary[enum_attr]["objects"][object]["marked"] = list(
                        set(int(x) for x in keys)
                    ) or [cmds.getAttr("%s.%s" % (object, enum_attr))]
                    spaceswitch_enum_dictionary[enum_attr]["objects"][object]["current"] = cmds.getAttr(
                        "%s.%s" % (object, enum_attr)
                    )

                    # If it's rotateOrder and requested, analyze gimbal
                    if enum_attr == "rotateOrder" and self.show_rotate_order:
                        gimbal_data = self.analyzer.analyze(object)
                        spaceswitch_enum_dictionary[enum_attr]["objects"][object]["gimbal"] = gimbal_data

        return spaceswitch_enum_dictionary

    def refresh(self, timeChange=False, force=False, *args):
        if timeChange:
            return

        sel = self.getSelectedObj(long=False)
        if sorted(sel) != sorted(self.last_selection) or force:
            self.last_selection = sel
            if not self.selection_label.isVisible():
                self.selection_label.setVisible(True)

            try:
                self.clearlayout(self.enums_layout)
                self.comboboxes.clear()
                if self.last_selection:
                    self.spaceswitch_enum_dictionary = self.getEnums()
                    if self.spaceswitch_enum_dictionary:
                        self.selection_label.setVisible(False)

                        for enum, data in self.spaceswitch_enum_dictionary.items():
                            unique_controls = sorted(data["objects"].keys())
                            name = self._format_object_name(unique_controls)

                            control_target = QLabel("%s %s" % (name, data["long"].title()))
                            control_target.setCursor(CONTEXTUAL_CURSOR)
                            control_target.setToolTip(self.formatXformTooltipObjects(unique_controls))
                            control_target.setContextMenuPolicy(Qt.CustomContextMenu)
                            control_target.customContextMenuRequested.connect(
                                lambda pos, s=control_target, d=data: self._show_change_target_dialog(s, d)
                            )

                            combobox = self.set_combobox(data["objects"])
                            options_map = self._build_options_map(data["objects"])

                            self.comboboxes[(enum, tuple(unique_controls))] = (combobox, options_map)

                            row = QHBoxLayout()
                            row.setContentsMargins(0, 0, 0, 0)
                            row.setSpacing(4)
                            row.addWidget(control_target)
                            row.addWidget(combobox)
                            self.enums_layout.insertLayout(0, row)
                self._refresh_footer()

            except Exception as e:
                cmds.warning("Error adding buttons: %s" % e)
            finally:
                self.setMinimumHeight(0)
                self.resize(self.width(), 0)
                self.adjustSize()

    def _format_object_name(self, objects):
        """Returns a human-friendly string for one or multiple objects."""
        if not objects:
            return ""
        if len(objects) == 1:
            name = objects[0].split("|")[-1]
            if ":" in name and not self.namespace_display:
                name = name.split(":")[-1]
            return ("..." + name[:50]) if len(name) > 50 else name
        return "(%s)" % len(objects)

    def _build_options_map(self, objects_data):
        """Constructs a mapping of enum options to their respective object target sets."""
        options_map = {}
        for obj, opt in objects_data.items():
            for i, o in enumerate(opt["enum"]):
                entry = options_map.setdefault(o, {"objects": [], "index": i})
                entry["objects"].append(obj)
        return options_map

    def _show_change_target_dialog(self, sender, data):
        selection = self.getSelectedObj(long=False)

        def on_close(objects):
            cmds.select(selection, replace=True)
            self._add_callbacks()
            sender.setToolTip(self.formatXformTooltipObjects(objects))

        objects_dict = data["objects"]
        self._remove_callbacks()
        dlg = SetupTargetsDialog(self, objects_dict, on_close=on_close)
        dlg.show()

    @staticmethod
    def formatXformTooltipObjects(objects):
        return (
            "<html>"
            "Current xform target/s:<br>"
            "%s"
            "<br><br><b>Right-click to modify...</b>"
            "</html>" % "<br>".join(objects)
        )

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
                timerange = [int(f) for f in cmds.timeControl("timeControl1", ra=1, q=True)]

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
                    dictionary_xforms[frame][t] = cmds.xform(t, q=True, ws=True, matrix=True)
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
                        status="Applying Positions (%s/%s)..." % (bar_value, max_bar_value),
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
                attribute = "%s.%s" % (target, attr)
                if cmds.objExists(attribute):
                    anim_curve = cmds.listConnections(attribute, source=True, type="animCurve")
                    if anim_curve:
                        anim_curve = anim_curve[0]
                        if cmds.objExists(anim_curve):
                            anim_curves.append(anim_curve)

        anim_curves = list(set(anim_curves))
        cmds.filterCurve(*anim_curves)

    @staticmethod
    def _collect_keyframes(targets, all_frames, timeline_selection, current_frames):
        if not timeline_selection and not all_frames:
            return targets, [cmds.currentTime(query=True)]

        # Gather all keyframes across targets
        all_keys = set(sum([cmds.keyframe(t, query=True) or [] for t in targets], []))

        keyframes = {
            frame: [t for t in targets if frame in (cmds.keyframe(t, query=True) or [])]
            for frame in sorted(all_keys)
        }

        # Restrict to timeline selection range if active
        if timeline_selection:
            keyframes = {
                f: objs for f, objs in keyframes.items() if current_frames[0] <= f <= current_frames[1]
            }

        return keyframes

    def apply_changes(self, enum_value, enum_attr, options_and_objects):
        all_frames_setting = self.all_frames

        # Special case: rotateOrder always applies to all frames
        if enum_attr == "rotateOrder":
            if " " in enum_value.strip():
                enum_value = enum_value.split(" ")[0]
            all_frames_setting = True

        targets = options_and_objects[enum_value]["objects"]
        enum_index = options_and_objects[enum_value]["index"]

        cmds.undoInfo(openChunk=True)
        cmds.refresh(suspend=True)
        self._remove_callbacks()

        # Save temporary keys
        temp_keyframes = {}

        timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
        current_frames = cmds.timeControl("timeControl1", q=True, ra=True)

        keyframes = self._collect_keyframes(targets, all_frames_setting, timeline_selection, current_frames)

        sorted_targets = sorted(targets, key=lambda x: x.count("|"), reverse=True)

        try:
            if sorted_targets:
                # Case 1: dict \u2192 multiple frames
                if isinstance(keyframes, dict) and keyframes:
                    self.multiple_frames(enum_attr, enum_index, keyframes)

                # Case 2: list \u2192 single frame
                elif isinstance(keyframes, list) and keyframes:
                    cmds.currentTime(keyframes[0])
                    for target in sorted_targets:
                        self.do_xform(target, enum_attr, enum_index)

                # Case 3: no explicit keys \u2192 create temp key only if attr has none
                else:
                    current_time = cmds.currentTime(query=True)
                    for target in sorted_targets:
                        attr_plug = "%s.%s" % (target, enum_attr)
                        existing_keys = cmds.keyframe(attr_plug, query=True, keyframeCount=True) or 0

                        if existing_keys == 0:
                            temp_keyframes.setdefault(target, {}).setdefault(enum_attr, []).append(
                                current_time
                            )
                            cmds.keyframe(attr_plug)

                        self.do_xform(target, enum_attr, enum_index)

            if self.euler_filter:
                self.apply_euler_filter(sorted_targets)

        finally:
            cmds.refresh(suspend=False)

            # Remove temporary keys if created
            for target, attributes in temp_keyframes.items():
                for attr, keys in attributes.items():
                    for frame in keys:
                        cmds.cutKey("%s.%s" % (target, attr), time=(frame,))

            self._add_callbacks()
            self.refresh(force=True)
            cmds.undoInfo(closeChunk=True)

        cmds.showWindow("MayaWindow")

    # Check for Updates
    def check_for_updates(self, warning=True, *args):
        import json

        script_name = APPCONFIG.get("title").lower()

        url = "https://raw.githubusercontent.com/Alehaaaa/mayascripts/main/version.json"

        if PYSIDE_VERSION < 6:
            from urllib2 import urlopen  # type: ignore
        else:
            from urllib.request import urlopen

        try:
            response = urlopen(url, timeout=1)
        except Exception:
            if warning:
                om.MGlobal.displayWarning(SpaceSwitchAlehaWidget.NO_INTERNET)
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

        if version > APPCONFIG.get("version"):
            update_available = cmds.confirmDialog(
                title="New update for {0}!".format(APPCONFIG.get("title")),
                message="Version {0} available, you are using {1}\n\nChangelog:\n{2}".format(
                    version, self.VERSION, convert_list_to_string()
                ),
                messageAlign="center",
                button=["Install", "Close"],
                defaultButton="Install",
                cancelButton="Close",
            )
            if update_available == "Install":
                self._cb.clear()
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
        widgets.Coffee.showUI(self)

    def closeEvent(self, e):
        self._cb.clear()
        super().closeEvent(e)
        self.deleteLater()


class SpaceSwitchManager:
    """
    Manages the creation and display of the SpaceSwitchAlehaWidget instance.
    """

    @classmethod
    def _launch(cls, popup):
        dlg = _MAIN_DICT.get("_SPACESWITCH_INSTANCE")
        if dlg is not None and isValid(dlg):
            try:
                dlg._cb.clear()
                dlg.close()
            finally:
                dlg = None

        if not (dlg is not None and isValid(dlg)):
            dlg = SpaceSwitchAlehaWidget(popup=popup)
            _MAIN_DICT["_SPACESWITCH_INSTANCE"] = dlg

        if popup == True:
            dlg.place_near_cursor()

        if dlg.isHidden():
            dlg.show()
        else:
            dlg.raise_()
            dlg.activateWindow()

    @classmethod
    def popup(cls):
        """Launches the tool as a temporary popup near the cursor with auto-close enabled."""
        cls._launch(popup=True)

    @classmethod
    def show(cls):
        """Launches the tool as a persistent window with the bottom bar visible."""
        cls._launch(popup=False)


def show():
    SpaceSwitchManager.show()


def popup():
    SpaceSwitchManager.popup()
