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

## 样式调整记录 - 设置中心导航栏命名与顺序

时间：2026-05-25 14:09:29 +08:00

### 需求

- `API 设定` 改为 `API`。
- `角色管理` 改为 `角色`。
- `系统日志` 改为 `平台日志`。
- API 不再使用机器人图标，Agent 保留机器人图标。
- 导航顺序改为：`API`、`角色`、`记忆`、`Agent`、`插件`、`对话日志`、`平台日志`、`系统`。

### 实施

- 只调整 `SettingsWindow` 的 `pages_info` 展示文案、图标与按钮顺序。
- 页面栈索引保持不变，避免影响保存按钮、页面切换和会话绑定逻辑。
- 更新 `tests/test_settings_window.py`，用精确顺序断言覆盖导航文案、图标和排序。
- 更新 `CLAUDE.md`、`docs/README.md`、`docs/architecture.md`、`docs/ui-guidelines.md` 中的相关页面名称说明。

## Bug 修复记录 - 设置中心导航高亮与目标页不一致

时间：2026-05-25 14:09:29 +08:00

### 根因

- 导航栏顺序调整后，按钮显示顺序不再等于页面栈索引。
- `_switch_page()` 仍用 `enumerate(self._nav_buttons)` 的按钮位置和页面索引比较，导致点击目标页正确但高亮项错误。

### 修复

- 每个导航按钮写入 `page_index` 属性，记录真实目标页面索引。
- `_switch_page()` 按按钮的 `page_index` 判断 checked 状态，而不是按按钮在导航栏中的位置判断。
- 新增 `test_settings_window_navigation_click_checks_clicked_target_page` 覆盖每个导航按钮的点击目标与唯一高亮项。

## 样式规范记录 - 统一设置中心下拉框样式

时间：2026-05-25 14:09:29 +08:00

### 需求

- 将平台日志页面中符合预期的下拉框样式写入项目 UI 规范。
- 设置中心其他页面的 `QComboBox` 统一使用同一套样式。

### 实施

- 在 `ui/theme.py` 中新增 `SAKURA_COMBO_BOX_STYLE` 和 `COMBO_ARROW_ICON`，把平台日志下拉框样式提升为共享主题常量。
- `api_page.py`、`memory_page.py`、`conversation_log_page.py`、`system_page.py`、`character_page.py`、`plugin_page.py`、`system_log_page.py` 均复用共享下拉框样式。
- `docs/ui-guidelines.md` 新增“下拉框”规范，明确禁止复制独立样式或使用 CSS 色块模拟箭头。
- 新增 `test_settings_combo_styles_share_platform_log_combo_style`，约束设置页和弹窗样式都包含统一箭头图标样式。

## 样式修复记录 - API TTS 语言下拉框

时间：2026-05-25 14:09:29 +08:00

### 需求

- API 页面 TTS 语音合成中的“参考语言”和“输出语言”右侧额外下拉按钮已不需要，需要删除。
- 这两个语言下拉框过长，需要缩短到接近“引擎”下拉框的宽度。

### 实施

- 删除 `_build_popup_combo_row()` 和 `comboPopupBtn` 样式。
- “参考语言”和“输出语言”直接使用可编辑 `QComboBox` 自身的下拉箭头。
- 为两个语言下拉框设置 `maximumWidth(220)`，避免随表单布局拉得过长。
- 更新 `test_api_page_tts_language_combos_have_presets_and_remain_editable`，断言不再创建额外按钮且宽度受限。

## 文档整理与会话收口记录

时间：2026-05-25 16:33:38 +08:00

### 需求

- 将本轮新增规范、功能和优化同步到文档。
- 删除已经彻底完成的日志工作台 spec / plan。
- 做文档 review，全部通过后提交并 push。
- 不提交用户本地配置 `data/config/agent.yaml`。

### 上下文检查

