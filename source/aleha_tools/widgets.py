try:
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QDialog,
        QFrame,
        QMenu,
        QWidgetAction,
        QApplication,
        QMessageBox,
        QScrollArea,
        QSlider,
        QLineEdit,
        QFormLayout,
        QCheckBox,
        QColorDialog,
    )
    from PySide6.QtGui import (  # type: ignore
        QIcon,
        QPainter,
        QAction,
        QActionGroup,
        QDoubleValidator,
        QRegularExpressionValidator,
        QPen,
        QColor,
        QDrag,
        QCursor,
        QPalette,
        QWheelEvent,
        QPixmap,
        QImage,
    )
    from PySide6.QtCore import (  # type: ignore
        Qt,
        QEvent,
        Signal,
        QPointF,
        QPoint,
        QRegularExpression,
        QMimeData,
    )
except ImportError:
    from PySide2.QtWidgets import (
        QWidget,
        QLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QDialog,
        QFrame,
        QMenu,
        QWidgetAction,
        QApplication,
        QMessageBox,
        QScrollArea,
        QSlider,
        QLineEdit,
        QFormLayout,
        QCheckBox,
        QColorDialog,
    )
    from PySide2.QtGui import (
        QIcon,
        QPainter,
        QRegExpValidator,
        QDoubleValidator,
        QPen,
        QColor,
        QDrag,
        QCursor,
        QPalette,
        QWheelEvent,
        QPixmap,
        QImage,
    )
    from PySide2.QtCore import (
        Qt,
        QRegExp,
        QEvent,
        Signal,
        QRegExp,
        QPointF,
        QPoint,
        QMimeData,
    )

    QRegularExpression = QRegExp
    QRegularExpressionValidator = QRegExpValidator

import maya.cmds as cmds
import base64

from functools import partial

from .util import (
    DPI,
    return_icon_path,
    get_cameras,
    getcolor,
    get_python_version,
)
from .funcs import (
    check_if_valid_camera,
    duplicate_cam,
    delete_cam,
    tear_off_cam,
    select_cam,
    deselect_cam,
    look_thru,
    save_display_to_cam,
    set_cam_display,
    get_cam_display,
    get_panels_from_camera,
    get_preferences_display,
    display_menu_elements,
    rename_cam,
)
from . import DATA


"""
QPainter for the cameras shelf tabBar
"""


class ShelfPainter(QWidget):
    def __init__(self, parent=None):
        super(ShelfPainter, self).__init__(parent)
        self.tabbar_width = DPI(16)
        self.line_thickness = DPI(1)
        self.line_color = QColor(130, 130, 130)
        self.margin = DPI(4)
        self.center = DPI(5)
        self.offset = DPI(1.5)

    def paintEvent(self, event):
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        color = self.palette().color(self.backgroundRole())
        painter = QPainter(self)
        painter.setPen(QPen(color, self.tabbar_width))
        painter.drawLine(
            self.tabbar_width // 2, 0, self.tabbar_width // 2, self.height()
        )

        pen = QPen(self.line_color)
        pen.setWidth(1)  # Line width of 1 pixel
        pen.setStyle(Qt.CustomDashLine)  # Enable custom dash pattern
        pen.setDashPattern([0.01, DPI(3)])  # 1 pixel dot, 1 pixel space
        painter.setPen(pen)

        painter.drawLine(
            QPointF(self.center - self.offset, self.margin / 3),
            QPointF(self.center - self.offset, self.height() - self.margin),
        )
        painter.drawLine(
            QPointF(self.center + self.offset, self.margin / 3),
            QPointF(self.center + self.offset, self.height() - self.margin),
        )

    def resizeEvent(self, event):
        self.update()

    def updateDrawingParameters(
        self,
        tabbar_width=None,
        line_thickness=None,
        line_color=None,
        margin=None,
        center=None,
        offset=None,
    ):
        """Update drawing parameters and refresh the widget."""
        if tabbar_width is not None:
            self.tabbar_width = tabbar_width.width()
        if line_thickness is not None:
            self.line_thickness = line_thickness
        if line_color is not None:
            self.line_color = line_color
        if margin is not None:
            self.margin = margin
        if center is not None:
            self.center = center
        if offset is not None:
            self.offset = offset
        self.update()


"""
QMenu that doesn't close
"""


class OpenMenu(QMenu):
    def __init__(self, title=None, parent=None):
        super().__init__(title, parent) if title else super().__init__(parent)

        if parent and hasattr(parent, "destroyed"):
            parent.destroyed.connect(self.close)

        self.triggered.connect(self._on_action_triggered)

    def _on_action_triggered(self, action):
        if isinstance(action, QWidgetAction):
            return

    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        if action and action.isEnabled():
            if action.isCheckable():
                action.setEnabled(False)
                super().mouseReleaseEvent(e)
                action.setEnabled(True)
                action.trigger()
            else:
                super().mouseReleaseEvent(e)
        else:
            super().mouseReleaseEvent(e)


"""
QLineEdit that doesn't trigger next action
"""


class CustomLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.returnPressed.emit()  # Emit the signal to trigger your logic
            return  # Stop the event from propagating to the parent menu
        super().keyPressEvent(event)  # Default behavior for other keys


"""
QPushButton hover detection
"""


