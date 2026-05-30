# Tauri UI 重构发布级设计

> 日期：2026-05-28
>
> 状态：发布级设计定稿，已通过 90+ 复审，等待进入实施计划。本文是进入实施计划前的架构契约，不是 implementation plan。

## 结论

Yumetsuki 的 UI 重构采用“桌面 UI 壳 + Python AI 内核”的双层产品结构：

```text
apps/desktop/frontend
  Vue3 + Pinia + TypeScript
  负责 UI、状态、主题、交互和渲染

apps/desktop/src-tauri
  Tauri Rust shell
  负责窗口、托盘、权限、sidecar supervisor、typed commands、事件桥和桌面能力

python_core
  Python headless sidecar
  负责 Agent、LLM、TTS 协议适配、STT 转写、OCR 识别、插件、MCP、配置、日志和记忆
```

主链路约束：

- 前端不直连 Python。
- Vue 只调用 Tauri typed command，并监听 Tauri event。
- Tauri 通过本地 stdio RPC 管理 Python sidecar。
- 短任务走 `request/response`。
- 长任务只返回一次 `accepted`，后续只走事件流，终态只能是 `done`、`error` 或 `cancelled` 三选一。
- 迁移期 PySide6 只作为旧 UI 行为参考和回归对照；全部移植完成后必须完全移除 PySide6 依赖、旧 `ui/` 实现和旧文档入口。

本文采纳第二轮 90+ 复审的硬要求。没有满足本文 gate 的阶段，不进入下一阶段。

## 非目标

- 不把 PySide6 UI 逐文件翻译成 Vue。
- 不在前端直接拼 Python RPC 协议。
- 不让 HTTP / axios 成为桌面主通信链路。
- 不在 Python sidecar 中保留 PySide6 运行时依赖。
- 不把 Tauri 视为插件、MCP 或命令执行的安全沙箱。
- 不在发布包中携带真实用户配置、日志、截图、模型、浏览器会话或本地记忆。
- 不把 Computer Use、无人值守高权限自动化或复杂桌面控制纳入本次 UI 重构默认范围。

## 复审硬门槛

第二轮复审最低分项必须通过设计和后续实施补到 90+：

| 风险域 | 必须补强为 |
|---|---|
| RPC / Tauri / Vue 新测试 gate | 目录化、命令化、失败阻塞 |
| sidecar 生命周期和崩溃恢复 | Rust supervisor + Python headless handshake |
| PySide6 deprecated -> removal | 退场表、双跑、替代验收、删除检查 |
| per-user app data | 统一 `RuntimePaths`，不再默认写发布目录 |
| stdio 背压 / 压测 | 有界队列、最大帧、节流、stderr drain、压力测试 |
| 插件 / MCP / 命令权限边界 | capability、确认、审计、撤销和路径约束 |
| stdout 协议污染 | stdout 只允许协议帧，插件 stdout 隔离 |
| Sakura Web / Pinia / parity | typed client、store 边界、Web 组件体系和等价矩阵 |

## 架构所有权

### 前端层

`apps/desktop/frontend` 只拥有：

- 页面组件、布局和路由。
- Pinia store 中的 UI 状态、草稿状态、筛选状态、滚动状态和运行态投影。
- Sakura Web 组件和 design tokens。
- typed Tauri client 的 TypeScript 类型封装。
- E2E 所需的页面测试选择器和可访问性标签。

前端禁止：

- 直接启动或连接 Python。
- 直接读取真实配置文件、日志文件、模型目录或截图目录。
- 直接执行系统命令、MCP 命令、插件代码或浏览器自动化。
- 拼接 sidecar 原始协议帧。
- 将 API key、长 OCR 原文、截图路径或模型完整路径写入 UI 状态持久化。

### Tauri shell 层

`apps/desktop/src-tauri` 拥有：

- 主窗口、桌宠窗口、托盘、透明窗口、拖拽、置顶和系统通知。
- Python sidecar supervisor。
- typed command 和 event bridge。
- per-user app data 路径发现与注入。
- 文件选择、路径 scope、权限确认和高风险操作确认。
- 麦克风录音、音频播放、屏幕截图、浏览器 profile 目录、桌面临时文件清理等桌面能力。
- 发布包清单检查、bundle 排除和 sidecar 生命周期测试。

Tauri shell 禁止：

- 绕过 Python 直接改写 AI 域配置。
- 暴露通用“任意 RPC passthrough”给前端。
- 把未脱敏诊断包、截图原图、音频、模型完整路径或真实 API key 传给前端。
- 默认允许 `file://`、路径穿越、任意命令执行或未经确认的外部插件执行。

### Python Core 层

`python_core` 拥有：

- Agent、Planner、Reflector、MultiStep、Proactive 的 headless 编排。
- LLM、TTS、STT、OCR 的协议适配和任务状态。
- 插件宿主、MCP host、ToolRegistry 和工具调用审计。
- ConfigManager、LogService、SessionContext、Memory、DiagnosticBundle。
- RPC handler、任务注册表、取消令牌、结构化事件发布。

Python Core 禁止：

- 导入 `PySide6`。
- 使用 stdout 输出非协议文本。
- 直接截图、录音、播放音频或管理窗口。
- 默认写入项目仓库内 `data/` 作为发布运行期目录。
- 让第三方插件 stdout、MCP stdout、print 调试文本污染 sidecar stdout。

## 目录结构

目标结构：

```text
Yumetsuki/
├── apps/
│   └── desktop/
│       ├── frontend/
│       └── src-tauri/
├── python_core/
├── plugins/
├── data/
│   ├── config/
│   └── characters/
├── docs/
└── tests/
```

迁移策略：

- 第一阶段先创建新边界，不立即批量移动全部 Python 模块。
- `agent/`、`llm/`、`tts/`、`stt/`、`vision/`、`core/`、`config/`、`session/`、`memory/` 逐步归入 `python_core` 或成为其内部包。
- 旧 `ui/` 在迁移期保留为行为参考；不得继续扩展新功能。
- 完全迁移后删除旧 Qt 启动链路和旧 `ui/` 页面实现。

## RPC Contract v1

### Framing

sidecar stdio 使用严格协议帧。优先方案为 NDJSON，每行一个 UTF-8 JSON frame；如果后续压测显示 NDJSON 不足以承载大消息，再升级为 `Content-Length` framing。无论采用哪种 framing，必须满足：

- stdout 只能写协议帧。
- 每个 frame 有最大字节数上限，该值为配置项候选。
- 超出上限的内容必须走句柄、文件、摘要或分页接口。
- stderr 可承载非结构化诊断文本，但发布版仍应避免敏感信息。
- 结构化日志优先走 `log.event` 或 JSONL 落盘。

### Envelope

请求：

```json
{
  "kind": "request",
  "request_id": "req_...",
  "method": "config.get_all",
  "params": {},
  "protocol_version": 1,
  "trace_id": "trace_...",
  "parent_trace_id": null,
  "session_id": "sess_...",
  "deadline_ms": 30000
}
```

响应：

```json
{
  "kind": "response",
  "request_id": "req_...",
  "ok": true,
  "result": {},
  "error": null,
  "protocol_version": 1,
  "trace_id": "trace_...",
  "parent_trace_id": null,
  "session_id": "sess_..."
}
```

事件：

```json
{
  "kind": "event",
  "type": "chat.delta",
  "request_id": "req_...",
  "protocol_version": 1,
  "trace_id": "trace_...",
  "parent_trace_id": null,
  "session_id": "sess_...",
  "sequence": 12,
  "timestamp_ms": 1779970000000,
  "payload": {}
}
```

错误：

```json
{
  "code": "tts.timeout",
  "message": "语音合成超时",
  "retryable": true,
  "user_message": "语音合成超时，可以重试或查看平台日志。",
  "details": {
    "stage": "tts",
    "summary": "request timeout"
  }
}
```

### ID 传播

所有 RPC 请求、响应、事件、日志、取消和诊断导出必须携带：

- `request_id`：一次 UI 发起操作或长任务的唯一 ID。
- `trace_id`：跨模块可观测链路 ID。
- `session_id`：对话会话 ID；非对话任务可为空字符串或专用 session。

命名约束：

- `request_id` 是协议唯一主键；不再使用 `id` 作为新协议字段。
- `request_id` 不复用。
- `trace_id` 可派生；重试时保留父 trace，并生成新的 request。
- `parent_trace_id` 必须在 envelope、event、日志和诊断 manifest 中显式存在，没有父 trace 时为 `null`。
- `session_id` 只表达会话，不承担取消语义。
- 取消只按 `request_id` 生效。

### 短任务状态机

短任务包括配置读取、页面列表、简单刷新、权限状态查询等。

```text
created
→ running
→ done | error
```

短任务规则：

- 只允许一个 response。
- 不产生 progress event；必要时改成长任务。
- 超时由 Rust shell 和 Python handler 双侧兜底，并统一表现为 `error(*.timeout)`；`timeout` 不是对外终态。
- 重复请求不自动合并，除非 method 明确声明幂等。

### 长任务状态机

长任务包括聊天、TTS、STT、OCR、诊断、MCP 刷新、插件扫描和导出。

```text
created
→ accepted
→ streaming
→ done | error | cancelled
```

规则：

- Python 接受任务后只返回一次 `accepted`。
- 后续进度、增量、状态、日志只走 event。
- 终态只能发一次，由 Python 任务注册表原子写入。
- 取消后迟到 chunk、迟到 result 或迟到错误只能写内部日志，不得更新 UI 主状态。
- 重复 cancel 是幂等操作；已终态任务返回当前终态摘要。
- sidecar 重启后，未终态 request 全部视为 `error(sidecar.restarted)`，前端必须显示可恢复状态。

### 取消语义

`sidecar.cancel(request_id)` 是独立 RPC method：

- 如果任务未开始：标记 `cancelled`，不执行。
- 如果任务运行中：设置 `CancelToken`，触发资源收口。
- 如果任务已终态：返回当前终态，不重复事件。
- 如果 sidecar 不认识 request：返回 `not_found`，前端按迟到或已清理处理。

Python Core 必须为以下任务接入统一 `CancelToken` / `TaskHandle`：

- LLM 流式生成。
- TTS 合成和句段队列。
- STT 转写。
- OCR 识别。
- MCP 请求。
- 插件工具调用。
- 诊断和导出任务。

### 事件流背压

所有高频事件必须有批量、节流和上限。以下数值为建议默认值或配置项候选，不能硬编码为永久常量：

| 项 | 建议默认或策略 |
|---|---|
| 单 frame 最大字节数 | 配置项候选，超限转句柄或摘要 |
| 每 request 事件队列 | 配置项候选，满后优先合并进度类事件 |
| 全局事件队列 | 配置项候选，满后暂停生产或降级摘要 |
| flush 间隔 | 配置项候选，聊天文本可短间隔合帧 |
| 日志事件 | 批量 append，前端虚拟列表消费 |
| TTS PCM | 不直接逐 chunk 穿越 UI event；优先由 Rust 播放或使用文件 / 流句柄 |
| OCR 长文本 | 传摘要和句柄，完整文本由分页查询读取 |
| 音频 / 截图 / 模型路径 | 不进入通用事件 payload |

丢弃策略：

- 文本 delta 可以合帧，不能乱序。
- 进度状态可以覆盖旧值。
- 错误和终态不能丢弃。
- 审计日志不能静默丢弃；内存窗口可裁切，但落盘队列不能被 UI 缓冲上限裁切。

### 错误码族

错误码按域分组：

- `rpc.*`
- `sidecar.*`
- `config.*`
- `chat.*`
- `llm.*`
- `tts.*`
- `stt.*`
- `ocr.*`
- `plugin.*`
- `mcp.*`
- `tool.*`
- `security.*`
- `filesystem.*`

错误对象必须同时满足：

- UI 有可展示 `user_message`。
- 日志有结构化 `details`。
- 诊断包可脱敏导出。
- retryable 语义明确。

## Sidecar Supervisor

### Python headless 入口

新增 `python_core/sidecar_main.py` 或等价入口。它只做 headless 初始化：

- 读取由 Tauri 注入的 `RuntimePaths`。
- 初始化配置、日志、Agent、LLM、TTS adapter、STT manager、OCR manager、插件和 MCP。
- 启动 RPC reader/writer。
- 提供 `sidecar.hello`、`sidecar.health`、`sidecar.shutdown`、`sidecar.cancel`。

入口禁止：

- 创建 `QApplication`。
- 导入旧 `ui/`。
- 导入 `PySide6`。
- 直接访问用户桌面能力。

### Rust supervisor

Tauri shell 负责：

- 启动 Python sidecar。
- 传入 app data 根目录、只读资源目录、日志目录和协议版本。
- 等待 `hello/ready` 握手。
- 定期 health ping。
- 捕获 stdout 协议帧和 stderr 诊断文本。
- 退出时先发 `sidecar.shutdown`，超时后强杀进程树。
- 崩溃时上报 `sidecar.crashed` 事件。
- 按配置候选做指数退避重启；频繁崩溃后停止自动重启并提示用户。
- Windows 下清理孤儿进程和子进程树。

### stdout / stderr 纪律

- stdout：只允许 RPC frame。
- stderr：允许短诊断文本；不得输出 API key、cookie、完整本地模型路径、长 OCR 原文、截图路径或私有 URL 全文。
- Python logging 默认写 JSONL 或 stderr，不能写 stdout。
- `print()` 在 sidecar 进程内默认重定向到 stderr，并在测试中扫描 stdout 合法性。
- 第三方插件 stdout/stderr 必须捕获到插件 worker 日志，不得直通 sidecar stdout。

## RuntimePaths

发布版运行期目录由 Tauri 发现并传入 Python。Python 不自行假设仓库根目录是可写运行期目录。

目录分区：

