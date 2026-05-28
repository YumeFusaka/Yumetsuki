from pathlib import Path
from dataclasses import dataclass
import re

from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QAbstractSpinBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QTextEdit,
    QTreeWidget,
    QWidget,
)


COMBO_ARROW_ICON = (Path(__file__).resolve().parent / "assets" / "combo-down.svg").as_posix()


@dataclass(frozen=True)
class SettingsFontTokens:
    family: str
    raw: int
    base: int
    small: int
    body: int
    list: int
    button: int
    section: int
    title: int
    mono: int
    html_small: int
    html_body: int


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def settings_font_tokens(system_config=None) -> SettingsFontTokens:
    family = getattr(system_config, "font_family", "") or "Microsoft YaHei"
    try:
        raw = int(getattr(system_config, "font_size", 14))
    except (TypeError, ValueError):
        raw = 14
    base = _clamp(raw, 12, 16)
    small = max(base - 1, 11)
    return SettingsFontTokens(
        family=family,
        raw=raw,
        base=base,
        small=small,
        body=base,
        list=base,
        button=base,
        section=min(base + 1, 16),
        title=min(base + 5, 20),
        mono=small,
        html_small=small,
        html_body=base,
    )


def font_for_role(tokens: SettingsFontTokens, role: str = "body") -> QFont:
    size = getattr(tokens, role, tokens.body)
    font = QFont(tokens.family)
    font.setPointSize(int(size))
    if role == "title":
        font.setBold(True)
    elif role == "section":
        font.setBold(True)
    return font


def set_settings_font_role(widget: QWidget, role: str) -> QWidget:
    widget.setProperty("settingsFontRole", role)
    return widget


def settings_page_title(label: QLabel) -> QLabel:
    set_settings_font_role(label, "title")
    label.setStyleSheet("font-weight: bold; color: #7a3a5a;")
    return label


def sakura_combo_box_style(font_size: int | None = None) -> str:
    size = int(font_size or 13)
    return f"""
QComboBox {{
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 8px;
    padding: 8px 28px 8px 10px;
    color: #4a3040;
    font-size: {size}px;
    min-height: 18px;
    selection-background-color: rgba(255, 210, 224, 0.9);
    selection-color: #4a3040;
}}
QComboBox:focus {{
    border-color: #d4567a;
    background: rgba(255, 255, 255, 0.86);
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
    background: transparent;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}
QComboBox::down-arrow {{
    image: url({COMBO_ARROW_ICON});
    width: 10px;
    height: 7px;
    border: none;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: rgba(255, 250, 252, 0.98);
    border: 1px solid rgba(220, 160, 180, 0.35);
    selection-background-color: rgba(255, 210, 224, 0.9);
    selection-color: #4a3040;
    color: #4a3040;
    padding: 4px;
}}
"""


SAKURA_COMBO_BOX_STYLE = sakura_combo_box_style()


SAKURA_MENU_STYLE = """
QMenu {
    background: #fffafc;
    border: 1px solid rgba(220, 160, 180, 0.35);
    border-radius: 8px;
    padding: 6px;
    color: #4a3040;
}
QMenu::item {
    background: transparent;
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    color: #4a3040;
}
QMenu::item:selected {
    background: rgba(255, 222, 232, 0.95);
    color: #9b3060;
}
QMenu::separator {
    height: 1px;
    background: rgba(220, 160, 180, 0.25);
    margin: 5px 8px;
}
"""


SAKURA_TOOLTIP_STYLE = """
QToolTip {
    background: #fff0f3;
    color: #4a3040;
    border: 1px solid rgba(220, 160, 180, 0.45);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
"""


def apply_sakura_menu_theme(menu: QMenu) -> None:
    menu.setStyleSheet(SAKURA_MENU_STYLE)
    palette = menu.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#fffafc"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#fffafc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#fffafc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#4a3040"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#4a3040"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#ffdee8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#9b3060"))
    menu.setPalette(palette)
    menu.setAutoFillBackground(True)


class SakuraMenuEventFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QMenu) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
            QEvent.Type.ShowToParent,
        }:
            apply_sakura_menu_theme(watched)
        return super().eventFilter(watched, event)


class WheelGuardEventFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.Wheel:
            return super().eventFilter(watched, event)
        if not isinstance(watched, (QComboBox, QAbstractSpinBox)):
            return super().eventFilter(watched, event)
        if _control_or_child_has_focus(watched):
            return super().eventFilter(watched, event)
        event.ignore()
        parent = watched.parentWidget()
        if parent is not None:
            QApplication.sendEvent(parent, event)
        return True


def install_sakura_menu_theme(app: QApplication | None = None) -> None:
    app = app or QApplication.instance()
    if app is None:
        return
    if getattr(app, "_sakura_menu_event_filter", None) is None:
        event_filter = SakuraMenuEventFilter(app)
        app.installEventFilter(event_filter)
        app._sakura_menu_event_filter = event_filter
    if getattr(app, "_settings_wheel_guard_event_filter", None) is None:
        event_filter = WheelGuardEventFilter(app)
        app.installEventFilter(event_filter)
        app._settings_wheel_guard_event_filter = event_filter


def apply_system_appearance(app: QApplication, system_config) -> None:
    system_config.theme = "sakura"
    font = QFont(system_config.font_family or "Microsoft YaHei")
    font.setPointSize(max(1, int(system_config.font_size)))
    app.setFont(font)
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#fff0f3"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#4a3040"))
    app.setPalette(palette)
    install_sakura_menu_theme(app)


def apply_settings_item_font(item, system_config) -> None:
    tokens = settings_font_tokens(system_config)
    item.setFont(font_for_role(tokens, "list"))


def apply_settings_tree_item_font(item, system_config) -> None:
    tokens = settings_font_tokens(system_config)
    _apply_settings_tree_item_font_with_tokens(item, tokens)


def apply_settings_fonts(root: QWidget, system_config) -> None:
    tokens = settings_font_tokens(system_config)
    tree_apply = getattr(root, "apply_settings_font_tree", None)
    if callable(tree_apply) and tree_apply(tokens):
        root.setProperty("_settingsFontTreeTokenKey", _settings_font_token_key(tokens))
        return
    _apply_settings_fonts_to_widget(root, tokens)
    for child in root.findChildren(QWidget):
        _apply_settings_fonts_to_widget(child, tokens)


def _apply_settings_fonts_to_widget(widget: QWidget, tokens: SettingsFontTokens) -> None:
    token_key = _settings_font_token_key(tokens)
    if widget.property("_settingsFontTokenKey") == token_key:
        if isinstance(widget, QListWidget):
            item_role = _item_font_role(widget)
            for index in range(widget.count()):
                item = widget.item(index)
                if item is not None:
                    item.setFont(font_for_role(tokens, item_role))
        if isinstance(widget, QTreeWidget):
            for index in range(widget.topLevelItemCount()):
                _apply_settings_tree_item_font_with_tokens(widget.topLevelItem(index), tokens)
        return

    role = widget.property("settingsFontRole")
    role_name = str(role) if role else ""
    if role:
        _set_font_if_changed(widget, font_for_role(tokens, role_name))
        _ensure_widget_font_size_style(widget, int(getattr(tokens, role_name, tokens.body)))
    elif isinstance(widget, QLabel):
        _set_font_if_changed(widget, font_for_role(tokens, "body"))
    elif isinstance(widget, QPushButton):
        _set_font_if_changed(widget, font_for_role(tokens, "button"))
    elif isinstance(widget, (QLineEdit, QComboBox)):
        _set_font_if_changed(widget, font_for_role(tokens, "body"))
    elif isinstance(widget, QTextEdit):
        _set_font_if_changed(widget, font_for_role(tokens, "mono"))
    elif isinstance(widget, (QListWidget, QTreeWidget)):
        _set_font_if_changed(widget, font_for_role(tokens, "list"))
    elif isinstance(widget, QGroupBox):
        _set_font_if_changed(widget, font_for_role(tokens, "section"))
    else:
        _set_font_if_changed(widget, font_for_role(tokens, "body"))

    _rewrite_widget_font_size_stylesheet(widget, tokens, role_name)
    apply_tokens = getattr(widget, "apply_settings_tokens", None)
    if callable(apply_tokens):
        apply_tokens(tokens)
    if isinstance(widget, QComboBox) and not _ancestor_has_combo_box_style(widget):
        _set_style_sheet_if_changed(widget, sakura_combo_box_style(tokens.body))
    if isinstance(widget, QListWidget):
        item_role = _item_font_role(widget)
        for index in range(widget.count()):
            item = widget.item(index)
            if item is not None:
                item.setFont(font_for_role(tokens, item_role))
    if isinstance(widget, QTreeWidget):
        for index in range(widget.topLevelItemCount()):
            _apply_settings_tree_item_font_with_tokens(widget.topLevelItem(index), tokens)
    widget.setProperty("_settingsFontTokenKey", token_key)


