## 项目上下文摘要（日志界面样式与行为修复）

生成时间：2026-05-25 14:09:29 +08:00

### 1. 相似实现分析

- **实现1**: `ui/settings/pages/system_log_page.py`
  - 模式：页面级 `PAGE_STYLE`、来源分组映射、定时刷新、上方列表 / 连续文本与下方详情联动。
  - 可复用：`_capture_scroll_state()`、`_restore_scroll_state()`、`_event_key()`、`SOURCE_GROUPS`。
  - 需注意：`QListWidget.clear()` 会触发当前行变化，若不阻断信号，会把选中详情误清空并重写。
- **实现2**: `ui/settings/pages/conversation_log_page.py`
  - 模式：`QTextEdit.setHtml()` 渲染可复制时间线，同时保留主题色与卡片样式。
  - 可复用：HTML 渲染与 `html_escape` 防止日志正文破坏标记结构。
  - 需注意：连续文本仍需保留 `toPlainText()` 可读输出和拖选复制能力。
- **实现3**: `ui/settings/window.py`
  - 模式：设置中心主窗口集中覆盖 `QMenu`、导航、滚动条和弹窗主题。
  - 可复用：主窗口 `setStyleSheet()` 是设置中心右键菜单主题入口。
  - 需注意：子控件原生右键菜单可能还会读取应用级样式，因此 `main.APP_STYLE` 也需要覆盖 `QMenu`。
- **实现4**: `ui/settings/pages/api_page.py`
  - 模式：下拉框和弹出按钮采用浅色背景、玫瑰色强调。
  - 可复用：避免用 Qt 不稳定的 CSS 边框三角模拟箭头，改用明确图标资源。
  - 需注意：Qt 样式表对 `QComboBox::down-arrow` 的 CSS border 支持不等同浏览器，容易显示成色块。

### 2. 项目约定

- **命名约定**: Qt 控件字段和内部方法使用 `_xxx`；测试函数使用 `test_...`。
- **文件组织**: 设置页在 `ui/settings/pages/`，共用资源放入 `ui/assets/`，测试在 `tests/test_*`。
- **导入顺序**: 标准库在前，PySide6 在后，项目内模块最后。
- **代码风格**: 4 空格缩进，页面样式集中在多行字符串中，行为逻辑保持小方法拆分。

### 3. 可复用组件清单

- `SystemLogPage._capture_scroll_state`: 捕获刷新前滚动条是否接近底部及当前位置。
- `SystemLogPage._restore_scroll_state`: 根据用户位置决定恢复原位或跟随底部。
- `SystemLogPage._event_key`: 在刷新后定位原选中事件。
- `ConversationLogPage` 的 HTML 时间线策略：用于连续文本按来源着色。
- `SettingsWindow.setStyleSheet` 与 `APP_STYLE`: 用于统一右键菜单浅色主题。

### 4. 测试策略

- **测试框架**: pytest + PySide6 offscreen。
- **测试模式**: 直接实例化页面，用伪 `LogService` 返回结构化事件，检查控件文本、HTML、样式字符串、滚动和选择状态。
- **参考文件**: `tests/test_system_log_page.py`、`tests/test_settings_window.py`。
- **覆盖要求**: 来源颜色唯一、选中态不覆盖来源色、连续文本按来源着色、下拉箭头不用色块三角、右键菜单浅色、刷新不清空选中详情、滚动位置保持。

### 5. 依赖和集成点

- **外部依赖**: PySide6 `QListWidget`、`QTextEdit`、`QComboBox`、Qt 样式表。
- **内部依赖**: `LogService.query_events()`、设置中心 `SettingsWindow`、`main.APP_STYLE`。
- **集成方式**: 系统日志页每秒 `_refresh_view()`，上方视图共享同一批筛选事件，下方详情通过列表选中事件联动。
- **配置来源**: 日志根目录来自 `ConfigManager().system.logging.log_root`，本次未改配置模型。

### 6. 技术选型理由

- **为什么用这个方案**: 沿用现有 PySide6 页面级样式和 pytest 实例化测试，不引入新框架；用 SVG 资源替代不稳定的 CSS 三角。
- **优势**: 改动局部、行为可回归、视觉策略明确，能覆盖用户反馈的 6 个问题。
- **劣势和风险**: Qt 不同平台对菜单和下拉箭头渲染仍可能有差异，已通过应用级和窗口级样式双重覆盖降低风险。

### 7. 关键风险点

- **并发问题**: 定时刷新可能发生在用户滚动或阅读详情时，已通过信号阻断和滚动恢复处理。
- **边界条件**: 无日志、筛选为空、选中事件消失、日志追加、用户停留历史位置、用户接近底部。
- **性能瓶颈**: 仍是每秒重建可见事件列表；本次修复不引入分页或索引。
- **安全考虑**: 本次只处理本地 UI 样式和滚动行为，不涉及认证、鉴权、加密或外部命令执行。

### 8. 工具可用性说明

- `sequential-thinking`、`shrimp-task-manager`、`desktop-commander`、`context7`、`github.search_code` 未在当前会话暴露可调用入口。
- 替代方式：使用本地源码阅读、既有文档、pytest 红绿验证和结构化操作日志完成任务。
