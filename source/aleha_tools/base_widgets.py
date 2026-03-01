try:
    from PySide6.QtWidgets import (  # type: ignore
        QWidget,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QPushButton,
        QDialog,
        QFrame,
        QSizePolicy,
        QLayout,
    )
    from PySide6.QtGui import (  # type: ignore
        QIcon,
        QColor,
        QPixmap,
    )
    from PySide6.QtCore import (  # type: ignore
        Qt,
        QSize,
        QEventLoop,
    )
except ImportError:
    from PySide2.QtWidgets import (
        QWidget,
        QHBoxLayout,
        QVBoxLayout,
        QLabel,
        QPushButton,
        QDialog,
        QFrame,
        QSizePolicy,
        QLayout,
    )
    from PySide2.QtGui import (
        QIcon,
        QColor,
        QPixmap,
    )
    from PySide2.QtCore import (
        Qt,
        QSize,
        QEventLoop,
    )

from functools import partial
from .util import (
    DPI,
    return_icon_path,
    get_maya_qt,
)


class DialogButton(dict):
    """A dictionary subclass that supports the | operator to return a list of buttons."""

    def __init__(self, name_or_dict=None, **kwargs):
        if name_or_dict is not None:
            if isinstance(name_or_dict, (str, bytes)):
                kwargs["name"] = name_or_dict
                super().__init__(**kwargs)
            elif isinstance(name_or_dict, dict):
                super().__init__(name_or_dict, **kwargs)
            else:
                super().__init__(**kwargs)
        else:
            super().__init__(**kwargs)

    def copy(self):
        return DialogButton(super().copy())

    def __eq__(self, other):
        if isinstance(other, (str, bytes)):
            return self.get("name") == other
        return super().__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __or__(self, other):
        if isinstance(other, (dict, DialogButton)):
            return DialogButtonList([self, other])
        if isinstance(other, list):
            return DialogButtonList([self] + other)
        # Support dict union for Python 3.9+ if available
        if hasattr(super(), "__or__"):
            return super().__or__(other)
        return NotImplemented

    def __ror__(self, other):
        if isinstance(other, list):
            return DialogButtonList(other + [self])
        if hasattr(super(), "__ror__"):
            return super().__ror__(other)
        return NotImplemented


class DialogButtonList(list):
    """A list subclass that supports the | operator to combine buttons."""

    def __or__(self, other):
        if isinstance(other, (dict, DialogButton)):
            return DialogButtonList(self + [other])
        if isinstance(other, list):
            return DialogButtonList(self + other)
        return self


class HoverableIcon:
    HIGHLIGHT_HEX = "#282828"

    @staticmethod
    def apply(btn, icon_path, highlight=False, brighten_amount=80):
        base_icon = QIcon(icon_path)
        if highlight:
            btn._icon_normal = HoverableIcon._color_icon(
                base_icon, HoverableIcon.HIGHLIGHT_HEX, btn.iconSize()
            )
        else:
            btn._icon_normal = base_icon

        btn._icon_hover = HoverableIcon._brighten_icon(btn._icon_normal, brighten_amount, btn.iconSize())

        btn.setIcon(btn._icon_normal)

        prev_enter = btn.enterEvent
        prev_leave = btn.leaveEvent

        def enterEvent(event):
            btn.setIcon(btn._icon_hover)
            if prev_enter:
                return prev_enter(event)

        def leaveEvent(event):
            btn.setIcon(btn._icon_normal)
            if prev_leave:
                return prev_leave(event)

        btn.enterEvent = enterEvent
        btn.leaveEvent = leaveEvent

    @staticmethod
    def _color_icon(icon, color, size):
        if isinstance(color, (str, bytes)):
            color = QColor(color)

        pix = icon.pixmap(size)
        img = pix.toImage()
        for x in range(img.width()):
            for y in range(img.height()):
                c = img.pixelColor(x, y)
                if c.alpha() > 0:
                    img.setPixelColor(x, y, QColor(color.red(), color.green(), color.blue(), c.alpha()))

        return QIcon(QPixmap.fromImage(img))

    @staticmethod
    def _brighten_icon(icon, amount, size):
        pix = icon.pixmap(size)
        img = pix.toImage()
        for x in range(img.width()):
            for y in range(img.height()):
                c = img.pixelColor(x, y)
                img.setPixelColor(
                    x,
                    y,
                    QColor(
                        min(c.red() + amount, 255),
                        min(c.green() + amount, 255),
                        min(c.blue() + amount, 255),
                        c.alpha(),
                    ),
                )
        return QIcon(QPixmap.fromImage(img))