- 已核对 `CLAUDE.md`、`docs/README.md`、`docs/development.md`、`docs/architecture.md`、`docs/ui-guidelines.md`。
- 已确认已完成日志工作台历史文件应删除：
  - `docs/superpowers/specs/2026-05-24-logging-workbench-design.md`
  - `docs/superpowers/specs/2026-05-24-logging-workbench-polish-design.md`
  - `docs/superpowers/plans/2026-05-24-logging-workbench-implementation.md`
  - `docs/superpowers/plans/2026-05-24-logging-workbench-polish-implementation.md`
- 已确认仍保留未来计划：
  - `docs/superpowers/specs/2026-05-24-phase-4-6-roadmap-design.md`
  - `docs/superpowers/specs/2026-05-24-phase-5-ui-stt-design.md`
  - `docs/superpowers/specs/2026-05-24-phase-6-browser-vision-ecosystem-design.md`

### 实施

- `CLAUDE.md`：同步平台日志命名、导航顺序、API / Agent 图标区分、平台日志 UI 收口和后续真实联调方向；移除已完成日志工作台 spec / plan 入口。
- `docs/README.md`：更新最后日期、当前进度、推荐阅读顺序和下一步方向；移除历史日志工作台 spec / plan 入口。
- `docs/development.md`：清空已完成日志工作台当前计划入口，把当前优先级调整为 Phase 5 / Phase 6 与平台日志真实场景联调；测试策略改为 `对话日志` / `平台日志` 页面入口。
- `docs/architecture.md`：补充 `ui/theme.py` 共享主题模块、设置中心导航顺序和“平台日志”展示名；说明内部 channel 仍沿用 `system`。
- `docs/ui-guidelines.md`：新增设置中心下拉框统一规范、导航顺序、API TTS 语言下拉框尺寸与无额外按钮规则；将“系统日志页面”改为“平台日志页面”。
- 删除四个已完成日志工作台 spec / plan，避免后续新会话继续引用历史实施材料。

### 文档 Review 记录

- 旧 spec / plan 文件名、旧导航名、旧页面标题扫描无命中：
  - `logging-workbench`
  - `日志工作台设计`
  - `日志工作台打磨实施计划`
  - `API 设定`
  - `角色管理`
  - `系统日志页面`
  - `系统日志 导航`
  - `🧪  系统日志`
- “系统日志”仅允许作为内部 channel、落盘目录或运行事件类型语境出现；面向 UI 的页面名统一为“平台日志”。

### 验证结果

- `rg -n "logging-workbench|日志工作台设计|日志工作台打磨实施计划|API 设定|角色管理|系统日志页面|系统日志 导航|🧪  系统日志" CLAUDE.md docs`
  - 结果：无命中，旧入口和旧页面名已清理。
- `QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q`
  - 结果：`300 passed in 10.75s`。
- `python -m py_compile ui/theme.py ui/settings/window.py ui/settings/pages/api_page.py ui/settings/pages/system_log_page.py tests/test_settings_window.py`
  - 结果：通过，无输出错误。
- `git diff --check`
  - 结果：通过；仅输出 Windows 换行转换提示，无空白错误。

## 计划编写记录 - Phase 5 桌宠体验、UI 与 STT

时间：2026-05-25 16:57:32 +08:00

### 需求

- 根据 `docs/superpowers/specs/2026-05-24-phase-5-ui-stt-design.md` 编写实施计划。
- 计划需覆盖系统设置与聊天界面优化、被动互动气泡、STT 模块和 STT / TTS 状态协调。

### 工具偏差记录

- 仓库准则要求的 `sequential-thinking`、`shrimp-task-manager`、`desktop-commander`、`context7`、`github.search_code` 当前没有暴露可调用工具。
- 已使用 `tool_search` 搜索 `sequential thinking task manager shrimp`，结果为 0 个可用工具。
- 替代方式：读取本地文档、使用 `rg` 搜索、读取相似实现和测试、用本日志记录替代流程。
- 只读检索过程中多次遇到 PowerShell 沙箱 `CreateProcessAsUserW failed: 1312`，均按权限规则以只读命令重新请求执行。