| 分类 | 归属 | 说明 |
|---|---|---|
| 只读资源 | bundle resource | 默认角色资源、示例配置、静态资源 |
| 用户配置 | app data config | `api.yaml`、`system_config.yaml`、`mcp.yaml`、`memory.yaml`、`agent.yaml` |
| 日志 | app data logs | 对话日志、平台日志、诊断日志 |
| 记忆 | app data memory | Chroma、SQLite、记忆账本 |
| OCR 截图 | app data vision | 中间产物，按配置清理 |
| 浏览器会话 | app data browser_sessions | Playwright profile、截图和会话产物 |
| 模型 | 用户选择或 app data models | 不随发布包携带真实模型 |
| 临时音频 | app data temp 或系统临时目录 | request 生命周期清理 |

迁移规则：

- 首次启动只复制 example/default 配置，不复制真实 `api.yaml` 或 `memory.yaml`。
- 发布包扫描到真实配置、日志、截图、模型、浏览器状态时构建失败。
- 所有保存路径必须 `resolve()` 后校验在 app data 或用户显式选择目录内。
- Python 侧只接受 `RuntimePaths` 派生路径，不接受任意相对路径作为运行期根。

## Python Core Headless 化

### Qt 依赖替代表

| 当前模块 | 当前 Qt 依赖 | 新归属 | 替代方案 |
|---|---|---|---|
| `main.py` | `QApplication`、`SettingsWindow` | 旧 UI | Tauri 启动桌面应用，Python sidecar 使用新入口 |
| `core/ui_event_bridge.py` | `QObject`、Qt signal | 移除或替换 | Python 事件队列 + RPC publisher |
| `agent/proactive.py` | `QObject`、`QThread`、`Signal` | Python Core | `threading`、`asyncio` 或调度器接口，事件通过 RPC 发出 |
| `vision/screen_capture.py` | `QGuiApplication` 截屏 | Tauri/Rust | Rust 截屏后传 PNG bytes 或受控路径给 Python OCR |
| `ui/chat/stt_recorder.py` | Qt 麦克风输入 | Tauri/Rust | Rust 录音并输出 WAV bytes 或受控临时文件 |
| `ui/chat/audio_backends.py` | Qt 音频播放 | Tauri/Rust | Rust 播放 WAV/PCM，播放状态回报事件 |
| `ui/chat/window.py` | UI、线程、TTS/STT/OCR 接线 | 拆分 | UI 进 Vue；headless chat service 进 Python Core |

### sidecar 无 PySide6 gate

发布前必须通过：

```text
未安装 PySide6 的环境中：
1. 导入 python_core sidecar 入口成功
2. sidecar.hello 成功
3. sidecar.health 成功
4. config.get_all mock 或真实默认配置读取成功
5. sidecar.shutdown 成功
```

同时静态检查：

- `python_core`、`agent`、`llm`、`tts`、`stt`、`vision`、`core`、`config`、`session`、`memory` 的发布路径不得导入 `PySide6`。
- `requirements-sidecar.txt` 不包含 `PySide6`。
- 旧 `requirements.txt` 中的 PySide6 只允许存在于迁移期旧 UI 环境；最终 removal gate 必须删除。

### TTS / STT / OCR 职责

TTS：

- Python 负责文本切句、TTS 服务协议适配、合成事件和错误归因。
- Rust 负责音频播放和播放状态回报。
- PCM 不逐 chunk 穿透 Vue；如需要低延迟播放，Rust 直接消费流或文件句柄。
- WAV 优先通过受控临时文件交给 Rust 播放，完成、失败、取消和退出时清理。

STT：

- Rust 负责录音、静音检测或录音 UI 状态。
- Python 接收 WAV bytes 或受控临时文件路径，执行 faster-whisper 转写。
- 模型加载、转写、超时、失败、迟到结果丢弃都产生事件和平台日志。

OCR：

- Rust 负责截图和权限提示。
- Python 接收 PNG bytes 或受控路径，执行 RapidOCR / PaddleOCR。
- OCR 文本进入 SessionContext 前必须截断、摘要和脱敏。
- 截图中间产物不进入诊断包。

## MCP 与插件治理

MCP stdio 必须升级：

- 连接超时、请求超时和总超时生效。
- stdout 读取不能无限阻塞。
- stderr 由独立 reader drain，避免 PIPE 填满死锁。
- close 时清理整棵进程树。
- 大输出、慢响应、stderr 洪泛和并发请求有压力测试。

插件治理：

- 内置可信插件可迁移期继续进程内运行，但 stdout 必须捕获或重定向。
- 第三方插件默认低信任，优先进入插件 worker 子进程。
- 工具调用必须有超时、取消、stdout/stderr 捕获、结构化错误和审计日志。
- 外部插件导入继续要求显式风险提示。
- 插件返回内容一律视为不可信输入，不得成为新指令。

系统命令：

- 禁止默认 `shell=True`。
- high 权限命令必须显式确认。
- 命令、参数、工作目录和环境变量进入审计摘要。
- 不允许读取 `.env`、SSH key、token、浏览器凭据等敏感文件。

## Desktop Capability 与安全边界

Tauri capability 最小化：

- 前端只能调用固定 typed command。
- 文件 scope 限定 app data 和用户显式选择路径。
- 浏览器导航默认只允许 `http/https`。
- `file://`、本地内网、私有服务地址访问需要单独确认或配置。
- OCR 截图区域和触发方式继续坚持显式触发；被动读屏默认关闭。

路径安全：

- 所有 filename 禁止绝对路径和 `..`。
- 所有保存路径 `resolve()` 后必须在受控目录。
- 浏览器截图、OCR 截图、诊断导出、临时音频均有路径穿越测试。

诊断包：

- 只导出脱敏结构化日志和 manifest。
- 不包含截图原图、音频、模型完整路径、API key、cookie、authorization、浏览器 profile、长 OCR 原文或私有 URL 全文。
- URL 默认只保留 scheme、host 分类或 hash；localhost、私有 IP、path、query 默认屏蔽。

## Frontend Architecture

### Pinia stores

| Store | 职责 |
|---|---|
| `appStore` | 应用启动状态、sidecar 状态、全局错误、路由可用性 |
| `windowStore` | 窗口可见性、透明窗口、拖拽、置顶、缩放、托盘状态 |
| `themeStore` | Sakura tokens、字体、字号、气泡倍率、边框规则 |
| `configStore` | 配置快照、页面草稿、dirty、保存中、保存失败回滚 |
| `chatStore` | 消息、流式草稿、request 状态、停止/重试、被动状态、状态条 |
| `audioStore` | TTS 播放状态、音频队列投影、播放失败、停止说话 |
| `sttStore` | 录音、识别、超时、迟到结果丢弃、错误展示 |
| `logStore` | 日志窗口、筛选、虚拟列表、follow-bottom、选中详情、拖选暂停刷新 |
| `toolStore` | 插件、MCP、工具目录、权限、诊断状态和审计摘要 |
| `diagnosticStore` | 诊断运行、取消、导出、敏感扫描失败、报告摘要和打开报告状态 |
| `characterStore` | 角色选择、立绘资源、情绪、核心文件保护 |

组件只能读写 store 和 typed client；不直接拼 RPC 帧。

### typed Tauri client

前端统一通过 client：

```text
commands/
  config.ts
  chat.ts
  logs.ts
  tools.ts
  diagnostics.ts
events/
  chatEvents.ts
  logEvents.ts
  sidecarEvents.ts
types/
  rpc.ts
  config.ts
  logs.ts
```

typed client 负责：

- command 参数校验。
- request_id / trace_id 生成或接收。
- event unsubscribe。
- 错误归一化。
- 长任务 accepted 后注册状态。
- 提供 mock/fake client，覆盖成功、错误、timeout、重复事件和乱序事件。

### Store lifecycle 和持久化边界

| Store | actions | getters | 订阅生命周期 | 持久化 |
|---|---|---|---|---|
| `appStore` | `bootstrap`、`recoverSidecar` | sidecar 可用性 | 应用生命周期 | 仅非敏感偏好 |
| `windowStore` | `openChat`、`setScale`、`setAlwaysOnTop` | 窗口投影 | 窗口创建到销毁 | 可持久化窗口偏好，不持久化运行中任务 |
| `themeStore` | `applyTokens` | CSS variables | 应用生命周期 | 可持久化主题名和字体偏好 |
| `configStore` | `load`、`editDraft`、`saveApi`、`saveSystem`、`rollback` | dirty、saving、masked config | 页面挂载到卸载 | 不持久化 API key 原文 |
| `chatStore` | `send`、`cancel`、`retry`、`applyDelta` | busy、canRetry、statusText | 聊天窗口生命周期 | 不持久化流式草稿 |
| `logStore` | `subscribe`、`pause`、`select`、`queryMore` | filtered、followBottom | 日志页可见期间 | 只持久化筛选偏好 |
| `toolStore` | `refreshPlugins`、`refreshMcp`、`setPermission` | tool summary | 页面可见期间 | 只持久化授权摘要，不存敏感命令全文 |
| `diagnosticStore` | `run`、`cancel`、`exportReport`、`openReport`、`copySummary` | running、canCancel、redactionFailed、reportReady | 诊断页可见期间；长任务终态后保留摘要到页面卸载 | 不持久化报告路径、原始日志或敏感扫描内容 |

跨 store 更新：

- `config.save_system` 成功后，只通过 typed event 更新 `themeStore/windowStore/chatStore` 的投影，不直接改运行中任务。
- `sidecar.restarted` 由 `appStore` 分发给各 store 清理 transient 状态。
- `chat.cancelled/error/done` 只由 `chatStore` 处理终态，其他 store 只消费派生事件。
- typed client mock 必须覆盖成功、错误、timeout、重复事件和乱序事件。

### Sakura Web 组件体系

必须先沉淀 design tokens 和基础组件：

- `Button`
- `IconButton`
- `Input`
- `Select`
- `Stepper` / `SpinBox`
- `Modal`
- `ConfirmDialog`
- `Toast`
- `Tooltip`
- `ContextMenu`
- `Splitter`
- `VirtualLogList`
- `ChatPanel`
- `PassiveBubble`
- `SettingsSection`

Web tokens 必须覆盖：

- 主背景渐变。
- 强调色、深强调色、主文字、次级文字。
- 输入框和按钮边框。
- tooltip / menu 浅色规则。
- focus 状态。
- 缩放和最小边框厚度。

### 骨架阶段 UI 最小闭环

骨架阶段不能只做空壳，必须完成：

- 透明或半透明桌宠窗口风险验证。
- 角色立绘加载。
- 基础 Sakura 样式。
- 输入、发送、mock 流式显示。
- 停止当前 mock 生成。
- 失败后保留输入。
- 重试。
- 打开最小日志查看器。
- 窗口拖拽、缩放和不遮挡输入。

日志最小查看器必须完成：

- 批量 append。
- 虚拟列表或等价高频渲染策略。
- 详情区稳定。
- follow-bottom。
- 用户拖选时暂停刷新。
- 页面不可见时暂停订阅。

## 设置中心保存语义

Tauri/Vue 必须保留现有保存语义：

- API 页面只保存 API 配置。
- 系统页面只保存系统配置。
- API / 系统切页放弃未保存草稿。
- 系统保存成功后广播应用到已打开聊天窗。
- 系统保存失败时回滚内存配置、页面草稿和已打开聊天窗投影。
- 记忆模型选择和启用语义保持现有约束。
- 高风险操作继续二次确认。

状态机：

```text
clean
→ editing
→ dirty
→ confirm
→ saving
→ saved | failed_rollback
```

## 测试 Gate

### 测试金字塔

| 层 | 目录 / 命令 | 阻塞目标 |
|---|---|---|
| Python Core | `python -m pytest tests/ -q` 和聚焦测试 | 现有领域逻辑不回退 |
| RPC Contract | `python -m pytest tests/rpc_contract/ -q` | envelope、状态机、取消、背压、stdout 零污染 |
| Tauri lifecycle | `cargo test` | sidecar supervisor、RuntimePaths、capability、路径安全 |
| Vue unit | `npm test` | Pinia store、typed client、组件状态机 |
| E2E smoke | `npm run e2e:smoke` | 骨架、设置保存、聊天最小闭环、日志查看 |
| Stress / Security | 专用脚本或测试命令 | 高频日志、慢消费者、stderr 洪泛、路径穿越、诊断包脱敏 |

这些命令在对应目录创建前作为设计 gate；目录落地后必须成为阶段阻塞命令。

### 现有 pytest 复用

保留为 Python Core 回归基座：

- `test_agent_*`
- `test_session_*`
- `test_memory_ledger.py`
- `test_log_*`
- `test_tts_*`
- `test_stt_*`
- `test_web_automation*`
- `test_mcp_host.py`
- `test_tool_registry.py`
- `test_diagnostic_*`
- `test_config*`

迁移为新栈测试：

- `test_settings_window.py` -> Vue page + RPC contract + Tauri command。
- `test_*page.py` -> Vue page/store tests。
- `test_chat_*` -> Python chat service tests + Vue chat store + E2E。
- `test_sprite_manager.py` -> frontend asset/render tests 或 Rust resource tests。
- `test_startup_appearance.py` -> Tauri startup + frontend screenshot smoke。

### PySide6 绑定测试退场表

退场表字段：

- 旧测试文件。
- 绑定对象。
- 替代测试层。
- 替代测试命令。
- 双跑阶段。
- 删除条件。
- 回滚方式。

没有替代测试前，不删除旧测试。

## 迁移阶段

### Phase 0：设计冻结

交付：

- 本设计通过复审。
- `RPC Contract v1` 文档冻结。
- `RuntimePaths` 和 PySide6 退场表冻结。
- Tauri 迁移验收矩阵冻结。

退出条件：

- 复审矩阵全部条目达到 90+。
- 用户确认进入实施计划。

### Phase 1：骨架、协议和最小闭环

交付：

