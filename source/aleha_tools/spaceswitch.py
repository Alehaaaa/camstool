from __future__ import division
# -*- coding: utf-8 -*-

import ast
import math
import sys

from maya import cmds, mel
from maya import OpenMaya as om
from maya import OpenMayaUI as omui

try:
    PYSIDE_VERSION = 6
    from PySide6.QtWidgets import (
        QWidget,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QFrame,
        QVBoxLayout,
        QSizePolicy,
        QSizeGrip,
        QListWidget,
        QListWidgetItem,
        QGraphicsOpacityEffect,
    )
    from PySide6.QtGui import (
        QIcon,
        QPainter,
        QColor,
        QCursor,
        QPixmap,
        QPen,
        QPolygonF,
        QGuiApplication,
        QBrush,
    )
    from PySide6.QtCore import Qt, QPointF, QPoint, QTimer, QSettings, QSize, QRectF
except ImportError:
    PYSIDE_VERSION = 2
    from PySide2.QtWidgets import (
        QWidget,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QFrame,
        QVBoxLayout,
        QSizePolicy,
        QSizeGrip,
        QListWidget,
        QListWidgetItem,
        QGraphicsOpacityEffect,
    )
    from PySide2.QtGui import (
        QIcon,
        QPainter,
        QColor,
        QCursor,
        QPixmap,
        QPen,
        QPolygonF,
        QGuiApplication,
        QBrush,
    )
    from PySide2.QtCore import Qt, QPointF, QPoint, QTimer, QSettings, QSize, QRectF

import aleha_tools
from aleha_tools import base_widgets, util, widgets

try:
    from importlib import reload
except ImportError:
    reload = None


DEBUG_RELOAD = False

if DEBUG_RELOAD and reload:
    reload(aleha_tools)
    reload(base_widgets)
    reload(util)
    reload(widgets)


_MAIN_DICT = sys.modules["__main__"].__dict__

DATA = {
    "TOOL": "SpaceSwitch",
    "VERSION": "2.2.0",
}
DATA["AUTHOR"] = aleha_tools.DATA["AUTHOR"]

COLOR_BG_MAIN = "#101010"
COLOR_BG_POPUP = "#444444"
COLOR_BG_TRACK = "#333333"
COLOR_ACCENT_DARK = "#7f4a77"
COLOR_ACCENT_MAIN = "#d384ca"
COLOR_ACCENT_LIGHT = "#e59ed0"
COLOR_ACCENT_HOVER = "#e688da"
COLOR_ACCENT_WHITE = "#f2c3ed"
COLOR_TEXT_MAIN = "#2a2a2a"
COLOR_TEXT_SECONDARY = "#bbbbbb"
COLOR_BLEND_MULTI = "#584655"


class Qtx(object):
    @staticmethod
    def global_pos(event):
        if PYSIDE_VERSION < 6:
            return event.globalPos()
        return event.globalPosition().toPoint()

    @staticmethod
    def local_x(event):
        if PYSIDE_VERSION < 6:
            return int(event.x())
        return int(event.position().x())

    @staticmethod
    def exec_menu(menu, pos):
        fn = getattr(menu, "exec", None) or getattr(menu, "exec_", None)
        if fn:
            return fn(pos)
        return None


class Maya(object):
    @staticmethod
    def exists(node):
        try:
            return bool(node and cmds.objExists(node))
        except Exception:
            return False

    @staticmethod
    def plug(node, attr):
        return "%s.%s" % (node, attr)

    @staticmethod
    def attr_exists(node, attr):
        try:
            return cmds.objExists(Maya.plug(node, attr))
        except Exception:
            return False

    @staticmethod
    def is_referenced(node):
        try:
            return cmds.referenceQuery(node, isNodeReferenced=True)
        except Exception:
            return False

    @staticmethod
    def reference_namespace(node):
        try:
            return cmds.referenceQuery(node, namespace=True).strip(":")
        except Exception:
            return ""

    @staticmethod
    def attr_type(node, attr, default=None):
        try:
            return cmds.attributeQuery(attr, node=node, attributeType=True)
        except Exception:
            return default

    @staticmethod
    def nice_name(node, attr):
        try:
            return cmds.attributeQuery(attr, node=node, niceName=True)
        except Exception:
            return attr

    @staticmethod
    def enum_labels(node, attr):
        try:
            raw = cmds.attributeQuery(attr, node=node, listEnum=True) or []
            if not raw:
                return []

            result = []
            for value in raw[0].split(":"):
                label = value.split("=", 1)[0].strip()
                if any(c.isalnum() for c in label):
                    result.append(label)

            return result
        except Exception:
            return []

    @staticmethod
    def get_float(node, attr, default=0.0):
        try:
            return float(cmds.getAttr(Maya.plug(node, attr)))
        except Exception:
            return float(default)

    @staticmethod
    def numeric_range(node, attr, attr_type):
        if attr_type == "bool":
            return 0.0, 1.0

        try:
            if not cmds.attributeQuery(attr, node=node, minExists=True):
                return None
            if not cmds.attributeQuery(attr, node=node, maxExists=True):
                return None

            mn = cmds.attributeQuery(attr, node=node, minimum=True)[0]
            mx = cmds.attributeQuery(attr, node=node, maximum=True)[0]
            return float(mn), float(mx)
        except Exception:
            return None

    @staticmethod
    def keyed_values(node, attr, fallback=None):
        try:
            values = cmds.keyframe(Maya.plug(node, attr), query=True, valueChange=True) or []
            values = sorted(set(float(v) for v in values))
            if values:
                return values
        except Exception:
            pass

        if fallback is None:
            fallback = Maya.get_float(node, attr)

        return [float(fallback)]

    @staticmethod
    def key_times_for_plug(plug):
        try:
            return set(cmds.keyframe(plug, query=True, timeChange=True) or [])
        except Exception:
            return set()

    @staticmethod
    def key_times_for_node(node):
        try:
            return set(cmds.keyframe(node, query=True, timeChange=True) or [])
        except Exception:
            return set()

    @staticmethod
    def connected(node, attr):
        plug = Maya.plug(node, attr)
        try:
            if cmds.connectionInfo(plug, isDestination=True):
                return True
            if cmds.connectionInfo(plug, isSource=True):
                return True
            return bool(cmds.listConnections(plug, s=True, d=True, plugs=True) or [])
        except Exception:
            return False

    @staticmethod
    def selection(long=False):
        try:
            return cmds.ls(selection=True, long=long) or []
        except Exception:
            return []

    @staticmethod
    def matrix(node):
        return cmds.xform(node, q=True, ws=True, matrix=True)

    @staticmethod
    def set_matrix(node, matrix):
        cmds.xform(node, ws=True, matrix=matrix)


class UndoChunk(object):
    def __init__(self, name="SpaceSwitch"):
        self.name = name
        self.opened = False

    def __enter__(self):
        cmds.undoInfo(openChunk=True, chunkName=self.name)
        self.opened = True
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.opened:
            cmds.undoInfo(closeChunk=True)
        return False


class UndoDisabled(object):
    def __init__(self):
        self.previous_state = None

    def __enter__(self):
        try:
            self.previous_state = cmds.undoInfo(q=True, state=True)
            cmds.undoInfo(stateWithoutFlush=False)
        except Exception:
            self.previous_state = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.previous_state is not None:
            try:
                cmds.undoInfo(state=self.previous_state)
            except Exception:
                pass
        return False


class RefreshSuspended(object):
    def __enter__(self):
        try:
            cmds.refresh(suspend=True)
        except Exception:
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            cmds.refresh(suspend=False)
        except Exception:
            pass
        return False


class ProgressBar(object):
    def __init__(self, maximum, status="Working...", interruptable=True):
        self.maximum = maximum
        self.status = status
        self.interruptable = interruptable
        self.ctrl = None
        self.active = False

    def __enter__(self):
        try:
            self.ctrl = mel.eval("$tmp = $gMainProgressBar")
            cmds.progressBar(
                self.ctrl,
                e=True,
                bp=True,
                max=max(1, int(self.maximum)),
                ii=self.interruptable,
                status=self.status,
            )
            self.active = True
        except Exception:
            self.active = False
        return self

    def step(self, status=None):
        if not self.active:
            return False

        try:
            if cmds.progressBar(self.ctrl, q=True, ic=True):
                return True

            kwargs = {"edit": True, "step": 1}
            if status:
                kwargs["status"] = status

            cmds.progressBar(self.ctrl, **kwargs)
        except Exception:
            pass

        return False

    def __exit__(self, exc_type, exc, tb):
        if self.active:
            try:
                cmds.progressBar(self.ctrl, e=True, ep=True)
            except Exception:
                pass
        return False