### 上下文检查

- 已查阅上下文摘要文件：`.codex/context-summary-phase-5-ui-stt-plan.md`
- 已分析相似实现：
  - `config/schema.py`
  - `ui/settings/pages/system_page.py`
  - `ui/chat/window.py`
  - `agent/proactive.py`
  - `tests/test_chat_tts_flow.py`
- 将复用以下组件：
  - `SystemConfig` / `ASRConfig`：承载 Phase 5 新配置。
  - `SystemPage` / `APIPage`：分别编辑显示配置和 ASR 配置。
  - `ChatWindow._on_send()`：STT 文本进入既有聊天主链路。
  - `ChatWindow._begin_new_tts_turn()`：录音或新输入时中断旧 TTS 轮次。
  - `ProactiveScheduler.proactive_message`：被动气泡的主动消息来源。
- 确认不重复造轮子：已检查现有 `font_family`、`font_size`、ASR 基础配置、TTS 管线与主动消息调度入口，计划只扩展这些入口。

### 输出

- 新增计划文档：`docs/superpowers/plans/2026-05-25-phase-5-ui-stt-implementation.md`
- 新增上下文摘要：`.codex/context-summary-phase-5-ui-stt-plan.md`
- 更新审查报告：`.codex/verification-report.md`

### 验证结果

- `rg -n "TBD|TODO|implement later|fill in details|Add appropriate|add validation|handle edge cases|Similar to Task" docs/superpowers/plans/2026-05-25-phase-5-ui-stt-implementation.md`
  - 结果：无命中，命令以 `1` 退出符合 `rg` 无匹配语义。
- `rg -n "Phase 5|STT|被动互动|系统设置|聊天界面|语音输入|字体|字号" docs/superpowers/plans/2026-05-25-phase-5-ui-stt-implementation.md`
  - 结果：命中计划目标、任务结构、STT、被动互动、显示配置与自检条目。
- `git diff --check`
  - 结果：通过；仅提示 `.codex/operations-log.md` 的 LF/CRLF 转换，无空白错误。

## Phase 5 Task 7 文档同步与验证记录

时间：2026-05-25 18:56:45 +08:00

### 任务范围

- 修改 `CLAUDE.md`、`docs/README.md`、`docs/architecture.md`、`docs/development.md`、`docs/ui-guidelines.md`。
- 追加 `.codex/operations-log.md` 与 `.codex/verification-report.md` 的 Phase 5 实施记录。
- 明确不触碰 `data/config/agent.yaml`。

### Task 1-7 实施摘要

- Task 1：`config/schema.py` 已扩展 `ASRConfig`，新增 `ChatDisplayConfig` 与 `PassiveInteractionConfig`，并挂入系统配置。
- Task 2：`ui/settings/pages/system_page.py` 与 `ui/settings/pages/api_page.py` 已接入显示配置、被动互动配置和 ASR / STT 配置。
- Task 3：`ui/settings/window.py` 已在启动聊天窗时传入 `system_config` 与 `asr_config`。
- Task 4：`ui/chat/window.py` 已接入显示配置、被动互动气泡、STT 按钮状态、录音 / 转写主链路和关闭态 worker 生命周期治理。
- Task 5：`stt/` 已新增 `STTResult`、`STTAdapter`、`OpenAIWhisperAdapter`、`STTManager`。
- Task 6：`ui/chat/stt_recorder.py` 已提供 Qt 麦克风录音、PCM 静音检测和 WAV 生成；`test_chat_passive_bubble.py`、`test_chat_stt_flow.py`、`test_stt_adapter.py`、`test_stt_recorder.py` 已覆盖离线主链路。
- Task 7：本轮同步协作文档、文档入口、架构、开发流程、UI 规范和审查记录。

### 工具与流程记录