- `apps/desktop/frontend` 和 `apps/desktop/src-tauri` 骨架。
- Python headless sidecar 最小入口。
- `sidecar.hello`、`sidecar.health`、`sidecar.shutdown`。
- 短任务 request/response。
- 长任务 accepted/event/cancel mock。
- 聊天窗最小闭环。
- 日志最小查看器。
- RuntimePaths 注入。

阻塞测试：

- Python sidecar smoke。
- RPC contract。
- Tauri lifecycle。
- Vue store unit。
- E2E smoke。

### Phase 2：设置中心迁移

交付：

- API、系统、记忆、Agent、角色基础页面。
- 配置草稿和保存状态机。
- 保存失败回滚。
- app data 配置读写。

阻塞测试：

- 配置 RPC contract。
- Vue page/store tests。
- E2E 覆盖保存、切页放弃、失败回滚、聊天窗投影应用。

### Phase 3：聊天窗迁移

交付：

- 桌宠窗口、立绘、输入、流式回复、停止、重试、状态条。
- TTS/STT/OCR 的 Tauri/Python 职责切分。
- Rust 音频播放和录音链路。
- Python chat headless service。
- 被动状态和气泡第一版。

阻塞测试：

- chat RPC contract。
- TTS/STT/OCR 取消和迟到结果丢弃。
- E2E 聊天最小主链路。
- 无 PySide6 sidecar import gate。

### Phase 4：日志、插件、MCP、诊断迁移

交付：

- 对话日志、平台日志、插件页、MCP 页、诊断页。
- 插件 / MCP 进程治理。
- 权限确认和审计。
- 诊断包脱敏强化。

阻塞测试：

- 高频日志压测。
- MCP stderr 洪泛和超时测试。
- 插件 stdout 隔离测试。
- 路径穿越测试。
- 诊断包敏感数据负向测试。

### Phase 5：PySide6 完全退场

交付：

- 删除 PySide6 依赖。
- 删除旧 Qt 启动链路。
- 删除或归档旧 `ui/`。
- 更新全部文档入口。
- 删除或替换旧 PySide6 测试。

阻塞检查：

- `requirements` 不含 PySide6。
- 发布包不含 PySide6。
- 发布路径无旧 Qt import。
- 文档不再把 PySide6 描述为主线。
- 新栈全量测试通过。

## PySide6 退场计划

| 对象 | 迁移期状态 | 替代实现 | 删除条件 |
|---|---|---|---|
| `main.py` Qt 入口 | 旧入口 | Tauri desktop 启动 | Tauri 主入口通过 E2E |
| `ui/settings/*` | 行为参考 | Vue 设置中心 | 设置页 parity matrix 全部通过 |
| `ui/chat/window.py` | 行为参考 | Vue chat + Python chat service | 聊天主链路和 TTS/STT/OCR 通过 |
| `ui/chat/stt_recorder.py` | 待替换 | Rust 录音 | STT E2E 和超时取消通过 |
| `ui/chat/audio_backends.py` | 待替换 | Rust 播放 | TTS 播放和清理测试通过 |
| `vision/screen_capture.py` Qt 截屏 | 待替换 | Rust 截屏 | OCR 截屏 E2E 通过 |
| `core/ui_event_bridge.py` | 待替换 | RPC event publisher | 日志和 Agent 事件桥通过 |
| `requirements.txt` PySide6 | 迁移期保留 | `requirements-sidecar.txt` 无 PySide6 | Phase 5 removal gate |
| PySide6 绑定测试 | 双跑 | Vue/Tauri/RPC tests | 替代测试连续通过后删除 |

## 文档策略

新增和更新顺序：

1. 新增本设计 spec。
2. 更新 `docs/README.md`，加入 Tauri 迁移专区和当前状态。
3. 更新 `docs/architecture.md`，区分旧 PySide6 架构和目标 Tauri 架构。
4. 更新 `docs/development.md`，加入迁移测试金字塔、阶段 gate 和 PySide6 退场表。
5. 更新 `docs/ui-guidelines.md`，加入 Sakura Web 组件规范和 Tauri 桌宠窗口规则。
6. 随页面迁移逐步更新插件、MCP、OCR、TTS、日志相关文档。
7. 全量迁移完成后删除旧 PySide6 主线说明。

CLAUDE.md 只保留最新入口和阶段状态，不堆实现细节。

## 发布前压力与安全矩阵

发布前必须覆盖：

- sidecar 崩溃重启。
- sidecar stdout 非法输出检测。
- 长流式回复。
- 高频平台日志，至少覆盖 1k / 10k 级别渲染策略。
- TTS 大量 chunk 和慢消费者。
- MCP stderr 洪泛。
- MCP 慢响应和超时。
- 插件 stdout 污染。
- 路径穿越。
- `file://` 和私有地址访问。
- OCR 高频截图清理。
- 诊断包敏感数据扫描。
- 未安装 PySide6 环境启动 sidecar。

## 发布级补充契约

本节把复审中仍低于 90 分的内容落成可执行矩阵。后续实施计划不得弱化本节约束。

### RPC method catalog

首版 method catalog 必须先覆盖以下方法。所有 method 都必须声明 `params`、`result`、错误码族和是否为长任务。

| Method | 类型 | Params 最小字段 | Result / accepted | 主要事件 |
|---|---|---|---|---|
| `sidecar.hello` | 短任务 | `protocol_version`、`capabilities` | `protocol_version`、`capabilities`、`runtime_paths_ready` | 无 |
| `sidecar.health` | 短任务 | `include_tasks` | `status`、`active_task_count`、`uptime_ms` | 无 |
| `sidecar.shutdown` | 短任务 | `reason`、`deadline_ms` | `accepted_shutdown` | `sidecar.exiting` |
| `sidecar.cancel` | 短任务 | `request_id`、`reason` | `status`、`terminal_state` | 目标任务的 `*.cancelled` |
| `config.get_all` | 短任务 | `scope` | 脱敏配置快照 | 无 |
| `config.save_api` | 短任务 | API 配置草稿、`confirm_token` | 保存结果、应用版本 | `config.changed` |
| `config.save_system` | 短任务 | 系统配置草稿、`confirm_token` | 保存结果、应用版本 | `config.changed`、`chat.config_applied` |
| `chat.send` | 长任务 | `text`、`session_id`、`visual_handle` 可选 | `accepted` | `chat.started`、`chat.delta`、`chat.done/error/cancelled` |
| `chat.retry` | 长任务 | `source_request_id`、`retry_policy` | `accepted` | 同 `chat.send` |
| `tts.synthesize` | 长任务 | `text`、`voice_config_ref`、`session_id` | `accepted` | `tts.started`、`tts.segment`、`tts.done/error/cancelled` |
| `stt.transcribe` | 长任务 | `audio_handle`、`language`、`timeout_ms` | `accepted` | `stt.started`、`stt.progress`、`stt.done/error/cancelled` |
| `ocr.recognize` | 长任务 | `image_handle`、`region`、`max_text_chars` | `accepted` | `ocr.started`、`ocr.done/error/cancelled` |
| `logs.query` | 短任务 | `channel`、`cursor`、`limit`、筛选条件 | `items`、`next_cursor` | 无 |
| `logs.subscribe` | 长任务 | `channel`、筛选条件、`cursor` | `accepted` | `log.batch`、`log.done/error/cancelled` |
| `tools.list` | 短任务 | `include_disabled` | 工具摘要列表 | 无 |
| `plugins.refresh` | 长任务 | 无或筛选条件 | `accepted` | `plugin.status`、`plugin.done/error/cancelled` |
| `mcp.refresh` | 长任务 | server 筛选条件 | `accepted` | `mcp.status`、`mcp.done/error/cancelled` |
| `diagnostics.run` | 长任务 | check 列表、`include_sensitive=false` | `accepted` | `diagnostic.progress`、`diagnostic.done/error/cancelled` |

字段契约规则：

- catalog 中每个 method 在实施计划中必须拆成独立 schema 文件或等价 TypeScript / Rust / Python 共享定义。
- 每个字段必须声明类型、必填 / 可选、默认值、脱敏规则和错误码族。
- 兼容性变更只能新增可选字段；删除字段、改语义、改默认值必须升级 `protocol_version`。
- typed client、Rust command、Python handler 必须由同一 schema 派生或通过 contract test 校验一致。

最小 schema 示例：

```text
chat.send.params
  text: string, required, max_text_chars 由配置约束
  session_id: string, required
  visual_handle: string | null, optional
  retry_of: request_id | null, optional

chat.send.accepted.result
  status: "accepted"
  request_id: string
  task_type: "chat.send"
  started_at_ms: integer

chat.done.payload
  terminal_state: "done"
  clean_text_handle?: handle_id
  message_id: string
  emotion?: string
```

`accepted` response schema：

```json
{
  "kind": "response",
  "request_id": "req_...",
  "ok": true,
  "result": {
    "status": "accepted",
    "request_id": "req_...",
    "task_type": "chat.send",
    "started_at_ms": 1779970000000
  },
  "error": null,
  "trace_id": "trace_...",
  "session_id": "sess_..."
}
```

终态事件 schema：

```json
{
  "kind": "event",
  "type": "chat.done",
  "request_id": "req_...",
  "trace_id": "trace_...",
  "session_id": "sess_...",
  "sequence": 42,
  "timestamp_ms": 1779970000000,
  "payload": {
    "terminal_state": "done",
    "summary": {},
    "result_handle": null
  }
}
```

终态事件只能是 `*.done`、`*.error`、`*.cancelled`。`deadline_ms` 超时映射为 `*.error`，错误码为对应域的 `*.timeout`；用户取消映射为 `*.cancelled`；sidecar 重启映射为 `sidecar.restarted` 错误事件。

### 协议版本和句柄协议

`sidecar.hello` 必须完成协议版本协商：

- Rust 发送 `supported_protocol_versions`。
- Python 返回选定 `protocol_version` 和 `capabilities`。
- 版本不兼容时返回 `rpc.protocol_unsupported`，不进入业务初始化。

大内容句柄 schema：

```json
{
  "handle_id": "h_...",
  "kind": "text|audio|image|file|json",
  "content_type": "text/plain",
  "byte_length": 12345,
  "expires_at_ms": 1779973600000,
  "owner_request_id": "req_...",
  "read_methods": ["handles.read_range", "handles.release"]
}
```

句柄方法：

| Method | 类型 | 说明 |
|---|---|---|
| `handles.read_range` | 短任务 | 按 byte range 读取，必须校验 owner、scope 和最大返回大小 |
| `handles.read_page` | 短任务 | 文本或 JSON 分页读取 |
| `handles.release` | 短任务 | 主动释放句柄和临时资源 |

句柄约束：

- 句柄不得暴露真实敏感路径。
- 句柄过期后读取返回 `filesystem.handle_expired`。
- sidecar 退出、任务取消、任务失败时必须清理请求拥有的临时句柄。
- 诊断包只记录句柄摘要，不记录句柄内容。

### 状态转移表

短任务状态表：

| 当前状态 | 输入 | 下一状态 | 规则 |
|---|---|---|---|
| `created` | request 写入成功 | `running` | Rust 已登记 request |
| `running` | response ok | `done` | 只允许一次 |
| `running` | response error | `error` | 只允许一次 |
| `running` | deadline 超时 | `error` | 错误码为 `*.timeout`，迟到 response 丢弃并记日志 |
| 终态 | 任意迟到 response | 终态不变 | 只写内部日志 |

长任务状态表：

| 当前状态 | 输入 | 下一状态 | 规则 |
|---|---|---|---|
| `created` | accepted response | `accepted` | 只允许一次 |
| `accepted` | progress/delta event | `streaming` | 可跳过，直接 done 合法 |
| `accepted` | done/error/cancelled | 终态 | 无 streaming 的快速完成合法 |
| `accepted` | cancel request | `cancelling` | 任务尚未产生输出也必须幂等取消 |
| `streaming` | progress/delta event | `streaming` | sequence 必须递增 |
| `streaming` | cancel request | `cancelling` | cancel 幂等 |
| `accepted/streaming/cancelling` | done/error/cancelled | 终态 | 终态 CAS，只允许一次 |
| 终态 | 任意迟到事件 | 终态不变 | 非终态迟到事件丢弃，终态重复记录告警 |

异常输入处理：

- 乱序非终态事件：按 `sequence` 丢弃旧事件，记录 `rpc.event_out_of_order`。
- 重复终态：不更新 UI，记录 `rpc.duplicate_terminal`。
- 前端重连：按 `request_id` 查询当前任务快照；sidecar 不存在该任务时返回 `not_found`。
- sidecar 重启：Rust 将所有未终态 request 标记为 `error(sidecar.restarted)`。
- `cancelling` 是长任务显式状态；该状态下只允许资源释放事件和终态事件。
- 取消和 timeout 同时发生：用户 cancel 已进入 `cancelling` 时优先 `cancelled`；未进入 `cancelling` 且 deadline 先到达时优先 `error(*.timeout)`；两者竞争必须通过任务注册表 CAS 保证单一终态。
- 短任务 timeout 后，Rust 侧必须丢弃迟到 response；Python handler 对有副作用短任务必须在写入前检查 deadline，避免超时后继续提交配置写入。

幂等策略：

- `sidecar.health`、`config.get_all`、`logs.query`、`tools.list` 是幂等短任务。
- `config.save_*`、`chat.send`、`tts.synthesize`、`stt.transcribe`、`ocr.recognize` 必须生成新 request。
- `sidecar.cancel` 对同一 `request_id` 幂等。

### 事件分类和背压预算

首版建议默认值作为配置项候选，实施时必须可配置：

| 项 | 建议默认值 / 验收预算 |
|---|---|
| 单 frame 最大值 | 256 KiB |
| 单 request 事件队列 | 512 条或 8 MiB，先到者触发背压 |
| 全局事件队列 | 5000 条或 32 MiB，先到者触发背压 |
| 文本 delta flush | 30-80 ms 合帧 |
| 日志 batch flush | 100-250 ms 或 100 条 |
| stdout stderr 单行采集 | 单行摘要不超过 4 KiB，完整内容落受控日志句柄 |
| 慢消费者阈值 | UI 连续 2 秒未消费则降级为摘要事件 |

