from __future__ import annotations

import json
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config.manager import ConfigManager
from core.plugin_host import PluginHost
from ui.settings.feedback import confirm_action, show_feedback
from ui.theme import (
    SAKURA_COMBO_BOX_STYLE,
    SAKURA_TOOLTIP_STYLE,
    apply_settings_fonts,
    font_for_role,
    set_settings_font_role,
    settings_font_tokens,
    settings_page_title,
)


BUILTIN_PLUGINS = {"system_control", "web_automation", "example_echo"}
PERMISSION_LEVELS = ["low", "medium", "high"]

DIALOG_STYLE = """
QDialog {
    background: #fff5f7; color: #4a3040;
}
QLabel { color: #4a3040; font-size: 13px; }
QLineEdit {
    background: rgba(255,255,255,0.8);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 10px;
    color: #4a3040; font-size: 13px;
}
QLineEdit:focus { border-color: #d4567a; }
QPushButton {
    background: rgba(255,200,210,0.4);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 16px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton:hover { background: rgba(255,154,162,0.4); }
""" + SAKURA_COMBO_BOX_STYLE

PAGE_STYLE = """
QLabel { color: #6b4a5a; font-size: 13px; }
QGroupBox {
    color: #7a4060; font-size: 15px; font-weight: bold;
    border: 1px solid rgba(220, 160, 180, 0.2);
    border-radius: 10px; margin-top: 12px; padding-top: 14px;
    background: rgba(255, 255, 255, 0.35);
}
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 6px; }
QListWidget {
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220, 160, 180, 0.25);
    border-radius: 8px; padding: 8px; color: #4a3040;
    outline: none;
}
QListWidget#pluginList::item { padding: 5px 8px; border-radius: 6px; color: #5a3050; font-size: 12px; }
QListWidget#pluginList::item:selected {
    background: rgba(255, 154, 162, 0.25);
    color: #9b3060; border: 1px solid #d4567a;
}
QListWidget#pluginList::item:hover { background: rgba(255, 200, 210, 0.2); }
QListWidget:focus { border-color: #d4567a; }
QTextEdit {
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220, 160, 180, 0.25);
    border-radius: 8px;
    padding: 10px 12px;
    color: #4a3040;
    font-size: 12px;
}
QPushButton {
    background: rgba(255,255,255,0.5);
    border: 1px solid rgba(220, 160, 180, 0.3);
    border-radius: 6px; padding: 7px 14px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton:hover { background: rgba(255, 200, 210, 0.4); }
QPushButton:disabled { color: rgba(107, 74, 90, 0.45); background: rgba(255,255,255,0.3); }
QPushButton#dangerButton {
    color: #9b3060;
    border-color: rgba(190, 70, 96, 0.35);
    background: rgba(255, 236, 240, 0.72);
}
QPushButton#dangerButton:hover { background: rgba(255, 218, 226, 0.88); }
QSplitter::handle { background: rgba(220, 160, 180, 0.16); }
""" + SAKURA_COMBO_BOX_STYLE + SAKURA_TOOLTIP_STYLE


@dataclass(frozen=True)
class PluginCatalogEntry:
    name: str
    description: str
    source: str


def _plugins_root() -> Path:
    return Path(__file__).parent.parent.parent.parent / "plugins"


def _is_builtin_plugin(plugin_dir: Path) -> bool:
    return plugin_dir.name in BUILTIN_PLUGINS


def _format_plugin_status_detail(status) -> str:
    state = "已加载" if status.loaded else "加载失败"
    source = "内置插件" if _is_builtin_plugin(Path(status.path)) else "外部插件"
    return "\n".join([
        f"名称：{status.name}",
        f"来源：{source}",
        f"状态：{state}",
        f"工具数量：{status.tools_count}",
        f"说明：{status.description or '无'}",
        f"路径：{status.path}",
        f"消息：{status.message or '无'}",
    ])


def _copy_plugin_dir(src: Path, dest_root: Path) -> Path | None:
    if not src.is_dir() or not (src / "plugin.py").exists():
        return None
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / src.name
    if dest.exists():
        return None
    shutil.copytree(src, dest)
    return dest


def _remove_plugin_dir(plugin_dir: Path, dest_root: Path) -> bool:
    try:
        plugin_dir.relative_to(dest_root)
    except ValueError:
        return False
    if _is_builtin_plugin(plugin_dir):
        return False
    if not plugin_dir.is_dir() or not (plugin_dir / "plugin.py").exists():
        return False
    shutil.rmtree(plugin_dir)
    return True