class FlatButton(QPushButton):
    """A customizable, flat-styled button for the bottom bar."""

    STYLE_SHEET = """
        FlatButton {
            color: %s;
            background-color: %s;
            border: none;
            border-radius: %spx;
            padding: 8px 12px;
            font-weight: %s;
            font-size: %spx;
        }
        FlatButton:hover {
            background-color: %s;
        }
        FlatButton:pressed {
            background-color: %s;
        }
    """

    DEFAULT_COLOR = "#ffffff"
    DEFAULT_BACKGROUND = "#5D5D5D"
    DEFAULT_HOVER_BACKGROUND = "#707070"
    DEFAULT_PRESSED_BACKGROUND = "#252525"

    HIGHLIGHT_COLOR = "#282828"
    HIGHLIGHT_BACKGROUND = "#bdbdbd"
    HIGHLIGHT_HOVER_BACKGROUND = "#cfcfcf"
    HIGHLIGHT_PRESSED_BACKGROUND = "#707070"

    DEFAULT_FONT_SIZE = DPI(12)
    HIGHLIGHT_FONT_SIZE = DPI(16)

    def __init__(
        self,
        text,
        color=DEFAULT_COLOR,
        background=DEFAULT_BACKGROUND,
        icon_path=None,
        border=8,
        highlight=False,
        parent=None,
    ):
        super().__init__(text, parent)
        self.setFlat(True)
        self.setFixedHeight(32)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if icon_path:
            self.setIconSize(QSize(20, 20))
            HoverableIcon.apply(self, icon_path, highlight=highlight)

        if highlight:
            self.setIconSize(QSize(24, 24))
            color = self.HIGHLIGHT_COLOR
            background = self.HIGHLIGHT_BACKGROUND
            hover_background = self.HIGHLIGHT_HOVER_BACKGROUND
            pressed_background = self.HIGHLIGHT_PRESSED_BACKGROUND
            font_size = self.HIGHLIGHT_FONT_SIZE
            weight = "bold"
        elif background != self.DEFAULT_BACKGROUND:
            try:
                base_background = int(background.lstrip("#"), 16)
                r, g, b = (
                    (base_background >> 16) & 0xFF,
                    (base_background >> 8) & 0xFF,
                    base_background & 0xFF,
                )
            except Exception:
                r, g, b = 93, 93, 93
            hover_background = "#%02x%02x%02x" % (min(r + 10, 255), min(g + 10, 255), min(b + 10, 255))
            pressed_background = "#%02x%02x%02x" % (max(r - 10, 0), max(g - 10, 0), max(b - 10, 0))
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"
        else:
            hover_background = self.DEFAULT_HOVER_BACKGROUND
            pressed_background = self.DEFAULT_PRESSED_BACKGROUND
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"

        self.setStyleSheet(
            self.STYLE_SHEET
            % (
                color,
                background,
                border * 1.4,
                weight,
                font_size,
                hover_background,
                pressed_background,
            )
        )


class BottomBar(QFrame):
    """
    A container widget for arranging FlatButtons horizontally.
    """

    def __init__(self, buttons=[], margins=8, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(DPI(margins), DPI(margins), DPI(margins), DPI(margins))
        layout.setSpacing(DPI(6))

        for button in buttons:
            layout.addWidget(button)


class QFlatDialog(QDialog):
    BORDER_RADIUS = 5

    # Button Preconfigurations
    CustomButton = DialogButton

    Yes = DialogButton("Yes", positive=True, icon=return_icon_path("apply"))
    Ok = DialogButton("Ok", positive=True, icon=return_icon_path("apply"))

    No = DialogButton("No", positive=False, icon=return_icon_path("cancel"))
    Cancel = DialogButton("Cancel", positive=False, icon=return_icon_path("cancel"))
    Close = DialogButton("Close", positive=False, icon=return_icon_path("close"))

    def __init__(self, parent=None, buttons=None, highlight=None, closeButton=False):
        if parent is None:
            parent = get_maya_qt()

        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Tool)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        self.bottomBar = None
        self.highlighted_button = highlight
        self._buttons_to_init = buttons
        self._default_button = None

    def _buttonConfigHook(self, index, config):
        """Hook for subclasses to modify button configuration before creation."""
        return config

    def _defineButtons(self, buttons):
        created_buttons = []
        for i, btn_data in enumerate(buttons):
            if isinstance(btn_data, (str, bytes)):
                config = DialogButton(btn_data)
            else:
                config = btn_data.copy()

            config = self._buttonConfigHook(i, config)

            # Handle automatic highlighting if matches highlight name or dict
            is_highlighted = config.get("highlight", False)
            if self.highlighted_button:
                if btn_data == self.highlighted_button or config.get("name") == self.highlighted_button:
                    is_highlighted = True

            btn = FlatButton(
                text=config.get("name", "Button"),
                background=config.get("background", "#5D5D5D"),
                icon_path=config.get("icon"),
                highlight=is_highlighted,
                border=self.BORDER_RADIUS,
            )

            # Connect callback if provided
            callback = config.get("callback")
            if callback and callable(callback):
                btn.clicked.connect(callback)

            if is_highlighted:
                btn.setAutoDefault(True)
                btn.setDefault(True)
                self._default_button = btn

            created_buttons.append(btn)
        return created_buttons

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._default_button:
                self._default_button.click()
                return
        super().keyPressEvent(event)

    def setBottomBar(self, buttons=None, closeButton=False, highlight=None):
        """Dynamically creates and adds a bottom bar with custom buttons."""
        if self.bottomBar:
            self.root_layout.removeWidget(self.bottomBar)
            self.bottomBar.setParent(None)
            self.bottomBar.deleteLater()
            self.bottomBar = None

        if highlight:
            self.highlighted_button = highlight

        # Prepare button data list
        btn_data = []
        if buttons:
            if isinstance(buttons, (list, tuple)):
                btn_data.extend(buttons)
            else:
                btn_data.append(buttons)

        if closeButton:
            close_cfg = self.Close.copy()
            # If no callback is defined, default to self.close
            if not close_cfg.get("callback"):
                close_cfg["callback"] = self.close
            btn_data.append(close_cfg)

        created_buttons = self._defineButtons(btn_data)

        if created_buttons:
            self.bottomBar = BottomBar(buttons=created_buttons, parent=self)
            self.root_layout.addWidget(self.bottomBar)