事件分类：

| 类型 | 合并策略 | 丢弃策略 | 阻塞策略 |
|---|---|---|---|
| `*.delta` 文本 | 可按时间窗合帧 | 不丢最新内容，不乱序 | request 队列满时暂停生产或降级摘要 |
| `*.progress` | 只保留最新 | 可覆盖旧进度 | 不阻塞终态 |
| `log.batch` | 批量追加 | UI 内存窗口可裁切，落盘不可丢 | 落盘队列满时触发错误 |
| `audit.*` | 不合并关键字段 | 不静默丢弃 | 必须落盘 |
| 终态事件 | 不合并 | 不丢弃 | 优先级最高 |
| large-content | 只传句柄 | 不传正文 | 句柄读取分页限流 |

压测通过标准：

- 10k 条平台日志批量进入前端，UI 不阻塞主交互，详情区稳定。
- 慢消费者场景下内存不持续增长，降级摘要事件可见。
- MCP stderr 洪泛不阻塞 stdout 协议读取。
- 长 OCR 文本通过句柄分页读取，不触发 frame 超限。
- TTS 大 chunk 不通过 Vue event 逐块传递。

### RpcContext 传播契约

新增 `RpcContext` 或等价上下文对象：

```text
RpcContext
  request_id
  trace_id
  parent_trace_id
  session_id
  user_id
  stage
  deadline_ms
  cancel_token
```

传播路径：

```text
Vue typed client
→ Tauri command
→ Rust sidecar request registry
→ Python RPC handler
→ Headless service facade
→ AgentManager / LLMManager / ToolRegistry / LogService / EventBus
→ RPC event publisher
```

要求：

- `AgentManager.chat_stream` 迁移后必须接收 `RpcContext` 或上下文参数。
- `LLMManager.chat_stream` 迁移后必须接收 `RpcContext`，并把 trace 写入日志。
- `ToolRegistry.call` 迁移后必须记录 `request_id`、`trace_id`、工具来源和权限。
- `LogService` 查询和诊断导出必须至少支持按 `trace_id`、`request_id`、`session_id` 聚合。
- event `sequence` 作用域为单个 `request_id` 内递增。
- 重试时生成新 `request_id`，保留 `parent_trace_id`，生成新 `trace_id`。
- envelope、event、LogEvent 和诊断 manifest 都必须显式承载 `parent_trace_id`，没有父 trace 时为空字符串或 null。
- Rust supervisor 自身事件使用独立 `request_id`，但继承触发该事件的 `trace_id`；无触发来源时生成 `trace_id=trace_sidecar_*`。
- 插件 worker、MCP 子进程和工具审计事件必须继承调用工具的 `trace_id/request_id/session_id`，并记录 worker id 或 server name。

### Python headless service facade

迁移时新增 headless service facade，避免 RPC handler 直接调用 UI 旧对象：

```text
ChatService
  send(context, text, visual_handle?)
  retry(context, source_request_id)
  cancel(context, request_id)

SpeechService
  synthesize(context, text, voice_config_ref)
  transcribe(context, audio_handle)

VisionService
  recognize(context, image_handle, region?)

ConfigService
  get_all(context, scope)
  save_api(context, draft)
  save_system(context, draft)

ToolService
  list(context)
  refresh_plugins(context)
  refresh_mcp(context)
```

兼容要求：

- `ChatService` 保持现有 `AgentManager -> LLMManager -> ToolRegistry -> SessionContext -> LogService` 行为。
- `SpeechService` 保留 GPT-SoVITS 原版兼容和 TTS 模式边界。
- `VisionService` 不截图，只处理 Tauri 传入的 image handle。
- `ConfigService` 使用 `RuntimePaths`，并负责首次默认配置复制和旧配置迁移。
- 旧 `EventBus` 迁移期可接入 RPC event publisher；当所有 UI 事件不再依赖 Qt bridge 后，`core/ui_event_bridge.py` 退场。

逐 method schema 规则：

- 每个 method 必须有独立 schema 块，写明 `params`、`result` / `accepted`、错误码族、事件、脱敏规则和是否长任务。
- 保存类 method 统一要求 `draft`、`base_version`、`confirm_token`。
- 查询类 method 统一要求 `scope`、`cursor`、`limit` 或等价分页字段。
- 长任务 method 统一要求 `accepted` 语义、`request_id`、`deadline_ms`、`CancelToken` 绑定和终态事件。
- 安全敏感 method 统一要求确认 token、审计字段和拒绝码。

逐 method 最小 schema 示例：

```text
config.save_memory(context, draft)
  params: draft, base_version, confirm_token
  result: applied_version, changed_scopes, redacted_snapshot
  error: config.validation_failed, config.version_conflict, config.write_failed
  events: config.changed

character.save(context, draft)
  params: draft, base_version, confirm_token
  result: applied_version, assets_refreshed, redacted_snapshot
  error: filesystem.path_out_of_scope, security.confirm_token_invalid, config.write_failed
  events: character.changed, character.assets_refreshed

logs.subscribe(context, channel, filters, cursor)
  params: channel, filters, cursor, limit
  result: accepted
  error: rpc.invalid_params, sidecar.not_ready
  events: log.batch, log.done, log.error, log.cancelled

tools.call(context, tool_name, args)
  params: tool_name, source, arguments, confirm_token?
  result: accepted | tool result
  error: tool.confirm_required, security.permission_denied, tool.execution_failed
  events: tool.started, tool.result, tool.error, tool.cancelled

diagnostics.run(context, checks, include_sensitive=false)
  params: checks, include_sensitive, confirm_token?
  result: accepted
  error: security.confirm_token_invalid, diagnostics.redaction_failed, diagnostics.write_failed
  events: diagnostic.progress, diagnostic.done, diagnostic.error, diagnostic.cancelled
```

旧接口到 facade 的 shim 规则：

| 当前接口 | shim 目标 | 必须变更 |
|---|---|---|
| `AgentManager.chat_stream(user_input, visual_capture)` | `ChatService.send(context, text, visual_handle)` | 增加 `RpcContext`、`CancelToken`、trace 日志传播 |
| `LLMManager.chat_stream(...)` | `ChatService` 内部调用 | 增加 context 参数、deadline、cancel 检查 |
| `TTSPipelineController` | `SpeechService` 句段状态 | 去除 UI 播放职责，保留句段生命周期 |
| `STTManager.transcribe_wav` | `SpeechService.transcribe` | 输入改为 handle/path，接入 request cancel |
| `VisionManager.recognize_image_text` | `VisionService.recognize` | 只识别 Tauri 提供的 image handle |
| `ConfigManager(config_dir=None)` | `ConfigService(RuntimePaths)` | 发布模式禁用 None 回退 |
| `EventBus -> UIEventBridge` | `EventBus -> RpcEventPublisher` | Qt bridge 退场 |

注意：

- 领域内停止 / 取消 action 只允许作为前端 action 或内部 helper，不能作为独立 wire method；它们在实现上都必须归一到 `sidecar.cancel(target_request_id)`。
- 如业务上需要停止某个子流程，必须先映射为对应 `request_id` 的 `sidecar.cancel`，再由 Python 任务注册表落到具体 domain 资源释放。

行为 parity matrix：

| 能力 | 旧行为来源 | 新验收 |
|---|---|---|
| API 保存 | `ui/settings/pages/api_page.py` | 脱敏读取、确认、保存、失败回滚 |
| 系统保存 | `ui/settings/pages/system_page.py` | 保存后广播聊天窗投影，失败回滚 |
| 聊天流式 | `ui/chat/window.py` | delta 合帧、停止、重试、迟到丢弃 |
| TTS | `ui/chat/window.py`、`tts/` | 句段事件、Rust 播放、取消清理 |
| STT | `ui/chat/stt_recorder.py`、`stt/` | Rust 录音、Python 转写、超时释放 |
| OCR | `vision/screen_capture.py`、`vision/manager.py` | Rust 截图、Python OCR、隐私截断 |
| 日志 | `ui/settings/pages/system_log_page.py` | 虚拟列表、拖选暂停、详情稳定 |
| 插件/MCP | `ui/settings/pages/plugin_page.py`、`mcp_page.py` | capability、worker、诊断和审计 |

### RuntimePaths schema

Tauri 传入 Python 的 RuntimePaths：

```json
{
  "app_data_dir": "C:/Users/<user>/AppData/Roaming/Yumetsuki",
  "config_dir": ".../config",
  "log_dir": ".../logs",
  "memory_dir": ".../memory",
  "vision_dir": ".../vision",
  "browser_sessions_dir": ".../browser_sessions",
  "temp_dir": ".../temp",
  "resource_dir": "<bundle>/resources",
  "models_dir": ".../models",
  "platform": "windows"
}
```

OS 映射：

| OS | app data 根目录策略 |
|---|---|
| Windows | Tauri app data dir，通常在用户 Roaming / Local app data 下 |
| macOS | Tauri app data dir，通常在用户 Library/Application Support 下 |
| Linux | Tauri app data dir，遵循 XDG data/config 目录 |

旧 `data/` 兼容：

- 开发模式可显式启用 repo-local `data/`，但发布模式禁止。
- 首次发布启动只复制 example/default，不复制真实敏感配置。
- 检测到旧仓库 `data/config/api.yaml` 时，只提示用户导入，不自动复制。
- 符号链接、UNC 路径、相对路径必须 resolve 后校验；无法证明在允许 scope 内则拒绝。

ConfigManager 注入：

- `ConfigManager` 迁移后必须显式接收 `config_dir`。
- 发布模式禁止 `config_dir=None` 回退到项目内 `data/config`。
- 路径测试必须覆盖相对路径、`..`、符号链接、UNC、用户选择外部模型目录。

### 敏感数据策略

`config.get_all` 返回 UI 时：

- API key、authorization、cookie、token 只返回是否已设置和尾部短 mask。
- 本地模型路径默认返回 basename、类别和 hash；完整路径只在用户显式查看时通过 Tauri 安全文件选择上下文展示。
- TTS `prompt_text`、参考音频路径、私有 URL 默认脱敏摘要。
- 浏览器 profile 路径不返回前端。

发布包扫描清单：

- 发现真实 `data/config/api.yaml` 构建失败。
- 发现真实 `data/config/memory.yaml` 构建失败。
- 发现 `data/logs/`、`data/vision/`、`data/browser_sessions/`、`data/memory/`、`data/models/` 构建失败。
- 发现 PySide6 进入最终发布 bundle 构建失败。

### 设置页面 parity 表

| 页面 | 读取 | 脱敏 | dirty | 保存 | 失败回滚 | 广播影响 |
|---|---|---|---|---|---|---|
| API | `config.get_all(scope=api)` | API key、URL 凭据、参考路径摘要 | 页面草稿 | `config.save_api` + confirm | 回滚草稿和内存配置 | LLM/TTS/STT 新请求生效 |
| 系统 | `config.get_all(scope=system)` | proxy 私有地址摘要 | 页面草稿 | `config.save_system` + confirm | 回滚草稿、内存配置、聊天窗投影 | 主题、字体、聊天显示、OCR 设置 |
| 记忆 | `config.get_all(scope=memory)` | 模型完整路径默认摘要 | 路径/开关草稿 | 记忆配置按现有语义保存 | 失败恢复旧模型选择 | 下轮记忆检索生效 |
| Agent | `config.get_all(scope=agent)` | 无敏感字段默认 | 页面草稿 | agent 保存 command | 回滚草稿 | 下轮规划/反思生效 |
| 角色 | `character.*` | 本地路径摘要 | 文件编辑草稿 | 角色保存/同步 command | 恢复旧文件快照 | 当前聊天窗角色资源刷新 |

并发规则：

- 同一页面保存中禁止二次保存。
- 切页时若保存中，必须提示等待或取消；不能静默丢弃。
- sidecar 重启中禁止保存，显示可恢复错误。
- 保存失败必须保留用户草稿和错误详情入口。

### Capability 权限矩阵

| 能力 | 默认 | 确认粒度 | 审计字段 | 特殊约束 |
|---|---|---|---|---|
| 读取配置摘要 | allow | 无 | scope、调用来源 | secrets 脱敏 |
| 保存配置 | confirm | 页面级 | diff 摘要、配置域 | API / 系统分开 |
| 打开 URL | confirm | 每次或域名记忆 | scheme、host hash | 默认只允许 http/https |
| 浏览器自动化 | deny | 每次任务 | URL、动作、权限级别 | profile 隔离 |
| OCR 截图 | confirm | 每次或被动状态配置 | region、文本长度 | 默认显式触发 |
| MCP stdio | deny | server 级 + 每次高风险工具 | command hash、server、tool | command 校验 |
| 插件工具 | deny 外部 / allow 内置 low | 工具级 | plugin、tool、permission | 外部插件低信任 |
| 命令执行 | deny | 每次 | argv 摘要、cwd、env keys | 禁止默认 shell |
| 文件保存 | confirm | 目录级 | path scope、文件类型 | 必须 scope 校验 |

命令执行约束：

- 使用 argv 数组，不使用默认 shell。
- `cwd` 必须在允许目录或用户显式选择目录。
- env 默认清洗，仅保留 allowlist。
- 敏感路径 denylist 包含 `.env`、SSH key、token、浏览器凭据、系统凭据目录。
- MCP stdio command 保存前必须显示风险确认和来源标记。

授权生命周期：

```text
CapabilityGrant
  grant_id
  capability
  scope
  subject: plugin | mcp_server | command | url_origin | directory
  created_at_ms
  expires_at_ms
  max_uses
  used_count
  revoked
  audit_trace_id
```

