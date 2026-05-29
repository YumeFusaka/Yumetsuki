# Yumetsuki 代码架构

## 总览

Yumetsuki 当前主线是 Tauri shell + Vue3 前端 + Python `python_core` headless sidecar。桌面 UI、窗口能力、权限和本机集成由 Tauri 承担；AI 业务、配置、日志、记忆、插件、MCP、TTS、STT 和 OCR 能力由 Python headless 内核承担。

历史 PySide6 入口、旧 `ui/` 主实现和 PySide6 运行时依赖已退场。后续架构判断以本文、`docs/development.md` 和 `docs/ui-guidelines.md` 为当前事实源；`docs/superpowers/specs/` 与 `docs/superpowers/plans/` 下的迁移材料只作为历史归档。

## 目录结构

```text
yumetsuki/
├── apps/desktop/              # Tauri + Vue 桌面工程
│   ├── frontend/              # Vue3、Pinia、typed client、Vitest、Playwright
│   └── src-tauri/             # Rust shell、capability、命令桥、sidecar supervisor
├── python_core/               # headless sidecar、stdio RPC、服务 facade、任务与事件
├── agent/                     # Agent 编排、规划、反思、多步推理、主动行为
├── config/                    # Pydantic 配置模型与 YAML 持久化
├── core/                      # 日志、事件总线、角色、插件、MCP、工具注册
├── llm/                       # LLM 适配与文本处理
├── memory/                    # 长期记忆与记忆账本
├── plugins/                   # 本地插件
├── session/                   # 短期会话上下文
├── stt/                       # 语音转文本适配
├── tts/                       # 语音合成适配
├── vision/                    # 截图、OCR 与视觉观察
├── scripts/                   # 迁移、发布、安全和性能 gate
└── tests/                     # Python core、RPC contract、security、migration、perf
```

## 运行边界

### `apps/desktop/frontend`

- Vue3 Composition API + Pinia 承担界面、交互状态和只读运行态投影。
- 前端只通过 typed client 调用 Tauri command，并订阅 Tauri 事件。
- 前端不直连 Python，不拼接 sidecar 原始协议帧，不读取真实配置文件、日志文件、截图或模型路径。
- 浏览器环境下的测试 transport 仅用于 Vitest / Playwright，不代表产品运行时 sidecar。

### `apps/desktop/src-tauri`

- Rust shell 负责窗口、托盘、权限、capability、桌面能力和 Python sidecar 生命周期。
- `SidecarSupervisor` 启动并管理 `python_core.sidecar_main --stdio`，只接受和转发结构化 RPC 帧。
- Tauri command 是前端唯一业务入口；长任务只返回 `accepted`，后续进度和终态都通过事件流返回。
- 取消 wire method 只有 `sidecar.cancel`。
- capability 文件按窗口收口权限，禁止通配权限和未经审核的文件、shell、HTTP、剪贴板能力。

### `python_core`

- `python_core.sidecar_main` 是 headless sidecar 入口，stdout 只输出 RPC 协议帧，诊断日志只能走 stderr。
- `python_core.rpc` 承担 envelope、framing、schema、method catalog、错误码、任务注册表和事件发布器。
- `python_core.rpc.services` 是 UI 可调用业务 facade，向现有 Python core 模块收口配置、聊天、日志、诊断、工具、插件、MCP、语音和视觉能力。
- sidecar 可达路径不得导入 PySide6 / Qt，也不得依赖桌面 UI 对象。

## 核心流程

### 启动

```text
Tauri app
→ RuntimePaths 注入
→ SidecarSupervisor 启动 Python sidecar
→ sidecar.hello 协商协议版本、schema hash 和 capability
→ Vue appStore 展示 sidecar 状态
```

### 聊天

```text
Vue ChatPanel
→ chatStore.send()
→ typed client
→ Tauri chat_send command
→ Python RPC chat.send
→ AgentManager / LLMManager / ToolRegistry
→ chat.delta / chat.done 事件
→ chatStore 合并流式文本并落到消息列表
```

聊天链路必须保留 request_id / trace_id / session_id，便于日志、取消、重试和诊断串联。

### 设置

```text
Vue SettingsPage
→ config.get_all 读取脱敏快照
→ 用户编辑草稿
→ config.save_* 携带 confirm_token 和 base_version
→ Python ConfigManager 写入 RuntimePaths.config_dir
→ config.changed / chat.config_applied 事件通知 UI 刷新
```

API key、模型路径和本地私有配置只以脱敏摘要返回给 UI。

### 日志与诊断

```text
Python LogService
→ 内存窗口 + JSONL 落盘
→ logs.query / logs.subscribe
→ Vue 日志工作台虚拟列表

diagnostics.run
→ accepted
→ diagnostic.progress
→ diagnostic.done
→ diagnostics.export
```

诊断包必须先经过脱敏扫描，禁止导出真实 token、私有 URL、用户路径、截图原图、完整音频或本地模型绝对路径。

### 语音与视觉

- TTS 合成由 Python speech facade 和现有 `tts/` 适配层承担；桌面播放能力由 Tauri/Rust 音频契约承接。
- STT 录音由 Tauri/Rust recorder 契约承接，转写由 Python `stt/` 适配层执行。
- 屏幕采集只在显式读屏、当前页面阅读或被动状态定时读屏启用时触发；Python 视觉层使用 headless 截图后端和 OCR 适配器。
- 截图、音频和导出报告都通过 handle 管理，必须有 TTL、释放和 sidecar shutdown 清理。

## 主要 Python 模块

### `config/`

- `schema.py` 定义 API、系统、记忆、Agent、MCP、语音和视觉配置。
- `manager.py` 按 RuntimePaths.config_dir 读写 YAML，保存使用原子替换。

### `agent/`

- `manager.py` 负责编排用户输入、短期上下文、记忆检索、工具调用、LLM 流式回复和反思。
- `planner.py` 做分层路由，简单对话零额外开销，复杂任务按需升级。
- `proactive.py` 是无 UI 依赖的主动行为调度器，使用标准线程和事件对象。

### `core/`

- `event_bus.py` 提供线程安全发布订阅。
- `ui_event_bridge.py` 现在是 headless 本地事件桥，不依赖桌面 UI 框架。
- `log_service.py` 提供结构化日志、脱敏、内存窗口和 JSONL 落盘。
- `plugin_host.py`、`mcp_host.py`、`tool_registry.py` 聚合本地插件和 MCP 工具。

### `llm/`

- `manager.py` 负责角色提示、短期上下文、长期记忆补充、工具调用循环和流式文本处理。
- `adapters/openai_compat.py` 保持 OpenAI-compatible API 兼容。

### `tts/`、`stt/`、`vision/`

- `tts/` 保持 GPT-SoVITS 兼容、参考策略、PCM/WAV 事件模型和失败回退。
- `stt/` 使用本地 faster-whisper 适配，录音输入由桌面侧契约提供。
- `vision/` 管理截图、OCR、文本截断、最近视觉观察和中间产物清理。

## 当前能力边界

- 自动化测试覆盖 RPC contract、headless Python core、Tauri capability、安全扫描、发布 manifest、性能预算和迁移退场 gate。
- 真实 API、TTS、STT、OCR、MCP 和浏览器自动化仍需要本机实机验收记录；这些属于 1.0 验收风险，不应阻塞 no-PySide6 主线。
- 所有新增 UI 能力必须先经过 `Vue typed client -> Tauri invoke/events -> Python stdio RPC`，不得重新引入 Python 桌面 UI 依赖。