class CallbackManager(object):
    def __init__(self):
        self.ids = []

    def add(self, cb_id):
        if cb_id is not None:
            self.ids.append(cb_id)

    def clear(self):
        for cb_id in self.ids:
            try:
                om.MMessage.removeCallback(cb_id)
            except Exception:
                pass
        self.ids[:] = []


class GimbalAnalyzer(object):
    ORDER_MAP = {
        "xyz": om.MEulerRotation.kXYZ,
        "yzx": om.MEulerRotation.kYZX,
        "zxy": om.MEulerRotation.kZXY,
        "xzy": om.MEulerRotation.kXZY,
        "yxz": om.MEulerRotation.kYXZ,
        "zyx": om.MEulerRotation.kZYX,
    }

    @staticmethod
    def radians_to_degrees(value):
        return value * (180.0 / math.pi)

    def convert_order_string(self, value):
        return self.ORDER_MAP.get(value, om.MEulerRotation.kZYX)

    @staticmethod
    def middle_axis_value(rotation):
        return {
            om.MEulerRotation.kZXY: rotation.x,
            om.MEulerRotation.kZYX: rotation.y,
            om.MEulerRotation.kXZY: rotation.z,
            om.MEulerRotation.kXYZ: rotation.y,
            om.MEulerRotation.kYZX: rotation.z,
            om.MEulerRotation.kYXZ: rotation.x,
        }[rotation.order]

    def gimbal_percentage(self, rotation):
        mid = self.radians_to_degrees(self.middle_axis_value(rotation))
        return int(abs(((mid + 90) % 180) - 90) / 90 * 100)

    def rotation_order_list(self, obj):
        try:
            if cmds.attributeQuery("rotateOrder", node=obj, exists=True):
                return cmds.attributeQuery("rotateOrder", node=obj, listEnum=True)[0].split(":")
        except Exception:
            pass
        return []

    def rotation_at_time(self, obj, time_value, order_list):
        rx = cmds.getAttr("%s.rotateX" % obj, time=time_value) or 0.0
        ry = cmds.getAttr("%s.rotateY" % obj, time=time_value) or 0.0
        rz = cmds.getAttr("%s.rotateZ" % obj, time=time_value) or 0.0
        idx = int(cmds.getAttr("%s.rotateOrder" % obj, time=time_value) or 0)
        idx = max(0, min(idx, len(order_list) - 1)) if order_list else 0
        order = order_list[idx] if order_list else "xyz"

        return om.MEulerRotation(
            math.radians(rx),
            math.radians(ry),
            math.radians(rz),
            self.convert_order_string(order),
        )

    def compute_all_percentages(self, obj, order_list):
        key_times = set()

        for attr in ("rotateX", "rotateY", "rotateZ"):
            try:
                key_times.update(cmds.keyframe(obj, attribute=attr, query=True, timeChange=True) or [])
            except Exception:
                pass

        if not key_times:
            key_times = {cmds.currentTime(query=True)}

        result = []

        for order_name in order_list:
            target_order = self.convert_order_string(order_name)
            worst = 0

            for time_value in sorted(key_times):
                rotation = self.rotation_at_time(obj, time_value, order_list)
                reordered = om.MEulerRotation(rotation.x, rotation.y, rotation.z, rotation.order)
                reordered.reorderIt(target_order)
                worst = max(worst, self.gimbal_percentage(reordered))

            result.append(worst)

        return result

    @staticmethod
    def classify(percentages):
        labels = [""] * len(percentages)

        if not percentages or len(set(percentages)) == 1:
            return labels

        best = min(percentages)

        for i, value in enumerate(percentages):
            diff = value - best

            if diff == 0:
                labels[i] = "Best"
            elif diff <= 2:
                labels[i] = "Good"
            elif diff <= 6:
                labels[i] = "OK"

        return labels

    def analyze(self, obj):
        order_list = self.rotation_order_list(obj)

        if not order_list:
            return {}

        try:
            percentages = self.compute_all_percentages(obj, order_list)
            labels = self.classify(percentages)
        except Exception:
            return {}

        return {
            order: {
                "percentage": percentages[i],
                "label": labels[i],
            }
            for i, order in enumerate(order_list)
        }


class SwitchOperation(object):
    def __init__(self, xform_target, attr_node, attr, value, label=None, source="local"):
        self.xform_target = xform_target
        self.attr_node = attr_node
        self.attr = attr
        self.value = value
        self.label = label if label is not None else value
        self.source = source

    @property
    def plug(self):
        return Maya.plug(self.attr_node, self.attr)

    def is_valid(self):
        return (
            Maya.exists(self.xform_target)
            and Maya.exists(self.attr_node)
            and cmds.objExists(self.plug)
        )

    def set_value(self, value):
        self.value = value
        return self


class SwitchEntry(object):
    def __init__(
        self,
        display_object,
        attr_node,
        attr,
        values,
        current,
        attr_type,
        min_value,
        max_value,
        xform_target=None,
        source="local",
        marked=None,
        gimbal=None,
        matched=None,
        match_roles=None,
    ):
        self.display_object = display_object
        self.attr_node = attr_node
        self.attr = attr
        self.values = values or []
        self.current = float(current)
        self.attr_type = attr_type
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.xform_target = xform_target or display_object
        self.source = source
        self.marked = marked or [self.current]
        self.gimbal = gimbal or {}
        self.matched = matched or []
        self.match_roles = match_roles or []

    def to_dict(self):
        return {
            "enum": self.values,
            "marked": self.marked,
            "current": self.current,
            "attr": self.attr,
            "type": self.attr_type,
            "min": self.min_value,
            "max": self.max_value,
            "attr_node": self.attr_node,
            "xform_target": self.xform_target,
            "source": self.source,
            "gimbal": self.gimbal,
            "matched": self.matched,
            "matchedRole": self.match_roles,
        }