def _load_catalog_entries(index_path_or_url: str) -> list[PluginCatalogEntry]:
    raw = index_path_or_url.strip()
    if not raw:
        return []
    if raw.startswith(("http://", "https://")):
        with urllib.request.urlopen(raw, timeout=10) as response:
            body = response.read().decode("utf-8")
    else:
        body = Path(raw).read_text(encoding="utf-8")
    data = json.loads(body)
    items = data if isinstance(data, list) else data.get("plugins", [])
    entries: list[PluginCatalogEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        source = str(item.get("path") or item.get("url") or item.get("source") or "").strip()
        if name and source:
            entries.append(PluginCatalogEntry(
                name=name,
                description=str(item.get("description", "")).strip(),
                source=source,
            ))
    return entries


def _safe_extract_zip(archive: Path, extract_dir: Path) -> None:
    extract_root = extract_dir.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (extract_dir / member.filename).resolve()
            try:
                target.relative_to(extract_root)
            except ValueError as exc:
                raise ValueError("插件压缩包包含不安全路径。") from exc
        zf.extractall(extract_dir)


def _stage_catalog_source(source: str) -> Path | None:
    raw = source.strip()
    if not raw:
        return None
    if raw.startswith(("http://", "https://")):
        tmp_dir = Path(tempfile.mkdtemp(prefix="yumetsuki_plugin_"))
        archive = tmp_dir / "plugin.zip"
        urllib.request.urlretrieve(raw, archive)
        if not zipfile.is_zipfile(archive):
            return None
        extract_dir = tmp_dir / "extracted"
        _safe_extract_zip(archive, extract_dir)
        candidates = [extract_dir] + [p for p in extract_dir.iterdir() if p.is_dir()]
        return next((p for p in candidates if (p / "plugin.py").exists()), None)
    path = Path(raw)
    if path.is_file() and zipfile.is_zipfile(path):
        tmp_dir = Path(tempfile.mkdtemp(prefix="yumetsuki_plugin_"))
        extract_dir = tmp_dir / "extracted"
        _safe_extract_zip(path, extract_dir)
        candidates = [extract_dir] + [p for p in extract_dir.iterdir() if p.is_dir()]
        return next((p for p in candidates if (p / "plugin.py").exists()), None)
    if path.is_dir() and (path / "plugin.py").exists():
        return path
    return None


class PluginPage(QWidget):
    def __init__(self, parent=None, config: ConfigManager | None = None):
        super().__init__(parent)
        self._config = config or ConfigManager()
        self._host = PluginHost(_plugins_root())
        self.setStyleSheet(PAGE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)

        title = settings_page_title(QLabel("插件"))
        layout.addWidget(title)

        desc = QLabel("管理本地插件、内置插件权限和外部插件导入。MCP 服务器已拆分到独立页面。")
        desc.setStyleSheet("color: #8c6b7a; font-size: 13px;")
        layout.addWidget(desc)

        top_row = QHBoxLayout()
        self._summary = QLabel("插件工具：0")
        self._summary.setStyleSheet("color: #6b4a5a; font-size: 12px; font-weight: bold;")
        top_row.addWidget(self._summary)
        top_row.addStretch()
        refresh_btn = QPushButton("↻ 刷新插件")
        refresh_btn.clicked.connect(lambda: self._refresh_plugins(notify=True))
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(splitter, 1)

        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)

        list_caption = QLabel("插件列表")
        list_caption.setStyleSheet("color: #7a4060; font-size: 13px; font-weight: bold;")
        list_layout.addWidget(list_caption)

        self._list = QListWidget()
        self._list.setObjectName("pluginList")
        self._list.setProperty("settingsItemFontRole", "small")
        self._list.currentItemChanged.connect(self._sync_detail)
        self._list.setMinimumHeight(360)
        self._list.setMinimumWidth(340)
        self._list.setUniformItemSizes(True)
        self._list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        list_layout.addWidget(self._list, 1)
        splitter.addWidget(list_panel)

        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(12, 0, 0, 0)
        side_layout.setSpacing(10)

        detail_caption = QLabel("诊断详情")
        detail_caption.setStyleSheet("color: #7a4060; font-size: 13px; font-weight: bold;")
        side_layout.addWidget(detail_caption)

        self._detail = QTextEdit("选择插件查看诊断详情。")
        self._detail.setReadOnly(True)
        self._detail.setAcceptRichText(False)
        self._detail.setMinimumHeight(132)
        self._detail.setMaximumHeight(170)
        self._detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        side_layout.addWidget(self._detail)

        permissions = QGroupBox("内置插件权限")
        form = QFormLayout(permissions)
        form.setContentsMargins(16, 18, 16, 14)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self._system_control_permission = self._permission_combo(
            self._config.agent.system_control.permission_level
        )
        self._web_automation_permission = self._permission_combo(
            self._config.agent.web_automation.permission_level
        )
        form.addRow("系统控制:", self._system_control_permission)
        form.addRow("Web 自动化:", self._web_automation_permission)
        hint = QLabel(
            "low 仅允许低风险操作；medium 允许常用文件/网页/浏览器操作；high 允许命令执行、点击填写等高风险能力。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        form.addRow("", hint)
        side_layout.addWidget(permissions)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        import_btn = QPushButton("+ 导入本地插件")
        import_btn.setToolTip("导入包含 plugin.py 的本地插件目录，导入前会要求确认第三方代码风险。")
        import_btn.clicked.connect(self._import_plugin_dir)
        btn_row.addWidget(import_btn)

        catalog_btn = QPushButton("搜索/下载外部插件")
        catalog_btn.setToolTip("读取 JSON 插件索引，只展示元数据，不自动执行远程代码。")
        catalog_btn.clicked.connect(self._search_catalog)
        btn_row.addWidget(catalog_btn)
        side_layout.addLayout(btn_row)

        permission_btn_row = QHBoxLayout()
        permission_btn_row.setSpacing(8)
        save_permission_btn = QPushButton("保存权限")
        save_permission_btn.clicked.connect(self._save_permissions)
        permission_btn_row.addWidget(save_permission_btn)

        remove_btn = QPushButton("删除外部插件")
        remove_btn.setObjectName("dangerButton")
        remove_btn.clicked.connect(self._remove_selected_plugin)
        permission_btn_row.addWidget(remove_btn)
        permission_btn_row.addStretch()
        side_layout.addLayout(permission_btn_row)
        side_layout.addStretch()

        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([520, 420])

        self._refresh_plugins()

    def _permission_combo(self, current: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(PERMISSION_LEVELS)
        combo.setCurrentText(current if current in PERMISSION_LEVELS else PERMISSION_LEVELS[0])
        combo.setMinimumWidth(180)
        combo.setStyleSheet(SAKURA_COMBO_BOX_STYLE)
        return combo

    def _refresh_plugins(self, notify: bool = False) -> None:
        self._list.clear()
        self._host.load()
        total_tools = sum(status.tools_count for status in self._host.statuses if status.loaded)
        builtin_count = sum(1 for status in self._host.statuses if _is_builtin_plugin(Path(status.path)))
        external_count = max(0, len(self._host.statuses) - builtin_count)
        self._summary.setText(
            f"插件工具：{total_tools}  内置 {builtin_count}  ·  外部 {external_count}"
        )
        self._set_detail_text("选择插件查看诊断详情。")

        if not self._host.statuses:
            self._add_list_item("（暂无已配置的插件）")
            return

        for status in self._host.statuses:
            plugin_dir = Path(status.path)
            source = "内置" if _is_builtin_plugin(plugin_dir) else "外部"
            state = "已加载" if status.loaded else "加载失败"
            description = self._compact_text(status.description or "无说明", 34)
            text = f"{status.name}  [{state}]  [{source}]\n{status.tools_count} 个工具  ·  {description}"
            if status.description:
                tooltip = f"{source}：{status.name}\n{state} · {status.tools_count} 个工具\n{status.description}"
            else:
                tooltip = f"{source}：{status.name}\n{state} · {status.tools_count} 个工具"
            item = self._add_list_item(text)
            item.setToolTip(tooltip)
            item.setData(Qt.ItemDataRole.UserRole, {
                "kind": "plugin_status",
                "path": status.path,
                "builtin": _is_builtin_plugin(plugin_dir),
                "detail": _format_plugin_status_detail(status),
            })
        if notify:
            show_feedback(self, "刷新成功", "插件列表已刷新。")

    def _import_plugin_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择插件目录")
        if not folder:
            return
        self._import_plugin_path(Path(folder))

    def _import_plugin_path(self, plugin_dir: Path) -> None:
        if not plugin_dir.is_dir() or not (plugin_dir / "plugin.py").exists():
            self._show_error("所选目录中没有 plugin.py。")
            return
        plugins_root = _plugins_root()
        target = plugins_root / plugin_dir.name
        if target.exists():
            self._show_error(f"插件 '{plugin_dir.name}' 已存在，已拒绝覆盖。")
            return
        if not confirm_action(
            self,
            "确认导入插件",
            f"插件 '{plugin_dir.name}' 包含会在加载时执行的 Python 代码。确定导入吗？",
        ):
            return
        imported = _copy_plugin_dir(plugin_dir, plugins_root)
        if not imported:
            self._show_error("插件导入失败，请确认目录结构和同名冲突。")
            return
        self._refresh_plugins()
        show_feedback(self, "导入成功", f"插件 '{imported.name}' 已导入。")

    def _search_catalog(self) -> None:
        source = PluginCatalogSourceDialog.get_source(self)
        if not source:
            return
        try:
            entries = _load_catalog_entries(source)
        except Exception as exc:
            self._show_error(f"插件索引读取失败：{exc}")
            return
        if not entries:
            self._show_error("插件索引为空或格式不正确。")
            return
        entry = PluginCatalogEntryDialog.get_entry(self, entries)
        if entry is None:
            return
        try:
            staged = _stage_catalog_source(entry.source)
        except Exception as exc:
            self._show_error(f"插件下载或解包失败：{exc}")
            return
        if staged is None:
            self._show_error("插件来源无效，未找到 plugin.py。")
            return
        self._import_plugin_path(staged)

    def _save_permissions(self) -> None:
        self._config.agent.system_control.permission_level = self._system_control_permission.currentText()
        self._config.agent.web_automation.permission_level = self._web_automation_permission.currentText()
        try:
            self._config.save_agent()
        except Exception as exc:
            self._show_error(f"权限保存失败：{exc}")
            return
        show_feedback(self, "保存成功", "内置插件权限已保存，重新加载插件后生效。")

    def _remove_selected_plugin(self) -> None:
        data = self._selected_data()
        if not data or data.get("kind") != "plugin_status":
            self._show_error("请先选择一个插件。")
            return
        plugin_dir = Path(data["path"])
        if data.get("builtin"):
            self._show_error(f"内置插件 '{plugin_dir.name}' 不能删除。")
            return
        if not confirm_action(self, "确认删除", f"确定删除外部插件 '{plugin_dir.name}' 吗？"):
            return
        if _remove_plugin_dir(plugin_dir, _plugins_root()):
            self._refresh_plugins()
            show_feedback(self, "删除成功", f"插件 '{plugin_dir.name}' 已删除。")
            return
        self._show_error("当前插件不支持删除。")

    def _selected_data(self) -> dict | None:
        item = self._list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _sync_detail(self) -> None:
        data = self._selected_data()
        if data and data.get("detail"):
            self._set_detail_text(data["detail"])
        else:
            self._set_detail_text("选择插件查看诊断详情。")

    def _add_list_item(self, text: str):
        self._list.addItem(text)
        item = self._list.item(self._list.count() - 1)
        tokens = settings_font_tokens(self._config.system)
        item.setFont(font_for_role(tokens, "small"))
        return item

    def _set_detail_text(self, text: str) -> None:
        self._detail.setPlainText(text)
        self._detail.verticalScrollBar().setValue(0)

    @staticmethod
    def _compact_text(text: str, max_length: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_length:
            return normalized
        return normalized[: max(0, max_length - 1)] + "…"

    def _show_error(self, message: str) -> None:
        show_feedback(self, "操作失败", message, success=False)


class PluginCatalogSourceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._system_config = _dialog_system_config(parent)
        self.setWindowTitle("外部插件索引")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("读取插件索引")
        set_settings_font_role(title, "title")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("输入 JSON 索引文件路径或 URL。这里只读取插件元数据，不会执行远程代码。")
        set_settings_font_role(desc, "small")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        layout.addWidget(desc)

        self._source = QLineEdit()
        self._source.setPlaceholderText("例如 E:/plugins/index.json 或 https://example.com/plugins.json")
        layout.addWidget(self._source)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_settings_fonts(self, self._system_config)

    @classmethod
    def get_source(cls, parent=None) -> str:
        dlg = cls(parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return ""
        return dlg._source.text().strip()


class PluginCatalogEntryDialog(QDialog):
    def __init__(self, entries: list[PluginCatalogEntry], parent=None):
        super().__init__(parent)
        self._entries = entries
        self._system_config = _dialog_system_config(parent)
        self.setWindowTitle("选择外部插件")
        self.setStyleSheet(DIALOG_STYLE)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("选择要下载/导入的插件")
        set_settings_font_role(title, "title")
        title.setStyleSheet("font-size: 17px; font-weight: bold; color: #7a3a5a;")
        layout.addWidget(title)

        desc = QLabel("下载后仍需确认导入。导入的第三方 Python 插件会在加载时执行。")
        set_settings_font_role(desc, "small")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8c6b7a; font-size: 12px;")
        layout.addWidget(desc)

        self._combo = QComboBox()
        for entry in entries:
            self._combo.addItem(f"{entry.name} — {entry.description or entry.source}", entry)
        layout.addWidget(self._combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_settings_fonts(self, self._system_config)

    @classmethod
    def get_entry(cls, parent, entries: list[PluginCatalogEntry]) -> PluginCatalogEntry | None:
        dlg = cls(entries, parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg._combo.currentData()


def _dialog_system_config(parent):
    while parent is not None:
        config = getattr(parent, "_config", None)
        if config is not None and hasattr(config, "system"):
            return config.system
        parent = parent.parent()
    return ConfigManager().system
