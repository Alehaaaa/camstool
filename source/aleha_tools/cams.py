"""

Run with:

import aleha_tools.cams as cams
cams.show()


"""

import os
import sys
import webbrowser
import maya.OpenMayaUI as omui
import maya.cmds as cmds
from functools import partial
from importlib import reload

# Attempt to import PySide6, fallback to PySide2 if unavailable

try:
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QMainWindow,
        QMessageBox,
        QLabel,
        QLayout,
        QDialog,
        QApplication,
        QHBoxLayout,
        QVBoxLayout,
        QPushButton,
        QFrame,
        QMenu,
        QMenuBar,
        QWidgetAction,
    )
    from PySide6.QtGui import (  # type: ignore
        QIcon,
        # QPainter,
        QKeyEvent,
        QAction,
        QActionGroup,
    )
    from PySide6.QtCore import (  # type: ignore
        Qt,
        QEvent,
        Signal,
        QTimer,
    )
except ImportError:
    from PySide2.QtWidgets import (
        QWidget,
        QMainWindow,
        QMessageBox,
        QLabel,
        QLayout,
        QAction,
        QActionGroup,
        QDialog,
        QApplication,
        QHBoxLayout,
        QVBoxLayout,
        QPushButton,
        QFrame,
        QMenu,
        QMenuBar,
        QWidgetAction,
    )
    from PySide2.QtGui import (
        QIcon,
        # QPainter,
        QKeyEvent,
    )
    from PySide2.QtCore import (
        Qt,
        QEvent,
        Signal,
        QTimer,
    )

# Maya-specific imports
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

# Remove outdated 'aleha_tools' modules except 'aleha_tools.cams'
modules_to_delete = [
    m
    for m in list(sys.modules.keys())
    if m.startswith("aleha_tools") and m != "aleha_tools.cams"
]

for mod_name in modules_to_delete:
    del sys.modules[mod_name]

# Import and reload necessary modules
import aleha_tools  # type: ignore  # noqa: E402
from . import settings, widgets, funcs, util, updater  # noqa: E402

reload(aleha_tools)
reload(settings)
reload(widgets)
reload(funcs)
reload(util)
reload(updater)

DATA = aleha_tools.DATA
TITLE = DATA["TOOL"].title()
VERSION = DATA["VERSION"]

# Import HUDWindow
from ._tools import HUDWindow as hud  # noqa: E402


def welcome():
    funcs.install_userSetup()
    show()


def show():
    try:
        funcs.close_all_Windows()
    except Exception:
        pass

    global cams_aleha_tool
    if "cams_aleha_tool" in globals():
        del cams_aleha_tool
    cams_aleha_tool = UI()
    cams_aleha_tool.showWindow()