class QFlatConfirmDialog(QFlatDialog):
    TEXT_COLOR = "#bbbbbb"

    def __init__(
        self,
        window="Confirm",
        title="",
        message="",
        buttons=["Ok"],
        closeButton=True,
        highlight=None,
        icon=None,
        exclusive=True,
        parent=None,
    ):
        super().__init__(parent=parent, buttons=buttons, highlight=highlight, closeButton=closeButton)

        # Ensure we are a Dialog but inherit Tool if parent has it
        new_flags = self.windowFlags() | Qt.Dialog
        if parent and (parent.windowFlags() & Qt.Tool):
            new_flags |= Qt.Tool

        self.setWindowFlags(new_flags)
        if parent:
            self.setParent(parent)

        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.root_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.setWindowTitle(window or "Confirm")
        self.clicked_button = None

        self._exclusive = exclusive
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(DPI(25), DPI(20), DPI(25), DPI(20))

        if icon:
            icon_label = QLabel()
            pix = QPixmap(icon)
            if not pix.isNull():
                icon_dim = DPI(80)
                icon_label.setPixmap(
                    pix.scaled(icon_dim, icon_dim, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                icon_label.setFixedSize(icon_dim, icon_dim)
                content_layout.addWidget(icon_label, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(DPI(5))
        content_layout.addLayout(text_layout, 1)

        if title:
            self.title_label = QLabel(title)
            self.title_label.setWordWrap(True)
            self.title_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
            self.title_label.setStyleSheet(
                "font-size: %spx; color: %s; font-weight: bold;" % (DPI(18), self.TEXT_COLOR)
            )
            text_layout.addWidget(self.title_label)

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("font-size: %spx; color: %s;" % (DPI(11.5), self.TEXT_COLOR))
        text_layout.addWidget(self.message_label)

        self.root_layout.addWidget(content_widget)

        self.setBottomBar(buttons, closeButton=closeButton, highlight=highlight)
        self.adjustSize()

    def _buttonConfigHook(self, index, config):
        """
        Adds specific callback logic for confirmation buttons.
        Determine if this button  is considered "positive
        """
        if isinstance(config, (str, bytes)):
            name = config
            is_pos = index == 0
            original_config = DialogButton(name, positive=is_pos)
        else:
            name = config.get("name", "Button")
            is_pos = config.get("positive", index == 0)
            # Take a snapshot to avoid polluting the result with the internal callback
            original_config = config.copy()

        config["callback"] = partial(self._on_button_clicked, original_config)
        return config

    def _on_button_clicked(self, config):
        self.clicked_button = config
        if config.get("positive", False):
            self.accept()
        else:
            self.reject()

    @classmethod
    def question(
        cls,
        parent,
        window,
        message,
        buttons=None,
        highlight=None,
        closeButton=False,
        title="Are you sure?",
        **kwargs,
    ):
        """Static-like helper to create and show a confirm dialog."""
        if buttons is None:
            buttons = [cls.Yes, cls.No]
        dlg = cls(
            window=window,
            title=title,
            message=message,
            buttons=buttons,
            highlight=highlight,
            closeButton=closeButton,
            parent=parent,
            **kwargs,
        )
        dlg.exec_()
        return dlg.clicked_button

    def confirm(self):
        """Executes the dialog and returns True if a 'positive' button was clicked."""
        if self._exclusive:
            return self.exec_() == QDialog.Accepted

        self.show()
        self.raise_()
        self.activateWindow()
        loop = QEventLoop()
        self.finished.connect(loop.quit)
        loop.exec_()
        return self.result() == QDialog.Accepted