- 仓库准则中提到的 `desktop-commander`、`sequential-thinking`、`shrimp-task-manager`、`context7`、`github.search_code` 当前未暴露为可调用工具。
- 本轮替代方式：使用 PowerShell 只读检索、`rg` 搜索、`apply_patch` 精确编辑，并在 `.codex/` 中记录工具偏差。
- 本轮为 Phase 5 实现子代理任务，未修改非任务范围文件，未 revert 其他协作者改动，未触碰 `data/config/agent.yaml`。

### 审查简述

- 文档已把第五阶段从“暂未展开实施计划 / 下一步”更新为“进行中，基础能力已落地”。
- 架构文档已补充 `stt/`、`ui/chat/stt_recorder.py`、聊天窗 STT / 被动气泡 / 显示配置职责和“语音输入 → STTRecorder → STTManager → _on_send()”流程。
- 开发文档已指向 Phase 5 实施计划，优先级调整为真实 STT / TTS / API 联调与 Phase 6，并补充 ASR、`chat_display`、`passive_interaction` 配置和聚焦测试命令。
- UI 规范已补充被动互动气泡和 STT 按钮状态规则。
- 剩余边界：真实麦克风、真实 Whisper 服务、真实 STT / TTS 互锁体验仍需主会话或本地设备环境回填联调结果。

## Phase 5 最终验证与 Qt 崩溃修复记录

时间：2026-05-25 19:15:11 +08:00

### 问题现象

- 聚焦测试均已通过，但 `python -m pytest tests/ -q` 在 Windows / PySide6 环境中触发原生崩溃。
- 初始栈显示崩溃位于 `ui/theme.py:111` 的 `QApplication.setStyleSheet()`；移除运行期全局样式追加后，崩溃点推进到 `ui/settings/window.py:120` 的 `SettingsWindow.setStyleSheet()`。
- 稳定复现序列：
  - `python -m pytest tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q`
  - `python -m pytest tests/test_chat_passive_bubble.py tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py::test_launch_chat_passes_tts_config -q`

### 根因判断

- 前序 Qt 窗口、计时器和 worker 测试会产生待清理的 PySide / Qt 对象；pytest 未进入完整 Qt 事件循环时，延迟删除事件可能在下一次复杂样式 polish 前仍未处理。
- `SettingsWindow` 构造时应用较复杂 QSS，会触发 Qt 原生层遍历和 polish 现存对象；在 Windows 环境下该状态可导致 `0xc0000374` 堆损坏或 access violation。
- `install_sakura_menu_theme()` 同时承担事件过滤器注册与全局 app 样式追加，扩大了运行期全局样式重算范围；菜单已有事件过滤器、主程序 `APP_STYLE` 和窗口级样式覆盖，不需要在设置窗口构造中追加全局样式。

### 修复内容

- `ui/theme.py`
  - `install_sakura_menu_theme()` 只负责注册 Sakura 菜单事件过滤器，不再在运行期修改 `QApplication` 全局样式表。
- `ui/settings/window.py`
  - 新增 `_drain_qt_cleanup_events()`，在设置窗口应用复杂样式前执行 `gc.collect()`、派发 `DeferredDelete` 事件并处理一次 Qt 事件。
- `ui/chat/window.py`
  - 关闭窗口时显式停止 `_passive_bubble_timer`，避免被动气泡定时器在关闭路径中继续保留活动状态。

### 最终验证结果

- `python -m pytest tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py -q`
  - 结果：`50 passed in 6.88s`。
- `python -m pytest tests/test_chat_passive_bubble.py tests/test_chat_stt_flow.py tests/test_chat_tts_flow.py::test_launch_chat_passes_tts_config -q`
  - 结果：`20 passed in 6.57s`。
- `python -m pytest tests/ -q`
  - 结果：`341 passed in 14.60s`。
- `python -m py_compile config/schema.py ui/settings/window.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py ui/chat/window.py ui/chat/stt_recorder.py ui/theme.py stt/types.py stt/adapter.py stt/adapters/openai_whisper.py stt/manager.py tests/test_chat_stt_flow.py tests/test_stt_adapter.py tests/test_stt_recorder.py`
  - 结果：通过，无输出错误。