- `confirm_token` 只能单次使用，绑定 `request_id`、capability、scope 和过期时间。
- token 过期、已使用或 scope 不匹配时返回 `security.confirm_token_invalid`。
- 用户必须能撤销持久授权；撤销后新请求必须重新确认。
- 授权状态持久化只保存 grant 摘要，不保存敏感命令参数全文。
- high 权限默认不允许长期记忆授权；如未来允许，必须有独立配置和明显 UI。

### URL 与浏览器路径安全

URL 规则：

- 导航前规范化 URL。
- 默认只允许 `http` 和 `https`。
- redirect 后必须二次校验 scheme、host、私网地址。
- localhost、私有 IP、内网域名访问需要显式确认或配置开启。
- 禁止默认访问 `file://`。
- 防 DNS rebinding：解析结果进入私网时按私网规则处理。

文件名规则：

- 只允许安全字符集：字母、数字、短横线、下划线、点。
- 禁止绝对路径、驱动器前缀、`..`、路径分隔符。
- 保存前 `resolve()` 并确认位于 app data 或用户选择目录。
- Playwright profile 固定在 app data 隔离目录，清理策略可配置。

### MCP stdio 和插件 worker 状态机

MCP stdio worker：

```text
created
→ starting
→ initializing
→ ready
→ calling
→ ready | failed | closing
→ closed
```

实现要求：

- stdout reader 和 stderr drain 独立线程或 async task。
- writer 有有界队列。
- 首版 MCP stdio 请求默认串行化；如支持并发，必须按 JSON-RPC id 路由响应。
- `connect_timeout_seconds` 作用于 `starting/initializing`。
- `request_timeout_seconds` 作用于单次 `tools/list` 和 `tools/call`。
- stderr 单行和累计缓冲都有上限，超限后写摘要事件。
- close 先发协议关闭或 terminate，超时后 kill 进程树。
- Windows 使用 job object 或等价策略清理子进程树。

插件 worker：

- 外部插件优先子进程隔离。
- stdout/stderr 捕获为插件日志事件，不直通 sidecar stdout。
- 调用超时后终止当前工具调用；无法安全中断时终止 worker。
- worker 崩溃产生 `plugin.worker_crashed`。
- 插件结果进入 ToolRegistry 前做大小限制、摘要和不可信标记。

插件 worker 状态机：

```text
created
→ starting
→ ready
→ calling
→ ready | cancelling | failed
→ closed
```

规则：

- 首版每个外部插件一个 worker；worker 池属于后续优化，不进入首版。
- `calling` 中收到 cancel 进入 `cancelling`，先发送协作取消，超时后终止 worker。
- worker 重启必须生成新 worker id，旧 worker 的迟到 stdout/stderr 只写隔离日志。
- 审计字段最少包含 `plugin_name`、`worker_id`、`tool_name`、`permission`、`request_id`、`trace_id`、耗时和终态。
- worker 崩溃不自动重放工具调用，除非用户显式重试。

### 长任务资源释放矩阵

| 任务 | 取消入口 | 可中断点 | 资源释放 | 迟到结果 | 终态测试 |
|---|---|---|---|---|---|
| LLM | `CancelToken` | stream 迭代、请求超时 | 关闭 HTTP stream 或丢弃迭代 | 只写内部日志 | done/error/cancelled 只一次 |
| TTS | `CancelToken` + 句段队列 | 翻译前、合成前、chunk 读取间隔 | 清理音频句柄、临时文件、队列 | 不播放、不更新 UI | 取消后无新播放事件 |
| STT | `CancelToken` + worker 标记 | 转写前、超时轮询 | 释放 audio handle，必要时丢弃 worker 结果 | 不写输入框 | 超时和取消互斥终态 |
| OCR | `CancelToken` | 识别前、OCR 调用后 | 释放 image handle，按保留策略清理截图 | 不注入 SessionContext | 长 OCR 走句柄 |
| MCP | `CancelToken` + request timeout | 读写等待、进程超时 | 终止请求或关闭 worker，drain stderr | 不触发后续工具 | stderr 洪泛不死锁 |
| 插件 | `CancelToken` + worker timeout | 调用前、worker 超时 | 捕获 stdout/stderr，必要时杀 worker | 结果标记丢弃 | worker 崩溃有事件 |
| 诊断 | `CancelToken` | 每个 check 前后 | 删除未完成导出临时目录 | 不生成成功包 | cancel 后无残留敏感文件 |

强制收口规则：

- faster-whisper / RapidOCR / PaddleOCR 等不可协作阻塞调用先通过 deadline 和迟到结果丢弃保证 UI 释放；如需要硬取消，必须放入可终止 worker 进程。
- TTS HTTP stream 取消时先关闭 response / session；关闭失败时丢弃后续 chunk 并释放句柄。
- MCP 子进程取消超时后终止当前 session；终止失败时 kill 进程树。
- 插件 worker 取消超时后终止 worker；worker 内模型或 GPU 资源由进程退出释放。
- 所有强制收口都必须产生审计日志和 `*.cancelled` 或 `*.error` 终态，不能静默失败。

### Sakura Web 组件矩阵

| 组件 | 必须状态 | 键盘 / 可访问性 | 复用边界 |
|---|---|---|---|
| `Button` | default、hover、active、disabled、loading、danger | Enter / Space、aria-label | 普通动作 |
| `IconButton` | default、hover、active、disabled、busy | tooltip、aria-label 必填 | 工具按钮、发送/停止 |
| `Input` | default、focus、disabled、error、readonly | label 关联、Esc 不误清 | 设置表单、聊天输入 |
| `Select` | closed、open、selected、disabled、error | 方向键、Enter、Esc | 配置选项 |
| `Stepper` / `SpinBox` | default、focus、disabled、error | 加减按钮可键盘操作 | 数值配置 |
| `Toggle` / `Checkbox` | checked、unchecked、disabled、focus | Space 切换、label 关联 | 布尔配置 |
| `Tabs` / `Radio` | selected、hover、disabled、focus | 方向键切换 | 设置子分组 |
| `Slider` | default、dragging、disabled、focus | 方向键调节 | 音量、倍率等连续值 |
| `Modal` | open、closing、danger、loading | focus trap、Esc、aria-modal | 确认和表单 |
| `ConfirmDialog` | normal、danger、loading | focus trap、默认焦点安全 | 二次确认 |
| `Toast` | success、error、warning、info | 不抢焦点 | 非阻塞反馈 |
| `Tooltip` | hover、focus、disabled target | 浅色主题 | 图标解释 |
| `ContextMenu` | open、hover item、disabled item | 方向键、Esc | 右键菜单 |
| `Splitter` | dragging、keyboard resize | aria-valuenow | 日志上下分区 |
| `VirtualLogList` | append、selected、follow-bottom、paused-selection | 可复制文本 | 平台日志 |
| `ChatPanel` | idle、streaming、busy、error、retryable | 输入焦点稳定 | 聊天主面板 |
| `PassiveBubble` | visible、hidden、timeout、clicked | click 恢复主对话 | 被动状态短消息 |
| `SettingsSection` | clean、dirty、saving、error | 标题语义 | 设置分组 |

所有组件必须使用 Sakura tokens，不使用浏览器默认黑色 tooltip/menu，不使用未定义的一次性样式绕过基础组件。

token 映射：

- 背景、边框、文字、强调色、危险色、focus ring 都从 CSS variables 读取。
- 组件尺寸分 `compact`、`regular`、`large` 三档，不用视口宽度缩放字体。
- icon button 必须有稳定宽高和 tooltip。
- 视觉回归 gate 至少覆盖设置页、聊天窗、日志页、弹窗和右键菜单。

### 测试命令矩阵

命令在对应目录落地前作为设计 gate；目录落地后成为阻塞 gate。

| 阶段 | 工作目录 | 命令 | 阻塞 | 覆盖 |
|---|---|---|---|---|
| Phase 1+ | repo root | `python -m pytest tests/rpc_contract/ -q` | 是 | RPC envelope、状态机、取消、stdout 零污染 |
| Phase 1+ | `apps/desktop/src-tauri` | `cargo test` | 是 | sidecar supervisor、RuntimePaths、capability |
| Phase 1+ | `apps/desktop/frontend` | `npm test` | 是 | Pinia stores、typed client、组件状态 |
| Phase 1+ | `apps/desktop` | `npm run e2e:smoke` | 是 | 骨架、聊天最小闭环、日志查看器 |
| Phase 3+ | repo root | `python -m pytest tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_tts_pipeline.py tests/test_stt_adapter.py tests/test_vision.py -q` | 是 | Python Core 主链路 |
| Phase 4+ | repo root | `python -m pytest tests/security/ -q` | 是 | 路径穿越、诊断脱敏、权限边界 |
| Phase 4+ | `apps/desktop` | `npm run e2e:stress` | 是 | 高频日志、慢消费者、TTS chunk、MCP stderr |
| Phase 5 | repo root | `python scripts/check_no_pyside6_in_sidecar.py` | 是 | sidecar 无 PySide6 |
| Phase 5 | repo root | `python scripts/check_release_manifest.py` | 是 | 发布包排除真实运行期数据 |

### pytest 全量迁移映射

| 测试文件 | 迁移归属 |
|---|---|
| `test_agent_manager.py`、`test_agent_log_events.py`、`test_agent_planner.py`、`test_planner_tiered.py`、`test_multi_step.py`、`test_reflector_deep.py`、`test_proactive.py` | Python Core 保留；`test_proactive.py` 迁移为 headless scheduler 测试 |
| `test_agent_page_events.py` | 拆分为 Python RPC event publisher 测试 + Vue Agent 页面 store 测试；旧 Qt 页面测试双跑后删除 |
| `test_llm_adapter.py`、`test_llm_manager_tools.py`、`test_text_processor.py` | Python Core 保留 |
| `test_tts_adapter.py`、`test_tts_pipeline.py` | Python Core 保留；补 RPC/Tauri 播放边界测试 |
| `test_stt_adapter.py` | Python Core 保留 |
| `test_stt_recorder.py`、`test_audio_backends.py` | 迁移到 Tauri/Rust 或 E2E；旧 Qt 测试双跑后删除 |
| `test_vision.py` | Python OCR 保留；截图部分迁移到 Tauri lifecycle |
| `test_memory_ledger.py`、`test_mem0_store.py`、`test_session_*` | Python Core 保留 |
| `test_log_*`、`test_logging_integration.py`、`test_diagnostic_*`、`test_config_health.py`、`test_diagnostic_runner.py` | Python Core 保留并补 RPC 查询/导出测试 |
| `test_config.py`、`test_config_agent.py` | Python Core 保留，迁移 RuntimePaths 覆盖 |
| `test_tool_registry.py`、`test_plugin_system.py`、`test_plugin_import.py`、`test_mcp_host.py`、`test_web_automation*`、`test_system_control.py` | 保留核心逻辑；插件/MCP/命令执行补 worker 和 capability 测试 |
| `test_settings_window.py`、`test_*page.py`、`test_conversation_log_page.py`、`test_system_log_page.py`、`test_diagnostics_page.py`、`test_feedback_toast.py` | Vue page/store/E2E 替代；旧 Qt 测试双跑后删除 |
| `test_chat_*`、`test_chat_window_scale.py`、`test_chat_passive_bubble.py` | 拆分为 Python chat service、Vue chat store、Tauri E2E |
| `test_sprite_manager.py`、`test_startup_appearance.py` | 前端 asset/render 或 Tauri startup smoke 替代 |
| `test_character.py` | Python Core 保留，角色 UI 操作迁移到 Vue 测试 |
| `test_event_bus.py` | Python EventBus 保留；新增 RPC event publisher 测试 |

### PySide6 绑定测试替换清单

| 旧测试 | 替代层 / 命令 | 双跑阶段 | 删除条件 |
|---|---|---|---|
| `test_settings_window.py` | `apps/desktop/frontend npm test` + `apps/desktop npm run e2e:settings` | Phase 2-4 | 设置 parity 连续两个阶段通过 |
| `test_agent_page_events.py` | `tests/rpc_contract/` + Vue Agent store test | Phase 2-4 | RPC event publisher 和 Agent 页面替代测试通过 |
| `test_diagnostics_page.py` | Vue diagnostics page test + `diagnostics.run` RPC contract | Phase 4 | 诊断页 E2E 通过 |
| `test_conversation_log_page.py`、`test_system_log_page.py` | Vue VirtualLogList tests + `npm run e2e:logs-tools` | Phase 4 | 日志压测和选择/滚动 parity 通过 |
| `test_feedback_toast.py` | Sakura `Toast` component unit + visual snapshot | Phase 1-4 | 组件矩阵测试通过 |
| `test_plugin_import.py` | Vue plugin page + plugin worker/capability tests | Phase 4 | 插件导入、权限、stdout 隔离通过 |
| `test_chat_tts_flow.py`、`test_chat_stt_flow.py`、`test_chat_passive_bubble.py`、`test_chat_window_scale.py` | Python ChatService + Vue chatStore + `npm run e2e:chat` | Phase 3-4 | 聊天 parity 连续两个阶段通过 |
| `test_stt_recorder.py` | Tauri/Rust recorder tests + E2E STT smoke | Phase 3-4 | Rust 录音和超时取消通过 |
| `test_audio_backends.py` | Tauri/Rust audio playback tests + TTS E2E | Phase 3-4 | Rust 播放和资源清理通过 |
| `test_sprite_manager.py` | frontend asset/render tests | Phase 3-4 | 立绘渲染 visual gate 通过 |
| `test_startup_appearance.py` | Tauri startup smoke + frontend visual snapshot | Phase 1-4 | Tauri 启动体验通过 |

### PySide6 文件级退场矩阵

