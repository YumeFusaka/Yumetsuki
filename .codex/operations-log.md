## 编码前检查 - 日志界面样式与行为修复

时间：2026-05-25 14:09:29 +08:00

□ 已查阅上下文摘要文件：`.codex/context-summary-logging-ui-polish.md`

□ 将使用以下可复用组件：

- `SystemLogPage._capture_scroll_state`: 保存刷新前的列表、连续文本和详情区滚动状态。
- `SystemLogPage._restore_scroll_state`: 刷新后恢复用户阅读位置，接近底部时才跟随到底。
- `SystemLogPage._event_key`: 重建列表后重新定位原选中事件。
- `SettingsWindow.setStyleSheet` 与 `APP_STYLE`: 覆盖设置中心和应用级右键菜单主题。
- `QTextEdit.setHtml`: 复用对话日志页已有的 HTML 时间线思路，为连续文本增加来源配色。

□ 将遵循命名约定：Qt 控件字段和内部方法使用 `_xxx`，测试函数使用 `test_...`

□ 将遵循代码风格：页面级 `PAGE_STYLE`、4 空格缩进、pytest 直接实例化控件验证

□ 确认不重复造轮子，证明：已检查 `system_log_page.py`、`conversation_log_page.py`、`window.py`、`api_page.py`、`agent_page.py` 与相关测试，现有 PySide6 样式和滚动恢复方法足够支撑修复

### 工具偏差记录

- 仓库准则要求的 `sequential-thinking`、`shrimp-task-manager`、`desktop-commander`、`context7`、`github.search_code` 当前没有暴露可调用工具。
- 替代方式：以本地源码阅读、项目文档、pytest 红绿验证和本操作日志记录替代。
- 首次并行读取部分文件时 PowerShell 沙箱返回 `CreateProcessAsUserW failed: 1312`，随后改用已可执行的 `pwsh.exe -Command` 和项目既有命令完成读取与验证。

## TDD 记录 - 日志界面样式与行为修复

时间：2026-05-25 14:09:29 +08:00

### RED

- 新增系统日志测试：
  - 来源色映射必须对已知来源唯一。
  - 选中结构化列表项后仍保留来源前景色。
  - 连续文本视图 HTML 中必须包含来源颜色。
  - 下拉箭头不得继续使用 CSS border 三角，需使用图标资源。
  - 刷新重建列表时不得把选中详情临时清空。
- 新增设置中心测试：
  - 窗口级和应用级 `QMenu` 都必须使用浅色背景。

执行结果：

- `python -m pytest tests/test_system_log_page.py tests/test_settings_window.py -q`
- 结果：6 个新增/更新断言失败，证明测试覆盖了现有问题。

### GREEN

实现动作：

- 拆分 `SOURCE_COLORS` 中重复颜色，保证每个已知来源颜色不同。
- 移除 `QListWidget::item:selected` 的文字颜色覆盖，只保留选中背景和边框。
- 新增 `ui/assets/combo-down.svg`，让 `QComboBox::down-arrow` 使用明确 SVG 图标，替代 Qt 不稳定的 CSS 边框三角。
- 连续文本视图改用 `setHtml()` 渲染，每条日志按 `source` 着色，同时保留 `toPlainText()` 和拖选复制能力。
- `_refresh_view()` 重建结构化列表时阻断 `currentRowChanged` 信号，避免 `clear()` 把选中详情误清空。
- 对连续文本、列表和详情区都保留滚动恢复；详情区在事件未变化时不重写。
- 在 `main.APP_STYLE` 和 `SettingsWindow` 样式中统一补齐浅色 `QMenu`。
- 更新 `docs/ui-guidelines.md` 记录系统日志页配色、选择态和滚动规则。
- 提交前同步 `CLAUDE.md` 与 `docs/README.md`，补充系统日志 UI 细节收口状态。

执行结果：

- `python -m pytest tests/test_system_log_page.py tests/test_settings_window.py -q`
- 结果：36 passed