class SwitchCatalogBuilder(object):
    ROTATE_ORDER_OPTIONS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]

    def __init__(self, analyzer, show_rotate_order=True):
        self.analyzer = analyzer
        self.show_rotate_order = show_rotate_order

    @staticmethod
    def add_entry(catalog, key, long_name, entry):
        if key not in catalog:
            catalog[key] = {
                "objects": {},
                "long": long_name or key,
            }

        catalog[key]["objects"][entry.display_object] = entry.to_dict()

    @staticmethod
    def merge_catalogs(primary, secondary):
        for key, data in secondary.items():
            if key not in primary:
                primary[key] = data
                continue

            primary[key].setdefault("objects", {})
            primary[key]["objects"].update(data.get("objects", {}))

            if not primary[key].get("long"):
                primary[key]["long"] = data.get("long", key)

        return primary

    @staticmethod
    def namespace_candidates(namespace):
        parts = namespace.strip(":").split(":")
        while parts:
            yield ":".join(parts)
            parts.pop()

    @staticmethod
    def relative_name(node, root_namespace):
        node = (node or "").strip(":")
        root_namespace = (root_namespace or "").strip(":")
        prefix = root_namespace + ":"

        if root_namespace and node.startswith(prefix):
            return node[len(prefix):]

        return node

    @staticmethod
    def full_name(root_namespace, node):
        node = (node or "").strip(":")
        root_namespace = (root_namespace or "").strip(":")

        if not node:
            return None

        candidates = []

        if root_namespace:
            candidates.append("%s:%s" % (root_namespace, node))

        candidates.append(node)

        for candidate in candidates:
            if Maya.exists(candidate):
                return candidate

        return candidates[0]

    def same_node(self, a, b, root_namespace):
        a = (a or "").strip(":")
        b = (b or "").strip(":")

        if not a or not b:
            return False

        if a == b:
            return True

        rel_a = self.relative_name(a, root_namespace)
        rel_b = self.relative_name(b, root_namespace)

        return rel_a == rel_b or a.endswith(":" + rel_b) or b.endswith(":" + rel_a)

    def find_space_control(self, node):
        namespace = Maya.reference_namespace(node)

        for ns in self.namespace_candidates(namespace):
            control = "%s:C_space_CTL" % ns
            if Maya.exists(control):
                return ns, control

        return None, None

    @staticmethod
    def parse_space_data(raw, source="spaceData"):
        if not raw:
            return {}

        try:
            data = ast.literal_eval(raw)
        except Exception as exc:
            cmds.warning("Could not parse {}: {}".format(source, exc))
            return {}

        if not isinstance(data, dict):
            cmds.warning("{} did not evaluate to a dictionary.".format(source))
            return {}

        return data

    def local_catalog(self, selection):
        catalog = {}

        for node in selection:
            if not Maya.exists(node):
                continue

            attrs = cmds.listAttr(node, ud=True) or []
            attrs = [
                attr for attr in attrs
                if not cmds.attributeQuery(attr, node=node, hidden=True)
            ]

            if self.show_rotate_order and Maya.attr_exists(node, "rotateOrder"):
                if "rotateOrder" not in attrs:
                    attrs.append("rotateOrder")

            for attr in attrs:
                attr_type = Maya.attr_type(node, attr)

                if not attr_type:
                    continue

                is_enum = attr_type == "enum"
                is_numeric = attr_type in ("bool", "long", "double", "float")

                if not is_enum and not is_numeric:
                    continue

                values = []
                min_value = 0.0
                max_value = 0.0

                if is_enum:
                    values = Maya.enum_labels(node, attr)

                    if len(set(values)) < 2:
                        continue

                    max_value = float(len(values) - 1)
                else:
                    attr_range = Maya.numeric_range(node, attr, attr_type)

                    if attr_range is None:
                        continue

                    min_value, max_value = attr_range

                if attr != "rotateOrder" and not Maya.connected(node, attr):
                    continue

                catalog_key = attr

                if is_enum and attr != "rotateOrder":
                    if [v.lower() for v in values] == [v.lower() for v in self.ROTATE_ORDER_OPTIONS]:
                        catalog_key = "rotateOrder"

                current = Maya.get_float(node, attr)
                gimbal = {}

                if catalog_key == "rotateOrder" and self.show_rotate_order:
                    gimbal = self.analyzer.analyze(node)

                entry = SwitchEntry(
                    display_object=node,
                    attr_node=node,
                    attr=attr,
                    values=values,
                    current=current,
                    attr_type=attr_type,
                    min_value=min_value,
                    max_value=max_value,
                    xform_target=node,
                    source="local",
                    marked=Maya.keyed_values(node, attr, current),
                    gimbal=gimbal,
                )

                self.add_entry(catalog, catalog_key, Maya.nice_name(node, attr), entry)

        return catalog

    def framestore_catalog(self, selection):
        catalog = {}

        for selected in selection:
            if not Maya.exists(selected):
                continue

            if not Maya.is_referenced(selected):
                continue

            root_namespace, space_control = self.find_space_control(selected)

            if not root_namespace or not space_control:
                continue

            space_data_plug = Maya.plug(space_control, "spaceData")

            if not cmds.objExists(space_data_plug):
                continue

            data = self.parse_space_data(
                cmds.getAttr(space_data_plug),
                source=space_data_plug,
            )

            if not data:
                continue

            self.collect_framestore_node(
                catalog=catalog,
                selected=selected,
                root_namespace=root_namespace,
                space_control=space_control,
                data=data,
            )

        return catalog

    def collect_framestore_node(self, catalog, selected, root_namespace, space_control, data):
        for attr_name, attr_data in data.items():
            spaces = attr_data.get("spaces") or {}

            if not spaces:
                continue

            if not Maya.attr_exists(space_control, attr_name):
                continue

            enum_values = list(spaces.keys())

            if len(enum_values) < 2:
                continue

            matches = self.framestore_matches(
                selected=selected,
                root_namespace=root_namespace,
                spaces=spaces,
            )

            if not matches:
                continue

            current = Maya.get_float(space_control, attr_name)
            long_name = Maya.nice_name(space_control, attr_name)

            for xform_target, match_data in matches.items():
                entry = SwitchEntry(
                    display_object=xform_target,
                    attr_node=space_control,
                    attr=attr_name,
                    values=enum_values,
                    current=current,
                    attr_type=Maya.attr_type(space_control, attr_name, "enum"),
                    min_value=0.0,
                    max_value=float(len(enum_values) - 1),
                    xform_target=xform_target,
                    source="framestore_spaceData",
                    marked=Maya.keyed_values(space_control, attr_name, current),
                    matched=sorted(match_data["spaces"]),
                    match_roles=sorted(match_data["roles"]),
                )

                self.add_entry(catalog, attr_name, long_name, entry)

    def framestore_matches(self, selected, root_namespace, spaces):
        matches = {}

        for space_name, info in spaces.items():
            getters = info.get("get") or []
            setters = info.get("set") or []
            match_types = info.get("matchType") or []
            count = max(len(getters), len(setters), len(match_types))

            for i in range(count):
                getter = getters[i] if i < len(getters) else None
                setter = setters[i] if i < len(setters) else None
                match_type = match_types[i] if i < len(match_types) else "parent"

                getter_full = self.full_name(root_namespace, getter) if getter else None
                setter_full = self.full_name(root_namespace, setter) if setter else None

                selected_is_setter = self.same_node(selected, setter_full, root_namespace)
                selected_is_getter = self.same_node(selected, getter_full, root_namespace)

                if not selected_is_setter and not selected_is_getter:
                    continue

                if selected_is_setter:
                    xform_target = setter_full
                    role = "setter"
                else:
                    xform_target = setter_full or selected
                    role = "getter"

                if not xform_target:
                    continue

                item = matches.setdefault(
                    xform_target,
                    {
                        "spaces": set(),
                        "roles": set(),
                        "matchTypes": set(),
                    },
                )

                item["spaces"].add(space_name)
                item["roles"].add(role)
                item["matchTypes"].add(match_type)

        return matches

    def combined_catalog(self, selection):
        local = self.local_catalog(selection)
        framestore = self.framestore_catalog(selection)

        if not framestore:
            return local

        result = framestore

        if "rotateOrder" in local:
            self.merge_catalogs(result, {"rotateOrder": local["rotateOrder"]})

        for key, data in local.items():
            if key == "rotateOrder":
                continue

            if key not in result:
                result[key] = data

        return result


class Grip(QSizeGrip):
    def __init__(self, parent):
        QSizeGrip.__init__(self, parent)
        self._parent_widget = parent
        self._start_geom = None

    def mousePressEvent(self, event):
        self._start_geom = self._parent_widget.geometry()
        self._parent_widget._suspend_auto_close()
        QSizeGrip.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        QSizeGrip.mouseReleaseEvent(self, event)

        if self._start_geom and self._parent_widget.geometry() != self._start_geom:
            self._parent_widget.showBottomBar()

        self._start_geom = None