| 文件 / 范围 | 分类 | 替代 | 删除 / 退场条件 |
|---|---|---|---|
| `main.py` | 旧入口 | Tauri desktop entry | Phase 5，Tauri 启动 smoke 通过 |
| `ui/settings/**` | 旧 UI 行为参考 | Vue 设置中心 | 设置 parity + E2E 通过 |
| `ui/chat/window.py` | 旧 UI 行为参考 / 业务拆分来源 | Vue ChatPanel + Python ChatService | 聊天 parity + TTS/STT/OCR 通过 |
| `ui/chat/web_view.py` | 迁移到前端 | WebChannel / WebView bridge 替换 | 聊天页面不再依赖 Qt WebEngine |
| `ui/chat/stt_recorder.py` | 迁移到 Tauri | Rust 录音 | STT 录音 E2E 通过 |
| `ui/chat/audio_backends.py` | 迁移到 Tauri | Rust 播放 | TTS 播放 E2E 通过 |
| `ui/chat/sprite.py` | 迁移到前端 | Web asset renderer | 立绘渲染截图验收通过 |
| `ui/theme.py`、`ui/widgets/**`、`ui/text_metrics.py` | 旧 UI 参考 | Sakura Web tokens/components | 组件矩阵测试通过 |
| `ui/chat/templates/**` | 迁移到前端 | Vue chat templates | 聊天页面不再依赖模板脚本 |
| `ui/assets/**` | 迁移到前端 | Web assets | 前端组件可直接消费后删除 |
| `ui/startup/**` | 旧启动窗 | Tauri 启动页 | Tauri startup smoke 通过 |
| `core/ui_event_bridge.py` | 迁入无 Qt event publisher | RPC event publisher | 所有事件不依赖 Qt 后删除 |
| `agent/proactive.py` Qt 基类 | 改造 | headless scheduler | 无 PySide6 import gate 通过 |
| `vision/screen_capture.py` Qt 截图 | 迁移到 Tauri | Rust screenshot | OCR E2E 通过 |
| `requirements.txt` 中 PySide6 | 迁移期旧 UI 依赖 | `requirements-sidecar.txt` 无 PySide6 | Phase 5 发布 gate 删除 |
| PySide6 绑定 tests | 双跑 | 新测试层 | 替代测试连续通过后删除 |

双跑规则：

- Phase 1-3 允许旧 PySide6 和 Tauri 新 UI 并存。
- Phase 4 起新功能只允许进入 Tauri 主线。
- Phase 5 删除旧入口前，保留一个回滚 tag 或备份分支策略，但主线不再保留 PySide6 依赖。

### 阶段命令矩阵

| 阶段 | 工作目录 | 阻塞命令 |
|---|---|---|
| Phase 0 | repo root | 文档复审矩阵全部 90+ |
| Phase 1 | repo root / `apps/desktop/src-tauri` / `apps/desktop/frontend` / `apps/desktop` | `python -m pytest tests/rpc_contract/ -q`; `cargo test`; `npm test`; `npm run e2e:smoke` |
| Phase 2 | repo root / `apps/desktop/src-tauri` / `apps/desktop/frontend` / `apps/desktop` | `python -m pytest tests/test_config.py tests/test_config_agent.py -q`; `cargo test`; `npm test`; `npm run e2e:settings` |
| Phase 3 | repo root / `apps/desktop/src-tauri` / `apps/desktop/frontend` / `apps/desktop` | `python -m pytest tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_tts_pipeline.py tests/test_stt_adapter.py tests/test_vision.py -q`; `cargo test`; `npm test`; `npm run e2e:chat` |
| Phase 4 | repo root / `apps/desktop/src-tauri` / `apps/desktop/frontend` / `apps/desktop` | `python -m pytest tests/test_log_service.py tests/test_mcp_host.py tests/test_tool_registry.py tests/test_diagnostic_bundle.py -q`; `python -m pytest tests/security/ -q`; `cargo test`; `npm test`; `npm run e2e:logs-tools`; `npm run e2e:stress` |
| Phase 5 | repo root / `apps/desktop/src-tauri` / `apps/desktop/frontend` / `apps/desktop` | `python scripts/check_no_pyside6_in_sidecar.py`; `python scripts/check_release_manifest.py`; `python -m pytest tests/ -q`; `cargo test`; `npm test`; `npm run e2e:smoke` |

### 文档入口更新矩阵

| 阶段 | 文档动作 |
|---|---|
| Phase 0 | `docs/README.md` 新增“ Tauri UI 重构”专区，链接本文；`CLAUDE.md` 文档入口加入本文 |
| Phase 1 | `docs/architecture.md` 增加目标三层架构和 RPC Contract 摘要 |
| Phase 2 | `docs/development.md` 增加测试命令矩阵和 RuntimePaths 规则 |
| Phase 3 | `docs/ui-guidelines.md` 增加 Sakura Web 组件规范和聊天窗 Tauri 验收 |
| Phase 4 | 更新 `plugin-mcp.md`、`vision-ocr.md`、`service-tts-compatibility.md` 的 Tauri 边界 |
| Phase 5 | 删除旧 PySide6 主线描述，只保留历史迁移记录或归档链接 |

### 发布包 gate

发布包检查必须生成 manifest：

```text
release_manifest
  app_version
  bundle_size_bytes
  sidecar_size_bytes
  frontend_size_bytes
  resource_size_bytes
  dependency_summary
  forbidden_paths_scan
  pyside6_import_scan
```

建议预算作为首版 gate 候选，实施时可按实测调整但必须配置化：

- 发布包不得包含 `data/models/`、`data/logs/`、`data/vision/`、`data/browser_sessions/`、`data/memory/`。
- sidecar 依赖清单必须来自 `requirements-sidecar.txt`。
- 最终 Phase 5 发布包不得包含 PySide6 wheel、Qt dll、QtWebEngine 或旧 `ui/`。
- bundle size 回归超过既定预算阈值时构建失败或需要显式批准。

### 诊断包 allowlist

诊断包只允许：

- `metadata.json`
- `events.jsonl`
- `manifest.json`
- 配置健康摘要
- 工具审计摘要
- 运行环境摘要

禁止：

- 截图原图。
- 音频。
- 浏览器 profile。
- 模型完整路径。
- API key、cookie、authorization、token。
- 私有 URL path/query。
- 长 OCR 原文。

`include_sensitive=true` 首版不支持。若未来支持，必须单独设计确认、审计和导出水印。

导出后必须运行敏感扫描命令；命中禁止项则导出失败并删除临时包。

## 第三轮复审补强契约

本节处理第三轮 90+ 复审中发现的阻断项。后续实施计划必须把本节拆成可执行任务和测试，不得降级为口头约定。

### Canonical RPC schema

协议字段统一规则：

- 新协议只使用 `request_id` 作为请求、响应、事件、取消、任务快照和日志关联主键。
- `id` 只允许作为旧草稿兼容输入别名；Phase 1 contract test 必须禁止新代码输出 `id`。
- 所有 request / response / event 都必须携带 `protocol_version`、`request_id`、`trace_id`、`parent_trace_id`、`session_id`。
- `parent_trace_id` 在首次请求中为 `null`，在 retry、工具调用、插件 worker、MCP 子进程和 supervisor 派生事件中必须继承。
- `sidecar.cancel` 是唯一取消 method 名称；前端 helper 可以命名为 `cancelTask`，但 wire method 不得变化。
- `timeout` 是错误码语义，不是对外终态；短任务和长任务都只允许 `done`、`error`、`cancelled` 作为终态族。

握手 schema：

```json
{
  "kind": "request",
  "request_id": "req_hello",
  "method": "sidecar.hello",
  "params": {
    "supported_protocol_versions": [1],
    "min_compatible_protocol_version": 1,
    "frontend_version": "0.0.0",
    "tauri_version": "0.0.0",
    "capabilities": ["runtime_paths.v1", "events.v1"]
  },
  "protocol_version": 1,
  "trace_id": "trace_boot",
  "parent_trace_id": null,
  "session_id": "",
  "deadline_ms": 10000
}
```

`sidecar.hello.result` 必须返回：

- `selected_protocol_version`
- `min_compatible_protocol_version`
- `sidecar_version`
- `capabilities`
- `runtime_paths_ready`
- `schema_hash`

兼容策略：

- Rust 和 Python 无共同版本时返回 `rpc.protocol_unsupported`，并进入前端降级页。
- 未知 method 返回 `rpc.method_not_found`。
- 未知必填字段返回 `rpc.invalid_params`。
- 未知可选字段忽略但写入 trace 级调试日志。
- schema hash 不一致时允许启动，但 contract test 必须失败；发布包 gate 必须阻塞。

### 完整首版 method catalog

首版 catalog 按服务域冻结。每个 method 的实施 schema 必须列出字段类型、必填性、默认值、脱敏规则、错误码和事件。

| 域 | Method | 类型 | 最小职责 |
|---|---|---|---|
| sidecar | `sidecar.hello`、`sidecar.health`、`sidecar.shutdown`、`sidecar.cancel`、`sidecar.task_snapshot` | 短任务 | 握手、健康、关闭、取消、按 `request_id` 恢复任务状态 |
| config | `config.get_all`、`config.save_api`、`config.save_system`、`config.save_memory`、`config.save_agent`、`config.save_mcp`、`config.validate` | 短任务 | 脱敏读取、分域保存、校验、失败回滚 |
| character | `character.list`、`character.get`、`character.save`、`character.sync_assets`、`character.delete`、`character.protect_core_files` | 短 / 长任务 | 角色文件、立绘资源、核心文件保护 |
| chat | `chat.send`、`chat.retry`、`chat.proactive_state` | 长任务 / 短任务 | 对话、重试、被动状态投影 |
| proactive | `proactive.start`、`proactive.stop`、`proactive.notify_interaction`、`proactive.update_context` | 短任务 | headless 主动行为调度 |
| speech | `tts.synthesize`、`stt.begin_recording`、`stt.stop_recording`、`stt.transcribe` | 长任务 / 短任务 | TTS 合成、录音、转写；录音停止不是 RPC 任务取消 |
| vision | `ocr.capture`、`ocr.recognize`、`ocr.cleanup` | 长 / 短任务 | Tauri 截图、Python OCR、截图清理 |
| logs | `logs.query`、`logs.subscribe`、`logs.export`、`logs.open_location` | 短 / 长任务 | 日志查询、订阅、导出和受控打开 |
| tools | `tools.list`、`tools.call`、`tools.audit_query` | 短 / 长任务 | 工具目录、工具调用、审计 |
| plugins | `plugins.refresh`、`plugins.enable`、`plugins.disable`、`plugins.import`、`plugins.status` | 长 / 短任务 | 插件扫描、导入、状态、权限 |
| mcp | `mcp.list_servers`、`mcp.save_server`、`mcp.refresh`、`mcp.call_tool`、`mcp.stop_server` | 长 / 短任务 | MCP 配置、连接、工具调用、关闭 |
| security | `security.confirm_required`、`security.approve`、`security.deny`、`security.revoke_grant`、`security.list_grants` | 事件 / 短任务 | 权限确认、拒绝、撤销、授权列表 |
| diagnostics | `diagnostics.run`、`diagnostics.export`、`diagnostics.open_report` | 长 / 短任务 | 诊断运行、脱敏导出、受控打开报告 |
| handles | `handles.read_range`、`handles.read_page`、`handles.release`、`handles.stat` | 短任务 | 大内容分页、范围读取、释放 |

每个保存类 method 必须满足：

- `params` 包含 `draft`、`base_version`、`confirm_token`。
- `result` 包含 `applied_version`、`changed_scopes`、`redacted_snapshot`。
- 写入前校验 `deadline_ms` 和 `confirm_token`。
- 写入失败回滚内存态，保留前端草稿。

逐 method schema 矩阵：

