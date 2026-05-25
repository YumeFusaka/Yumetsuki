## 项目上下文摘要（日志界面样式与行为修复）

生成时间：2026-05-25 00:00:00

### 1. 相似实现分析

- **实现1**: `ui/settings/pages/system_log_page.py`
  - 模式：页面级 `PAGE_STYLE` + `QVBoxLayout` 主布局 + 定时刷新。
  - 可复用：`_capture_scroll_state()`、`_restore_scroll_state()`、`_filter_events()`、`SOURCE_GROUPS`。
  - 需注意：结构化列表会在 `clear()` 后重建，刷新时必须显式保持滚动位置和选择状态。
- **实现2**: `ui/settings/pages/conversation_log_page.py`
  - 模式：页面级 `PAGE_STYLE` + HTML 卡片渲染对话时间线。
  - 可复用：`_render_message_card()` 中已有胶囊标签样式。
  - 需注意：内联情绪标签与下方标签样式应保持一致，避免出现半圆角矩形。
- **实现3**: `ui/settings/window.py`
  - 模式：主窗口集中设置全局 Sakura 主题、导航区、滚动条和对话框样式。
  - 可复用：`GLOBAL_SCROLLBAR` 与主窗口 `setStyleSheet()` 的全局样式入口。
  - 需注意：右键菜单属于 `QMenu`，当前全局样式未覆盖，默认深色背景会破坏主题一致性。
- **实现4**: `ui/settings/pages/agent_page.py`
  - 模式：设置页使用独立 `PAGE_STYLE`、浅色输入控件、圆角边框。
  - 可复用：浅色输入框、按钮、列表控件视觉策略。
  - 需注意：项目设置页倾向使用直接 Qt 样式表，而非额外主题系统。

### 2. 项目约定

- **命名约定**: Qt 控件实例字段使用 `_xxx` 私有命名；测试函数使用 `test_...`。
- **文件组织**: 设置页位于 `ui/settings/pages/`，对应测试位于 `tests/test_*_page.py`。
- **导入顺序**: 标准库在前，第三方 PySide6 在后，项目内模块最后；既有文件未强制格式化工具。
- **代码风格**: 4 空格缩进，简洁方法拆分，页面样式以多行字符串集中维护。

### 3. 可复用组件清单

- `SystemLogPage._capture_scroll_state`: 捕获滚动条是否接近底部及当前位置。
- `SystemLogPage._restore_scroll_state`: 根据捕获状态决定保持当前位置或跟随到底部。
- `ConversationLogPage._render_message_card`: 对话卡片与标签 HTML 生成入口。
- `SettingsWindow.setStyleSheet`: 设置窗口全局主题入口，可覆盖 `QMenu`。

### 4. 测试策略

- **测试框架**: pytest。
- **测试模式**: 直接实例化 PySide6 页面对象，通过伪造 log service 验证控件状态、样式字符串与渲染输出。
- **参考文件**: `tests/test_system_log_page.py`、`tests/test_conversation_log_page.py`、`tests/test_settings_window.py`。
- **覆盖要求**: 工具栏布局、下拉框样式、结构化列表滚动保持、来源颜色、菜单主题、情绪标签与记忆标签文案。

### 5. 依赖和集成点

- **外部依赖**: PySide6 控件与 Qt 样式表。
- **内部依赖**: `LogService.query_events()` 提供日志事件；设置窗口创建日志页并共享 `LogService`。
- **集成方式**: 页面定时调用 `_refresh_view()`，列表项通过 `QListWidgetItem` 承载事件字典。
- **配置来源**: 日志根目录来自 `ConfigManager().system.logging.log_root`。

### 6. 技术选型理由

- **为什么用这个方案**: 当前项目已在设置页广泛使用 PySide6 样式表和控件内局部方法；沿用可减少额外依赖与维护成本。
- **优势**: 变更局部、测试可直接覆盖、与既有 Sakura 主题一致。
- **劣势和风险**: Qt 样式表对下拉箭头的渲染受平台影响，测试只能约束样式策略，最终视觉仍需人工查看。

### 7. 关键风险点

- **并发问题**: 定时刷新可能和用户滚动/选择同时发生，刷新函数需在重建后恢复滚动位置。
- **边界条件**: 无日志、筛选为空、选中事件消失、日志新增但用户不在底部。
- **性能瓶颈**: 每秒重建列表在日志量较大时有成本；本次仅修复滚动与可读性，不引入新索引。
- **安全考虑**: 本次不涉及认证、鉴权或外部输入执行。

### 8. 工具可用性说明

- `sequential-thinking`、`shrimp-task-manager`、`desktop-commander`、`context7`、`github.search_code` 在当前会话未暴露可调用工具。
- 已使用本地文件读取、pytest 和项目内既有测试替代，并在操作日志记录偏差。
