# Tauri UI Phase 1 对照摘要

Phase 1 只冻结 Tauri/Vue 前端骨架、边界和测试夹具，不声明完整替代 PySide6 UI。旧 PySide6 主线在 Phase 1-4 继续保留。

## 已读取旧 UI 对照文件

- `ui/settings/window.py`
- `ui/chat/window.py`
- `ui/startup/loading_window.py`
- `ui/settings/pages/conversation_log_page.py`
- `ui/settings/pages/diagnostics_page.py`
- `ui/theme.py`
- `ui/widgets/rose_spin_box.py`
- `ui/widgets/removable_combo_box.py`

## 结构来源

- 设置中心左侧导航顺序来自 `SettingsWindow.pages_info`：API、角色、记忆、Agent、插件、MCP、对话日志、平台日志、诊断、系统。
- 设置中心底部保留“启动对话”和 API / 系统保存入口；Phase 1 中保存按钮为禁用占位，Phase 2 接入真实表单和失败回滚。
- 聊天窗保留输入、发送、停止、重试、流式状态、对话显示区和日志入口的最小结构；TTS、STT、OCR、立绘和被动气泡在 Phase 3 迁移。
- 对话日志保留日志列表、刷新 / follow-bottom 语义和空态；Phase 4 接入虚拟列表、筛选和详情操作。
- 诊断页保留配置健康 / 本机诊断 / 导出诊断包入口；Phase 4 接入真实运行、取消、导出和脱敏失败状态。
- 启动视图保留首屏非空、进度 / 状态可见和 schema hash 诊断状态；Tauri 原生窗口生命周期后续在 Phase 5 打包前硬化。

## 必须保留

- 旧入口不能删除：PySide6 `ui/`、`main.py`、设置中心和聊天窗仍是可回退主线。
- 新前端页面按 `chat`、`settings`、`logs`、`tools`、`diagnostics` 分组；设置页不重复内嵌日志、插件、MCP、诊断状态。
- 业务请求只能经 typed client、composable 或 store，组件和页面不得直接 import Tauri API、HTTP client 或 `fetch()`。
- 持久化只允许 allowlist 字段，运行中 request、confirm token、日志正文、诊断包路径、完整本地路径和敏感原文不得持久化。
- sidecar restart 时 store 必须释放订阅并清理运行态，保留非敏感偏好。

## 允许差异

- Phase 1 页面是骨架和禁用占位，不包含完整业务表单和真实后端联动。
- Web 控件使用 Sakura Web 基础组件替代 Qt widget，视觉不要求像素级一致。
- E2E 目前覆盖最小启动、smoke、a11y 和响应式夹具；完整页面细节随 Phase 2-5 递增。