class FloatingWidget(base_widgets.QFlatDialog):
    BORDER_RADIUS = util.DPI(5)
    AUTO_CLOSE_DIST = util.DPI(10)
    TEXT_COLOR = COLOR_TEXT_SECONDARY

    def __init__(self, popup=False, parent=None):
        base_widgets.QFlatDialog.__init__(self, parent)

        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._is_dragging = False
        self._drag_offset = QPoint()
        self._drag_start_pos = QPoint()
        self._auto_close_active = True if popup else None

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.setInterval(200)
        self._auto_close_timer.timeout.connect(self._process_auto_close_request)

        self._setup_ui()
        self.setMouseTracking(True)

    def _setup_ui(self):
        self.mainContent = QWidget(self)
        self.mainLayout = QVBoxLayout(self.mainContent)
        self.mainLayout.setContentsMargins(util.DPI(6), util.DPI(8), util.DPI(6), util.DPI(8))
        self.mainLayout.setSpacing(2)

        self.root_layout.insertWidget(0, self.mainContent, 1)

        self.grip = Grip(self)
        self.grip.setCursor(Qt.SizeBDiagCursor)

    def setBottomBar(self, *args, **kwargs):
        if self.bottomBar:
            self.bottomBar.setParent(None)
            self.bottomBar.deleteLater()
            self.bottomBar = None

        kwargs.setdefault("margins", 0)
        base_widgets.QFlatDialog.setBottomBar(self, *args, **kwargs)

    def showBottomBar(self):
        self._disable_auto_close()

        if hasattr(self, "_refresh_footer"):
            self._refresh_footer()
        elif not self.bottomBar:
            self.setBottomBar(closeButton=True)

    def place_near_cursor(self):
        self.resize(self.sizeHint())

        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        x = max(geo.left(), min(cursor_pos.x(), geo.right() - self.width()))
        y = max(geo.top(), min(cursor_pos.y() - self.height() // 2, geo.bottom() - self.height()))

        self.move(x, y)

    def _is_cursor_within_bounds(self):
        cursor = QCursor.pos()

        if util.is_valid_widget(self) and self.frameGeometry().contains(cursor):
            return True

        popup = getattr(self, "_active_popup", None)

        if popup and util.is_valid_widget(popup) and popup.isVisible():
            return popup.frameGeometry().contains(cursor)

        return False

    def _process_auto_close_request(self):
        if not self._auto_close_active or not self.isVisible():
            return

        if self._is_cursor_within_bounds():
            return

        cursor = QCursor.pos()
        bounds = self.frameGeometry()

        dx = max(bounds.left() - cursor.x(), 0, cursor.x() - bounds.right())
        dy = max(bounds.top() - cursor.y(), 0, cursor.y() - bounds.bottom())

        if (dx * dx + dy * dy) > (self.AUTO_CLOSE_DIST * self.AUTO_CLOSE_DIST):
            self.close()

    def _resume_auto_close(self):
        if self._auto_close_active is True and not self._is_cursor_within_bounds():
            self._auto_close_timer.start()

    def _suspend_auto_close(self):
        if self._auto_close_active is True:
            self._auto_close_active = False

        if self._auto_close_timer:
            self._auto_close_timer.stop()

    def _disable_auto_close(self):
        if self._auto_close_timer:
            self._auto_close_timer.stop()

        self._auto_close_active = None

    def enterEvent(self, event):
        self._auto_close_timer.stop()
        base_widgets.QFlatDialog.enterEvent(self, event)

    def leaveEvent(self, event):
        if self._auto_close_active:
            self._auto_close_timer.start()

        base_widgets.QFlatDialog.leaveEvent(self, event)

    def resizeEvent(self, event):
        size = self.grip.sizeHint()
        self.grip.setFixedSize(size)
        self.grip.move(self.width() - size.width(), 0)
        self.grip.raise_()
        base_widgets.QFlatDialog.resizeEvent(self, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = Qtx.global_pos(event)
            self._is_dragging = True
            self._drag_start_pos = pos
            self._drag_offset = pos - self.frameGeometry().topLeft()
            self._suspend_auto_close()

        base_widgets.QFlatDialog.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if self._is_dragging and event.buttons() & Qt.LeftButton:
            self.move(Qtx.global_pos(event) - self._drag_offset)

        base_widgets.QFlatDialog.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            distance = (Qtx.global_pos(event) - self._drag_start_pos).manhattanLength()

            if distance > util.DPI(10):
                self.showBottomBar()
            elif self._auto_close_active is False:
                self._auto_close_active = True
                self._resume_auto_close()

        base_widgets.QFlatDialog.mouseReleaseEvent(self, event)

    def paintEvent(self, event):
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_BG_TRACK))
        painter.drawRoundedRect(self.rect(), self.BORDER_RADIUS, self.BORDER_RADIUS)

    def closeEvent(self, event):
        self._disable_auto_close()
        base_widgets.QFlatDialog.closeEvent(self, event)


class PillSlider(QWidget):
    HEIGHT = util.DPI(32)
    HANDLE_RADIUS = util.DPI(13)
    SNAP_POINTS = [0.0, 0.5, 1.0]
    SNAP_THRESHOLD = 0.06

    def __init__(self, value, min_value, max_value, callback, parent=None):
        QWidget.__init__(self, parent)

        self.setFixedSize(util.DPI(140), self.HEIGHT)
        self.value = float(value)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.callback = callback
        self._dragging = False
        self._original_value = self.value

        self.setCursor(Qt.PointingHandCursor)

    def _value_to_x(self, value):
        offset = self.height() / 2.0

        if self.max_value <= self.min_value:
            return self.width() // 2

        inner = self.width() - (2 * offset)
        ratio = (value - self.min_value) / (self.max_value - self.min_value)
        return int(offset + ratio * inner)

    def _x_to_value(self, x):
        offset = self.height() / 2.0
        inner = self.width() - (2 * offset)

        if inner <= 0:
            return self.min_value

        ratio = (x - offset) / float(inner)
        ratio = max(0.0, min(1.0, ratio))

        for snap in self.SNAP_POINTS:
            if abs(ratio - snap) < self.SNAP_THRESHOLD:
                ratio = snap
                break

        return self.min_value + ratio * (self.max_value - self.min_value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_ACCENT_DARK))
        painter.drawRoundedRect(rect, radius, radius)

        center_y = self.height() / 2
        handle_radius = self.HANDLE_RADIUS

        if self._dragging:
            shadow_x = self._value_to_x(self._original_value)
            painter.setBrush(QColor(COLOR_BLEND_MULTI))
            painter.drawEllipse(QPoint(shadow_x, int(center_y)), handle_radius, handle_radius)

        handle_x = self._value_to_x(self.value)
        painter.setBrush(QColor(COLOR_BG_TRACK))
        painter.drawEllipse(QPoint(handle_x, int(center_y)), handle_radius, handle_radius)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._original_value = self.value
            self.value = self._x_to_value(Qtx.local_x(event))
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.value = self._x_to_value(Qtx.local_x(event))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.callback(self.value)