class HoverButton(QPushButton):
    dropped = Signal(tuple)

    def __init__(self, camera, ui=None, width=True):
        super(HoverButton, self).__init__()
        self.parentUI = ui
        self.camera = camera
        self.pressed = False
        self._width = width
        self.dragging = False
        self.start_pos = None

        self.is_modifiable = check_if_valid_camera(self.camera)

        # Initialization sequence
        self._initialize_camera_type()
        self._setup_ui()
        self._setup_styles()
        self._setup_icons()
        self._setup_event_handlers()

    # Initialization Helpers ##################################################
    def _initialize_camera_type(self):
        self.cam_type = "camera"
        type_attr = f"{self.camera}.cams_type"
        if cmds.objExists(type_attr):
            self.cam_type = cmds.getAttr(type_attr)

    def _setup_ui(self):
        self.setAcceptDrops(True)
        self.setFixedHeight(DPI(25))
        self._update_button_name()
        self.setToolTip(self.camera)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _setup_styles(self):
        base_color = getcolor(self.camera)
        self.base_color = ", ".join(str(x) for x in base_color)
        self.light_color = ", ".join(str(x * 1.2) for x in base_color)
        self.dark_color = ", ".join(str(x * 0.6) for x in base_color)

        self.setStyleSheet(f"""
            QPushButton {{
                padding-left: {DPI(4)}px;
                padding-right: {DPI(4)}px;
                color: black;
                background-color: rgb({self.base_color});
                border-radius: {DPI(5)}px;
            }}
            QToolTip {{ 
                background-color: rgb({self.light_color});
            }}
        """)
        self.setStatusTip(f"Look thru {self.camera}")

    def _setup_icons(self):
        icon_map = {
            "default": f"{self.cam_type}",
            "select": "select",
            "deselect": "deselect",
            "duplicate": "duplicate",
            "rename": "rename",
            "remove": "remove",
            "tearoff": "tear_off",
            "attributes": "attributes",
        }
        self.icons = {k: QIcon(return_icon_path(v)) for k, v in icon_map.items()}
        self.setIcon(self.icons["default"])

    def _setup_event_handlers(self):
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.installEventFilter(self)

        if self.parentUI:
            try:
                self.parentUI.keys_pressed_changed.connect(self._handle_key_modifiers)
            except Exception:
                pass

    # Context Menu Management #################################################
    def _show_context_menu(self, pos):
        if not cmds.objExists(self.camera):
            self.parentUI.reload_cams_UI()
            return

        menu = OpenMenu()
        self._build_context_menu(menu)
        menu.exec_(self.mapToGlobal(pos))

    def _build_context_menu(self, menu):
        self._add_title_section(menu)
        self._add_selection_actions(menu)
        self._add_duplicate_action(menu)
        self._add_rename_section(menu)
        menu.addSeparator()
        self._add_default_camera_menu(menu)
        self._add_display_options_menu(menu)
        menu.addSeparator()
        self._add_camera_specific_actions(menu)
        self._add_common_actions(menu)

    def _add_title_section(self, menu):
        style = f"""
            font-size: {DPI(14)}px; 
            font-weight: bold;
            padding: 0 {DPI(20)}px;
        """

        # Rename UI elements
        self.rename_label = QLabel(self._truncated_name())
        self.rename_label.setFixedHeight(DPI(32))
        self.rename_label.setStyleSheet(style)

        # Add to menu
        label_action = self._create_widget_action(self.rename_label)
        menu.addAction(label_action)

        # Enable rename interaction
        if self.is_modifiable:
            self.rename_field = CustomLineEdit()
            self.rename_field.setStyleSheet(style)
            self.rename_field.returnPressed.connect(self._finalize_rename)

            # Add to menu
            field_action = self._create_widget_action(self.rename_field)

            menu.addAction(field_action)
            field_action.setVisible(False)

            self.rename_label.mouseDoubleClickEvent = lambda e: self._enter_rename_mode(
                label_action, field_action
            )

    def _add_selection_actions(self, menu):
        self.select_action = menu.addAction(
            self.icons["select"], "Select", partial(select_cam, self.camera, self)
        )
        self.deselect_action = menu.addAction(
            self.icons["deselect"], "Deselect", partial(deselect_cam, self.camera, self)
        )

        is_selected = self.camera in cmds.ls(selection=True)
        self.select_action.setVisible(not is_selected)
        self.deselect_action.setVisible(is_selected)

    def _add_duplicate_action(self, menu):
        menu.addAction(
            self.icons["duplicate"],
            "Duplicate",
            partial(duplicate_cam, self.camera, self),
        )

    def _add_rename_section(self, menu):
        menu.addAction(
            self.icons["rename"], "Rename", partial(rename_cam, self.camera, "", self)
        )

    def _add_default_camera_menu(self, menu):
        if self.camera == self.parentUI.default_cam[0]:
            default_cam_menu = OpenMenu("Default camera")
            default_cam_menu.setIcon(self.icons["default"])
            default_cam_menu_grp = QActionGroup(self)

            for c in get_cameras(default=True):
                action = default_cam_menu.addAction(
                    c, partial(self._set_default_cam, (c, True), menu)
                )
                default_cam_menu_grp.addAction(action)
                action.setCheckable(True)
                if c == self.camera:
                    action.setChecked(True)
                    action.setEnabled(False)
            menu.addMenu(default_cam_menu)
        menu.addSeparator()

    def _set_default_cam(self, default_cam, menu):
        self.parentUI.process_prefs(cam=default_cam)
        menu.close()

    def _add_display_options_menu(self, menu):
        display_menu = OpenMenu("Viewport Show")
        display_menu.setTearOffEnabled(True)
        self._build_display_menu(display_menu)
        menu.addMenu(display_menu)

    def _build_display_menu(self, menu):
        self.show_elements = display_menu_elements()

        cam_panels = get_panels_from_camera(self.camera)
        preferences = get_preferences_display(self.camera)

        for section, elements in self.show_elements.items():
            menu.addSeparator()
            section_action = menu.addAction(section)
            section_action.setCheckable(True)

            element_actions = []
            for label, attr, is_plugin in elements:
                action = menu.addAction(f"     {label}")
                action.setCheckable(True)
                state = self._get_display_state(
                    attr, is_plugin, cam_panels, preferences
                )
                action.setChecked(state)
                element_actions.append((action, attr, is_plugin))

            section_state = all(a[0].isChecked() for a in element_actions)
            section_action.setChecked(section_state)

            # Connect actions
            section_action.triggered.connect(
                partial(self._toggle_section, section_action, element_actions)
            )
            for action, attr, is_plugin in element_actions:
                action.triggered.connect(
                    partial(self._update_display_attribute, attr, is_plugin, action)
                )

    # Display State Management ################################################
    def _get_display_state(self, attribute, is_plugin, panels, preferences):
        if panels:
            state = get_cam_display(panels, attribute, is_plugin)
            return state or False
        state = preferences.get(attribute, (None, False))[1]
        return state or False

    def _toggle_section(self, section_action, elements):
        state = section_action.isChecked()
        for action, attr, is_plugin in elements:
            action.setChecked(state)
            self._update_display_attribute(attr, is_plugin, state)

    def _update_display_attribute(self, attribute, is_plugin, state):
        if isinstance(state, QAction):
            state = state.isChecked()
        panels = get_panels_from_camera(self.camera)

        if panels:
            set_cam_display(panels, attribute, is_plugin, state)
        save_display_to_cam(self.camera, [(attribute, is_plugin, state)])

    # Event Handling ##########################################################
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self._set_background_color("dark")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = None
            self._set_background_color("light")
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if not self._should_start_drag(event):
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/maya-data", b"")
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.pos() - self.rect().topLeft())

        drag.exec_(Qt.MoveAction)
        self._handle_drop_position(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self._handle_key_modifiers()
            self._set_background_color("light")

        elif event.type() == QEvent.Leave:
            self.setIcon(self.icons["default"])
            self._set_background_color("base")

        return super().eventFilter(obj, event)

    # UI Utilities ############################################################
    def _truncated_name(self, length=18):
        return (
            f"..{self.camera[-length + 2 :]}"
            if len(self.camera) > length
            else self.camera
        )

    def _update_button_name(self):
        self.setText(self._truncated_name(10))
        if self._width:
            self.setFixedWidth(DPI(25 + len(self.text()) * 5.5))

    def _set_background_color(self, variant):
        color = getattr(self, f"{variant}_color", self.base_color)
        self.setStyleSheet(
            self.styleSheet() + f"QPushButton {{ background-color: rgb({color}); }}"
        )

    # Modifier Key Handling ###################################################
    def _handle_key_modifiers(self):
        if self.underMouse():
            mods = self.parentUI.keys_pressed
            ctrl, shift, alt = (
                mods[Qt.Key_Control],
                mods[Qt.Key_Shift],
                mods[Qt.Key_Alt],
            )

            action_map = {
                (0, 1, 0): ("select", partial(select_cam, self.camera)),
                (1, 0, 0): ("deselect", partial(deselect_cam, self.camera)),
                (1, 1, 0): ("duplicate", partial(duplicate_cam, self.camera, self)),
                (1, 0, 1): ("rename", partial(rename_cam, self.camera, self.parentUI)),
                (1, 1, 1): ("remove", partial(delete_cam, self.camera, self.parentUI)),
                (0, 1, 1): ("tearoff", partial(tear_off_cam, self.camera)),
                (0, 0, 1): (
                    "attributes",
                    partial(Attributes.show_dialog, self.camera, self.window()),
                ),
            }

            icon_name, action = next(
                (v for k, v in action_map.items() if k == (ctrl, shift, alt)),
                ("default", partial(look_thru, cam=self.camera, ui=self.parentUI)),
            )

            self.setIcon(self.icons[icon_name])
            try:
                self.clicked.disconnect()
            except Exception:
                pass
            self.clicked.connect(action)

    # Context Menu Helpers ####################################################
    def _create_widget_action(self, widget, height=DPI(32)):
        widget.setFixedHeight(height)
        widget.setMouseTracking(True)  # Enable mouse tracking

        def mouseMoveEvent(event):
            if widget.rect().contains(event.pos()):
                widget.setCursor(QCursor(Qt.IBeamCursor))
            else:
                widget.setCursor(QCursor(Qt.ArrowCursor))

        widget.mouseMoveEvent = mouseMoveEvent

        action = QWidgetAction(self)
        action.setDefaultWidget(widget)
        return action

    def _enter_rename_mode(self, label_action, field_action):
        self.rename_field.setText(self.camera)
        label_action.setVisible(False)
        field_action.setVisible(True)
        self.rename_field.setFocus()

    def _finalize_rename(self):
        new_name = self.rename_field.text()
        if new_name and new_name != self.camera:
            success = rename_cam(self.camera, new_name, self.parentUI)
            if success:
                self.camera = new_name
                self._update_button_name()
        self.rename_field.parent().hide()

    # Drag and Drop ###########################################################
    def _should_start_drag(self, event):
        return (
            event.buttons() == Qt.LeftButton
            and (event.pos() - self.start_pos).manhattanLength()
            >= QApplication.startDragDistance()
        )

    def _handle_drop_position(self, event):
        btn_pos = event.globalPos() - QPoint(self.width() // 2, self.height() // 2)
        self.dropped.emit((btn_pos, QCursor.pos()))
        self.start_pos = None

    # Camera Type Specific ####################################################
    def _add_camera_specific_actions(self, menu):
        if self.cam_type == "camera_aim":
            self._add_aim_actions(menu)
        elif self.cam_type == "camera_follow":
            self._add_follow_actions(menu)

    def _add_aim_actions(self, menu):
        offset_attr = f"{self.camera}.cams_aim_offset"
        if cmds.objExists(offset_attr):
            menu.addAction(
                QIcon(return_icon_path("aim")),
                "Position Aim",
                partial(self._position_aim_offset, offset_attr),
            )

    def _add_follow_actions(self, menu):
        const_attr = f"{self.camera}.cams_follow_attr"
        if cmds.objExists(const_attr):
            attribute = cmds.getAttr(const_attr)
            if attribute:
                if "|" in attribute:
                    uuid, attr = attribute.split("|")
                    camera_grp = cmds.ls(uuid)
                    if not camera_grp:
                        return
                    else:
                        camera_grp = camera_grp[0]
                    follow_mode_attr = "%s.%s" % (camera_grp, attr)
                else:
                    try:
                        camera_grp = attribute.rsplit(".", 1)[0]
                        follow_mode_attr = attribute
                    except Exception as e:
                        print(f"Error occurred: {e}")
                        return

                if not cmds.objExists(follow_mode_attr):
                    return

                follow_mode_menu = OpenMenu("Follow Mode")
                current_mode = cmds.getAttr(follow_mode_attr)

                modes = [("Position, Rotation", True), ("Only Position", False)]

                group = QActionGroup(self)
                for label, mode in modes:
                    action = follow_mode_menu.addAction(label)
                    action.setCheckable(True)
                    action.setChecked(mode == current_mode)
                    action.triggered.connect(
                        partial(cmds.setAttr, follow_mode_attr, mode)
                    )
                    group.addAction(action)

                follow_mode_menu.addSeparator()

                mute_menu = OpenMenu("Active Channels", self)
                mute_menu.setTearOffEnabled(True)

                mute_channels = [
                    ("Translate X", "tx"),
                    ("Translate Y", "ty"),
                    ("Translate Z", "tz"),
                    ("Rotate X", "rx"),
                    ("Rotate Y", "ry"),
                    ("Rotate Z", "rz"),
                ]

                for name, channel in mute_channels:
                    mute_channel_attr = "%s.%s" % (camera_grp, channel)

                    action = mute_menu.addAction(name)
                    action.setCheckable(True)
                    action.setChecked(not cmds.mute(mute_channel_attr, q=True))
                    action.triggered.connect(
                        partial(self._mute_follow_channel, action, mute_channel_attr)
                    )

                follow_mode_menu.addMenu(mute_menu)

                menu.addMenu(follow_mode_menu)

    def _mute_follow_channel(self, action, channel):
        cmds.mute(channel, disable=action.isChecked())

    # Common Actions ##########################################################
    def _add_common_actions(self, menu):
        menu.addSeparator()
        self._add_filmgate_action(menu)
        self._add_attributes_action(menu)
        self._add_defaults_action(menu)
        menu.addSeparator()
        self._add_tearoff_action(menu)
        menu.addSeparator()
        self._add_delete_action(menu)

    def _add_filmgate_action(self, menu):
        action = menu.addAction("FilmGate Mask", self._toggle_filmgate)
        action.setCheckable(True)
        action.setChecked(
            cmds.getAttr(f"{self.camera}.displayFilmGate")
            and cmds.getAttr(f"{self.camera}.displayGateMask")
        )

    def _toggle_filmgate(self):
        cmds.setAttr(f"{self.camera}.displayFilmGate", self.sender().isChecked())
        cmds.setAttr(f"{self.camera}.displayGateMask", self.sender().isChecked())

    def _add_attributes_action(self, menu):
        menu.addAction(
            self.icons["attributes"],
            "Attributes",
            partial(Attributes.show_dialog, self.camera, self.window()),
        )

    def _add_defaults_action(self, menu):
        menu.addAction(
            QIcon(return_icon_path("default")),
            "Apply Defaults",
            partial(self.parentUI.apply_camera_default, self.camera, self),
        )

    def _add_tearoff_action(self, menu):
        menu.addAction(
            self.icons["tearoff"], "Tear Off Copy", partial(tear_off_cam, self.camera)
        )

    def _add_delete_action(self, menu):
        if self.camera != self.parentUI.default_cam[0] and not cmds.referenceQuery(
            self.camera, isNodeReferenced=True
        ):
            menu.addSeparator()
            menu.addAction(
                self.icons["remove"],
                "Delete",
                partial(delete_cam, self.camera, self.parentUI),
            )

    # Aim Offset Handling #####################################################
    def _position_aim_offset(self, offset_attr):
        try:
            offset_obj = self._find_aim_offset_object(offset_attr)
            cmds.select(offset_obj)
            cmds.setToolTo("moveSuperContext")
        except Exception as e:
            cmds.error(f"Could not select Aim Locator for {self.camera}: {str(e)}")

    def _find_aim_offset_object(self, offset_attr):
        try:
            type_info = eval(cmds.getAttr(offset_attr))
            return cmds.ls(type_info[1], type=type_info[0])[0]
        except Exception:
            return self._fallback_find_offset_object(offset_attr)

    def _fallback_find_offset_object(self, offset_attr):
        attr_value = cmds.getAttr(offset_attr)
        candidates = cmds.ls(attr_value.lstrip("|"), long=True)

        for candidate in candidates:
            if self._is_valid_offset(candidate):
                self._update_offset_reference(candidate, offset_attr)
                return candidate

        return self._find_child_locator()

    def _is_valid_offset(self, candidate):
        parents = cmds.listRelatives(candidate, parent=True, fullPath=True)
        return parents and self.camera in cmds.listRelatives(
            parents[0].split("|")[1], children=True
        )

    def _update_offset_reference(self, candidate, offset_attr):
        type_ref = (
            f"['{cmds.objectType(candidate)}', '{cmds.ls(candidate, uuid=True)[0]}']"
        )
        cmds.setAttr(offset_attr, type_ref, type="string")

    def _find_child_locator(self):
        parent = cmds.listRelatives(self.camera, parent=True)[0]
        for child in cmds.listRelatives(parent, allDescendents=True):
            if cmds.objectType(child) == "locator":
                return child
        raise ValueError("No valid aim offset found")


"""
QScroll for the cameras layout
"""


class HorizontalScrollArea(QScrollArea):
    def __init__(self, height, parent=None):
        super(HorizontalScrollArea, self).__init__(parent)

        self.setFrameStyle(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setFixedHeight(height)

        # Create a container widget for the content
        self.container_widget = QWidget(self)
        self.container_layout = QHBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(DPI(5))

        # Set the container widget as the scroll area's widget
        self.setWidget(self.container_widget)

    def wheelEvent(self, event):
        if event.type() == QWheelEvent.Wheel:
            delta = event.angleDelta().y() / 120  # Normalizing delta
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - (delta * 30)
            )
            event.accept()
        super(HorizontalScrollArea, self).wheelEvent(event)


"""
Attributes
"""


class Attributes(QDialog):
    dlg_instance = None

    @classmethod
    def show_dialog(cls, cams, parent):
        try:
            cls.dlg_instance.close()
            cls.dlg_instance.deleteLater()
        except Exception:
            pass

        cls.dlg_instance = Attributes(cams, parent)
        cls.dlg_instance.show()

    def __init__(self, cam, parent=None):
        super(Attributes, self).__init__(parent)

        self.cam = cam

        self.setWindowTitle("Attributes: " + self.cam)
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)

        # First section: Attributes
        self.onlyFloat = QDoubleValidator(self)

        self.create_layouts()
        self.create_widgets()
        self.create_connections()

        self.setFixedSize(self.sizeHint().width(), self.sizeHint().height())

    def create_layouts(self):
        self.form_layout = QFormLayout(self)
        self.form_layout.setVerticalSpacing(DPI(10))
        self.focal_length_container = QHBoxLayout()
        self.near_clip_plane_container = QHBoxLayout()
        self.far_clip_plane_container = QHBoxLayout()
        self.overscan_container = QHBoxLayout()
        self.opacity_container = QHBoxLayout()
        self.color_slider_and_picker = QHBoxLayout()
        self.apply_buttons = QHBoxLayout()

    def create_widgets(self):
        self.focal_length_slider = QSlider(Qt.Horizontal)
        self.focal_length_slider.setRange(2500, 500000)
        self.focal_length_slider.setValue(
            int(round(cmds.getAttr(self.cam + ".fl") * 1000))
        )

        self.focal_length_value = QLineEdit()
        self.focal_length_value.setText(
            str(self.get_float(self.focal_length_slider.value()))
        )
        self.focal_length_value.setFixedWidth(DPI(80))

        self.overscan_slider = QSlider(Qt.Horizontal)
        self.overscan_slider.setRange(1000, 2000)
        self.overscan_slider.setValue(int(cmds.getAttr(self.cam + ".overscan") * 1000))

        self.overscan_value = QLineEdit()
        self.overscan_value.setText(str(self.get_float(self.overscan_slider.value())))
        self.overscan_value.setFixedWidth(DPI(80))

        self.near_clip_plane = QLineEdit()
        self.far_clip_plane = QLineEdit()
        self.near_clip_plane.setFixedWidth(DPI(80))
        self.far_clip_plane.setFixedWidth(DPI(80))

        self.focal_length_value.setValidator(self.onlyFloat)
        self.overscan_value.setValidator(self.onlyFloat)
        self.near_clip_plane.setValidator(self.onlyFloat)
        self.far_clip_plane.setValidator(self.onlyFloat)

        self.near_clip_plane.setText(str(cmds.getAttr(self.cam + ".ncp")))
        self.far_clip_plane.setText(str(cmds.getAttr(self.cam + ".fcp")))

        self.near_clip_lock = self.create_lock_button()
        self.near_clip_lock.setVisible(False)
        self.near_clip_plane_container.addWidget(self.near_clip_plane)
        self.near_clip_plane_container.addStretch()
        self.near_clip_plane_container.addWidget(self.near_clip_lock)

        self.far_clip_lock = self.create_lock_button()
        self.far_clip_lock.setVisible(False)
        self.far_clip_plane_container.addWidget(self.far_clip_plane)
        self.far_clip_plane_container.addStretch()
        self.far_clip_plane_container.addWidget(self.far_clip_lock)

        self.focal_length_lock = self.create_lock_button()
        self.focal_length_lock.setVisible(False)
        self.focal_length_container.addWidget(self.focal_length_value)
        self.focal_length_container.addWidget(self.focal_length_slider)
        self.focal_length_container.addStretch()
        self.focal_length_container.addWidget(self.focal_length_lock)

        self.overscan_lock = self.create_lock_button()
        self.overscan_lock.setVisible(False)
        self.overscan_container.addWidget(self.overscan_value)
        self.overscan_container.addWidget(self.overscan_slider)
        self.overscan_container.addStretch()
        self.overscan_container.addWidget(self.overscan_lock)

        # Second section: Display Attributes
        self.gate_mask_opacity_slider = QSlider(Qt.Horizontal)
        self.gate_mask_opacity_slider.setRange(0, 1000)
        self.gate_mask_opacity_slider.setValue(
            int(round(cmds.getAttr(self.cam + ".displayGateMaskOpacity") * 1000))
        )
        self.gate_mask_opacity_value = QLineEdit()
        self.gate_mask_opacity_value.setText(
            str(self.get_float(self.gate_mask_opacity_slider.value()))
        )
        self.gate_mask_opacity_value.setFixedWidth(DPI(80))

        self.opacity_lock = self.create_lock_button()
        self.opacity_lock.setVisible(False)
        self.opacity_container.addWidget(self.gate_mask_opacity_value)
        self.opacity_container.addWidget(self.gate_mask_opacity_slider)
        self.opacity_container.addStretch()
        self.opacity_container.addWidget(self.opacity_lock)

        self.gate_mask_color_slider = QSlider(Qt.Horizontal)
        self.gate_mask_color_slider.setRange(0, 255)
        self.gate_mask_color_slider.setValue(128)
        self.gate_mask_color_picker = QPushButton()
        self.gate_mask_color_picker.setFixedWidth(DPI(80))
        self.gate_mask_color_picker.setFixedHeight(DPI(17))

        self.update_button_color(self.cam)

        self.color_lock = self.create_lock_button()
        self.color_lock.setVisible(False)
        self.color_slider_and_picker.addWidget(self.gate_mask_color_picker)
        self.color_slider_and_picker.addWidget(self.gate_mask_color_slider)
        self.color_slider_and_picker.addStretch()
        self.color_slider_and_picker.addWidget(self.color_lock)

        self.ok_btn = QPushButton("OK")
        self.apply_btn = QPushButton("Apply")
        self.cancel_btn = QPushButton("Cancel")

        self.apply_buttons.addWidget(self.ok_btn)
        self.apply_buttons.addWidget(self.apply_btn)
        self.apply_buttons.addWidget(self.cancel_btn)

        self.form_layout.addRow("Focal Length:", self.focal_length_container)
        self.form_layout.addRow(QFrame(frameShape=QFrame.HLine))
        self.form_layout.addRow("Near Clip Plane:", self.near_clip_plane_container)
        self.form_layout.addRow("Far Clip Plane:", self.far_clip_plane_container)
        self.form_layout.addRow(QFrame(frameShape=QFrame.HLine))
        self.form_layout.addRow("Overscan:", self.overscan_container)
        self.form_layout.addRow("Gate Mask Opacity:", self.opacity_container)
        self.form_layout.addRow("Gate Mask Color:", self.color_slider_and_picker)

        self.form_layout.addRow(self.apply_buttons)

        self.all_widgets = [
            {
                "target": [self.focal_length_value, self.focal_length_slider],
                "attr": ".fl",
                "lock": self.focal_length_lock,
            },
            {
                "target": [self.overscan_value, self.overscan_slider],
                "attr": ".overscan",
                "lock": self.overscan_lock,
            },
            {
                "target": [self.near_clip_plane],
                "attr": ".ncp",
                "lock": self.near_clip_lock,
            },
            {
                "target": [self.far_clip_plane],
                "attr": ".fcp",
                "lock": self.far_clip_lock,
            },
            {
                "target": [self.gate_mask_opacity_value, self.gate_mask_color_slider],
                "attr": ".displayGateMaskOpacity",
                "lock": self.opacity_lock,
            },
            {
                "target": [self.gate_mask_color_picker, self.gate_mask_opacity_slider],
                "attr": ".displayGateMaskColor",
                "lock": self.color_lock,
            },
        ]

    def create_connections(self):
        for widget in self.all_widgets:
            attr = self.cam + widget.get("attr", "")
            targets = widget.get("target", [])
            lock_btn = widget.get("lock", "")

            settable = True

            if not cmds.getAttr(attr, settable=True):
                settable = False
                lock_btn.setVisible(True)
                lock_btn.clicked.connect(
                    partial(self.disconnect_locked_attr, attr, targets, lock_btn)
                )

            for target in targets:
                value = cmds.getAttr(attr)
                if isinstance(target, QLineEdit):
                    target.setText(str(str(self.get_float(value * 1000))))
                    target.returnPressed.connect(
                        partial(self.apply_modifications, self.cam, close=True)
                    )
                elif isinstance(target, QSlider) and not isinstance(value, list):
                    target.setValue(int(round(value * 1000)))

                target.setEnabled(settable)

        self.ok_btn.clicked.connect(
            partial(self.apply_modifications, self.cam, close=True)
        )
        self.apply_btn.clicked.connect(partial(self.apply_modifications, self.cam))
        self.cancel_btn.clicked.connect(self.close)

        self.focal_length_slider.valueChanged.connect(
            lambda: self.focal_length_value.setText(
                str(self.get_float(self.focal_length_slider.value()))
            )
        )

        self.overscan_slider.valueChanged.connect(
            lambda: self.overscan_value.setText(
                str(self.get_float(self.overscan_slider.value()))
            )
        )

        self.gate_mask_opacity_slider.valueChanged.connect(
            lambda: self.gate_mask_opacity_value.setText(
                self.get_float(self.gate_mask_opacity_slider.value())
            )
        )

        self.gate_mask_color_picker.clicked.connect(
            lambda: self.show_color_selector(self.gate_mask_color_picker)
        )

        self.gate_mask_color_slider.valueChanged.connect(
            lambda: self.update_button_value(self.gate_mask_color_slider.value())
        )

    def create_lock_button(self):
        lock_btn = QPushButton()
        lock_btn.setToolTip("Break connection")
        lock_btn.setStatusTip("Break connection")

        lock_btn.setIcon(QIcon(return_icon_path("locked")))
        lock_btn.setFixedSize(DPI(15), DPI(15))

        return lock_btn

    def disconnect_locked_attr(self, attr, targets, lock_btn):
        res = QMessageBox.question(
            None,
            "Break connection",
            "Are you sure you want to break the connection to\n'" + attr + "'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return
        connections = cmds.listConnections(attr, plugs=True)
        if connections:
            cmds.disconnectAttr(connections[0], attr)

        for target in targets:
            target.setEnabled(True)

        lock_btn.setVisible(False)

    """
    Create functions
    """

    def apply_modifications(self, cam, close=False):
        cmds.undoInfo(chunkName="applyCamAttributes", openChunk=True)
        try:
            self.get_picker_color()
            parameters = {
                "fl": self.focal_length_value.text(),
                "overscan": self.overscan_value.text(),
                "ncp": self.near_clip_plane.text(),
                "fcp": self.far_clip_plane.text(),
                "displayGateMaskOpacity": self.gate_mask_opacity_value.text(),
                "displayGateMaskColor": self.gate_mask_color_rgbf,
            }

            for i, v in parameters.items():
                attr = cam + "." + i
                if cmds.getAttr(attr, settable=True):
                    if v:
                        if not isinstance(v, list):
                            cmds.setAttr(attr, float(v))
                        else:
                            r, g, b = v
                            cmds.setAttr(attr, r, g, b, type="double3")

            if close:
                self.close()
        finally:
            cmds.undoInfo(closeChunk=True)

    def get_float(self, value):
        return "%.3f" % (value / 1000.0)

    def get_picker_color(self):
        style_sheet = self.gate_mask_color_picker.styleSheet()
        bg_color = style_sheet[style_sheet.find(":") + 1 :].strip()
        qcolor = QColor(bg_color)
        r, g, b, _ = qcolor.getRgbF()
        self.gate_mask_color_rgbf = [r, g, b]

    def update_button_color(self, cam):
        rgb = cmds.getAttr(cam + ".displayGateMaskColor")[0]
        qcolor = QColor(*[int(q * 255) for q in rgb])
        h, s, v, _ = qcolor.getHsv()
        qcolor.setHsv(h, s, v)
        self.gate_mask_color_picker.setStyleSheet("background-color: " + qcolor.name())
        self.gate_mask_color_slider.setValue(v)

    def update_button_value(self, value):
        color = self.gate_mask_color_picker.palette().color(QPalette.Button)
        h, s, v, _ = color.getHsv()
        color.setHsv(h, s, value)
        self.gate_mask_color_picker.setStyleSheet("background-color: " + color.name())

    def show_color_selector(self, button):
        initial_color = button.palette().color(QPalette.Base)
        color = QColorDialog.getColor(initial=initial_color)
        if color.isValid():
            button.setStyleSheet("background-color: " + color.name())
            h, s, v, _ = color.getHsv()
            self.gate_mask_color_slider.setValue(v)


"""
Default Settings
"""


class DefaultSettings(QDialog):
    dlg_instance = None

    @classmethod
    def show_dialog(cls, parent):
        try:
            cls.dlg_instance.close()
            cls.dlg_instance.deleteLater()
        except Exception:
            pass

        cls.dlg_instance = DefaultSettings(parent)
        cls.dlg_instance.show()

    def __init__(self, parent=None):
        super(DefaultSettings, self).__init__(parent)

        self.parentUI = parent

        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Default Attributes")

        self.create_layouts()
        self.create_widgets()
        self.create_connections()

        self.setFixedSize(DPI(320), self.sizeHint().height())

    def create_layouts(self):
        self.main_layout = QFormLayout()
        self.main_layout.setVerticalSpacing(DPI(10))
        self.setLayout(self.main_layout)

    def create_widgets(self):
        if get_python_version() < 3:
            onlyFloat = QRegExpValidator(QRegExp(r"[0-9].+"))
        else:
            onlyFloat = QRegularExpressionValidator(QRegularExpression(r"[0-9].+"))  # type: ignore

        description_label = QLabel("Mark the default attributes you want to be saved.")
        description_label.setAlignment(Qt.AlignCenter)

        self.near_clip_plane = QLineEdit()
        self.far_clip_plane = QLineEdit()
        self.near_clip_plane.setText(str(self.parentUI.default_near_clip_plane[0]))
        self.far_clip_plane.setText(str(self.parentUI.default_far_clip_plane[0]))

        self.near_clip_plane.setEnabled(self.parentUI.default_near_clip_plane[1])
        self.far_clip_plane.setEnabled(self.parentUI.default_far_clip_plane[1])

        self.overscan_slider = QSlider(Qt.Horizontal)
        self.overscan_value = QLineEdit()
        self.overscan_slider.setRange(1000, 2000)
        self.overscan_slider.setValue((float(self.parentUI.default_overscan[0]) * 1000))
        self.overscan_value.setText(str(self.get_float(self.overscan_slider.value())))

        self.overscan_slider.setEnabled(self.parentUI.default_overscan[1])
        self.overscan_value.setEnabled(self.parentUI.default_overscan[1])

        self.gate_mask_opacity_slider = QSlider(Qt.Horizontal)
        self.gate_mask_opacity_slider.setRange(0, 1000)
        self.gate_mask_opacity_slider.setValue(
            int(float(self.parentUI.default_gate_mask_opacity[0]) * 1000)
        )

        self.gate_mask_opacity_value = QLineEdit()
        self.gate_mask_opacity_value.setText(
            str(self.get_float(self.gate_mask_opacity_slider.value()))
        )

        self.gate_mask_opacity_slider.setEnabled(
            self.parentUI.default_gate_mask_opacity[1]
        )
        self.gate_mask_opacity_value.setEnabled(
            self.parentUI.default_gate_mask_opacity[1]
        )

        overscan_container = QHBoxLayout()
        overscan_container.addWidget(self.overscan_value)
        overscan_container.addWidget(self.overscan_slider)

        gate_mask_opacity_container = QHBoxLayout()
        gate_mask_opacity_container.addWidget(self.gate_mask_opacity_value)
        gate_mask_opacity_container.addWidget(self.gate_mask_opacity_slider)

        color_slider_and_picker = QHBoxLayout()
        self.gate_mask_color_slider = QSlider(Qt.Horizontal)
        self.gate_mask_color_slider.setRange(0, 255)
        self.gate_mask_color_slider.setValue(128)
        self.gate_mask_color_picker = QPushButton()
        self.gate_mask_color_picker.setFixedWidth(DPI(80))
        self.gate_mask_color_picker.setFixedHeight(DPI(17))

        self.gate_mask_color_picker.setEnabled(self.parentUI.default_gate_mask_color[1])
        self.gate_mask_color_slider.setEnabled(self.parentUI.default_gate_mask_color[1])

        self.update_button_color()

        color_slider_and_picker.addWidget(self.gate_mask_color_picker)
        color_slider_and_picker.addWidget(self.gate_mask_color_slider)

        self.near_clip_plane.setValidator(onlyFloat)
        self.far_clip_plane.setValidator(onlyFloat)
        self.overscan_value.setValidator(onlyFloat)
        self.gate_mask_opacity_value.setValidator(onlyFloat)

        self.near_clip_plane.setFixedWidth(DPI(80))
        self.far_clip_plane.setFixedWidth(DPI(80))
        self.overscan_value.setFixedWidth(DPI(80))
        self.gate_mask_opacity_value.setFixedWidth(DPI(80))

        ok_close_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.close_btn = QPushButton("Close")
        ok_close_layout.addWidget(self.ok_btn)
        ok_close_layout.addWidget(self.close_btn)

        layout_dict = {
            "Near Clip Plane": self.near_clip_plane,
            "Far Clip Plane": self.far_clip_plane,
            "Overscan": overscan_container,
            "Gate Mask Opacity": gate_mask_opacity_container,
            "Gate Mask Color": color_slider_and_picker,
        }

        self.main_layout.addRow(description_label)
        self.main_layout.addRow(QFrame(frameShape=QFrame.HLine))
        # Loop through each key-value pair in the dictionary and add it to the layout with a checkbox
        for index, (key, value) in enumerate(layout_dict.items()):
            if index == 2:
                self.main_layout.addRow(QFrame(frameShape=QFrame.HLine))

            widget_container = QHBoxLayout()
            widget_container.setSpacing(DPI(5))
            checkbox = QCheckBox()
            checkbox.setFixedWidth(DPI(15))
            widget_container.addWidget(checkbox)
            label = QLabel(key)
            label.setFixedWidth(DPI(100))
            widget_container.addWidget(label)
            if isinstance(value, QLayout):
                for i in range(value.count()):
                    widget = value.itemAt(i).widget()
                    if isinstance(widget, QWidget):
                        checkbox.setChecked(widget.isEnabled())
                        checkbox.toggled.connect(
                            lambda checked=checkbox.isChecked(), v=widget: v.setEnabled(
                                checked
                            )
                        )
                widget_container.addLayout(value)
            if isinstance(value, QWidget):
                checkbox.setChecked(value.isEnabled())
                checkbox.toggled.connect(
                    lambda checked=checkbox.isChecked(), v=value: v.setEnabled(checked)
                )
                widget_container.addWidget(value)
            self.main_layout.addRow(widget_container)

        self.main_layout.addRow(ok_close_layout)

    def create_connections(self):
        self.overscan_slider.valueChanged.connect(
            lambda: self.overscan_value.setText(
                str(self.get_float(self.overscan_slider.value()))
            )
        )

        self.gate_mask_opacity_slider.valueChanged.connect(
            lambda: self.gate_mask_opacity_value.setText(
                self.get_float(self.gate_mask_opacity_slider.value())
            )
        )

        self.gate_mask_color_picker.clicked.connect(
            lambda: self.show_color_selector(self.gate_mask_color_picker)
        )

        self.gate_mask_color_slider.valueChanged.connect(
            lambda: self.update_button_value(self.gate_mask_color_slider.value())
        )

        all_widgets = [
            self.near_clip_plane,
            self.far_clip_plane,
            self.overscan_value,
            self.gate_mask_opacity_value,
        ]

        for widget in all_widgets:
            widget.returnPressed.connect(self.apply_settings)

        self.ok_btn.clicked.connect(partial(self.apply_settings, close=True))
        self.close_btn.clicked.connect(lambda: self.close())

    def get_float(self, value):
        return "{:.3f}".format(value / 1000.0)

    def update_button_color(self):
        rgb = self.parentUI.default_gate_mask_color[0]
        qcolor = QColor(*[int(q * 255) for q in rgb])
        h, s, v, _ = qcolor.getHsv()
        qcolor.setHsv(h, s, v)
        self.gate_mask_color_picker.setStyleSheet("background-color: " + qcolor.name())
        self.gate_mask_color_slider.setValue(v)

    def update_button_value(self, value):
        color = self.gate_mask_color_picker.palette().color(QPalette.Button)
        h, s, v, _ = color.getHsv()
        color.setHsv(h, s, value)
        self.gate_mask_color_picker.setStyleSheet("background-color: " + color.name())

    def show_color_selector(self, button):
        initial_color = button.palette().color(QPalette.Base)
        color = QColorDialog.getColor(initial=initial_color)
        if color.isValid():
            button.setStyleSheet("background-color: " + color.name())
            h, s, v, _ = color.getHsv()
            self.gate_mask_color_slider.setValue(v)

    def apply_settings(self, close=False):
        near = float(self.near_clip_plane.text()), self.near_clip_plane.isEnabled()
        far = float(self.far_clip_plane.text()), self.far_clip_plane.isEnabled()
        overscan = float(self.overscan_value.text()), self.overscan_value.isEnabled()
        mask_op = (
            float(self.gate_mask_opacity_value.text()),
            self.gate_mask_opacity_value.isEnabled(),
        )
        r, g, b, _ = (
            self.gate_mask_color_picker.palette().color(QPalette.Button).getRgb()
        )
        mask_color = (
            [round(x / 255.0, 3) for x in [r, g, b]],
            self.gate_mask_color_picker.isEnabled(),
        )

        self.parentUI.process_prefs(
            near=near,
            far=far,
            overscan=overscan,
            mask_op=mask_op,
            mask_color=mask_color,
        )
        if self.parentUI.default_cam[1]:
            self.parentUI.default_cam_btn.setText(self.parentUI.default_cam[0])
        if close:
            self.close()


"""
Coffee window
"""


class Coffee(QMessageBox):
    def __init__(self):
        super(Coffee, self).__init__()

        base64Data = "/9j/4AAQSkZJRgABAQAAAQABAAD/4QAqRXhpZgAASUkqAAgAAAABADEBAgAHAAAAGgAAAAAAAABHb29nbGUAAP/bAIQAAwICAwICAwMDAwQDAwQFCAUFBAQFCgcHBggMCgwMCwoLCw0OEhANDhEOCwsQFhARExQVFRUMDxcYFhQYEhQVFAEDBAQFBAUJBQUJFA0LDRQUFBQUFBQUFBQUFBQUFBQUFBQUFBMUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU/8AAEQgAIAAgAwERAAIRAQMRAf/EABkAAQEAAwEAAAAAAAAAAAAAAAcIBAUGA//EACwQAAEEAQIFAwIHAAAAAAAAAAECAwQRBQYSAAcIEyEiMUFRYRQXMkJTcdH/xAAbAQACAgMBAAAAAAAAAAAAAAAHCAUJAwQGAf/EADMRAAEDAgQEBAQFBQAAAAAAAAECAxEEIQAFEjEGQVFhB3GBoRMikcEUUrHR8CMkMkKC/9oADAMBAAIRAxEAPwBMTk04Rt2a73iwwkrcTHZW84oD4S2gKUo/QJBPDD1rqWWFOKSVRyAk4r64fbdqcwbp23Ut6jErVpT6n9Le04DdRdXULV+YaY0jraJjWEqUFRcjGfipWgD004pKNzilV43gAK9lbfK15tnNdXVDigpSGv8AUJUAQOqikzfcjbl1JsX4e4To8pomkOIQt8f5qWglJJ5I1AC2wNp3IvGMmZ1Kaq0TiX52Oy6ZsxlAWuDkkLWknxdtqWSUfdpY+nnzxG0WaZhTODS8VJnZR1A+puPqOuJ+uynLX25LISoflGg/QWPnfFhcrtfsczeWmltXx2Uxm81Aalqjpc7gZcIpxvdQ3bVhSboXXsODDTO/iWg51wJ3CaZ5TKjsYwaYxtxWSjBlG93uJ2pPizfgcEWqWlFO4tatIAMnpbf0whWWoW9WsNtN/EUpaQEzGolQhM8pNp5Y9dTdL2L1viUymtOQYUl38S/PLUJp9yQvuLIKVFVW4ACNxFbxuAIIClIV/ckSCkmdRvHPy9t8WwLdIohqKkqQAAgEJmIHcjsJ2xInU9034flVAwLaMw+xLnyi21go0r1BPkdwIBpPkijQ/VXzxnYe1VBTII6xyx49TlVAXdBFhuZv0nmcUv0XtL0pyQh6bfeEl3HzH3DITVOd5Xe+PkFZH3q/mgV+HHBU0ytIjSY9gfvgDcSqNDXIC1SVpnyuR9sbPC5VnM4yHlIal9iQgOtlSSlQsX5HweCVQ11Nm1KHmTqQrcH3BH6/thJ87ybMuFM0XQVo0PNkEEGx5pWhVrHcGxBsYUCB0M/X3MBnDpwumdPOZtx5oNsZBqWywzEtSrMkuGwkWPWEuGgAGybJXfP8nZy3M3WdWls/MkdjuB5GfSMWD+HnFj3E3DtPWuJ+JUIJbcJkypAEExeVJgmI+YkzEAAXNblvhovPLQULNsxcjlZjiXJZYBbakPNRXHnFBPg7N7QofQgH54x8LUjdbmTbCh/TJMjsEkj3jEz4lZ/W5NwvUV7bhDqQkJ5wVOJTaexOGnBZJvBNNQ48duLDbG1DbIoJ/wB/v34ZFvLWKdkNU6dIHLCCN8W1tVVGor1lalbn+cuw2wfa61V+UuIm5ZEbv4kJLiGN5Cd/8RNHZZPpPmhYqkgEaOUdZw/nCXqITTvH5hyBuT5dUn/nYDBnymvyrxL4WOV50rTmNImG3N1qTYJPLV+VwE7wuQVWP+R/UxqfI6zU7LisZuLkEOJh41qmkR1NpWu0GlE2EkEqJ/b5HgcaXFtInMqP8cpUKb7bgkCPQ3+vUYKXh3TU/Cr5yqkSSl66iTfUATJ5XFoAGw3ucAevubuvub3PsaoabVpqZhlKjwURyHRGJ9Cxak04VBRCrFV4r3uG4cy59pSXW5TBmY35fS/rOOu4yqqDMmHMvqQHUKEFM23mZBnUCAbGxHnLjh+oHPY/JoGpsdClY9e1C3cSwtpxo3RXtW4sLH2FHwas0kmtuvUD84kdsKfmPh5S/BJy5xQcF4WQQe0pSnSe5kdYEkf/2Qis"
        if get_python_version() < 3:
            image_64_decode = base64.decodestring(base64Data)
        else:
            image_64_decode = base64.decodebytes(base64Data.encode("utf-8"))
        image = QImage()
        image.loadFromData(image_64_decode, "JPG")
        pixmap = QPixmap(image).scaledToHeight(DPI(56), Qt.SmoothTransformation)
        self.setIconPixmap(pixmap)

        self.setWindowTitle("About " + DATA["TOOL"].title())
        self.setText(
            '<p><font color="white">Version:  '
            + DATA["VERSION"]
            + "</p>"
            + "By @"
            + DATA["AUTHOR"]["name"]
            + ' - <a href="'
            + DATA["AUTHOR"]["instagram"]
            + '"><font color="white">Instagram</font></a>'
            + "<br>"
            "My website - <a href="
            + DATA["AUTHOR"]["website"]
            + '><font color="white">'
            + DATA["AUTHOR"]["website"]
            + "</a>"
            + "<br>"
            "<br>"
            "If you liked this set of tools,<br>you can send me some love!"
        )
        self.setFixedSize(DPI(400), DPI(300))