class UI(MayaQWidgetDockableMixin, QDialog):
    keys_pressed_changed = Signal(dict)

    def __init__(self, parent=None):
        self.TITLE = TITLE
        self.VERSION = VERSION

        super(self.__class__, self).__init__(parent=parent)

        self.setWindowTitle(self.TITLE)
        self.setObjectName(self.TITLE)
        if sys.platform == "darwin":
            self.setWindowFlags(Qt.Tool)
        else:
            self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.setContextMenuPolicy(Qt.PreventContextMenu)

        self.workspace_control_name = self.objectName() + "WorkspaceControl"
        self.all_created_scriptjobs = []
        self.all_displayed_buttons = {}

        self.current_layout = cmds.workspaceLayoutManager(q=1, current=True)
        self.settings_window = None
        self.options = None

        self.user_prefs = settings.get_all_prefs()
        self.process_prefs()

        self.create_layouts()
        self.create_widgets()
        self.create_menu()

        self.create_connections()

        self.reload_cams_UI()

        self.add_scriptjobs()
        self.selection_changed_scripjob()

        self.modifier_keys_status = {
            Qt.Key_Control: False,
            Qt.Key_Shift: False,
            Qt.Key_Alt: False,
        }
        self._in_update_keys_pressed = False

        self.set_global_preferences()

        self.installEventFilter(self)

    @property
    def keys_pressed(self):
        return self.modifier_keys_status

    @keys_pressed.setter
    def keys_pressed(self, values):
        self.modifier_keys_status = values  # Update the stored value
        self.keys_pressed_changed.emit(values)  # Emit the signal
        self._in_update_keys_pressed = False  # Reset the flag after update

    def eventFilter(self, obj, event):
        if event.type() in (
            QEvent.Enter,
            QEvent.Leave,
            QKeyEvent.KeyPress,
            QKeyEvent.KeyRelease,
        ):
            updated_keys = (
                self.modifier_keys_status.copy()
            )  # Start with the current state

            if event.type() == QKeyEvent.KeyPress:
                for key in updated_keys.keys():
                    if key == event.key():
                        updated_keys[key] = True

            elif event.type() == QKeyEvent.KeyRelease:
                for key in updated_keys.keys():
                    if key == event.key():
                        updated_keys[key] = False

            elif event.type() == QEvent.Enter or event.type() == QEvent.Leave:
                current_modifiers = QApplication.keyboardModifiers()
                updated_keys = {
                    Qt.Key_Control: bool(current_modifiers & Qt.ControlModifier),
                    Qt.Key_Shift: bool(current_modifiers & Qt.ShiftModifier),
                    Qt.Key_Alt: bool(current_modifiers & Qt.AltModifier),
                }

            # Trigger the setter, which will emit the signal if there are changes
            if (
                not self._in_update_keys_pressed
                and updated_keys != self.modifier_keys_status
            ):
                self._in_update_keys_pressed = (
                    True  # Set the flag to True before updating
                )
                self.keys_pressed = updated_keys

        if util.get_python_version() > 2:
            return super().eventFilter(obj, event)
        else:
            return super(self.__class__, self).eventFilter(obj, event)

    def visible_change_command(self, *args):
        if not cmds.workspaceControl(self.workspace_control_name, ex=True):
            return
        if self.current_layout != cmds.workspaceLayoutManager(q=1, current=True):
            self.current_layout = cmds.workspaceLayoutManager(q=1, current=True)
            if not cmds.workspaceControl(
                self.workspace_control_name, q=True, visible=True
            ):
                cmds.evalDeferred(show, lowestPriority=True)
                return

        if not cmds.workspaceControl(
            self.workspace_control_name, q=True, floating=True
        ):
            if cmds.workspaceControl(
                self.workspace_control_name, q=True, collapse=True
            ):
                timer = QTimer(self)
                timer.setSingleShot(True)

                timer.timeout.connect(
                    partial(
                        cmds.workspaceControl,
                        self.workspace_control_name,
                        e=True,
                        collapse=False,
                        tp=["west", 0],
                    )
                )
                timer.start(100)

            if util.is_valid_widget(self.dock_ui_btn, QPushButton):
                self.dock_ui_btn.setHidden(True)
        else:
            if util.is_valid_widget(self.dock_ui_btn, QPushButton):
                self.dock_ui_btn.setHidden(False)
            cmds.workspaceControl(
                self.workspace_control_name, e=True, actLikeMayaUIElement=True
            )
            # cmds.evalDeferred(self.shelf_tabbar)

    def showWindow(self, dock=True):
        self.show(dockable=True, retain=False, actLikeMayaUIElement=True)

        if dock:
            self.dock_ui_btn.setHidden(True)
            is_floating = cmds.workspaceControl(
                self.workspace_control_name, q=True, floating=True
            )

            # Build up kwargs for the workspaceControl command
            kwargs = {
                "e": True,
                "visibleChangeCommand": self.visible_change_command,
                "actLikeMayaUIElement": True,
            }

            # If it's floating and the referenced layout isn't visible, reset the position
            if util.check_visible_layout(self.position[0]):
                kwargs["dockToControl"] = self.position

            # If it's floating, include the extra params
            if is_floating:
                kwargs["tp"] = ["west", 0]
                # kwargs["rsh"] = util.DPI(15)
                # kwargs["rsw"] = util.DPI(50)

            # Make the workspaceControl call just once
            cmds.workspaceControl(self.workspace_control_name, **kwargs)

            # Defer tab bar creation or update
            # cmds.evalDeferred(self.shelf_tabbar, lowestPriority=True)

        return
        is_floating = cmds.workspaceControl(
            self.workspace_control_name, e=True, floating=True
        )
        self.dock_ui_btn.setHidden(False)

    # def shelf_tabbar(self):
    #     try:
    #         if self.shelf_painter:
    #             QPainter(self.shelf_painter).end()
    #             self.shelf_painter.setParent(None)
    #             self.shelf_painter.deleteLater()

    #             self.shelf_painter = None
    #     except Exception:
    #         pass

    #     qctrl = omui.MQtUtil.findControl(self.workspace_control_name)
    #     control = util.get_maya_qt(qctrl)
    #     try:
    #         tab_handle = control.parent().parent()
    #     except Exception:
    #         return

    #     if cmds.workspaceControl(self.workspace_control_name, q=True, floating=True):
    #         tab_handle.tabBar().setVisible(False)
    #         return

    #     self.shelf_painter = widgets.ShelfPainter(tab_handle)
    #     self.shelf_painter.setGeometry(tab_handle.geometry())
    #     self.shelf_painter.updateDrawingParameters(
    #         tabbar_width=tab_handle.tabBar().geometry()
    #     )
    #     self.shelf_painter.move(tab_handle.tabBar().pos())

    #     self.shelf_painter.show()
    #     tab_handle.tabBar().setVisible(True)

    """
    Setup the UI
    """

    def create_layouts(self):
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(
            util.DPI(13), util.DPI(3), util.DPI(3), util.DPI(3)
        )

        main_widget = QWidget(self)
        self.main_widget_layout = QVBoxLayout(main_widget)
        self.main_widget_layout.setContentsMargins(0, 0, 0, 0)

        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_widget_layout.addLayout(self.main_layout)

        container_layout.addWidget(main_widget)

        self.default_cam_layout = QHBoxLayout()
        self.main_layout.addLayout(self.default_cam_layout)

        self.cams_scroll = widgets.HorizontalScrollArea(util.DPI(26), self)

        cams_scroll_widget = QWidget(self.cams_scroll)
        self.cams_scroll.container_layout.addWidget(cams_scroll_widget)

    def create_widgets(self):
        self.default_cam_btn = widgets.HoverButton(
            self.default_cam[0], self, width=False
        )
        self.default_cam_layout.addWidget(self.default_cam_btn)
        self.default_cam_btn.dropped.connect(
            partial(funcs.drag_insert_camera, self.default_cam[0], self)
        )

        self.line = QFrame()
        self.line.setFrameShape(QFrame.VLine)
        self.line.setLineWidth(1)
        self.main_layout.addWidget(self.line)

        self.main_layout.addWidget(self.cams_scroll)

        self.dock_ui_btn = QPushButton()
        self.dock_ui_btn.setToolTip("Dock to UI")
        self.dock_ui_btn.setStatusTip("Dock to UI")

        self.dock_ui_btn.setIcon(QIcon(util.return_icon_path("dock")))
        self.dock_ui_btn.setFixedSize(util.DPI(15), util.DPI(15))
        self.dock_ui_btn.setStyleSheet("""
                            QPushButton {
                            border-radius: 20px;
                            background-color: #333;
                            padding:0;
                            margin:0;
                            }
                            QPushButton:hover {
                            background-color: #888;
                            }
                            """)

    def create_buttons(self):
        try:
            # Get current cameras
            cameras = util.get_cameras()
            camera_set = set(cameras)

            # Early exit if cameras haven't changed (excluding 'main' which == always shown)
            current_displayed = set(self.all_displayed_buttons.keys()) - {"main"}
            if camera_set == current_displayed:
                return current_displayed

            # Get existing buttons from layout
            existing_buttons = {
                self.cams_scroll.container_layout.itemAt(i)
                .widget()
                .camera: self.cams_scroll.container_layout.itemAt(i).widget()
                for i in range(self.cams_scroll.container_layout.count())
                if isinstance(
                    self.cams_scroll.container_layout.itemAt(i).widget(),
                    widgets.HoverButton,
                )
            }

            # Remove buttons for cameras that no longer exist
            obsolete_cams = current_displayed - camera_set
            for cam in obsolete_cams:
                button = existing_buttons.get(cam)
                if button:
                    self.cams_scroll.container_layout.removeWidget(button)
                    button.deleteLater()

            self.all_displayed_buttons = {"main": self.default_cam_btn}

            if cameras:
                # Add stretch if layout == empty
                if self.cams_scroll.container_layout.count() == 0:
                    self.cams_scroll.container_layout.addStretch()

                # Add or reuse buttons
                for cam in reversed(cameras):
                    if cam in existing_buttons:
                        button = existing_buttons[cam]
                        self.cams_scroll.container_layout.insertWidget(0, button)
                    else:
                        button = widgets.HoverButton(cam, self)
                        self.cams_scroll.container_layout.insertWidget(0, button)
                        button.dropped.connect(
                            partial(funcs.drag_insert_camera, cam, self)
                        )

                    self.all_displayed_buttons[cam] = button

            return self.all_displayed_buttons.keys()

        except Exception as e:
            print("Error adding buttons:", e)

    # Menu bar layout

    def create_menu(self):
        menu_bar = QMenuBar()

        menu_general = widgets.OpenMenu("General", menu_bar)
        menu_general.setTearOffEnabled(True)
        menu_bar.addMenu(menu_general)

        title_label = QLabel("CAMS %s" % self.VERSION)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setFixedHeight(util.DPI(32))
        title_label.setContentsMargins(util.DPI(20), 0, util.DPI(20), 0)
        title_label.setStyleSheet(
            """
                                  QLabel {
                                  font-size: """
            + str(util.DPI(14))
            + """px;
                                  font-weight: bold;
                                  color: #ececec;
                                  }
                                  QLabel:hover {
                                  background-color: rgb(80, 133, 164);
                                  }
                                  
                                  """
        )

        title_action = QWidgetAction(self)
        title_action.setDefaultWidget(title_label)
        title_action.triggered.connect(
            partial(webbrowser.open, DATA["AUTHOR"]["website"])
        )
        menu_general.addAction(title_action)

        self.reload_btn = menu_general.addAction(
            QIcon(util.return_icon_path("refresh")), "Refresh Cameras"
        )
        menu_general.addSeparator()

        self.about = menu_general.addAction(
            QIcon(util.return_icon_path("info")), "About"
        )
        self.updates = menu_general.addAction(
            QIcon(util.return_icon_path("updates")), "Check for Updates"
        )

        menu_general.addSeparator()

        self.settings_btn = menu_general.addAction(
            QIcon(util.return_icon_path("default_attributes")), "Default Attributes"
        )
        menu_general.addSeparator()

        ## DOCK TAB ##

        self.dock_menu = QMenu("Dock Window")
        self.dock_menu.setIcon(QIcon(util.return_icon_path("dock")))
        self.dock_menu.setTearOffEnabled(True)

        self.pos_ac_group = QActionGroup(self)
        self.docking_orients = {
            "top": "To Top",
            "bottom": "To Bottom",
        }
        for orient, name in self.docking_orients.items():
            ori_btn = QAction(name, self)
            ori_btn.setCheckable(True)
            self.pos_ac_group.addAction(ori_btn)
            self.dock_menu.addAction(ori_btn)
            ori_btn.triggered.connect(partial(self.dock_to_ui, orient=orient))
            if orient == self.position[1]:
                ori_btn.setChecked(True)
                ori_btn.setEnabled(False)

        self.dock_menu.addSeparator()

        self.dock_ac_group = QActionGroup(self)
        self.docking_layouts = {
            "AttributeEditor": "Attribute Editor",
            "ChannelBoxLayerEditor": "Channel Box",
            "Outliner": "Outliner",
            "MainPane": "Main Viewport",
            "TimeSlider": "Time Slider",
            "RangeSlider": "Range Slider",
            "Shelf": "Shelf",
        }

        for layout, name in self.docking_layouts.items():
            dock_btn = QAction(name, self)
            dock_btn.setCheckable(True)
            self.dock_ac_group.addAction(dock_btn)
            self.dock_menu.addAction(dock_btn)

            dock_btn.triggered.connect(partial(self.dock_to_ui, layout=layout))
            if layout == self.position[0]:
                dock_btn.setChecked(True)
                dock_btn.setEnabled(False)

        self.dock_menu.aboutToShow.connect(self.update_dock_menu)

        menu_general.addMenu(self.dock_menu)

        ## SETTINGS TAB ##

        system_menu = widgets.OpenMenu("System", menu_general)
        menu_general.addMenu(system_menu)
        system_menu.setIcon(QIcon(util.return_icon_path("system")))
        system_menu.setTearOffEnabled(True)

        self.startup_Viewport_checkbox = system_menu.addAction("Viewport on Startup")
        self.startup_Viewport_checkbox.setToolTip(
            "Apply Show settings to Viewports on Startup"
        )
        self.startup_Viewport_checkbox.setStatusTip(
            "Apply Show settings to Viewports on Startup"
        )
        self.startup_Viewport_checkbox.setCheckable(True)
        self.startup_Viewport_checkbox.setChecked(self.startup_viewport)
        self.startup_Viewport_checkbox.triggered.connect(
            lambda state=self.startup_Viewport_checkbox.isChecked(): self.process_prefs(
                startup_viewport=state
            )
        )

        self.startup_HUD_checkbox = system_menu.addAction("HUD on Startup")
        self.startup_HUD_checkbox.setCheckable(True)
        self.startup_HUD_checkbox.setChecked(self.startup_hud)
        self.startup_HUD_checkbox.triggered.connect(
            lambda state=self.startup_HUD_checkbox.isChecked(): self.process_prefs(
                startup_hud=state
            )
        )

        system_menu.addSeparator()

        self.reset_cams_data = system_menu.addAction(
            QIcon(util.return_icon_path("warning")), "Reset All Settings"
        )
        system_menu.addSeparator()
        self.close_btn = system_menu.addAction(
            QIcon(util.return_icon_path("close")), "Close"
        )
        self.uninstall_btn = system_menu.addAction(
            QIcon(util.return_icon_path("remove")), "Uninstall"
        )

        ## TOOLS MENU ##

        menu_tools = widgets.OpenMenu("Tools", menu_bar)
        menu_bar.addMenu(menu_tools)
        menu_tools.setTearOffEnabled(True)
        self.followCam = menu_tools.addAction(
            QIcon(util.return_icon_path("follow")), "Follow Cam"
        )
        self.aimCam = menu_tools.addAction(
            QIcon(util.return_icon_path("aim")), "Aim Cam"
        )
        menu_tools.addSeparator()
        self.multicams = menu_tools.addAction(
            QIcon(util.return_icon_path("camera_multicams")), "MultiCams"
        )

        menu_tools.addSeparator()

        self.menu_presets = widgets.OpenMenu("HUD Presets", menu_tools)
        menu_tools.addMenu(self.menu_presets)
        self.menu_presets.setTearOffEnabled(True)

        self.add_presets()
        self.menu_presets.aboutToShow.connect(self.add_presets)

        self.HUD_checkbox = menu_tools.addAction("Display HUDs")
        self.HUD_checkbox.setCheckable(True)
        self.HUD_checkbox.setChecked(self.HUD_display_cam())
        self.HUD_checkbox.triggered.connect(
            lambda state=self.HUD_display_cam(): self.HUD_display_cam(state=state)
        )

        self.version_bar = menu_bar.addMenu(self.VERSION)
        is_author = funcs.check_author()
        self.version_bar.setEnabled(is_author)
        if is_author:
            self.populate_version_bar()

        menu_bar.setCornerWidget(self.dock_ui_btn)
        self.main_widget_layout.setMenuBar(menu_bar)

    def update_dock_menu(self):
        """Update the enabled state of dock buttons before the menu == shown"""
        for action in self.dock_menu.actions():
            layout = next(
                (
                    key
                    for key, name in self.docking_layouts.items()
                    if name == action.text()
                ),
                None,
            )
            if layout:
                if layout == self.position[0]:
                    action.setEnabled(False)
                    continue
                action.setEnabled(util.check_visible_layout(layout))

    def create_connections(self):
        self.dock_ui_btn.clicked.connect(self.dock_to_ui)

        self.settings_btn.triggered.connect(self.settings)
        self.reload_btn.triggered.connect(self.reload_cams_UI)
        self.close_btn.triggered.connect(partial(funcs.close_UI, self))

        self.uninstall_btn.triggered.connect(partial(funcs.unistall, self))

        self.followCam.triggered.connect(partial(self._run_tools, "followCam"))
        self.aimCam.triggered.connect(partial(self._run_tools, "aimCam"))
        self.multicams.triggered.connect(partial(self._run_tools, "multicams"))

        self.reset_cams_data.triggered.connect(lambda: self.process_prefs(reset=True))
        self.updates.triggered.connect(partial(funcs.check_for_updates, self))
        self.about.triggered.connect(self.coffee)

        self.version_bar.aboutToShow.connect(self.open_version_bar)

    def _run_tools(self, tool):
        funcs.run_tools(tool)

        self.reload_cams_UI()

    def open_version_bar(self):
        if not funcs.check_author():
            self.version_bar.close()
            self.version_bar.setEnabled(False)
            return

        try:
            import aleha_tools  # type: ignore

            reload(aleha_tools)
            local_version = aleha_tools.DATA.get("VERSION")

            online_version = updater.get_latest_version()
            if online_version < local_version:
                version = "Update needed\nLocal (%s)\nOnline (%s)" % (
                    local_version,
                    online_version,
                )
            else:
                version = "Up-to-date"

        except Exception as e:
            print(e)
            version = "Error..."
        self.latest_label.setText(version)
        self.latest_label.setFixedHeight(
            (version.strip().count("\n") + 1) * util.DPI(32)
        )

    def populate_version_bar(self):
        latest_action = QWidgetAction(self)

        self.latest_label = QLabel()
        self.latest_label.setFixedHeight(util.DPI(32))
        self.latest_label.setContentsMargins(util.DPI(20), 0, util.DPI(20), 0)
        self.latest_label.setStyleSheet(
            "font-size: " + str(util.DPI(14)) + "px; font-weight: bold;"
        )
        latest_action.setDefaultWidget(self.latest_label)
        self.version_bar.addAction(latest_action)

        self.open_github_desktop = self.version_bar.addAction("Open on GitHub Desktop")

        self.version_bar.addSeparator()

        self.compile_update = self.version_bar.addAction(
            QIcon(util.return_icon_path("updates")), "Compile Update"
        )
        self.generate_release_notes = self.version_bar.addAction(
            QIcon(util.return_icon_path("refresh")), "Generate Changes"
        )
        self.version_bar.addSeparator()

        self.open_release_notes = self.version_bar.addAction(
            QIcon(util.return_icon_path("load")), "Open Release Notes"
        )

        self.version_bar.addSeparator()

        self.debug_menu = self.version_bar.addMenu(
            QIcon(util.return_icon_path("debug")), "Debug Functions"
        )
        self.debug_menu.aboutToShow.connect(self.open_debug_bar)

        force_update = self.version_bar.addAction(
            QIcon(util.return_icon_path("updates")), "Force Install Update"
        )
        force_update.triggered.connect(
            partial(funcs.check_for_updates, self, force=True)
        )

        self.compile_update.triggered.connect(funcs.compile_version)

        self.generate_release_notes.triggered.connect(funcs.changes_compiler)

        self.open_github_desktop.triggered.connect(
            partial(
                os.startfile,
                r"C:\Users\alejandro\AppData\Local\GitHubDesktop\GitHubDesktop.exe",
            )
        )

        self.open_release_notes.triggered.connect(self.open_release_notes_function)

    def open_debug_bar(self):
        """Handles opening and resizing the debug bar in Maya."""
        from . import debug  # Importing the debug module

        reload(debug)
        debug.on_show(self.debug_menu)  # Populate the debug menu

    def open_release_notes_function(self):
        notes_path = r"\\hkey\temp\from_alejandro\cams_tool\release_notes.json"  # funcs.get_release_notes_path()
        if notes_path:
            if sys.platform == "win32":
                os.startfile(os.path.normpath(notes_path))
            else:
                import subprocess

                _open = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([_open, notes_path])
        else:
            cmds.error("Error: Release Notes file not found.")

    def set_global_preferences(self):
        self.set_scene_preferences()

        if self.startup_hud:
            pres = self.hud_settings["presets"]
            pref_sel = self.hud_settings["selected"]
            sel = pref_sel if len(pres.keys()) > pref_sel else None
            if sel is not None:
                hud.apply_selection(pres[list(pres.keys())[sel]])

        if not self.skip_update:
            cmds.evalDeferred(
                partial(funcs.check_for_updates, self, warning=False),
                lowestPriority=True,
            )

    def set_scene_preferences(self):
        if self.startup_viewport:
            model_editor_cams = funcs.get_camsDisplay_modeleditor()
            if model_editor_cams:
                for panel, camera in model_editor_cams.items():
                    funcs.look_thru(camera, panel)

        # Set Icons
        for dag in cmds.ls(type="dagContainer"):
            icon_attr = dag + ".iconName"
            if cmds.objExists(icon_attr):
                icon_path = cmds.getAttr(icon_attr)
                if "aleha_tools" in icon_path:
                    cams_type = os.path.basename(icon_path).split(".")[0]
                    cmds.setAttr(
                        icon_attr, util.return_icon_path(cams_type), type="string"
                    )

    def dock_to_ui(self, layout=None, orient=None):
        docked = True

        if not layout:
            layout_name = self.dock_ac_group.checkedAction().text()
            index = list(self.docking_layouts.values()).index(layout_name)
            layout = list(self.docking_layouts.keys())[index]
        if not orient:
            orient_name = self.pos_ac_group.checkedAction().text()
            index = list(self.docking_orients.values()).index(orient_name)
            orient = list(self.docking_orients.keys())[index]

        # Enable / Disable actions
        self.pos_ac_group.checkedAction().setEnabled(False)
        self.dock_ac_group.checkedAction().setEnabled(False)

        for group in [self.pos_ac_group, self.dock_ac_group]:
            for action in group.actions():
                action.setEnabled(not action.isChecked())

        # Build up kwargs for the workspaceControl command
        kwargs = {
            "e": True,
            # "visibleChangeCommand": self.visible_change_command,
            # "tp": ["west", 0],
            # "rsw": util.DPI(200),
            # "rsh": util.DPI(15),
        }

        if util.check_visible_layout(self.position[0]):
            kwargs["dockToControl"] = [layout, orient]

            self.process_prefs(position=[layout, orient])
            docked = False

        # Make the workspaceControl call just once
        cmds.workspaceControl(self.workspace_control_name, **kwargs)

        return docked

    def add_presets(self):
        self.hud_settings = settings.get_pref(
            "hudSettings"
        ) or settings.initial_settings().get("defaultSettings", None)

        self.menu_presets.clear()

        presets_ac_group = QActionGroup(self)
        if self.hud_settings:
            self.menu_presets.addSeparator().setText("Presets")

            if not self.hud_settings.get("presets", None):
                self.hud_presets = self.hud_settings
                self.hud_settings = {}
                self.hud_settings["presets"] = self.hud_presets
            if type(self.hud_settings.get("selected", None)) is not int:
                self.hud_settings["selected"] = 0

            hud_presets = self.hud_settings["presets"]
            selected = self.hud_settings["selected"]

            for ind, p in enumerate(hud_presets):
                preset = QAction(p, self)
                preset.setCheckable(True)
                presets_ac_group.addAction(preset)
                self.menu_presets.addAction(preset)
                if ind == selected:
                    preset.setChecked(True)
                preset.triggered.connect(
                    partial(self.hud_preset_triggered, ind, hud_presets[p])
                )

        self.menu_presets.addSeparator()

        self.hud_editor = self.menu_presets.addAction("HUD Editor")
        self.hud_editor.triggered.connect(partial(funcs.run_tools, "HUDWindow", self))

    def hud_preset_triggered(self, hud_index, preset):
        self.hud_settings["selected"] = hud_index
        settings.save_to_disk("hudSettings", self.hud_settings)
        hud.apply_selection(preset)

    def HUD_display_cam(self, state=None):
        if state is None:
            return cmds.headsUpDisplay(q=True, layoutVisibility=1)
        cmds.headsUpDisplay(e=True, layoutVisibility=state)

    def process_prefs(
        self,
        cam=None,
        near=None,
        far=None,
        overscan=None,
        mask_op=None,
        mask_color=None,
        position=None,
        startup_hud=None,
        startup_viewport=None,
        skip_update=None,
        save=True,
        reset=False,
    ):
        _initial_settings = settings.initial_settings()

        self.cams_prefs = self.user_prefs.get(
            "defaultCameraSettings", None
        ) or _initial_settings.get("defaultCameraSettings", None)
        self.startup_prefs = self.user_prefs.get(
            "startupSettings", {}
        ) or _initial_settings.get("startupSettings", {})

        # Set the value of the attribute to a dictionary of multiple variable values
        if cam:
            if cam != self.cams_prefs["camera"]:
                self.clearLayout(self.default_cam_layout)
                self.default_cam_btn = widgets.HoverButton(cam[0], self, width=False)
                self.default_cam_layout.addWidget(self.default_cam_btn)
                self.default_cam_btn.dropped.connect(
                    partial(funcs.drag_insert_camera, cam[0], self)
                )

                self.all_displayed_buttons["main"] = self.default_cam_btn
                if cam[0] in cmds.ls(sl=1):
                    self.set_selection_style(self.default_cam_btn, True)

            self.cams_prefs["camera"] = cam
        if near:
            self.cams_prefs["near_clip"] = near
        if far:
            self.cams_prefs["far_clip"] = far
        if overscan:
            self.cams_prefs["overscan"] = overscan
        if mask_op:
            self.cams_prefs["mask_opacity"] = mask_op
        if mask_color:
            self.cams_prefs["mask_color"] = mask_color

        if position:
            self.startup_prefs["position"] = position
        if startup_hud is not None:
            self.startup_prefs["startup_hud"] = startup_hud
        if startup_viewport is not None:
            self.startup_prefs["startup_viewport"] = startup_viewport
        if skip_update is not None:
            self.startup_prefs["skip_update"] = skip_update

        self.default_cam = (
            self.cams_prefs.get("camera", None)
            or _initial_settings["defaultCameraSettings"]["camera"]
        )

        self.default_overscan = (
            self.cams_prefs.get("overscan", None)
            or _initial_settings["defaultCameraSettings"]["overscan"]
        )

        self.default_near_clip_plane = (
            self.cams_prefs.get("near_clip", None)
            or _initial_settings["defaultCameraSettings"]["near_clip"]
        )

        self.default_far_clip_plane = (
            self.cams_prefs.get("far_clip", None)
            or _initial_settings["defaultCameraSettings"]["far_clip"]
        )

        self.default_resolution = (
            self.cams_prefs.get("display_resolution", None)
            or _initial_settings["defaultCameraSettings"]["display_resolution"]
        )

        self.default_gate_mask_opacity = (
            self.cams_prefs.get("mask_opacity", None)
            or _initial_settings["defaultCameraSettings"]["mask_opacity"]
        )

        self.default_gate_mask_color = (
            self.cams_prefs.get("mask_color", None)
            or _initial_settings["defaultCameraSettings"]["mask_color"]
        )

        self.position = (
            self.startup_prefs.get("position")
            if isinstance(self.startup_prefs, dict)
            and self.startup_prefs.get("position") is not None
            else _initial_settings["startupSettings"]["position"]
        )

        self.startup_hud = (
            self.startup_prefs.get("startup_hud")
            if isinstance(self.startup_prefs, dict)
            and self.startup_prefs.get("startup_hud") is not None
            else _initial_settings["startupSettings"]["startup_hud"]
        )

        self.startup_viewport = (
            self.startup_prefs.get("startup_viewport")
            if isinstance(self.startup_prefs, dict)
            and self.startup_prefs.get("startup_viewport") is not None
            else _initial_settings["startupSettings"]["startup_viewport"]
        )

        self.skip_update = (
            self.startup_prefs.get("skip_update")
            if isinstance(self.startup_prefs, dict)
            and self.startup_prefs.get("skip_update") is not None
            else _initial_settings["startupSettings"]["skip_update"]
        )

        self.confirm_exit = (
            self.startup_prefs.get("confirm_exit")
            if isinstance(self.startup_prefs, dict)
            and self.startup_prefs.get("confirm_exit") is not None
            else _initial_settings["startupSettings"]["confirm_exit"]
        )

        if save:
            if not reset:
                settings.save_to_disk("defaultCameraSettings", self.cams_prefs)
                settings.save_to_disk("startupSettings", self.startup_prefs)
            else:
                box = QMessageBox()
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle("About to erase All Settings!")
                box.setText(
                    "Are you sure you want to delete all the settings in Default Attributes?\nThis action is not undoable."
                )
                box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

                reset = box.button(QMessageBox.Yes)
                reset.setText("Reset")
                cancel = box.button(QMessageBox.No)
                cancel.setText("Cancel")
                box.exec_()

                if box.clickedButton() == reset:
                    settings.save_to_disk()

    def settings(self):
        self.process_prefs(save=False)
        try:
            self.settings_window.close()
            self.settings_window.deleteLater()
            self.settings_window = None
        except Exception:
            pass

        self.settings_window = widgets.DefaultSettings
        self.settings_window.show_dialog(self)

    def apply_camera_default(self, cam, button=None):
        parameters = {
            "overscan": self.default_overscan,
            "ncp": self.default_near_clip_plane,
            "fcp": self.default_far_clip_plane,
            "displayGateMaskOpacity": self.default_gate_mask_opacity,
            "displayFilmGate": self.default_resolution,
            "displayGateMaskColor": self.default_gate_mask_color,
        }

        for i, v in parameters.items():
            try:
                if i == "displayFilmGate":
                    if v[1]:
                        cmds.setAttr(cam + "." + i, v[0])
                        cmds.setAttr(cam + ".displayGateMask", v[0])
                        if button:
                            button.resolution_checkbox.setChecked(v[0])
                elif i == "displayGateMaskColor":
                    if v[1]:
                        r, g, b = v[0]
                        cmds.setAttr(cam + "." + i, r, g, b, type="double3")
                else:
                    if v[1]:
                        cmds.setAttr(cam + "." + i, v[0])
            except Exception:
                pass

    def clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                elif isinstance(item, QLayout):
                    self.clearLayout(item)
                    del item

    def reload_cams_UI(self):
        new_buttons = self.create_buttons()
        if new_buttons:
            self.line.show()
        else:
            self.line.hide()

    """
    Extra Functionality
    """

    def coffee(self):
        coffee_dialog = widgets.Coffee()
        coffee_dialog.exec_()

    def resizeEvent(self, event):
        def get_qt():
            cams_widget = omui.MQtUtil.findControl(self.workspace_control_name)
            if not cams_widget:
                return
            return util.get_maya_qt(cams_widget, QWidget)

        if cmds.workspaceControl(self.workspace_control_name, q=True, floating=True):
            topmost_parent = []
            cams_ui = get_qt()
            if not cams_ui:
                return
            while True:
                parent_widget = cams_ui.parent()
                if not parent_widget:
                    break
                topmost_parent.append(parent_widget)
                if isinstance(parent_widget, QMainWindow):
                    break
                cams_ui = parent_widget
            topmost_parent = topmost_parent[-2]
            current_width = topmost_parent.width()
            new_height = util.DPI(54)
            topmost_parent.resize(current_width, new_height)

        else:
            cams_ui = get_qt()
            if not cams_ui:
                return
            cams_ui = cams_ui.parent().parent()
            cams_ui.setFixedHeight(util.DPI(54))
            return

    def camera_creation_scripjob(self):
        new_camera = cmds.ls(sl=1)
        if not new_camera:
            return

        new_camera = new_camera[0]
        try:
            shape_type = cmds.nodeType(cmds.listRelatives(new_camera)) or cmds.nodeType(
                cmds.listRelatives(new_camera, shapes=True)[0]
            )
        except Exception:
            return

        if shape_type == "camera":
            self.reload_cams_UI()
            cmds.scriptJob(nodeDeleted=[new_camera, self.reload_cams_UI])

    def set_selection_style(self, button, selected=False):
        if selected:
            _width = button.sizeHint().width()
            button.setStyleSheet(
                button.styleSheet()
                + """
                QPushButton { 
                    border: 2px solid #6ba5cc;
                }
            """
            )
            button.setFixedWidth(_width)
        else:
            button.setStyleSheet(
                button.styleSheet()
                + """
                QPushButton { 
                    border: none;
                }
            """
            )

    def selection_changed_scripjob(self):
        for _, button in self.all_displayed_buttons.items():
            selected = button.camera in cmds.ls(sl=1)
            self.set_selection_style(button, selected)

    def sceneopened_scripjob(self):
        self.reload_cams_UI()
        self.set_scene_preferences()

    def menuchanged_scripjob(self):
        cmds.evalDeferred(
            cmds.evalDeferred(show, lowestPriority=True), lowestPriority=True
        )

    def add_scriptjobs(self):
        for cam in util.get_cameras():
            self.all_created_scriptjobs.append(
                cmds.scriptJob(nodeDeleted=[cam, self.reload_cams_UI])
            )

        self.all_created_scriptjobs.append(
            cmds.scriptJob(event=["SelectionChanged", self.selection_changed_scripjob])
        )

        # self.all_created_scriptjobs.append(cmds.scriptJob(event=["DagObjectCreated", self.camera_creation_scripjob]))

        self.all_created_scriptjobs.append(
            cmds.scriptJob(event=["SceneOpened", self.sceneopened_scripjob])
        )

        # self.all_created_scriptjobs.append(cmds.scriptJob(event=["SceneSaved", self.reload_cams_UI]))

        # self.all_created_scriptjobs.append(cmds.scriptJob(event=["MenuModeChanged", self.menuchanged_scripjob]))

        self.all_created_scriptjobs.append(
            cmds.scriptJob(
                event=[
                    "quitApplication",
                    lambda: funcs.close_all_Windows(self.objectName()),
                ]
            )
        )

    def kill_all_scriptJobs(self):
        for job_id in self.all_created_scriptjobs:
            if cmds.scriptJob(exists=job_id):
                cmds.scriptJob(kill=job_id, force=True)
        self.all_created_scriptjobs = []

    def dockCloseEventTriggered(self):
        funcs.close_all_Windows(self.objectName())
        self.kill_all_scriptJobs()