## 编码后声明 - 日志界面样式与行为修复

时间：2026-05-25 14:09:29 +08:00

### 1. 复用了以下既有组件

- `SystemLogPage._capture_scroll_state`: 用于刷新前捕获上方列表、连续文本和下方详情区滚动位置。
- `SystemLogPage._restore_scroll_state` / `_restore_scroll_state_later`: 用于即时和延迟恢复 Qt 布局更新后的滚动位置。
- `SystemLogPage._event_key`: 用于刷新后恢复原选中事件。
- `SettingsWindow.setStyleSheet` 与 `APP_STYLE`: 用于统一设置中心右键菜单浅色主题。

### 2. 遵循了以下项目约定

- 命名约定：新增 `COMBO_ARROW_ICON`、`_render_continuous_html()` 等名称与现有模块风格一致。
- 代码风格：继续使用页面级样式字符串和小方法拆分。
- 文件组织：图标资源放在 `ui/assets/`，页面测试保留在 `tests/test_system_log_page.py` 和 `tests/test_settings_window.py`。
- 文档同步：已更新 `docs/ui-guidelines.md` 的系统日志页面约束。

### 3. 对比了以下相似实现

- `system_log_page.py`: 保留原有筛选、导出、复制、滚动恢复接口，只修复配色、刷新和渲染策略。
- `conversation_log_page.py`: 连续文本借鉴 HTML 时间线渲染，但保持系统日志的紧凑文本格式。
- `window.py` / `main.py`: 菜单主题沿用集中样式覆盖，不新增菜单子类。
- `api_page.py`: 下拉箭头不继续依赖 CSS 边框三角，改为显式图标资源以避免色块问题。

### 4. 未重复造轮子的证明

- 已检查 `ui/settings/pages/` 下日志页、API 页、Agent 页和设置窗口现有样式体系。
- 已确认无需新增控件框架、主题系统或日志模型；本次只在现有 PySide6 页面内补足缺失行为。

## Bug 级返修记录 - 系统日志与右键菜单残留问题

时间：2026-05-25 14:09:29 +08:00

### 反馈项

- 右键功能菜单仍出现黑色背景。
- 系统日志结构化列表仍会在自动刷新时滚到最底部。
- 系统日志结构化列表选中项字体仍会变色，未保持来源配色。

### 根因复查

- 上次测试只检查样式字符串，未检查标准文本控件实际创建的 `QMenu` 实例；标准复制 / 粘贴菜单需要实例级主题兜底。
- `SCROLL_BOTTOM_THRESHOLD = 24` 对 `QListWidget` 等价于“离底部 24 个滚动单位内都算底部”，用户离底部还有多条日志时会被误判为应跟底。
- 移除 QSS 里的 `color` 还不够，Qt 选中态绘制会使用 `HighlightedText` 调色板，默认仍可能变成白色。

### 新增红灯测试

- `test_settings_window_styles_standard_text_context_menu`
- `test_system_log_page_structured_list_does_not_treat_near_bottom_as_bottom`
- `test_system_log_page_selected_item_paints_highlighted_text_with_source_color`

执行结果：三个测试在当前实现下全部失败，分别暴露菜单实例无主题、近底部误跟底、选中绘制仍使用白色高亮文字。

### 修复动作

- 新增 `ui/theme.py`，集中定义 Sakura 菜单样式、菜单实例调色板和应用级 `QMenu` 事件过滤器。
- `SettingsWindow` 初始化时安装菜单事件过滤器，并提供 `_apply_menu_theme()` 供标准菜单实例测试和复用。
- `SCROLL_BOTTOM_THRESHOLD` 从 24 收紧为 2，避免把“正在翻阅接近底部的历史日志”误判为应自动跟底。
- 新增 `SourceColorItemDelegate`，在 `initStyleOption()` 中把 `Text` 与 `HighlightedText` 都设为日志来源色。
- 同步更新 `CLAUDE.md`、`docs/README.md`、`docs/ui-guidelines.md`。