| Method | 长任务 | Params 最小字段 | Result / accepted | 事件 | 错误码族 | 敏感字段规则 |
|---|---|---|---|---|---|---|
| `sidecar.hello` | 否 | supported versions、capabilities、frontend_version | selected version、capabilities、schema_hash | 无 | `rpc.*`、`sidecar.*` | 不含敏感信息 |
| `sidecar.health` | 否 | `include_tasks` | status、active_task_count、uptime_ms | 无 | `sidecar.*` | task 仅摘要 |
| `sidecar.shutdown` | 否 | reason、deadline_ms | accepted_shutdown | `sidecar.exiting` | `sidecar.*` | reason 脱敏 |
| `sidecar.cancel` | 否 | target `request_id`、reason | terminal_state 或 accepted_cancel | 目标任务终态 | `rpc.*`、domain timeout/cancel | reason 脱敏 |
| `sidecar.task_snapshot` | 否 | target `request_id` | task_state、last_sequence、terminal_summary | 无 | `rpc.*`、`sidecar.*` | 只返回摘要 |
| `config.get_all` | 否 | scope | redacted_snapshot、version | 无 | `config.*` | secrets mask |
| `config.save_api` | 否 | draft、base_version、confirm_token | applied_version、redacted_snapshot | `config.changed` | `config.*`、`security.*` | API key 不回显 |
| `config.save_system` | 否 | draft、base_version、confirm_token | applied_version、changed_scopes | `config.changed`、`chat.config_applied` | `config.*`、`security.*` | proxy / path 摘要 |
| `config.save_memory` | 否 | draft、base_version、confirm_token | applied_version、redacted_snapshot | `config.changed` | `config.*`、`filesystem.*` | 模型路径默认 basename/hash |
| `config.save_agent` | 否 | draft、base_version、confirm_token | applied_version、redacted_snapshot | `config.changed` | `config.*` | prompt / policy 摘要 |
| `config.save_mcp` | 否 | draft、base_version、confirm_token | applied_version、server_summary | `mcp.config_changed` | `config.*`、`security.*` | command/env 脱敏 |
| `config.validate` | 否 | scope、draft | validation_result | 无 | `config.*` | 不落盘 secrets |
| `character.list` | 否 | include_disabled | items | 无 | `filesystem.*` | 路径摘要 |
| `character.get` | 否 | character_id | redacted_character | 无 | `filesystem.*` | 本地路径摘要 |
| `character.save` | 否 | draft、base_version、confirm_token | applied_version、asset_summary | `character.changed` | `config.*`、`filesystem.*`、`security.*` | 文件正文按 scope 校验 |
| `character.sync_assets` | 是 | character_id、asset_handles | accepted | `character.assets_progress/done/error/cancelled` | `filesystem.*` | handle 不暴露真实路径 |
| `character.delete` | 否 | character_id、confirm_token | deleted / protected | `character.changed` | `security.*`、`filesystem.*` | 核心文件拒绝 |
| `character.protect_core_files` | 否 | character_id | protection_summary | 无 | `security.*` | 无 |
| `chat.send` | 是 | text、session_id、visual_handle? | accepted | `chat.started/delta/done/error/cancelled` | `chat.*`、`llm.*`、`tool.*` | 长文本可走 handle |
| `chat.retry` | 是 | source_request_id、retry_policy | accepted | 同 `chat.send` | `chat.*` | 保留 parent_trace_id |
| `chat.proactive_state` | 否 | passive_state、window_visible、last_interaction_ms | accepted_state | `chat.proactive_state_changed` | `chat.*` | 只传运行态摘要 |
| `proactive.start` | 否 | policy_version | started | `proactive.status` | `chat.*` | 无 |
| `proactive.stop` | 否 | reason | stopped | `proactive.status` | `chat.*` | reason 脱敏 |
| `proactive.notify_interaction` | 否 | interaction_type、timestamp_ms | accepted | 无 | `chat.*` | 不传正文 |
| `proactive.update_context` | 否 | character_summary、visual_summary_handle? | accepted | `proactive.context_updated` | `chat.*`、`filesystem.*` | OCR 摘要或 handle |
| `tts.synthesize` | 是 | text、voice_config_ref、session_id | accepted | `tts.started/segment/done/error/cancelled` | `tts.*` | prompt / path 脱敏 |
| `stt.begin_recording` | 是 | device_hint、timeout_ms | accepted | `stt.recording/progress/error/cancelled` | `stt.*` | 音频仅 handle |
| `stt.stop_recording` | 否 | recording_request_id | audio_handle / no_audio | `stt.recording_stopped` | `stt.*` | 不传 PCM |
| `stt.transcribe` | 是 | audio_handle、language、timeout_ms | accepted | `stt.started/progress/done/error/cancelled` | `stt.*` | audio_handle scoped |
| `ocr.capture` | 是 | region、reason、confirm_token? | accepted | `ocr.capture_done/error/cancelled` | `ocr.*`、`security.*` | image_handle scoped |
| `ocr.recognize` | 是 | image_handle、region、max_text_chars | accepted | `ocr.started/done/error/cancelled` | `ocr.*` | 长 OCR 走 handle |
| `ocr.cleanup` | 否 | policy | cleanup_summary | 无 | `filesystem.*` | 只删受控目录 |
| `logs.query` | 否 | channel、cursor、limit、filters | items、next_cursor | 无 | `filesystem.*` | details 脱敏 |
| `logs.subscribe` | 是 | channel、filters、cursor | accepted | `log.batch/done/error/cancelled` | `rpc.*`、`filesystem.*` | 批量脱敏 |
| `logs.export` | 是 | channel、filters、format、confirm_token? | accepted | `log.export_progress/done/error/cancelled` | `filesystem.*`、`security.*` | 输出走 allowlist |
| `logs.open_location` | 否 | handle_id 或 report_id | opened | 无 | `filesystem.*`、`security.*` | 禁止任意路径 |
| `tools.list` | 否 | include_disabled | items | 无 | `tool.*` | 参数 schema 脱敏 |
| `tools.call` | 视工具 | tool_name、source、arguments、confirm_token? | accepted 或 result | `tool.started/result/error/cancelled` | `tool.*`、`security.*` | argv/env/cwd 摘要 |
| `tools.audit_query` | 否 | cursor、limit、filters | items、next_cursor | 无 | `tool.*` | 审计脱敏 |
| `plugins.refresh` | 是 | filters | accepted | `plugin.status/done/error/cancelled` | `plugin.*` | stdout/stderr 摘要 |
| `plugins.enable` | 否 | plugin_id、confirm_token | enabled | `plugin.status` | `plugin.*`、`security.*` | plugin path scoped |
| `plugins.disable` | 否 | plugin_id | disabled | `plugin.status` | `plugin.*` | 无 |
| `plugins.import` | 是 | package_handle、confirm_token | accepted | `plugin.import_progress/done/error/cancelled` | `plugin.*`、`security.*`、`filesystem.*` | 包内容不信任 |
| `plugins.status` | 否 | plugin_id? | status list | 无 | `plugin.*` | stdout 摘要 |
| `mcp.list_servers` | 否 | include_disabled | servers | 无 | `mcp.*` | command/env 摘要 |
| `mcp.save_server` | 否 | draft、base_version、confirm_token | applied_version、server_summary | `mcp.config_changed` | `mcp.*`、`security.*` | env/secrets 脱敏 |
| `mcp.refresh` | 是 | server_id? | accepted | `mcp.status/done/error/cancelled` | `mcp.*` | stderr 摘要 |
| `mcp.call_tool` | 是 | server_id、tool_name、arguments、confirm_token? | accepted 或 result | `mcp.tool_started/done/error/cancelled` | `mcp.*`、`security.*` | arguments 脱敏 |
| `mcp.stop_server` | 否 | server_id、reason | stopped | `mcp.status` | `mcp.*` | reason 脱敏 |
| `security.approve` | 否 | confirmation_id、confirm_token | approved | `security.approved` | `security.*` | token 不落日志 |
| `security.deny` | 否 | confirmation_id、reason | denied | `security.denied` | `security.*` | reason 脱敏 |
| `security.revoke_grant` | 否 | grant_id | revoked | `security.grant_revoked` | `security.*` | grant 摘要 |
| `security.list_grants` | 否 | filters | grants | 无 | `security.*` | 只返回授权摘要 |
| `diagnostics.run` | 是 | checks、include_sensitive=false | accepted | `diagnostic.progress/done/error/cancelled` | `diagnostics.*`、`security.*` | 首版禁止敏感导出 |
| `diagnostics.export` | 是 | report_handle、format | accepted | `diagnostic.export_progress/done/error/cancelled` | `diagnostics.*`、`filesystem.*` | allowlist + scan |
| `diagnostics.open_report` | 否 | report_id | opened | 无 | `filesystem.*`、`security.*` | 仅受控报告 |
| `handles.read_range` | 否 | handle_id、start、length | bytes / text chunk | 无 | `filesystem.*` | scope 校验 |
| `handles.read_page` | 否 | handle_id、page_token、limit | page、next_token | 无 | `filesystem.*` | 内容按 handle policy 脱敏 |
| `handles.release` | 否 | handle_id | released | 无 | `filesystem.*` | 无 |
| `handles.stat` | 否 | handle_id | kind、byte_length、expires_at_ms | 无 | `filesystem.*` | 不返回真实路径 |

`tools.call` 的 params 必须使用：

```text
tool_name: string
source: builtin | plugin | mcp
arguments: object
confirm_token?: string
dry_run?: boolean
```

命令类工具参数必须使用 `argv: string[]`；禁止默认 `shell=true`。旧 `system_control.command` 在迁移期只能通过 shim 转为 argv，无法转换时拒绝并返回 `security.shell_command_denied`。

### 最小错误码字典

错误对象统一为：

```text
code: string
message: string
user_message: string
retryable: boolean
details: redacted object
```

首版必须至少覆盖：

| 错误码 | retryable | 语义 |
|---|---|---|
| `rpc.invalid_frame` | 否 | stdout frame 非法或超限 |
| `rpc.invalid_params` | 否 | 参数类型、必填字段或取值非法 |
| `rpc.method_not_found` | 否 | method 未注册 |
| `rpc.protocol_unsupported` | 否 | 协议版本无交集 |
| `rpc.request_timeout` | 是 | request deadline 到达 |
| `rpc.duplicate_terminal` | 否 | 收到重复终态 |
| `rpc.event_out_of_order` | 否 | 事件 sequence 乱序 |
| `sidecar.not_ready` | 是 | sidecar 未完成初始化 |
| `sidecar.restarted` | 是 | sidecar 崩溃或重启导致任务失败 |
| `sidecar.shutdown_timeout` | 是 | 优雅关闭超时 |
| `config.version_conflict` | 是 | 保存基线版本过旧 |
| `config.validation_failed` | 否 | 配置校验失败 |
| `config.write_failed` | 是 | 配置写入失败且已回滚 |
| `chat.cancelled` | 是 | 用户取消对话 |
| `chat.context_unavailable` | 是 | 会话上下文不可用 |
| `llm.timeout` | 是 | LLM 超时 |
| `tts.timeout` | 是 | TTS 超时 |
| `stt.timeout` | 是 | STT 超时 |
| `ocr.timeout` | 是 | OCR 超时 |
| `plugin.worker_crashed` | 是 | 插件 worker 崩溃 |
| `mcp.server_unavailable` | 是 | MCP server 不可用 |
| `tool.confirm_required` | 否 | 工具调用需要确认 |
| `tool.execution_failed` | 视工具 | 工具执行失败 |
| `security.confirm_token_invalid` | 否 | 确认 token 过期、已用或 scope 不匹配 |
| `security.permission_denied` | 否 | 权限被拒绝 |
| `security.shell_command_denied` | 否 | shell 命令被禁止 |
| `filesystem.path_out_of_scope` | 否 | 路径不在允许 scope |
| `filesystem.handle_expired` | 是 | 句柄过期 |

新增错误码必须归属现有域；新增域需要同步 typed client、Rust enum、Python enum 和诊断脱敏规则。

### Headless facade 闭环

Python Core 首版 facade 必须覆盖：

```text
ChatService
SpeechService
VisionService
ConfigService
CharacterService
LogService
DiagnosticService
ToolService
PluginService
McpService
SecurityConfirmationService
ProactiveService
```

新增 facade 职责：

| Service | 必须方法 | 迁移约束 |
|---|---|---|
| `ConfigService` | `save_memory`、`save_agent`、`save_mcp`、`validate` | 使用 `RuntimePaths`，保存失败回滚内存态 |
| `CharacterService` | `list/get/save/sync_assets/delete/protect_core_files` | 核心文件保护必须在 Python 和 Tauri 两侧都有校验 |
| `LogService` | `query/subscribe/export/open_location` | 查询脱敏，导出走诊断 allowlist |
| `DiagnosticService` | `run/export/cancel` | 临时目录失败即清理，导出后敏感扫描 |
| `SecurityConfirmationService` | `request/approve/deny/revoke/list_grants` | confirm token 单次使用、可撤销、可审计 |
| `ProactiveService` | `start/stop/notify_interaction/update_context/set_passive_state` | 不依赖 Qt Signal，事件走 `RpcEventPublisher` |

`ProactiveScheduler` shim：

| 旧接口 | 新入口 | 规则 |
|---|---|---|
| `start()` | `proactive.start` | sidecar ready 后启动，重复调用幂等 |
| `stop()` | `proactive.stop` | shutdown 前必须等待调度线程退出 |
| `notify_interaction()` | `proactive.notify_interaction` | 刷新空闲计时和 can_fire 输入 |
| `register_trigger()` | `ProactiveService` 内部注册 | trigger 不持有 UI 对象 |
| `set_character_context()` | `proactive.update_context` | 仅传角色摘要和资源 handle |
| `set_visual_context()` | `proactive.update_context` | 仅传脱敏 OCR 摘要和 handle |
| `proactive_message` Signal | `chat.proactive` event | 由 `RpcEventPublisher` 发布，前端按 `request_id` 处理 |

`can_fire` 由前端运行态投影和 Python 策略共同决定：前端提供窗口可见性、被动状态、用户最近交互；Python 判断冷却、角色策略、上下文可用性。任一侧不可用时禁止主动发言。

工具确认协议：

```text
ToolRegistry.call(context, tool_name, args)
→ SecurityConfirmationService.evaluate(...)
→ 低风险 allow 或发布 security.confirm_required event
→ Vue 显示 ConfirmDialog
→ Tauri security.approve / security.deny
→ Python 恢复工具调用或返回 security.permission_denied
```

确认状态机：

```text
created
→ pending_user
→ approved | denied | expired | cancelled
```

- pending 中原工具调用必须挂起，但保留 request deadline。
- approve/deny 必须携带 `confirm_token` 和 `request_id`。
- sidecar 重启时所有 pending confirmation 进入 `cancelled`，前端显示可重试。
- confirm 事件、批准、拒绝和撤销必须写审计日志。

### Frontend store lifecycle 完整表

| Store | init | dispose | sidecar restart | 事件 owner | 持久化 |
|---|---|---|---|---|---|
| `appStore` | app mounted | app exit | 标记 degraded，广播 reset | app root | 启动偏好摘要 |
| `windowStore` | window created | window closed | 保留窗口偏好，清运行态 | window root | 窗口位置、缩放、置顶 |
| `themeStore` | app mounted | app exit | 重新应用 token | app root | 主题名、字体、倍率 |
| `configStore` | settings mounted | settings unmounted | 清 saving，保留草稿并标记需重载 | settings page | 不持久化配置正文 |
| `chatStore` | chat window opened | chat window closed | pending request 全部转 `sidecar.restarted` | chat window | 不持久化消息流式草稿 |
| `audioStore` | chat window opened | chat window closed | 停止播放投影，清队列状态 | chat window | 不持久化音频状态 |
| `sttStore` | recorder button mounted | chat window closed | 录音/识别置为 failed 可重试 | chat window | 不持久化录音状态 |
| `logStore` | log page visible | log page hidden | 退订后可重新 query | log page | 筛选、列宽、follow 偏好 |
| `toolStore` | tools page visible | page hidden | 清 running，保留目录摘要 | tools page | 授权摘要 id、筛选 |
| `diagnosticStore` | diagnostics page visible | page hidden 或导出完成 | running 转 failed(sidecar.restarted)，清 report handle，保留摘要 | diagnostics page | 仅诊断选项偏好，不保存报告路径 |
| `characterStore` | character page or chat opened | owner closed | 资源状态置 stale | page/window owner | 最近角色 id、非敏感偏好 |