- `git diff --check`
  - 结果：通过；仅提示工作区 LF/CRLF 转换，无空白错误。

## Phase 5 当前进度整理与 Trellis 配置忽略

时间：2026-05-25 22:43:40 +08:00

### 需求

- 第五阶段核心实现已基本完成，需要把当前进度同步到项目文档。
- 新加入 Trellis skill 后，项目目录出现 `.trellis/`、`.agents/`、`AGENTS.md`、`.codex/config.toml`、`.codex/hooks*` 等本地工具配置，需要放入 `.gitignore`。
- 整理完成后执行本地验证、提交并推送。

### 执行记录

- 恢复被 Trellis 初始化影响而显示为删除的既有 `.codex` 留痕文件，避免丢失项目上下文摘要、操作日志和验证报告。
- `.gitignore` 新增 Trellis / 本地 Agent 工具配置忽略项：
  - `.trellis/`
  - `.agents/`
  - `AGENTS.md`
  - `.codex/agents/`
  - `.codex/skills/`
  - `.codex/hooks/`
  - `.codex/config.toml`
  - `.codex/hooks.json`
- `CLAUDE.md` 与 `docs/README.md` 已把 Phase 5 状态更新为“基本完成，等待用户实机测试与真实联调”。
- `docs/superpowers/specs/2026-05-25-phase-5-stt-passive-settings-refinement-design.md` 已更新状态、系统设置五组布局、字体预览回退策略和当前进度。
- `docs/superpowers/plans/2026-05-25-phase-5-stt-passive-settings-refinement-implementation.md` 已补充当前进度、ASR `API URL` 命名、被动气泡独立分组和不可缩放字体预览回退策略。
- 本地运行配置 `data/config/agent.yaml`、`data/config/system_config.yaml` 保持未暂存，避免提交用户本地状态。

### 验证边界

- 用户明确要求本轮不执行自动化测试，后续由用户进行实机测试。
- 本轮只核对文档同步、忽略规则和 Git 暂存范围。
- 核对暂存区不包含本地运行配置和 Trellis 工具配置。

### 注意事项

- 未修改、未暂存 `data/config/agent.yaml`，该文件仍视为用户本地配置改动。
- 真实麦克风、真实 Whisper 服务和真实 STT / TTS 互锁体验仍属于设备与服务联调边界，不由离线 pytest 完全覆盖。

## Phase 5 改进设计与计划记录

时间：2026-05-25 19:49:56 +08:00

### 需求

- 根据用户反馈修正 Phase 5 方向：
  - STT 不再兼容 `openai_whisper`，只接入 faster-whisper 本地服务地址接口。
  - 被动互动改为聊天窗运行态：空闲阈值自动进入，右键菜单手动切换，被动状态下主动消息走气泡。
  - 系统设置外观区域拆分，避免控件拥挤。
  - 字体使用系统字体下拉框。
  - 系统页拥有独立保存按钮，只保存系统配置，保存后应用到已打开聊天窗。

### 输出

- 新增并已提交设计文档：
  - `docs/superpowers/specs/2026-05-25-phase-5-stt-passive-settings-refinement-design.md`
  - 提交：`551f62d docs: 记录第五阶段改进设计`
- 新增实施计划：
  - `docs/superpowers/plans/2026-05-25-phase-5-stt-passive-settings-refinement-implementation.md`
- 已同步文档入口和进度：
  - `CLAUDE.md`
  - `docs/README.md`
  - `docs/development.md`
  - `docs/architecture.md`
  - `docs/ui-guidelines.md`

### 工具与流程记录

- 已按 brainstorming 流程先确认设计，再写入 spec。
- 已按 writing-plans 流程编写 TDD 实施计划。
- 当前仅编写计划和文档同步，尚未实施代码改进。
- 提交和 push 前会排除 `data/config/agent.yaml`、`data/config/system_config.yaml` 等本地配置文件。

### 文档自检