def _settings_font_token_key(tokens: SettingsFontTokens) -> tuple:
    return (
        tokens.family,
        tokens.raw,
        tokens.base,
        tokens.small,
        tokens.body,
        tokens.list,
        tokens.button,
        tokens.section,
        tokens.title,
        tokens.mono,
        tokens.html_small,
        tokens.html_body,
    )


def _apply_settings_tree_item_font_with_tokens(item, tokens: SettingsFontTokens) -> None:
    for column in range(item.columnCount()):
        item.setFont(column, font_for_role(tokens, "list"))
    for index in range(item.childCount()):
        _apply_settings_tree_item_font_with_tokens(item.child(index), tokens)


def _item_font_role(widget: QWidget) -> str:
    role = widget.property("settingsItemFontRole") or widget.property("settingsFontRole") or "list"
    return str(role)


def _rewrite_widget_font_size_stylesheet(widget: QWidget, tokens: SettingsFontTokens, role: str) -> None:
    style = widget.styleSheet()
    if "font-size:" not in style:
        return

    def size_for_selector(selector: str) -> int:
        if role:
            return int(getattr(tokens, role, tokens.body))
        if "#logActionButton" in selector or "#pluginList::item" in selector:
            return tokens.small
        if "QPushButton" in selector:
            return tokens.button
        if "QListWidget" in selector or "QTreeWidget" in selector:
            return tokens.list
        if "QTextEdit" in selector:
            return tokens.mono
        if "QGroupBox" in selector:
            return tokens.section
        return tokens.body

    def rewrite_block(match: re.Match) -> str:
        selector = match.group(1)
        declarations = match.group(2)
        size = size_for_selector(selector)
        rewritten_declarations = re.sub(
            r"font-size:\s*\d+px",
            f"font-size: {int(size)}px",
            declarations,
        )
        if rewritten_declarations == declarations:
            return match.group(0)
        return f"{selector}{{{rewritten_declarations}}}"

    rewritten = re.sub(r"([^{}]+)\{([^{}]*)\}", rewrite_block, style)
    if rewritten == style:
        fallback_size = getattr(tokens, role, tokens.body) if role else tokens.body
        rewritten = re.sub(r"font-size:\s*\d+px", f"font-size: {int(fallback_size)}px", style)
    if rewritten != style:
        _set_style_sheet_if_changed(widget, rewritten)


def _ensure_widget_font_size_style(widget: QWidget, size: int) -> None:
    style = widget.styleSheet().strip()
    if not style:
        _set_style_sheet_if_changed(widget, f"font-size: {int(size)}px;")
        return
    if "{" in style or "}" in style:
        rewritten = re.sub(r"font-size:\s*\d+px", f"font-size: {int(size)}px", style)
        if rewritten != style:
            _set_style_sheet_if_changed(widget, rewritten)
        return
    if "font-size:" in style:
        _set_style_sheet_if_changed(
            widget,
            re.sub(r"font-size:\s*\d+px", f"font-size: {int(size)}px", style),
        )
        return
    separator = "" if style.endswith(";") else ";"
    _set_style_sheet_if_changed(widget, f"{style}{separator} font-size: {int(size)}px;")


def _set_style_sheet_if_changed(widget: QWidget, style: str) -> None:
    if widget.styleSheet() != style:
        widget.setStyleSheet(style)


def _set_font_if_changed(widget: QWidget, font: QFont) -> None:
    current = widget.font()
    if (
        current.family() == font.family()
        and current.pointSize() == font.pointSize()
        and current.bold() == font.bold()
    ):
        return
    widget.setFont(font)


def _ancestor_has_combo_box_style(widget: QWidget) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if "QComboBox" in parent.styleSheet():
            return True
        parent = parent.parentWidget()
    return False


def _control_or_child_has_focus(widget: QWidget) -> bool:
    if widget.hasFocus():
        return True
    focus_widget = QApplication.focusWidget()
    if focus_widget is None:
        return False
    return focus_widget is widget or widget.isAncestorOf(focus_widget)