生命周期规则：

- 每个 store 必须有 `init()`、`dispose()`、`resetOnSidecarRestart()`。
- 事件订阅必须由 owner 管理，重复 init 先执行 idempotent guard，不产生重复订阅。
- HMR / dev reload 必须执行 dispose 或由 typed client 清理全部 unsubscribe。
- 窗口关闭后的迟到事件只能进入日志，不更新已销毁窗口 store。
- 终态事件只由 owning store 处理一次；派生 store 不写终态。

### Frontend persistence allowlist

| Store | storage key | 字段 | 默认值 / 迁移 | 禁止字段 |
|---|---|---|---|---|
| `windowStore` | `yumetsuki.window.v1` | 位置、尺寸、缩放、置顶、透明偏好 | schema version 自动迁移 | request、句柄、截图路径 |
| `themeStore` | `yumetsuki.theme.v1` | 主题名、字体族、字号倍率 | 缺失时用 Sakura 默认 | token 临时覆盖、运行态错误 |
| `logStore` | `yumetsuki.logs.v1` | channel、source、level、follow-bottom、列宽 | 不兼容时清空 | 日志正文、详情、trace 全量 |
| `toolStore` | `yumetsuki.tools.v1` | grant_id 摘要、筛选、展开状态 | grant 不存在时丢弃 | 命令全文、env、cwd、token |
| `diagnosticStore` | `yumetsuki.diagnostics.v1` | 最近 check 选择、导出格式偏好 | 不兼容时清空 | 诊断包路径、日志正文、敏感扫描命中内容 |
| `characterStore` | `yumetsuki.character.v1` | 最近角色 id、显示偏好 | 角色不存在时回默认 | 角色文件正文、完整本地路径 |

全局禁止持久化：API key 原文、authorization、cookie、完整模型路径、截图路径、长 OCR 原文、工具命令全文、运行中 request、音频 / STT 临时状态、浏览器 profile 路径、诊断包路径。

### 完整设置与诊断 UI parity

| 页面 | 状态 | 主要动作 | 失败 / 回滚 | E2E 验收 |
|---|---|---|---|---|
| API | clean/dirty/saving/error | 读取、保存、测试连接 | 保存失败保留草稿 | 脱敏、确认、失败回滚 |
| 角色 | loading/dirty/syncing/error | 列表、编辑、同步资源、保护删除 | 核心文件拒绝删除 | 资源刷新和保护弹窗 |
| 记忆 | clean/dirty/saving/error | 开关、模型选择、保存 | 模型不可用回滚选择 | 下轮检索生效 |
| Agent | clean/dirty/saving/error | 规划/反思/主动行为保存 | 保存失败恢复旧策略 | 主动行为配置生效 |
| 插件 | loading/empty/scanning/error/permission-required | 扫描、导入、启用、禁用 | stdout 污染隔离 | 导入反馈、权限确认 |
| MCP | disconnected/connecting/ready/error | 新增、编辑、诊断、刷新工具 | 超时显示可重试 | 连接诊断和 stderr 洪泛 |
| 对话日志 | loading/empty/ready/filtering/error | 查询、筛选、导出、复制 | 导出失败保留筛选 | 拖选暂停、详情稳定 |
| 平台日志 | streaming/paused/filtering/error | 订阅、筛选、打开详情、导出 | 慢消费者降级可见 | 10k 日志不卡交互 |
| 系统 | clean/dirty/saving/error | 外观、OCR、网络、被动状态保存 | 回滚聊天窗投影 | 保存广播和失败回滚 |
| 诊断 | idle/running/cancelling/failed/exported/redaction-failed | 运行、取消、导出、打开报告、复制摘要 | 敏感扫描失败删除临时包 | 脱敏失败阻塞导出 |

页面 view model 必须显式绑定 store、RPC method、事件、toast/dialog 和 E2E 用例。诊断页的 `redaction-failed` 不能提供“仍然导出”按钮。

### Accessibility gate

前端 UI gate 必须覆盖：

- 文本和交互控件对比度不低于 WCAG AA。
- 全局键盘路径覆盖主窗口、聊天输入、设置页导航、日志筛选、确认弹窗和诊断页。
- Modal / ConfirmDialog 使用 focus trap，关闭后恢复触发控件焦点。
- Toast 不抢焦点，但通过 `aria-live="polite"` 暴露状态。
- 错误、状态条、诊断进度使用节流后的 live region；流式回复不逐 token 朗读。
- 支持 `prefers-reduced-motion`，动态效果提供降级。
- `npm test` 或 E2E 必须包含 axe 或等价 a11y 检查，至少覆盖聊天、设置、日志、诊断和确认弹窗。

### Tauri capability manifest 契约

Tauri 权限必须先由 capability manifest 收口，再进入 Rust command 内部校验。

| 窗口 / scope | 允许 command | 默认禁用 |
|---|---|---|
| main window | `sidecar_*`、`config_*`、`chat_*`、`logs_*`、`diagnostics_*` | 任意 shell、任意 file system、任意 URL open |
| pet window | `window_drag`、`window_scale`、`chat_send`、`sidecar_cancel` | 配置写入、插件导入、MCP 修改 |
| settings window | `config_*`、`character_*`、`plugins_*`、`mcp_*`、`security_*` | 录音、截图、任意命令 |
| diagnostics view | `diagnostics_*`、`logs_query`、`logs_export` | 未脱敏文件读取 |

manifest scan 必须检查：

- command 未出现在任何 capability 时构建失败。
- 新增 command 没有安全分类时构建失败。
- 默认 Tauri 插件权限不得宽开；文件、shell、opener、http、clipboard 等按最小 scope 配置。
- 文件 scope 必须来自 `RuntimePaths` 或用户选择目录。
- URL scope 默认只允许 `http/https` 并经过二次校验。

### Startup / shutdown / recovery 状态机

启动状态：

```text
frontend_loaded
→ sidecar_starting
→ handshake
→ ready | degraded | failed
```

规则：

- `sidecar_starting` 超过预算进入 `degraded`，UI 只允许打开日志、设置和重试。
- `handshake` 失败分为协议不兼容、RuntimePaths 失败、Python import 失败和 stdout 污染。
- 部分初始化失败时，必须返回 capability 降级列表；不可用功能在 UI 中禁用并给出日志入口。

关闭顺序：

```text
block_new_requests
→ cancel_or_drain_long_tasks
→ release_handles
→ flush_logs
→ stop_plugin_mcp_workers
→ sidecar.shutdown
→ kill_after_deadline
→ frontend_dispose
```

恢复规则：

- sidecar 崩溃后 Rust 标记所有 pending request 为 `error(sidecar.restarted)`。
- 各 store 执行 `resetOnSidecarRestart()`，保留可恢复草稿和非敏感偏好。
- 插件 worker、MCP server 和临时句柄不自动重放；用户显式重试才重新执行。
- 关闭超时、kill 进程树和日志 flush 失败都必须写入审计日志。

### 性能预算

首版预算作为发布 gate 候选，实施后按真实机器基线配置化。

| 项 | 预算候选 | 测量命令 / 场景 |
|---|---|---|
| 前端首屏到 shell ready | 冷启动 3s 内，热启动 1.5s 内 | `npm run e2e:startup` |
| sidecar hello | 10s 内返回或进入 degraded | Tauri lifecycle test |
| sidecar 常驻内存 | 基线后 500 MiB 内，模型加载另计 | diagnostics perf check |
| 空闲 CPU | 2% 以下持续 60s | diagnostics perf check |
| 聊天首字延迟 | mock 300ms 内，真实 LLM 单独记录 | `npm run e2e:chat` |
| TTS 首段可播 | mock 500ms 内，真实服务单独记录 | TTS smoke |
| 10k 平台日志 | 滚动、筛选、详情 30 FPS 以上 | `npm run e2e:stress` |
| 透明窗口渲染 | 拖拽和缩放无明显掉帧 | visual smoke |
| OCR 单次识别 | 默认超时内返回摘要或 timeout | OCR contract |
| 发布包体积 | manifest 记录并设回归阈值 | `check_release_manifest.py` |

### Packaging strategy

可重复打包必须冻结：

- Python 版本来源和 `requirements-sidecar.txt`。
- Node / pnpm 或 npm 版本来源。
- Rust toolchain 来源。
- Tauri sidecar 构建方式和资源目录。
- native DLL / wheel / onnxruntime / faster-whisper / Playwright browser 策略。
- Windows 干净机 smoke：安装包启动、sidecar hello、日志打开、设置读取、聊天 mock、关闭清理。
- 依赖升级必须先更新 lock、运行发布包扫描和 smoke，再进入主线。

发布扫描输入：

- Tauri bundle 目录。
- `resources/` 和 sidecar 目录。
- Python 依赖摘要。
- 前端 `dist/`。
- 配置示例文件。
- 诊断导出样本。

发布扫描失败条件：

- 命中 PySide6 wheel、Qt DLL、QtWebEngine、旧 `ui/` 运行时代码。
- 命中真实 `data/config/*.yaml`、日志、截图、浏览器 profile、记忆库、模型缓存。
- 命中 `.env`、SSH key、token、cookie、authorization、私有 URL path/query。
- bundle size 或 sidecar size 超出配置阈值且无显式批准记录。

### 测试与文档冻结补强

每个阶段合并前必须运行：

```text
python -m pytest tests/ -q
```

阶段内可使用聚焦测试做开发循环，但不能替代阶段出口全量 Python 回归。

测试文件覆盖规则：

- Phase 0 生成或维护 `tests/test_*.py` 文件级映射清单。
- 任何未被迁移表覆盖的测试文件使 Phase 0 / Phase 5 gate 失败。
- 任何直接导入 PySide6 的测试文件必须列出替代层、替代命令、双跑阶段、删除条件和回滚方式。

新增 PySide6 绑定测试替换项：

| 旧测试 | 替代层 / 命令 | 双跑阶段 | 删除条件 |
|---|---|---|---|
| `test_logging_integration.py` | Python LogService + RPC logs contract | Phase 2-4 | 日志查询、订阅、导出 contract 通过 |
| `test_event_bus.py` | Python EventBus + RPC event publisher | Phase 1-4 | Qt bridge 不再参与事件发布 |
| `test_proactive.py` | `ProactiveService` headless scheduler tests | Phase 3-4 | 主动行为无 Qt Signal 且 shutdown wait 通过 |
| `test_plugin_import.py` | plugin worker + Vue plugin page E2E | Phase 4 | 导入、权限、stdout 隔离通过 |

文档冻结规则：

- `docs/README.md` 和 `CLAUDE.md` 必须显式链接本文，并标注“当前实现仍为 PySide6，目标架构为 Tauri，实施尚未开始”。
- `docs/architecture.md`、`docs/development.md`、`docs/ui-guidelines.md` 在实施阶段再改为目标架构细节；Phase 0 只加入口和状态，避免误写成已落地。
- 设计稿定稿前不得删除旧 PySide6 文档描述；只能增加目标架构提示和迁移入口。

## 复审映射

| 低分项 | 本文覆盖章节 |
|---|---|
| RPC 状态机不足 | RPC Contract v1 |
| 高频事件无背压 | 事件流背压、发布前压力矩阵 |
| ID 传播不足 | ID 传播 |
| 取消语义不足 | 取消语义、长任务状态机 |
| Pinia store 缺失 | Frontend Architecture |
| Sakura Web 缺失 | Sakura Web 组件体系 |
| sidecar 生命周期缺失 | Sidecar Supervisor |
| app data 缺失 | RuntimePaths |
| stdout 污染 | stdout / stderr 纪律 |
| Qt 依赖未剥离 | Python Core Headless 化 |
| MCP / 插件治理不足 | MCP 与插件治理 |
| 安全权限不足 | Desktop Capability 与安全边界 |
| 测试 gate 缺失 | 测试 Gate |
| PySide6 退场缺失 | PySide6 退场计划 |
| RPC method schema 不足 | RPC method catalog |
| 大内容句柄不足 | 协议版本和句柄协议 |
| 状态机非法转移不足 | 状态转移表 |
| ID 上下文传播不足 | RpcContext 传播契约 |
| RuntimePaths schema 不足 | RuntimePaths schema |
| 权限矩阵不足 | Capability 权限矩阵 |
| Sakura 组件矩阵不足 | Sakura Web 组件矩阵 |
| 测试命令不可执行 | 测试命令矩阵、阶段命令矩阵 |
| RPC canonical 字段冲突 | Canonical RPC schema |
| method catalog 不完整 | 完整首版 method catalog |
| 错误码不可执行 | 最小错误码字典 |
| Python facade 覆盖不足 | Headless facade 闭环 |
| 工具确认链路不足 | Headless facade 闭环 |
| Pinia lifecycle / persistence 不足 | Frontend store lifecycle 完整表、Frontend persistence allowlist |
| 设置 / 日志 / 诊断 UI parity 不足 | 完整设置与诊断 UI parity |
| 可访问性不足 | Accessibility gate |
| Tauri capability manifest 不足 | Tauri capability manifest 契约 |
| 启动关闭恢复不足 | Startup / shutdown / recovery 状态机 |
| 性能预算不足 | 性能预算 |
| 打包可维护性不足 | Packaging strategy |
| 测试和文档入口冻结不足 | 测试与文档冻结补强 |

## 自检

- 本文已通过 90+ 复审，进入实施计划前仍需以这里的 gate 为准。
- 每个第二轮复审低分项都有对应补强章节。
- 关键数值只作为建议默认值或配置项候选，不作为永久硬编码。
- PySide6 完全移除被定义为发布 gate，而不是口头目标。
- 高风险权限、路径、诊断和插件/MCP 内容均按不可信输入处理。