- 计划文档无 `TBD`、`TODO`、`implement later`、`fill in details`、`handle edge cases` 等占位式内容。
- 计划覆盖：
  - `ASRConfig` faster-whisper 默认值
  - `APIPage` 本地服务字段
  - `FasterWhisperAdapter`
  - `ChatWindow` 被动状态状态机
  - `SystemPage` 字体下拉框与布局拆分
  - `SettingsWindow` API / 系统页保存分流
  - 文档和验证任务

## Phase 5 改进实现执行记录

时间：2026-05-25 20:16:42 +08:00

### 工具可用性说明

- 用户提供的 AGENTS 要求优先使用 `sequential-thinking`、`shrimp-task-manager`、`desktop-commander`、`context7` 和 `github.search_code`。
- 当前 Codex 工具集中未提供这些工具；已改用本地 `rg`、`Get-Content`、`pytest`、`py_compile` 和 `git diff --check` 执行等价检索与验证。
- 所有本地配置文件继续排除提交范围：`data/config/agent.yaml`、`data/config/system_config.yaml`。

### 编码前检查 - Phase 5 改进实现

□ 已查阅上下文摘要文件：`.codex/context-summary-phase-5-stt-passive-settings-refinement.md`
□ 将使用以下可复用组件：

- `stt.adapter.STTAdapter`: 保持 STT 适配器抽象。
- `stt.types.STTResult`: 统一 STT 返回协议。
- `ui.settings.pages.api_page.APIPage`: 复用设置页 apply/reset 模式。
- `ui.settings.pages.system_page.SystemPage`: 复用系统页配置写回模式。
- `ui.chat.window.ChatWindow._show_passive_bubble()`: 复用被动气泡展示能力。
- `ui.chat.window.ChatWindow._apply_scale()`: 复用聊天窗外观应用能力。

□ 将遵循命名约定：私有控件字段使用 `_xxx`，测试函数使用 `test_行为描述`
□ 将遵循代码风格：4 空格缩进、PySide 信号在构造阶段连接、pytest monkeypatch 隔离外部服务
□ 确认不重复造轮子：已检查 `stt/`、`ui/settings/pages/`、`ui/chat/window.py`、相关测试文件，确认需要替换而不是新增平行链路

### 执行结果

- Task 1：`ASRConfig` 默认值已改为 `faster_whisper` 本地服务；`PassiveInteractionConfig` 已移除 `enabled` 并新增 `idle_threshold_seconds`。
- Task 2：API 页 ASR 配置已改为 `none / faster_whisper`，本地服务字段使用 `api_url`，删除 OpenAI Whisper Base URL / API Key 控件。
- Task 3：已新增 `stt/adapters/faster_whisper.py`，`STTManager` 只识别 `none` 与 `faster_whisper`，删除 `stt/adapters/openai_whisper.py`。
- Task 4：`ChatWindow` 已新增运行态被动状态、空闲计时器、交互刷新、右键菜单进入 / 退出被动状态；主动消息仅在被动状态下使用气泡。
- Task 5：系统页已拆分为基础外观、聊天显示、被动状态、被动气泡、网络；字体改为带预览的系统字体下拉框，不可平滑缩放字体只保留名称；移除实时保存。
- Task 6：设置中心保存按钮已支持 API 页和系统页分流；系统页保存后调用 `ChatWindow.apply_system_config()` 应用到已打开聊天窗。
- Task 7：已同步 `CLAUDE.md`、`docs/README.md`、`docs/architecture.md`、`docs/development.md`、`docs/ui-guidelines.md` 和 `.codex` 留痕。

### 已执行的 TDD 红绿记录