class AttributePopup(QWidget):
    ALL_KEYFRAMES = "All Keyframes"
    CURRENT_KEYFRAMES = "Current Keyframes"

    def __init__(self, item_widget, on_select):
        QWidget.__init__(self, item_widget.window())

        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.item_widget = item_widget
        self.options = item_widget.options
        self.current_idx = item_widget.current_idx
        self.indices = item_widget.indices
        self.current_indices = item_widget.current_indices
        self.marked_indices = item_widget.marked_indices
        self.on_select = on_select

        any_obj = next(iter(item_widget.objects_map.values()))

        self.is_enum = any_obj.get("type") == "enum"
        self.min_value = any_obj.get("min", 0.0)
        self.max_value = any_obj.get("max", 1.0)

        self._setup_ui()

    def _setup_ui(self):
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("PopupFrame")
        self.main_frame.setStyleSheet(
            """
            QFrame#PopupFrame {{
                background-color: {};
                border-radius: {}px;
            }}
            """.format(COLOR_BG_POPUP, util.DPI(8))
        )

        self.content_layout = QVBoxLayout(self.main_frame)
        self.content_layout.setContentsMargins(util.DPI(20), util.DPI(10), util.DPI(18), util.DPI(16))
        self.content_layout.setSpacing(util.DPI(1))

        if self.is_enum:
            self._build_enum_ui()
        else:
            self._build_numeric_ui()

        self.adjustSize()

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(util.DPI(10), 0, 0, 0)
        self.outer_layout.addWidget(self.main_frame)

    def _build_enum_ui(self):
        is_rotate_order = self.item_widget.enum_attr == "rotateOrder"

        if is_rotate_order:
            self._add_category(self.ALL_KEYFRAMES, is_all=True, is_rotate_order=True)
        else:
            self._add_category(self.CURRENT_KEYFRAMES, is_all=False)
            self._add_separator()
            self._add_category(self.ALL_KEYFRAMES, is_all=True)

    def _build_numeric_ui(self):
        self._add_slider_section(self.CURRENT_KEYFRAMES, is_all=False)
        self._add_separator()
        self._add_slider_section(self.ALL_KEYFRAMES, is_all=True)

    def _title(self, text):
        label = QLabel(text)
        label.setContentsMargins(0, 0, 0, util.DPI(4))
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label.setStyleSheet("color: {}; font-size: {}px;".format(COLOR_TEXT_SECONDARY, util.DPI(11)))
        return label

    def _add_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: {};".format(COLOR_BG_TRACK))

        self.content_layout.addSpacing(util.DPI(10))
        self.content_layout.addWidget(line)
        self.content_layout.addSpacing(util.DPI(10))

    def _add_category(self, title, is_all, is_rotate_order=False):
        self.content_layout.addWidget(self._title(title))

        for i, option in enumerate(self.options):
            text = option

            if is_rotate_order and self.item_widget.gimbal_info:
                info = self.item_widget.gimbal_info.get(option, {})
                label = info.get("label", "")
                if label:
                    text = "{} ({})".format(option, label)

            self.content_layout.addWidget(self._button(text, i, is_all))

            if is_rotate_order and i == 2:
                self.content_layout.addSpacing(util.DPI(5))

    def _add_slider_section(self, title, is_all):
        self.content_layout.addWidget(self._title(title))

        slider = PillSlider(
            self.current_idx,
            self.min_value,
            self.max_value,
            lambda value, mode=is_all: self.select_option(value, all_frames=mode),
            parent=self.main_frame,
        )

        self.content_layout.addWidget(slider)

    def _button(self, text, index, is_all):
        button = QPushButton(text)
        button.setFlat(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumWidth(util.DPI(60))
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        button.setStyleSheet(
            """
            QPushButton {{
                color: {0};
                background-color: {1};
                text-align: left;
                padding: {2}px {3}px {2}px {2}px;
                border-radius: {4}px;
                font-size: {5}px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {6};
                color: {1};
            }}
            """.format(
                COLOR_ACCENT_HOVER,
                COLOR_ACCENT_DARK,
                util.DPI(8),
                util.DPI(18),
                util.DPI(6),
                util.DPI(11),
                COLOR_ACCENT_MAIN,
            )
        )

        layout = QHBoxLayout(button)
        layout.setContentsMargins(0, 0, util.DPI(6), 0)
        layout.addStretch()

        dot = QWidget()
        dot.setAttribute(Qt.WA_TransparentForMouseEvents)

        dot_size = util.DPI(10)
        dot.setFixedSize(dot_size, dot_size)

        if index in self.current_indices:
            dot.setStyleSheet("background: {}; border-radius: {}px;".format(COLOR_BG_TRACK, dot_size // 2))
        elif index in self.marked_indices:
            dot.setStyleSheet("background: {}; border-radius: {}px;".format(COLOR_BLEND_MULTI, dot_size // 2))
        else:
            dot.setStyleSheet("background: transparent;")

        layout.addWidget(dot)

        button.clicked.connect(lambda checked=False: self.select_option(index, all_frames=is_all))
        return button

    def select_option(self, index, all_frames=None):
        self.on_select(index, all_frames=all_frames)
        self.close()

    def show_beside(self, widget):
        self.adjustSize()

        width = self.width()
        height = self.height()

        target_y = widget.mapToGlobal(QPoint(0, widget.height() // 2)).y()
        pos = widget.mapToGlobal(QPoint(widget.width(), 0))

        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        self.side = "right"

        if pos.x() + width > geo.right():
            self.side = "left"
            pos.setX(widget.mapToGlobal(QPoint(0, 0)).x() - width)

        y = target_y - height // 2
        y = min(y, geo.bottom() - height - util.DPI(5))
        y = max(y, geo.top() + util.DPI(5))

        pos.setY(y)
        self.arrow_y = target_y - y

        arrow_width = util.DPI(10)

        if self.side == "right":
            self.outer_layout.setContentsMargins(arrow_width, 0, 0, 0)
        else:
            self.outer_layout.setContentsMargins(0, 0, arrow_width, 0)

        self.move(pos)
        self.show()

    def enterEvent(self, event):
        parent = self.parent()

        if parent and hasattr(parent, "_update_interaction_state"):
            parent._update_interaction_state(True)

        QWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        parent = self.parent()

        if parent and hasattr(parent, "_update_interaction_state"):
            QTimer.singleShot(150, lambda: parent._update_interaction_state(False))

        QWidget.leaveEvent(self, event)

    def closeEvent(self, event):
        parent = self.parent()

        if parent:
            if getattr(parent, "_active_popup", None) == self:
                parent._active_popup = None

            if hasattr(parent, "_resume_auto_close"):
                parent._resume_auto_close()

        QWidget.closeEvent(self, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_BG_POPUP))

        arrow_width = util.DPI(10)
        arrow_height = util.DPI(15)
        arrow_y = getattr(self, "arrow_y", self.height() / 2)

        if getattr(self, "side", "right") == "right":
            poly = QPolygonF(
                [
                    QPointF(0, arrow_y),
                    QPointF(arrow_width + 1, arrow_y - arrow_height / 2),
                    QPointF(arrow_width + 1, arrow_y + arrow_height / 2),
                ]
            )
        else:
            width = self.width()
            poly = QPolygonF(
                [
                    QPointF(width, arrow_y),
                    QPointF(width - arrow_width - 1, arrow_y - arrow_height / 2),
                    QPointF(width - arrow_width - 1, arrow_y + arrow_height / 2),
                ]
            )

        painter.drawPolygon(poly)


class AttributeItem(QWidget):
    def __init__(self, label_text, enum_attr, unique_controls, objects_map, parent_dialog):
        QWidget.__init__(self, parent_dialog.mainContent)

        self.label_text = label_text
        self.enum_attr = enum_attr
        self.unique_controls = unique_controls
        self.objects_map = objects_map
        self.parent_dialog = parent_dialog

        any_obj = next(iter(objects_map.values()))

        self.is_enum = any_obj.get("type") == "enum"
        self.min_value = any_obj.get("min", 0.0)
        self.max_value = any_obj.get("max", 1.0)
        self.options = any_obj.get("enum", [])
        self.current_idx = any_obj.get("current", 0.0)
        self.gimbal_info = any_obj.get("gimbal", {})
        self.is_toggle = self.is_enum and len(self.options) <= 2

        if self.is_enum:
            self.current_indices = {int(obj.get("current", 0)) for obj in objects_map.values()}
            self.marked_indices = {int(idx) for obj in objects_map.values() for idx in obj.get("marked", [])}
        else:
            self.current_indices = set()
            self.marked_indices = set()

        self.indices = self.current_indices | self.marked_indices
        self._hover_active = False

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(util.DPI(6), util.DPI(6), util.DPI(6), util.DPI(6))
        self.main_layout.setSpacing(util.DPI(6))

        self.name_label = QLabel(self.label_text, self)
        self.name_label.setStyleSheet("color: {}; font-size: {}px;".format(COLOR_TEXT_MAIN, util.DPI(11)))
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.pill_container = QWidget(self)
        self.pill_container.setFixedSize(util.DPI(60), util.DPI(16))

        self.pill_layout = QHBoxLayout(self.pill_container)
        self.pill_layout.setContentsMargins(util.DPI(2), 0, util.DPI(2), 0)
        self.pill_layout.setSpacing(util.DPI(2))

        self.sq_btn = QPushButton(self.pill_container)
        self.sq_btn.setFixedSize(util.DPI(12), util.DPI(12))
        self.sq_btn.setFocusPolicy(Qt.NoFocus)
        self.sq_btn.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.val_label = QLabel(self.current_display_value(), self.pill_container)
        self.val_label.setStyleSheet("color: {}; font-size: {}px;".format(COLOR_ACCENT_LIGHT, util.DPI(11)))
        self.val_label.setAlignment(Qt.AlignCenter)
        self.val_label.setVisible(self.is_enum and not self.is_toggle)

        if self.is_enum:
            if self.is_toggle or self.enum_attr == "rotateOrder":
                self.pill_layout.addWidget(self.sq_btn)
                self.sq_btn.show()
            else:
                self.sq_btn.hide()

            self.pill_layout.addStretch()
            self.pill_layout.addWidget(self.val_label)
            self.pill_layout.addStretch()
        else:
            self.pill_layout.removeWidget(self.sq_btn)
            self.pill_layout.setContentsMargins(util.DPI(2), 0, util.DPI(2), 0)
            self.pill_layout.addWidget(self.val_label)
            self.sq_btn.setParent(self.pill_container)
            QTimer.singleShot(0, self._update_numeric_ball_pos)

        self._refresh_pill_style()

        self.main_layout.addWidget(self.name_label, 1)
        self.main_layout.addWidget(self.pill_container)

        self.pill_opacity = QGraphicsOpacityEffect(self.pill_container)
        self.pill_container.setGraphicsEffect(self.pill_opacity)
        self.pill_opacity.setOpacity(0.0)

    def current_display_value(self):
        if self.is_enum and self.options:
            index = int(self.current_idx)

            if 0 <= index < len(self.options):
                return self.options[index]

            return ""

        return "{:.2f}".format(float(self.current_idx))

    def _update_numeric_ball_pos(self):
        if self.is_enum:
            return

        width = self.pill_container.width()
        ball_width = self.sq_btn.width()
        padding = util.DPI(2)
        usable_width = width - ball_width - (padding * 2)

        if self.max_value <= self.min_value:
            x = padding + (usable_width // 2)
        else:
            ratio = (float(self.current_idx) - self.min_value) / (self.max_value - self.min_value)
            ratio = max(0.0, min(1.0, ratio))
            x = int(padding + ratio * usable_width)

        self.sq_btn.move(x, (self.pill_container.height() - self.sq_btn.height()) // 2)
        self.sq_btn.show()

    def _refresh_pill_style(self):
        ball_color = COLOR_ACCENT_MAIN
        pill_bg = COLOR_ACCENT_DARK

        try:
            current_index = int(self.current_idx)
        except Exception:
            current_index = self.current_idx

        if current_index in self.marked_indices:
            ball_color = COLOR_ACCENT_LIGHT

        if self.enum_attr == "rotateOrder":
            self.sq_btn.setStyleSheet("background: transparent; border: none;")
            pixmap = QPixmap(util.return_icon_path("globe.svg"))

            if not pixmap.isNull():
                size = max(1, int(util.DPI(12)))
                pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                tinted = QPixmap(pixmap.size())
                tinted.fill(Qt.transparent)

                painter = QPainter(tinted)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                painter.fillRect(tinted.rect(), QColor(ball_color))
                painter.end()

                self.sq_btn.setIcon(QIcon(tinted))
                self.sq_btn.setIconSize(QSize(size, size))
            else:
                self.sq_btn.setIcon(QIcon())
                self.sq_btn.setStyleSheet(
                    "background: {}; border-radius: {}px; border: none;".format(
                        ball_color,
                        int(util.DPI(6)),
                    )
                )
        else:
            self.sq_btn.setIcon(QIcon())
            self.sq_btn.setStyleSheet(
                "background: {}; border-radius: {}px; border: none;".format(
                    ball_color,
                    int(util.DPI(6)),
                )
            )

        self.pill_container.setStyleSheet(
            "background: {}; border-radius: {}px;".format(
                pill_bg,
                util.DPI(8),
            )
        )

    def currentText(self):
        if not self.is_enum:
            return self.current_idx

        if not self.options:
            return ""

        index = int(self.current_idx)

        if index < 0 or index >= len(self.options):
            return ""

        return self.options[index]

    def on_select(self, index, all_frames=None):
        self.current_idx = index
        self.val_label.setText(self.current_display_value())

        if not self.is_enum:
            self._update_numeric_ball_pos()

        self._refresh_pill_style()

        if all_frames is None:
            return

        if self.is_enum:
            value = self.options[int(index)]
        else:
            value = index

        options_map = None

        if self.is_enum:
            for _, item_data in self.parent_dialog._active_switch_widgets.items():
                item, item_options_map = item_data

                if item == self:
                    options_map = item_options_map
                    break
        else:
            operations = []

            for obj, data in self.objects_map.items():
                operations.append(
                    SwitchOperation(
                        xform_target=data.get("xform_target", obj),
                        attr_node=data.get("attr_node", obj),
                        attr=data["attr"],
                        value=index,
                        label=index,
                        source=data.get("source", "local"),
                    )
                )

            options_map = {
                index: {
                    "index": index,
                    "operations": operations,
                }
            }

        if options_map:
            self.parent_dialog._apply_attribute_switch(
                value,
                self.enum_attr,
                options_map,
                all_frames_override=all_frames,
            )

    def enterEvent(self, event):
        self._hover_active = True
        self.update()

        if self.parent_dialog:
            self.parent_dialog._handle_attr_hover(self)

            if hasattr(self.parent_dialog, "_update_interaction_state"):
                self.parent_dialog._update_interaction_state(True)

        QWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        self._hover_active = False
        self.update()

        if self.parent_dialog:
            self.parent_dialog._handle_attr_leave(self)

        QWidget.leaveEvent(self, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        bg = QColor(COLOR_ACCENT_WHITE if self._hover_active else COLOR_ACCENT_MAIN)

        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(QColor("white"), 1))
        painter.drawRoundedRect(rect, 2, 2)


class TargetItemWidget(QWidget):
    def __init__(self, name, list_ref):
        QWidget.__init__(self)

        self.name = name
        self.list_ref = list_ref

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        label = QLabel(name.split(":")[-1])

        close_btn = QPushButton()
        base_widgets.QFlatHoverableIcon.apply(close_btn, util.return_icon_path("close"))
        close_btn.setIconSize(QSize(15, 15))
        close_btn.setFixedSize(15, 15)
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.clicked.connect(self._remove)
        close_btn.setStyleSheet(
            """
            QPushButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:pressed {
                background: #101010;
            }
            """
        )

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(close_btn)

    def _remove(self):
        self.list_ref.remove_target(self.name)


class TargetsList(QListWidget):
    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)

        self.backing_store = []
        self.setStyleSheet(
            """
            QListWidget:focus {
                outline: none;
                border: none;
            }
            """
        )

    def add_target(self, name):
        if not Maya.exists(name) or name in self.backing_store:
            return

        self.backing_store.append(name)

        item = QListWidgetItem()
        item.setFlags(Qt.NoItemFlags)

        widget = TargetItemWidget(name, self)
        item.setSizeHint(widget.sizeHint())

        self.addItem(item)
        self.setItemWidget(item, widget)

    def remove_target(self, name):
        if name in self.backing_store:
            self.backing_store.remove(name)

        for i in range(self.count()):
            widget = self.itemWidget(self.item(i))

            if widget and widget.name == name:
                self.takeItem(i)
                break


class SetupTargetsDialog(FloatingWidget):
    def __init__(self, parent, objects_dict, on_close):
        FloatingWidget.__init__(self, popup=False, parent=parent)

        self.on_close = on_close
        self.objects_dict = objects_dict

        if parent and hasattr(parent, "_suspend_auto_close"):
            parent._suspend_auto_close()

        self._create_layouts()
        self.setBottomBar(
            [
                base_widgets.QFlatDialogButton(
                    "Add",
                    callback=self._add_target,
                    icon=util.return_icon_path("add"),
                    highlight=True,
                )
            ],
            closeButton=True,
            spacing=util.DPI(2),
        )

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

    def _add_target(self):
        for obj in Maya.selection():
            self.targets_list.add_target(obj)

    def closeEvent(self, event):
        order = self.targets_list.backing_store
        original_values = list(self.objects_dict.values())
        fallback = original_values[0] if original_values else {}

        new_dict = {}

        for target in order:
            new_dict[target] = self.objects_dict.get(target, fallback)

        self.objects_dict.clear()
        self.objects_dict.update(new_dict)

        if callable(self.on_close):
            self.on_close(self.objects_dict.keys())

        parent = self.parent()

        if parent and hasattr(parent, "_resume_auto_close"):
            parent._resume_auto_close()

        FloatingWidget.closeEvent(self, event)


class Timeline(QWidget):
    def __init__(self, parent, timerange=None, color=(200, 120, 200), autodestroy=300):
        QWidget.__init__(self, parent)

        self.timerange = timerange or [int(f) for f in cmds.timeControl("timeControl1", ra=1, q=True)]
        self.color = QColor(*(list(color) + [70]))
        self.timer = None

        if not self.timerange:
            self.hide()
            return

        self.setGeometry(parent.rect())
        self.show()
        self.raise_()

        if autodestroy is not None:
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.delete_marker)
            self.timer.start(autodestroy)

    @classmethod
    def create(cls, timerange=None, color=(200, 120, 200), autodestroy=300):
        parent = cls.get_timeline()

        if not parent:
            return None

        return cls(
            parent=parent,
            timerange=timerange,
            color=color,
            autodestroy=autodestroy,
        )

    @classmethod
    def get_timeline(cls):
        try:
            timeline = mel.eval("$tmpVar=$gPlayBackSlider")
            ptr = (
                omui.MQtUtil.findControl(timeline)
                or omui.MQtUtil.findLayout(timeline)
                or omui.MQtUtil.findMenuItem(timeline)
            )

            if ptr:
                return util.get_maya_qt(ptr, QWidget)
        except Exception:
            pass

        return None

    def paintEvent(self, event):
        if not self.timerange:
            return

        try:
            start = cmds.playbackOptions(q=True, minTime=True)
            end = cmds.playbackOptions(q=True, maxTime=True)
        except Exception:
            return

        if end <= start:
            return

        total_width = self.width()
        step = (total_width - (total_width * 0.01)) / float(end - start + 1)

        start_frame, end_frame = self.timerange
        end_frame -= 1

        pos_start = (start_frame - start) * step + (total_width * 0.005)
        pos_end = (end_frame + 1 - start) * step + (total_width * 0.005)

        rect = QRectF(QPointF(pos_start, 0), QPointF(pos_end, self.height()))

        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.fillRect(rect, QBrush(self.color))

    def delete_marker(self):
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass


class SwitchExecutor(object):
    def __init__(self, owner):
        self.owner = owner

    @staticmethod
    def operation_matrix(operation):
        return Maya.matrix(operation.xform_target)

    @staticmethod
    def apply_operation(operation, matrix=None):
        if not operation.is_valid():
            cmds.warning("Invalid switch operation: {} -> {}".format(operation.xform_target, operation.plug))
            return False

        matrix = matrix or Maya.matrix(operation.xform_target)

        cmds.setAttr(operation.plug, operation.value)
        Maya.set_matrix(operation.xform_target, matrix)

        return True

    def collect_frames(self, operations, all_frames, timeline_selection, current_frames):
        current_time = cmds.currentTime(query=True)

        if not all_frames and not timeline_selection:
            return [current_time]

        frames = set()

        with UndoDisabled():
            for operation in operations:
                if not operation.is_valid():
                    continue

                frames.update(Maya.key_times_for_node(operation.xform_target))
                frames.update(Maya.key_times_for_plug(operation.plug))

        if timeline_selection:
            start, end = current_frames
            frames = {frame for frame in frames if start <= frame <= end}

        return sorted(frames) or [current_time]

    def apply_once(self, operations):
        for operation in operations:
            self.apply_operation(operation)

    def apply_on_frames(self, operations, frames):
        current_time = cmds.currentTime(q=True)
        marker = None

        try:
            marker = Timeline.create([frames[0], frames[-1] + 1])

            matrices = {}

            with UndoDisabled():
                with ProgressBar(len(frames), status="Saving Positions...", interruptable=True) as progress:
                    for i, frame in enumerate(frames, 1):
                        if progress.step("Saving Positions (%s/%s)..." % (i, len(frames))):
                            return

                        cmds.currentTime(frame)
                        frame_data = []

                        for operation in operations:
                            if operation.is_valid():
                                frame_data.append((operation, self.operation_matrix(operation)))

                        matrices[frame] = frame_data

            with ProgressBar(len(frames), status="Applying Positions...", interruptable=False) as progress:
                for i, frame in enumerate(frames, 1):
                    cmds.currentTime(frame)

                    for operation, matrix in matrices.get(frame, []):
                        self.apply_operation(operation, matrix=matrix)

                    progress.step("Applying Positions (%s/%s)..." % (i, len(frames)))

        finally:
            cmds.currentTime(current_time)

            if marker:
                marker.delete_marker()

    def apply(self, operations, frames):
        if len(frames) > 1:
            self.apply_on_frames(operations, frames)
        else:
            cmds.currentTime(frames[0])
            self.apply_once(operations)


class SpaceSwitchAlehaWidget(FloatingWidget):
    ROTATE_ORDER_OPTIONS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]

    def __init__(self, popup=False, parent=None):
        parent = parent or util.get_maya_qt()
        FloatingWidget.__init__(self, popup=popup, parent=parent)

        self._active_popup = None
        self._popup_pending_item = None
        self._is_ui_hovered = False
        self._active_switch_widgets = {}
        self._previous_selection = []
        self._switch_data = {}

        self._popup_timer = QTimer(self)
        self._popup_timer.setSingleShot(True)
        self._popup_timer.setInterval(100)
        self._popup_timer.timeout.connect(self._show_pending_popup)

        self.settings = QSettings(DATA.get("AUTHOR", {}).get("NAME"), DATA.get("TOOL"))
        self._load_persistent_settings()

        self.analyzer = GimbalAnalyzer()
        self.catalog_builder = SwitchCatalogBuilder(self.analyzer, self.show_rotate_order)
        self.executor = SwitchExecutor(self)

        self._cb = CallbackManager()

        self._create_layouts()
        self._create_selection_layout()
        self._add_callbacks()
        self.refresh(force=True)

    def _create_layouts(self):
        self.mainContent.setMinimumWidth(util.DPI(220))
        self.mainContent.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mainContent.customContextMenuRequested.connect(self._show_context_menu)

        self.enums_layout = QVBoxLayout()
        self.enums_layout.setSpacing(util.DPI(1))

        self.mainLayout.addLayout(self.enums_layout)
        self.mainLayout.addStretch(1)

    def _create_selection_layout(self):
        layout = QVBoxLayout()
        layout.setSpacing(util.DPI(5))
        layout.setContentsMargins(0, util.DPI(6), 0, util.DPI(8))

        title = QLabel("Selection")
        title.setStyleSheet(
            "font-size: %spx; color: %s; font-weight: bold; background: transparent;"
            % (util.DPI(18), self.TEXT_COLOR)
        )
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        title.setWordWrap(False)
        title.setFixedHeight(title.fontMetrics().height() + 2)

        self.selection_label = QLabel("No switches for selection")
        self.selection_label.setStyleSheet("color: %s; background: transparent;" % self.TEXT_COLOR)

        layout.addWidget(title)
        layout.addWidget(self.selection_label)

        self.mainLayout.insertLayout(0, layout)

    def _load_persistent_settings(self):
        self.namespace_display = self._setting_bool("namespace_display", False)
        self.all_frames = self._setting_bool("all_frames", False)
        self.euler_filter = self._setting_bool("euler_filter", True)
        self.show_rotate_order = self._setting_bool("show_rotate_order", True)

    def _setting_bool(self, key, default):
        value = self.settings.value(key, default)

        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return bool(value)

        if isinstance(value, str):
            return value.lower() == "true"

        return bool(default)

    def set_setting(self, setting, state, refresh=False):
        self.settings.setValue(setting, state)
        setattr(self, setting, state)

        if setting == "show_rotate_order":
            self.catalog_builder.show_rotate_order = state

        if refresh:
            self.refresh(force=True)

    def _add_callbacks(self):
        try:
            self._cb.add(
                om.MEventMessage.addEventCallback(
                    "SelectionChanged",
                    lambda *a: self.refresh(force=True),
                )
            )
            self._cb.add(
                om.MEventMessage.addEventCallback(
                    "timeChanged",
                    lambda *a: self.refresh(force=True),
                )
            )
            self._cb.add(
                om.MEventMessage.addEventCallback(
                    "Undo",
                    lambda *a: self.refresh(force=True),
                )
            )
            self._cb.add(
                om.MSceneMessage.addCallback(
                    om.MSceneMessage.kAfterOpen,
                    lambda *a: self._refresh_callbacks(),
                )
            )
        except Exception as exc:
            cmds.warning("Could not add Maya callbacks: %s" % exc)

    def _remove_callbacks(self):
        try:
            self._cb.clear()
        except Exception as exc:
            cmds.warning("Could not remove Maya callbacks: %s" % exc)

    def _refresh_callbacks(self, *args):
        self._remove_callbacks()

        if util.is_valid_widget(self):
            self._add_callbacks()

    def _clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)

            if child.widget():
                child.widget().deleteLater()

            if child.layout():
                self._clear_layout(child.layout())

    def _refresh_footer(self):
        self.setBottomBar(closeButton=not self._auto_close_active)

    def refresh(self, force=False):
        self._close_active_popup()

        current_selection = Maya.selection(long=False)

        if sorted(current_selection) == sorted(self._previous_selection) and not force:
            self._refresh_footer()
            return

        self._previous_selection = current_selection
        self._rebuild_active_widgets()

    def _rebuild_active_widgets(self):
        self._clear_layout(self.enums_layout)
        self._active_switch_widgets.clear()

        if not self._previous_selection:
            self.selection_label.setVisible(True)
            self.adjustSize()
            self._refresh_footer()
            return

        try:
            self._switch_data = self.catalog_builder.combined_catalog(self._previous_selection)

            if not self._switch_data:
                self.selection_label.setVisible(True)
            else:
                self.selection_label.setVisible(False)

                for enum_name, data in self._switch_data.items():
                    self._create_switch_item(enum_name, data)

        except Exception as exc:
            cmds.warning("Error rebuilding SpaceSwitch widgets: {}".format(exc))
        finally:
            self._update_interaction_state(self._is_ui_hovered, force=True)
            self._refresh_footer()
            self.adjustSize()

    def _create_switch_item(self, enum_name, data):
        target_nodes = list(data["objects"].keys())
        display_name = self._format_object_name(target_nodes)

        attr_item = AttributeItem(
            "{} {}".format(display_name, data["long"].title()),
            enum_name,
            target_nodes,
            data["objects"],
            self,
        )

        attr_item.setToolTip(self.formatXformTooltipObjects(target_nodes))
        attr_item.setContextMenuPolicy(Qt.CustomContextMenu)
        attr_item.customContextMenuRequested.connect(
            lambda pos, sender=attr_item, item_data=data: self._show_change_target_dialog(sender, item_data)
        )

        options_map = self._build_options_map(data["objects"])
        self._active_switch_widgets[(enum_name, tuple(target_nodes))] = (attr_item, options_map)
        self.enums_layout.insertWidget(0, attr_item)

    def _build_options_map(self, objects_data):
        options_map = {}

        for display_object, data in objects_data.items():
            attr_node = data.get("attr_node", display_object)
            xform_target = data.get("xform_target", display_object)
            attr = data.get("attr")
            source = data.get("source", "local")

            for index, option in enumerate(data.get("enum", [])):
                entry = options_map.setdefault(
                    option,
                    {
                        "index": index,
                        "operations": [],
                    },
                )

                entry["operations"].append(
                    SwitchOperation(
                        xform_target=xform_target,
                        attr_node=attr_node,
                        attr=attr,
                        value=index,
                        label=option,
                        source=source,
                    )
                )

        return options_map

    def _format_object_name(self, objects):
        if not objects:
            return ""

        if len(objects) > 1:
            return "(%s)" % len(objects)

        name = objects[0].split("|")[-1]

        if ":" in name and not self.namespace_display:
            name = name.split(":")[-1]

        if len(name) > 50:
            return "..." + name[-50:]

        return name

    @staticmethod
    def formatXformTooltipObjects(objects):
        return "<html>Current xform target/s:<br>%s<br><br><b>Right-click to modify...</b></html>" % "<br>".join(objects)

    def _apply_attribute_switch(self, enum_value, enum_attr, options_and_objects, all_frames_override=None):
        all_frames_setting = all_frames_override if all_frames_override is not None else self.all_frames

        if enum_attr == "rotateOrder":
            if isinstance(enum_value, (str, bytes)) and " " in enum_value.strip():
                enum_value = enum_value.split(" ")[0]
            all_frames_setting = True

        data = options_and_objects[enum_value]
        value_index = data.get("index", enum_value)
        operations = [op.set_value(value_index) for op in data.get("operations", [])]
        operations = [op for op in operations if op.is_valid()]

        if not operations:
            return

        timeline_selection = cmds.timeControl("timeControl1", q=True, rv=True)
        current_frames = cmds.timeControl("timeControl1", q=True, ra=True)

        frames = self.executor.collect_frames(
            operations=operations,
            all_frames=all_frames_setting,
            timeline_selection=timeline_selection,
            current_frames=current_frames,
        )

        self._remove_callbacks()

        try:
            with UndoChunk("SpaceSwitch"):
                with RefreshSuspended():
                    self.executor.apply(operations, frames)

                    if self.euler_filter:
                        self.apply_euler_filter([op.xform_target for op in operations])
        finally:
            self._add_callbacks()
            self.refresh(force=True)

    def apply_euler_filter(self, targets):
        curves = []

        for target in targets:
            for attr in ("rx", "ry", "rz"):
                plug = Maya.plug(target, attr)

                if not cmds.objExists(plug):
                    continue

                connected = cmds.listConnections(plug, source=True, type="animCurve") or []
                curves.extend([curve for curve in connected if Maya.exists(curve)])

        curves = sorted(set(curves))

        if curves:
            cmds.filterCurve(*curves)

    def apply_active_changes(self):
        for (enum_attr, _), (attr_item, options_map) in self._active_switch_widgets.items():
            self._apply_attribute_switch(attr_item.currentText(), enum_attr, options_map)

    def _update_interaction_state(self, is_active, force=False):
        if not is_active:
            cursor = QCursor.pos()

            if util.is_valid_widget(self) and self.frameGeometry().contains(cursor):
                is_active = True

            popup = self._active_popup

            if not is_active and popup and util.is_valid_widget(popup) and popup.isVisible():
                if popup.frameGeometry().contains(cursor):
                    is_active = True

        if not force and self._is_ui_hovered == is_active:
            return

        self._is_ui_hovered = is_active

        if self._is_ui_hovered:
            self._auto_close_timer.stop()
        else:
            self._resume_auto_close()

        for _, item_data in self._active_switch_widgets.items():
            attr_item = item_data[0]

            if not util.is_valid_widget(attr_item):
                continue

            if hasattr(attr_item, "pill_opacity"):
                attr_item.pill_opacity.setOpacity(1.0 if self._is_ui_hovered else 0.0)

            if hasattr(attr_item, "val_label"):
                if not attr_item.is_enum:
                    attr_item.val_label.setVisible(False)
                elif attr_item.is_toggle:
                    attr_item.val_label.setVisible(self._is_ui_hovered)
                else:
                    attr_item.val_label.setVisible(True)

            attr_item.update()

    def enterEvent(self, event):
        self._update_interaction_state(True)
        FloatingWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        QTimer.singleShot(150, lambda: self._update_interaction_state(False))
        FloatingWidget.leaveEvent(self, event)

    def _handle_attr_hover(self, item):
        self._popup_pending_item = item
        self._popup_timer.start()

    def _handle_attr_leave(self, item):
        if self._popup_pending_item == item:
            self._popup_pending_item = None

        self._popup_timer.start()

    def _show_pending_popup(self):
        if not self._popup_pending_item or not util.is_valid_widget(self._popup_pending_item):
            popup = self._active_popup

            if popup and util.is_valid_widget(popup) and not popup.underMouse():
                popup.hide()

            return

        item = self._popup_pending_item

        if (
            self._active_popup
            and util.is_valid_widget(self._active_popup)
            and self._active_popup.item_widget == item
            and self._active_popup.isVisible()
        ):
            return

        self._close_active_popup()

        self._active_popup = AttributePopup(item, item.on_select)
        self._active_popup.show_beside(item)

        item._hover_active = True
        item.update()

    def _close_active_popup(self):
        if self._active_popup and util.is_valid_widget(self._active_popup):
            self._active_popup.hide()
            self._active_popup.deleteLater()

        self._active_popup = None

    def _show_change_target_dialog(self, sender, data):
        selection = Maya.selection(long=False)

        def on_close(objects):
            cmds.select(selection, replace=True)
            self._add_callbacks()
            sender.setToolTip(self.formatXformTooltipObjects(objects))

        self._remove_callbacks()

        dialog = SetupTargetsDialog(self, data["objects"], on_close=on_close)
        dialog.show()

    def _show_context_menu(self, pos):
        self.context_menu = widgets.QFlatMenu(self)
        self.context_menu.aboutToShow.connect(self._suspend_auto_close)
        self.context_menu.aboutToHide.connect(self._resume_auto_close)

        namespace_action = self.context_menu.addAction(
            "Show namespaces",
            description="Show namespaces for listed attributes.",
        )
        namespace_action.setCheckable(True)
        namespace_action.setChecked(self.namespace_display)

        rotate_action = self.context_menu.addAction(
            "Enable Rotate Order",
            description="List Rotate Order attributes for selected objects.",
        )
        rotate_action.setCheckable(True)
        rotate_action.setChecked(self.show_rotate_order)

        self.context_menu.addSeparator()

        euler_action = self.context_menu.addAction(
            "Auto Euler Filter",
            description="Apply euler filter to switched attributes.",
        )
        euler_action.setCheckable(True)
        euler_action.setChecked(self.euler_filter)

        self.context_menu.addSeparator()

        about_action = self.context_menu.addAction(
            "About",
            description="General information about SpaceSwitch and the author.",
        )
        about_action.setIcon(QIcon(util.return_icon_path("info")))
        about_action.triggered.connect(self.show_credits_dialog)

        rotate_action.toggled.connect(lambda state: self.set_setting("show_rotate_order", state, refresh=True))
        namespace_action.toggled.connect(lambda state: self.set_setting("namespace_display", state, refresh=True))
        euler_action.toggled.connect(lambda state: self.set_setting("euler_filter", state))

        Qtx.exec_menu(self.context_menu, QCursor.pos())

    def show_credits_dialog(self):
        self._suspend_auto_close()
        widgets.QAboutDialog.showUI(self, data=DATA)

        if widgets.QAboutDialog.dlg_instance:
            widgets.QAboutDialog.dlg_instance.finished.connect(lambda *args: self._resume_auto_close())

    def closeEvent(self, event):
        self._close_active_popup()
        self._cb.clear()
        FloatingWidget.closeEvent(self, event)
        self.deleteLater()


class SpaceSwitchManager(object):
    @classmethod
    def _launch(cls, popup):
        dialog = _MAIN_DICT.get("_SPACESWITCH_INSTANCE")

        if dialog is not None and util.is_valid_widget(dialog):
            try:
                dialog._cb.clear()
                dialog.close()
            finally:
                dialog = None

        if dialog is None or not util.is_valid_widget(dialog):
            dialog = SpaceSwitchAlehaWidget(popup=popup)
            _MAIN_DICT["_SPACESWITCH_INSTANCE"] = dialog

        if popup:
            dialog.place_near_cursor()

        if dialog.isHidden():
            dialog.show()
        else:
            dialog.raise_()
            dialog.activateWindow()

    @classmethod
    def popup(cls):
        cls._launch(popup=True)

    @classmethod
    def show(cls):
        cls._launch(popup=False)


def show():
    SpaceSwitchManager.show()


def popup():
    SpaceSwitchManager.popup()