- `tests/test_config.py`：先确认 faster-whisper 默认值和被动阈值测试红灯，再实现配置模型并通过 `14 passed`。
- `tests/test_settings_window.py::test_api_page_asr_uses_faster_whisper_local_service_fields`：先因旧 `base_url/api_key` 字段红灯，再实现 API 页并通过。
- `tests/test_stt_adapter.py`：先因缺少 `stt.adapters.faster_whisper` 与旧 OpenAI 适配器红灯，再实现本地 HTTP 适配器并通过 `10 passed`。
- `tests/test_chat_passive_bubble.py`：先因旧 `enabled` 与缺少被动状态方法红灯，再实现聊天窗被动状态并通过 `6 passed`。
- `tests/test_settings_window.py` 系统页聚焦测试：先因旧实时保存和旧字体输入红灯，再实现字体下拉、布局拆分和非实时保存并通过 `3 passed`。
- `tests/test_settings_window.py` 与 `tests/test_chat_window_scale.py` 保存分流聚焦测试：先因旧保存文案、缺少系统保存分流和缺少 `apply_system_config()` 红灯，再实现并通过 `3 passed`。

### 编码后声明 - Phase 5 改进实现

#### 1. 复用了以下既有组件

- `STTAdapter` / `STTResult`: 用于保持 STT 适配层与结果协议稳定。
- `RoseSpinBox`: 用于录音超时、静音阈值、系统显示倍率和被动阈值输入。
- `SAKURA_COMBO_BOX_STYLE`: 用于 API 页和系统页下拉框主题一致。
- `ChatWindow._apply_scale()`: 用于保存系统配置后刷新已打开聊天窗外观。
- `ChatWindow._show_passive_bubble()` / `_hide_passive_bubble()`: 用于被动状态下主动消息展示。

#### 2. 遵循了以下项目约定

- 命名约定：新增 `_asr_url`、`_asr_timeout`、`_idle_threshold`、`_is_passive`、`_passive_idle_timer` 与既有私有字段一致。
- 代码风格：沿用 PySide 控件构造、信号连接、`apply()` 写回配置的局部模式。
- 文件组织：STT 适配器仍位于 `stt/adapters/`；设置页仍位于 `ui/settings/pages/`；聊天窗运行态仍在 `ui/chat/window.py`。

#### 3. 对比了以下相似实现

- `APIPage` TTS 本地服务字段：ASR 本地服务字段沿用相同 URL 输入模式，但字段名使用 `api_url`。
- `SystemPage` 旧实时保存：本轮保留 `apply()` 写配置模式，删除实时保存连接，由 `SettingsWindow` 统一落盘。
- `ChatWindow` 旧气泡能力：本轮复用气泡样式、尺寸和定时隐藏，只把触发条件改为运行态被动状态。
- `STTManager` 旧引擎分发：保留未知引擎错误路径，替换有效适配器为 `FasterWhisperAdapter`。

#### 4. 未重复造轮子的证明

- 已检查 `stt/manager.py`、`stt/adapter.py`、`stt/types.py`，没有现成 faster-whisper HTTP 适配器。
- 已检查 `ui/chat/window.py`，已有被动气泡显示能力但没有运行态状态机，因此复用气泡函数并补状态机。
- 已检查 `ui/settings/window.py`，已有 API 保存分流入口，因此扩展为 API / 系统保存路由。

### 最终验证结果

- `python -m pytest tests/test_config.py tests/test_settings_window.py tests/test_chat_window_scale.py tests/test_chat_passive_bubble.py tests/test_chat_stt_flow.py tests/test_stt_adapter.py tests/test_stt_recorder.py -q`
  - 结果：`88 passed in 14.74s`。
- `python -m pytest tests/ -q`
  - 结果：`350 passed in 46.82s`。
- `python -m py_compile config/schema.py ui/settings/window.py ui/settings/pages/api_page.py ui/settings/pages/system_page.py ui/chat/window.py ui/chat/stt_recorder.py ui/theme.py stt/types.py stt/adapter.py stt/adapters/faster_whisper.py stt/manager.py tests/test_chat_stt_flow.py tests/test_stt_adapter.py tests/test_stt_recorder.py`
  - 结果：通过，无输出错误。
- `git diff --check`
  - 结果：通过；仅提示工作区 LF/CRLF 转换，无空白错误。
