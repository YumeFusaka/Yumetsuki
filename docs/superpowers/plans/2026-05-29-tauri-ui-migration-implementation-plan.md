# Tauri UI 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 状态：已通过 90+ 并行复审，已确认进入实施；当前处于 Phase 0 计划冻结与基线。本文同时记录实施 gate 的真实结果。

**Goal:** 按已定稿的 Tauri UI 重构设计，把现有 PySide6 UI 分阶段迁移为 Tauri + Vue3 组合式 + Pinia + TypeScript，并在全部迁移完成后移除 PySide6。

**Architecture:** 新 UI 由 `apps/desktop/frontend` 承担界面、交互和状态投影，`apps/desktop/src-tauri` 承担桌面能力、权限、窗口和 Python sidecar supervisor，`python_core` 承担 headless AI 业务内核。所有 UI 到 Python 的业务通信必须经过 `Vue typed client -> Tauri invoke/events -> Python stdio RPC`，取消统一走 `sidecar.cancel(request_id)`。

**Tech Stack:** Tauri 2、Rust、Vue3 Composition API、Pinia、TypeScript、Vite、Vitest、Playwright、Python 3、pytest、现有 Agent / LLM / TTS / STT / OCR / 插件 / MCP 模块。

---

## 设计来源

本计划严格执行已定稿设计：

- `docs/superpowers/specs/2026-05-28-tauri-ui-migration-design.md`
- `CLAUDE.md`
- `docs/README.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/ui-guidelines.md`
- `docs/tauri-ui-parity.md`

硬约束：

- 不使用 axios 作为桌面主通信链路。
- 前端不直连 Python，不拼 sidecar 原始协议帧。
- Python sidecar 不导入 PySide6，不向 stdout 输出非协议文本。
- 每个 Vue / Tauri 页面或组件设计、实现前必须先读取对应 `ui/` 旧实现文件，并产出旧 UI 对照摘要。
- Tauri UI 必须完整保留旧 PySide6 UI 的入口、层级、分组、控件项、菜单 / 弹窗、状态语义和功能链路；样式允许 Web 化，但不得自由重构结构或遗漏功能项。
- 截图只作为辅助参考；结构和功能验收以 `ui/` 源码对照、结构 parity 清单和测试为准。
- 前端包管理器固定使用 `pnpm`，不得在迁移计划和命令中改用 npm / yarn。
- 长任务只返回 `accepted`，后续状态只走事件流。
- 取消 wire method 只有 `sidecar.cancel`。
- 每阶段合并前必须运行 `python -m pytest tests/ -q`。
- Phase 5 前不得删除旧 PySide6 UI；Phase 5 完成后必须删除 PySide6 依赖、旧 `ui/` 主实现和旧文档入口。

## 执行策略

- 先建新边界，再迁移功能，不做大规模一次性搬迁。
- 每个 Phase 必须保持项目可运行、可测试。
- 每个 Task 完成后先跑聚焦验证，再跑该 Phase 出口验证。
- 涉及提交和推送时，执行者先确认工作区只包含本任务相关变更；提交信息使用中文。
- 如果执行中发现已有用户改动，不能回滚；必须先读懂并在其基础上继续。
- 如果发现设计与代码事实冲突，暂停当前 Task，更新计划或设计补充后再实施。

## 目标目录与职责

### 新增目录

- Create: `apps/desktop/frontend/`
  - Vue3 + Pinia + TypeScript UI 工程。
  - 只保存非敏感 UI 偏好和运行态投影。
  - 不读取真实配置文件、日志、截图、模型路径或浏览器 profile。
- Create: `apps/desktop/package.json`
  - 统一承载 `e2e:startup`、`e2e:smoke`、`e2e:settings`、`e2e:chat`、`e2e:logs-tools`、`e2e:stress`、`e2e:responsive`、`test:a11y` 脚本。
  - 所有 E2E 命令都从 `apps/desktop` 执行，避免脚本落点歧义。
- Create: `apps/desktop/e2e/`
  - Playwright E2E、a11y、启动性能和压力测试。
- Create: `apps/desktop/src-tauri/`
  - Tauri shell、窗口、托盘、桌面能力、capability、Rust command、sidecar supervisor。
  - 负责 `RuntimePaths`、权限确认、受控文件/URL 打开、sidecar 生命周期和事件桥。
- Create: `apps/desktop/src-tauri/capabilities/`
  - Tauri capability manifest，按窗口和 command scope 收口权限。
- Create: `python_core/`
  - Python headless sidecar 入口、RPC 协议、服务 facade、任务注册表和事件发布器。
  - 迁移期复用现有 `agent/`、`llm/`、`tts/`、`stt/`、`vision/`、`core/`、`config/`、`session/`、`memory/`。
- Create: `python_core/resources/`
  - 统一管理 audio/image/text/file/json handle、TTL、取消清理、sidecar shutdown 清理。
- Create: `tests/rpc_contract/`
  - Python sidecar 协议、状态机、错误码、stdout 零污染和 schema 契约测试。
- Create: `tests/security/`
  - 路径 scope、URL 安全、诊断脱敏、capability manifest、发布包扫描测试。
- Create: `tests/migration/`
  - 测试库存、PySide6 绑定测试替换表、文件级退场检查。
- Create: `scripts/check_test_inventory.py`
  - 比对 `rg --files tests -g 'test_*.py'` 与 `tests/migration/test_inventory.md`，发现缺失或多余即失败。
- Create: `scripts/check_no_pyside6_in_sidecar.py`
  - Phase 5 检查 sidecar 可达路径没有 PySide6 import。
- Create: `scripts/check_no_stdout_in_sidecar.py`
  - 扫描 sidecar 可达路径中的 `print()`、`sys.stdout.write()`，防止 stdout 污染协议。
- Create: `schemas/release_manifest.schema.json`
  - Phase 5 固化发布 manifest JSON schema，供脚本和测试复用。
- Create: `scripts/check_release_manifest.py`
  - Phase 5 检查发布包 manifest、敏感数据、PySide6/Qt 残留和体积预算。
- Create: `scripts/check_release_reproducibility.py`
  - Phase 5 检查发布 artifact、lockfile、toolchain、schema hash 和 manifest 可复现性。
- Create: `scripts/check_final_capabilities_match_build.py`
  - Phase 5 检查最终 `tauri build` 使用的 capability 文件与安全审核输入完全一致。
- Create: `scripts/check_docs_no_stale_ui_status.py`
  - Phase 5 全量扫描文档入口中的过期 PySide6 主线描述，并内置迁移归档 allowlist。
- Create: `scripts/run_no_pyside6_sidecar_smoke.ps1`
  - 在隔离 venv 中只安装 `requirements-sidecar.txt`，验证 sidecar 不依赖 PySide6。
- Create: `scripts/smoke_windows_clean_machine.ps1`
  - 在无仓库、无开发环境、无 PySide6 的 Windows 干净机或等价沙箱中验证安装包。

### 迁移期保留目录

- Keep: `ui/`
  - Phase 1-4 仅作为旧行为参考和双跑回归对象。
  - Phase 5 删除或归档旧主实现。
- Keep: `main.py`
  - Phase 1-4 保留旧入口。
  - Phase 5 从主线入口退场。
- Keep: `requirements.txt`
  - Phase 1-4 允许保留 PySide6 以支持旧 UI 双跑。
  - Phase 5 拆出 `requirements-sidecar.txt` 并从最终 sidecar 依赖中移除 PySide6。

## Phase 0：计划冻结与基线

**目标:** 把实施计划、测试映射和执行基线冻结，保证后续任务不会误删 PySide6 旧行为，也不会遗漏测试迁移。

**Files:**
- Modify: `docs/superpowers/plans/2026-05-29-tauri-ui-migration-implementation-plan.md`
- Modify: `docs/README.md`
- Modify: `CLAUDE.md`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `docs/ui-guidelines.md`
- Create: `tests/migration/test_inventory.md`
- Create: `tests/migration/replacement_status.json`
- Create: `scripts/check_test_inventory.py`
- Create: `scripts/check_pyside6_test_replacement.py`
- Create: `scripts/check_replacement_status.py`

### Task 0.1：冻结测试文件级映射

- [x] **Step 1: 生成当前测试文件清单**

Run:

```powershell
rg --files tests -g 'test_*.py' | Sort-Object
```

Expected:

```text
输出当前所有测试文件路径。顶层 `tests/test_*.py` 作为迁移前 legacy 清单，嵌套目录测试作为新增迁移测试清单。
```

- [x] **Step 2: 创建迁移测试清单**

Create: `tests/migration/test_inventory.md`

内容必须包含：

```markdown
# UI 重构测试迁移清单

> 状态：Phase 0 基线。新增或删除测试文件时必须同步更新本文。
>
> 口径：
> - `tests/test_*.py` 是迁移前 legacy 顶层 pytest 清单，必须在 `Python Core 保留`、`Tauri / Vue 替换`、`Headless 同名改写` 三个互斥分类中出现一次。
> - `tests/rpc_contract/test_*.py`、`tests/security/test_*.py`、`tests/migration/test_*.py`、`tests/perf/test_*.py`、`tests/release/test_*.py` 是新增迁移测试，必须登记在“新增迁移测试清单”。
> - Phase 5 删除旧测试后，已删除 legacy 测试移入“已退场旧测试”，不得从历史映射中消失。

## Python Core 保留

- `tests/test_agent_manager.py`
- `tests/test_agent_log_events.py`
- `tests/test_agent_planner.py`
- `tests/test_planner_tiered.py`
- `tests/test_multi_step.py`
- `tests/test_reflector_deep.py`
- `tests/test_llm_adapter.py`
- `tests/test_llm_manager_tools.py`
- `tests/test_text_processor.py`
- `tests/test_tts_adapter.py`
- `tests/test_tts_pipeline.py`
- `tests/test_stt_adapter.py`
- `tests/test_vision.py`
- `tests/test_memory_ledger.py`
- `tests/test_mem0_store.py`
- `tests/test_session_context.py`
- `tests/test_session_store.py`
- `tests/test_log_sanitizer.py`
- `tests/test_log_service.py`
- `tests/test_diagnostic_bundle.py`
- `tests/test_diagnostic_runner.py`
- `tests/test_config_health.py`
- `tests/test_config.py`
- `tests/test_config_agent.py`
- `tests/test_tool_registry.py`
- `tests/test_plugin_system.py`
- `tests/test_mcp_host.py`
- `tests/test_web_automation.py`
- `tests/test_web_automation_session.py`
- `tests/test_system_control.py`
- `tests/test_character.py`

## Tauri / Vue 替换

- `tests/test_settings_window.py`
- `tests/test_agent_page_events.py`
- `tests/test_diagnostics_page.py`
- `tests/test_conversation_log_page.py`
- `tests/test_system_log_page.py`
- `tests/test_feedback_toast.py`
- `tests/test_plugin_import.py`
- `tests/test_chat_tts_flow.py`
- `tests/test_chat_stt_flow.py`
- `tests/test_chat_passive_bubble.py`
- `tests/test_chat_window_scale.py`
- `tests/test_stt_recorder.py`
- `tests/test_audio_backends.py`
- `tests/test_sprite_manager.py`
- `tests/test_startup_appearance.py`

## Headless 同名改写

- `tests/test_logging_integration.py`
- `tests/test_event_bus.py`
- `tests/test_proactive.py`

## Gate

- Phase 1-4 允许旧 PySide6 测试和新 Tauri/Vue 测试双跑。
- Phase 5 删除 PySide6 前，本文中每个“替换”测试必须有新测试文件和命令。
- “Headless 同名改写”测试必须保留原文件名，但测试内容改为不导入 PySide6 / Qt。
- 任何未在本文 legacy 分类出现的顶层 `tests/test_*.py` 都使 Phase 0 / Phase 5 gate 失败。
- 任何未在“新增迁移测试清单”登记的嵌套目录 `test_*.py` 都使 Phase 1-5 gate 失败。
- 同一测试文件不得同时出现在 `Python Core 保留`、`Tauri / Vue 替换`、`Headless 同名改写` 三个互斥分类。

## 新增迁移测试清单

### RPC contract

- `tests/rpc_contract/test_envelope.py`
- `tests/rpc_contract/test_errors.py`
- `tests/rpc_contract/test_error_catalog.py`
- `tests/rpc_contract/test_framing.py`
- `tests/rpc_contract/test_method_catalog.py`
- `tests/rpc_contract/test_registry_matches_catalog.py`
- `tests/rpc_contract/test_protocol_negotiation.py`
- `tests/rpc_contract/test_runtime_paths_schema.py`
- `tests/rpc_contract/test_runtime_paths.py`
- `tests/rpc_contract/test_sidecar_smoke.py`
- `tests/rpc_contract/test_stdout_zero_pollution.py`
- `tests/rpc_contract/test_shutdown_coordinator.py`
- `tests/rpc_contract/test_no_stdout_static.py`
- `tests/rpc_contract/test_no_pyside6_import_static.py`
- `tests/rpc_contract/test_sidecar_import_graph_no_qt.py`
- `tests/rpc_contract/test_task_state_machine.py`
- `tests/rpc_contract/test_event_backpressure.py`
- `tests/rpc_contract/test_event_publisher.py`
- `tests/rpc_contract/test_handles.py`
- `tests/rpc_contract/test_handle_registry_security.py`
- `tests/rpc_contract/test_shutdown_process_tree.py`
- `tests/rpc_contract/test_config_methods.py`
- `tests/rpc_contract/test_character_methods.py`
- `tests/rpc_contract/test_chat_methods.py`
- `tests/rpc_contract/test_speech_vision_methods.py`
- `tests/rpc_contract/test_logs_diagnostics_methods.py`
- `tests/rpc_contract/test_tools_plugins_mcp_methods.py`
- `tests/rpc_contract/test_worker_stdio_capture.py`

### Security / release / perf / migration

- `tests/security/test_capability_manifest.py`
- `tests/security/test_url_path_safety.py`
- `tests/security/test_diagnostic_redaction.py`
- `tests/security/test_tool_confirmation.py`
- `tests/security/test_release_manifest.py`
- `tests/security/test_release_forbidden_content.py`
- `tests/security/test_release_reproducibility.py`
- `tests/perf/test_perf_budgets.py`
- `tests/release/test_windows_clean_machine_smoke.py`
- `tests/migration/test_no_pyside6_environment_smoke.py`

## 已退场旧测试

> Phase 5 删除 legacy 测试时，把旧文件路径、替代文件和删除提交记录到本节。

## PySide6 绑定测试替换表

| 旧测试 | Qt / PySide6 依赖点 | 退场动作 | 替代层 | 新测试文件 / 命令 | 双跑阶段 | 删除条件 | 回滚方式 |
|---|---|---|---|---|---|---|---|
| `tests/test_settings_window.py` | 设置窗口和 Qt 控件 | 删除 | Vue 设置页 + ConfigService | `apps/desktop/e2e/settings.spec.ts`、`apps/desktop/frontend/src/pages/settings/*.spec.ts`、`pnpm run e2e:settings` | Phase 2-4 | replacement status 记录连续两个阶段通过 | 保留旧测试文件并恢复 PySide6 依赖 |
| `tests/test_agent_page_events.py` | Qt Agent 页事件桥 | 删除 | RPC event publisher + Vue Agent store | `tests/rpc_contract/test_event_publisher.py`、`python -m pytest tests/rpc_contract/test_event_publisher.py -q`、`pnpm test` | Phase 2-4 | replacement status 记录连续两个阶段通过 | 恢复 `core/ui_event_bridge.py` 双跑 |
| `tests/test_diagnostics_page.py` | Qt 诊断页 | 删除 | Vue diagnostics page + DiagnosticService | `apps/desktop/e2e/logs-tools.spec.ts`、`tests/rpc_contract/test_logs_diagnostics_methods.py`、`pnpm run e2e:logs-tools` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧诊断页测试 |
| `tests/test_conversation_log_page.py` | Qt 对话日志页 | 删除 | Vue ConversationLogPage + LogService | `apps/desktop/e2e/logs-tools.spec.ts`、`pnpm run e2e:logs-tools` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧日志页测试 |
| `tests/test_system_log_page.py` | Qt 平台日志页 | 删除 | Vue SystemLogPage + VirtualLogList | `apps/desktop/e2e/stress.spec.ts`、`pnpm run e2e:stress` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧日志页测试 |
| `tests/test_feedback_toast.py` | Qt toast | 删除 | Sakura Toast | `apps/desktop/e2e/a11y.spec.ts`、`pnpm test`、`pnpm run test:a11y` | Phase 1-4 | replacement status 记录连续两个阶段通过 | 恢复旧 toast 测试 |
| `tests/test_plugin_import.py` | Qt 插件导入 UI | 删除 | Vue PluginPage + PluginService | `apps/desktop/e2e/logs-tools.spec.ts`、`tests/rpc_contract/test_tools_plugins_mcp_methods.py`、`pnpm run e2e:logs-tools` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧插件导入测试 |
| `tests/test_chat_tts_flow.py` | Qt ChatWindow + TTS 播放 | 删除 | ChatService + SpeechService + Rust audio | `apps/desktop/e2e/chat.spec.ts`、`tests/rpc_contract/test_speech_vision_methods.py`、`pnpm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧聊天 TTS 测试 |
| `tests/test_chat_stt_flow.py` | Qt ChatWindow + STT 录音 | 删除 | Rust recorder + SpeechService | `apps/desktop/e2e/chat.spec.ts`、`apps/desktop/src-tauri/tests/media_contract.rs`、`pnpm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧聊天 STT 测试 |
| `tests/test_chat_passive_bubble.py` | Qt 被动气泡 | 删除 | Vue PassiveBubble + chatStore | `apps/desktop/e2e/chat.spec.ts`、`pnpm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧被动气泡测试 |
| `tests/test_chat_window_scale.py` | Qt 窗口缩放 | 删除 | Tauri window + Vue ChatPanel | `apps/desktop/e2e/chat.spec.ts`、`pnpm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧窗口缩放测试 |
| `tests/test_stt_recorder.py` | Qt 录音 | 删除 | Rust recorder | `apps/desktop/src-tauri/tests/media_contract.rs`、`cargo test --test media_contract` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧录音测试 |
| `tests/test_audio_backends.py` | Qt 音频播放 | 删除 | Rust audio playback | `apps/desktop/src-tauri/tests/media_contract.rs`、`cargo test --test media_contract` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧音频后端测试 |
| `tests/test_sprite_manager.py` | Qt pixmap / 立绘 | 删除 | Vue SpriteView | `apps/desktop/e2e/chat.spec.ts`、`pnpm test`、`pnpm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧立绘测试 |
| `tests/test_startup_appearance.py` | Qt 启动窗 | 删除 | Tauri startup view | `apps/desktop/e2e/startup.spec.ts`、`pnpm run e2e:startup` | Phase 1-4 | replacement status 记录连续两个阶段通过 | 恢复旧启动窗测试 |
| `tests/test_logging_integration.py` | UI 日志桥和 Qt 页面消费 | 同名改写 | Python LogService + RPC logs contract + Vue 日志页 | `tests/test_logging_integration.py`、`tests/rpc_contract/test_logs_diagnostics_methods.py`、`pnpm run e2e:logs-tools` | Phase 2-4 | 同名测试不导入 Qt，replacement status 记录连续两个阶段通过 | 恢复旧日志集成测试 |
| `tests/test_event_bus.py` | `core/ui_event_bridge.py` 路径 | 同名改写 | Python EventBus + RpcEventPublisher | `tests/test_event_bus.py`、`tests/rpc_contract/test_event_publisher.py` | Phase 1-4 | 同名测试不导入 `core/ui_event_bridge.py`、PySide6 或 Qt bridge，replacement status 记录连续两个阶段通过 | 恢复旧 bridge 双跑 |
| `tests/test_proactive.py` | `QObject/QThread/Signal` scheduler | 同名改写 | ProactiveService headless scheduler | `tests/test_proactive.py`、`tests/rpc_contract/test_chat_methods.py` | Phase 3-4 | 同名测试不导入 Qt，replacement status 记录连续两个阶段通过 | 恢复旧 proactive scheduler |
```

- [x] **Step 3: 运行文档扫描**

Run:

```powershell
$patterns = @('T' + 'BD', 'TO' + 'DO', '待' + '定', 'place' + 'holder')
Select-String -Path 'tests/migration/test_inventory.md','docs/superpowers/plans/2026-05-29-tauri-ui-migration-implementation-plan.md' -Pattern $patterns
```

Expected:

```text
无输出。
```

- [x] **Step 4: 创建测试库存检查脚本**

Create: `scripts/check_test_inventory.py`

实现要求：

- 读取 `rg --files tests -g 'test_*.py'` 的实际测试文件。
- 顶层 `tests/test_*.py` 必须与 legacy 三个互斥分类加“已退场旧测试”的记录一致。
- 嵌套目录测试必须与“新增迁移测试清单”一致。
- 任何实际测试既不在 legacy 分类、也不在新增迁移测试清单、也不在已退场旧测试记录中时失败。
- 多余或缺失任一文件时退出码为 1，并打印差异。
- 检查 `tests/migration/test_inventory.md` 中测试文件不得出现在多个互斥分类。
- 检查每个替换表条目的新测试文件至少有一个真实文件路径，或命令被对应 Phase 出口 gate 覆盖。
- Phase 5 删除旧测试后，检查替代覆盖 `settings`、`chat`、`logs`、`plugins`、`mcp`、`diagnostics`、`startup`、`event bridge` 八类能力。

- [x] **Step 5: 创建 PySide6 测试替换扫描脚本**

Create: `scripts/check_pyside6_test_replacement.py`

实现要求：

- 扫描 `tests/test_*.py` 中的 `PySide6|QApplication|QObject|QThread|Signal|qtbot|QWidget|QPixmap`。
- 每个命中文件必须出现在 PySide6 绑定测试替换表，且 `退场动作` 为 `删除` 或 `同名改写`。
- Phase 5 后命中 `同名改写` 文件必须不再包含上述 Qt 关键字。
- 任一漏项或冲突分类退出码为 1。

- [x] **Step 6: 创建替换状态记录和检查脚本**

Create: `tests/migration/replacement_status.json`

内容结构必须包含：

```json
{
  "items": [
    {
      "legacy_test": "tests/test_settings_window.py",
      "replacement_tests": ["apps/desktop/e2e/settings.spec.ts"],
      "retirement_action": "delete",
      "phase_pass_records": [],
      "delete_approved": false
    }
  ]
}
```

Create: `scripts/check_replacement_status.py`

实现要求：

- 每个替换表条目都必须出现在 `replacement_status.json`。
- Phase 5 删除前，每个条目必须有两个连续 Phase 的通过记录，记录包含 phase、command、date、result_summary。
- Phase 1-4 每个出口 gate 必须运行 `python scripts/check_replacement_status.py --phase N --record-from-last-run`，把本阶段新替代测试通过记录写入 `replacement_status.json`。
- `--record-from-last-run` 只记录本阶段出口命令中真实执行并通过的替代命令，不允许手写空记录。
- `--record-from-last-run` 必须读取结构化 run report 或 command hash，记录命令、退出码、测试摘要、schema hash、执行时间和阶段；不得用人工摘要冒充真实执行结果。
- `--phase 5 --record-from-last-run --pre-delete` 必须记录 Phase 5 删除前替代测试结果，特别覆盖双跑阶段只从 Phase 4 开始的日志、诊断、插件、MCP 项。
- `--phase 5 --pre-delete` 必须在删除旧 UI 前运行，确认 replacement status 已满足删除条件。
- `delete_approved` 只能在连续两个阶段记录满足、Phase 5 pre-delete gate 通过、且用户确认删除范围后由脚本或文档化步骤改为 `true`；手写跳过验证无效。
- `delete_approved=false` 时禁止删除旧测试。
- 同名改写条目必须保留旧文件名，但通过 Qt 关键字扫描。

- [x] **Step 7: 运行测试库存检查**

Run:

```powershell
python scripts/check_test_inventory.py
python scripts/check_pyside6_test_replacement.py
python scripts/check_replacement_status.py --phase 0
```

Expected:

```text
输出 tests inventory ok，退出码为 0。
```

### Task 0.2：冻结执行入口文档

- [x] **Step 1: 更新入口状态**

Modify:

- `docs/README.md`
- `CLAUDE.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/ui-guidelines.md`

要求：

- 标注设计已定稿。
- 标注实施计划路径。
- 标注代码迁移尚未开始。
- 标注当前主 UI 仍为 PySide6。
- `docs/architecture.md`、`docs/development.md`、`docs/ui-guidelines.md` 只增加 Tauri UI 重构入口和状态，不把目标架构写成已落地。

- [x] **Step 2: 验证入口**

Run:

```powershell
Select-String -Path 'docs/README.md','CLAUDE.md','docs/architecture.md','docs/development.md','docs/ui-guidelines.md' -Pattern 'Tauri UI 重构|设计已定稿|实施计划|尚未实施'
```

Expected:

```text
五个入口文档都能命中状态、设计入口或实施计划入口。
```

### Task 0.3：迁移前全量基线验证

- [x] **Step 1: 运行旧 PySide6 主线全量 pytest**

Run:

```powershell
python -m pytest tests/ -q
```

Expected:

```text
全量 pytest 通过，作为迁移前基线。
```

- [x] **Step 2: 记录 Phase 0 基线结果**

Modify: `docs/superpowers/plans/2026-05-29-tauri-ui-migration-implementation-plan.md`

要求：

- 在本文“Phase 0 基线结果”小节记录运行日期、命令和结果摘要。
- 失败时不得进入 Phase 1；必须先修复或明确标记为迁移前既有问题。

### Phase 0 基线结果

- 运行日期：2026-05-30
- 工作区：`.worktrees/tauri-ui-phase0`
- 分支：`tauri-ui-phase0`
- `rg --files tests -g 'test_*.py' | Sort-Object`：通过，已生成当前测试文件清单。
- 文档占位扫描：通过，`tests/migration/test_inventory.md` 与本计划未命中 `TBD`、`TODO`、`待定`、`placeholder`。
- `python scripts/check_test_inventory.py`：通过，输出 `tests inventory ok`。
- `python scripts/check_pyside6_test_replacement.py`：通过，输出 `pyside6 test replacement ok (17 legacy Qt-bound tests)`。
- `python scripts/check_replacement_status.py --phase 0`：通过，输出 `replacement status ok`。
- 入口文档扫描：通过，`docs/README.md`、`CLAUDE.md`、`docs/architecture.md`、`docs/development.md`、`docs/ui-guidelines.md` 均命中 Tauri UI 重构状态、设计入口或实施计划入口。
- `python -m py_compile scripts\check_test_inventory.py scripts\check_pyside6_test_replacement.py scripts\check_replacement_status.py`：通过。
- 聚焦 Python 测试：`python -m pytest tests/test_config.py tests/test_log_service.py -q` 通过，`33 passed in 0.48s`。
- 全量旧 PySide6 主线基线：本会话中 `python -m pytest tests/ -q` 首次 120 秒超时，第二次 300 秒超时；`python -m pytest tests/ -vv -x` 120 秒超时且无摘要。2026-05-30 用户反馈：同一实施计划在其他会话回档前已执行并确认 Phase 0 通过，因此本次 Phase 0 出口按用户确认的外部基线结果判定为通过，可以进入 Phase 1。该结论不得改写为“本会话全量 pytest 已通过”。

## Phase 1：骨架、协议和最小闭环

**目标:** 建立 Tauri / Vue / Python sidecar 三层骨架、RPC Contract v1、RuntimePaths、最小聊天 mock 和日志查看器，形成可运行的新 UI 主链路。

**强制执行顺序:** `Task 1.1A -> Task 1.1 -> Task 1.1B -> Task 1.2 -> Task 1.2A -> Task 1.3 -> Task 1.3A -> Task 1.4A -> Task 1.4 -> Task 1.5`。任务标题在文档中的物理顺序不代表执行顺序；执行者必须按本行顺序推进。Phase 2-4 只能实现已冻结 catalog 的 handler，不允许临时发明 wire 字段、错误码或取消入口。

### Task 1.1：创建 Python RPC contract 和测试

**Files:**
- Create: `python_core/__init__.py`
- Create: `python_core/rpc/__init__.py`
- Create: `python_core/rpc/schema/catalog.json`
- Create: `python_core/rpc/schema/schema_hash.py`
- Create: `python_core/rpc/schema/validate.py`
- Create: `python_core/rpc/envelope.py`
- Create: `python_core/rpc/errors.py`
- Create: `python_core/rpc/context.py`
- Create: `python_core/rpc/framing.py`
- Create: `tests/rpc_contract/test_envelope.py`
- Create: `tests/rpc_contract/test_errors.py`
- Create: `tests/rpc_contract/test_error_catalog.py`
- Create: `tests/rpc_contract/test_framing.py`
- Create: `tests/rpc_contract/test_method_catalog.py`
- Create: `tests/rpc_contract/test_protocol_negotiation.py`
- Create: `apps/desktop/src-tauri/tests/error_codes.rs`
- Create: `apps/desktop/frontend/src/client/errorCodes.spec.ts`
- Create: `apps/desktop/frontend/src/client/errorCodes.ts`
- Create: `apps/desktop/src-tauri/src/error_codes.rs`

- [x] **Step 1: 写 envelope 失败测试**

Create: `tests/rpc_contract/test_envelope.py`

Test coverage:

- request / response / event 都必须包含 `protocol_version`、`request_id`、`trace_id`、`parent_trace_id`、`session_id`。
- request canonical 字段必须包含 `kind="request"`、`method`、`params`、`deadline_ms`；缺任一字段失败。
- response canonical 字段必须包含 `kind="response"`、`ok`、`result`、`error`；`ok=true` 时 `error=null`，`ok=false` 时 `result=null`。
- event canonical 字段必须包含 `kind="event"`、`type`、`sequence`、`timestamp_ms`、`payload`；同一 request 内 `sequence` 必须递增。
- `RpcError` canonical 字段必须包含 `code`、`message`、`user_message`、`retryable`、`details`；`details` 必须通过脱敏策略校验后才能进入 response 或 event。
- envelope 测试必须使用表驱动样例覆盖合法 request、合法成功 response、合法错误 response、合法 event、缺字段、字段类型错误和 details 未脱敏。
- 新协议输出中不能出现 `id`。
- `timeout` 不允许作为终态。
- 长任务终态只允许 `done`、`error`、`cancelled`。

Run:

```powershell
python -m pytest tests/rpc_contract/test_envelope.py -q
```

Expected:

```text
失败，提示 python_core.rpc.envelope 尚不存在。
```

- [x] **Step 2: 实现最小 envelope 类型**

Create: `python_core/rpc/envelope.py`

实现要求：

- `RequestEnvelope`
- `ResponseEnvelope`
- `EventEnvelope`
- `RpcError`
- `TerminalState = Literal["done", "error", "cancelled"]`
- `validate_no_legacy_id(payload: dict) -> None`
- `validate_request_envelope(payload: dict) -> RequestEnvelope`
- `validate_response_envelope(payload: dict) -> ResponseEnvelope`
- `validate_event_envelope(payload: dict) -> EventEnvelope`
- `validate_rpc_error(payload: dict) -> RpcError`
- response validator 必须强制 `ok/result/error` 互斥规则。
- event validator 必须强制 `type`、`sequence`、`timestamp_ms`、`payload` 存在。
- error validator 必须调用 redaction validator，拒绝 API key、authorization、cookie、token、个人路径和私有 URL 原文进入 `details`。

- [x] **Step 3: 写错误码测试**

Create: `tests/rpc_contract/test_errors.py`

Test coverage:

- `rpc.protocol_unsupported`
- `rpc.method_not_found`
- `rpc.invalid_params`
- `rpc.invalid_frame`
- `rpc.request_timeout`
- `rpc.duplicate_terminal`
- `rpc.event_out_of_order`
- `rpc.payload_too_large`
- `sidecar.not_ready`
- `sidecar.restarted`
- `sidecar.task_not_found`
- `sidecar.shutdown_timeout`
- `security.confirm_token_invalid`
- `filesystem.path_out_of_scope`
- `config.version_conflict`
- `config.validation_failed`
- `plugin.worker_crashed`
- `mcp.server_unavailable`
- 每个错误都含 `message`、`user_message`、`retryable`、`details`、`redaction_policy`。

- [x] **Step 4: 实现错误码字典**

Create: `python_core/rpc/errors.py`

实现要求：

- 定义 `RpcErrorCode` 常量或 enum。
- 定义 `make_error(code, message, retryable, details)`。
- 一次性定义设计稿“最小错误码字典”全集，覆盖 `rpc.*`、`sidecar.*`、`config.*`、`character.*`、`chat.*`、`llm.*`、`tool.*`、`plugin.*`、`mcp.*`、`tts.*`、`stt.*`、`ocr.*`、`logs.*`、`diagnostics.*`、`security.*`、`filesystem.*`。
- 不在错误 details 中保留 API key、cookie、authorization、token。

- [x] **Step 5: 写 error catalog 映射测试**

Create: `tests/rpc_contract/test_error_catalog.py`

Test coverage:

- `catalog.json` 中出现的每个错误码或错误码族都能映射到 `errors.py`。
- `errors.py` 中每个错误码都有 `message`、`user_message`、`retryable`、`details_schema`、`redaction_policy`。
- Rust `RpcErrorCode` 和 TS `RpcErrorCode` union 与 Python 错误码集合一致。
- 未知错误码禁止进入 response / event。

Create:

- `apps/desktop/src-tauri/tests/error_codes.rs`
- `apps/desktop/frontend/src/client/errorCodes.spec.ts`

- [x] **Step 6: 写 framing 测试**

Create: `tests/rpc_contract/test_framing.py`

Test coverage:

- NDJSON 每行一个 UTF-8 JSON frame。
- stdout 非 JSON 行返回 `rpc.invalid_frame`。
- 单 frame 超限返回 `rpc.invalid_frame` 或转句柄策略错误。

- [x] **Step 7: 实现 framing**

Create: `python_core/rpc/framing.py`

实现要求：

- `encode_frame(payload: dict) -> bytes`
- `decode_frame(line: bytes) -> dict`
- 默认最大 frame 256 KiB，可通过参数覆盖。

- [x] **Step 8: 验证**

Run:

```powershell
python -m pytest tests/rpc_contract/test_envelope.py tests/rpc_contract/test_errors.py tests/rpc_contract/test_error_catalog.py tests/rpc_contract/test_framing.py -q
Set-Location E:/Project/Yumetsuki/apps/desktop/src-tauri
cargo test --test error_codes
Set-Location ..
pnpm test -- errorCodes
```

Expected:

```text
tests/rpc_contract/ 全部通过。
```

#### Task 1.1 验证结果

- 运行日期：2026-05-30
- `python -m pytest tests/rpc_contract/test_envelope.py tests/rpc_contract/test_errors.py tests/rpc_contract/test_error_catalog.py tests/rpc_contract/test_framing.py -q`：通过，`18 passed in 0.23s`。
- `python scripts/check_rpc_schema_contract.py`：通过，输出 `rpc schema contract ok (60 methods, schema_hash=ee71fbdbf2a94a2696a62b696641ed75265c31adc0f34ffcfd69270b9e3a60a9)`。
- `cargo test --test error_codes`：通过，`2 passed`。
- `pnpm test -- errorCodes`：通过，输出 `frontend catalog ok (60 methods, 32 events)` 和 `frontend error codes ok (34 codes)`。

### Task 1.2：实现 Python sidecar 最小入口

**Files:**
- Create: `python_core/sidecar_main.py`
- Create: `python_core/runtime_paths.py`
- Create: `python_core/rpc/registry.py`
- Create: `python_core/rpc/shutdown.py`
- Test: `tests/rpc_contract/test_sidecar_smoke.py`
- Test: `tests/rpc_contract/test_stdout_zero_pollution.py`
- Test: `tests/rpc_contract/test_shutdown_coordinator.py`

- [x] **Step 1: 写 sidecar smoke 测试**

Create: `tests/rpc_contract/test_sidecar_smoke.py`

Test coverage:

- `sidecar.hello` 返回 selected protocol、capabilities、schema_hash。
- `sidecar.health` 返回 status 和 uptime。
- `sidecar.shutdown` 返回 accepted_shutdown。
- `sidecar.cancel` 对未知 request 固定返回结构化 `sidecar.task_not_found`，不得返回 `rpc.method_not_found`。
- sidecar 导入路径不创建 `QApplication`。
- sidecar 启动时把普通 `print()` 重定向到 stderr。
- stdout 只包含协议帧。

- [x] **Step 2: 实现 RuntimePaths**

Create: `python_core/runtime_paths.py`

实现要求：

- `RuntimePaths` dataclass 覆盖 `app_data_dir`、`config_dir`、`log_dir`、`memory_dir`、`vision_dir`、`browser_sessions_dir`、`temp_dir`、`resource_dir`、`models_dir`、`platform`。
- 发布模式不允许回退仓库内 `data/config`。
- 所有路径进入服务前 `resolve()`。

- [x] **Step 3: 实现 method registry**

Create: `python_core/rpc/registry.py`

实现要求：

- 从 `python_core/rpc/schema/catalog.json` 加载完整首版 method catalog。
- 所有 catalog method 都必须注册 handler；业务未迁移的 method 注册 stub handler，返回结构化 `sidecar.not_ready`，不得返回 `rpc.method_not_found`。
- 未出现在 catalog 的 method 返回 `rpc.method_not_found`。
- 参数错误返回 `rpc.invalid_params`。

- [x] **Step 4: 实现 sidecar_main**

Create: `python_core/sidecar_main.py`

实现要求：

- 从 stdin 读取 NDJSON request。
- stdout 只输出协议 frame。
- 非协议日志写 stderr。
- 启动后重定向 `builtins.print` 或 stdout helper 到 stderr，防止第三方 adapter 污染协议 stdout。
- 支持 `--stdio` 和 `--runtime-paths-json`。

- [x] **Step 5: 写 stdout 零污染测试**

Create: `tests/rpc_contract/test_stdout_zero_pollution.py`

Test coverage:

- sidecar 子进程执行测试 handler，handler 内调用 `print("debug")`。
- 真实 sidecar 子进程执行 `sidecar.hello`、`config.get_all`、TTS fake adapter、插件 fake worker、MCP fake server。
- fake worker 向 stdout/stderr 输出非 JSON、大输出和洪泛输出，sidecar stdout 每行仍能被 `decode_frame()` 解析。
- `tts/adapters/gptsovits.py` 的 `print()` 在 Phase 1 或 Phase 3 前置任务中迁移为 stderr logger，不允许等到 Phase 5。
- 插件 stdout 和 MCP stdout/stderr 洪泛不阻塞 sidecar stdout reader。
- stdout 每一行都能被 `decode_frame()` 解析。
- sidecar stderr 脱敏测试必须覆盖 adapter `print()` 输出 API token、个人路径、私有 URL、authorization header；stderr 允许诊断日志但不允许未脱敏敏感内容。

- [x] **Step 6: 写 shutdown coordinator 测试**

Create: `tests/rpc_contract/test_shutdown_coordinator.py`

Test coverage:

- shutdown 后阻止新 request。
- pending chat/TTS/STT/OCR/MCP/plugin request 只进入一次终态。
- shutdown 顺序为 block_new_requests、cancel_or_drain_long_tasks、release_handles、flush_logs、stop_plugin_mcp_workers、sidecar.shutdown。
- fake plugin/MCP worker 生成子进程，cancel/shutdown 后断言无残留子进程。
- flush 失败和强制 kill 必须写审计日志。

- [x] **Step 7: 实现 shutdown coordinator**

Create: `python_core/rpc/shutdown.py`

实现要求：

- 统一协调 TaskRegistry、HandleRegistry、LogService、PluginService、McpService。
- sidecar crash restart 时调用 TaskRegistry 标记所有 pending request 为 `sidecar.restarted`。
- 正常关闭和异常关闭都不能留下未释放 handle。

- [x] **Step 8: 验证**

Run:

```powershell
python -m pytest tests/rpc_contract/test_sidecar_smoke.py tests/rpc_contract/test_stdout_zero_pollution.py tests/rpc_contract/test_shutdown_coordinator.py tests/rpc_contract/ -q
```

Expected:

```text
全部通过。
```

#### Task 1.2 验证结果

- 运行日期：2026-05-30
- 新增测试红灯确认：`python -m pytest tests/rpc_contract/test_sidecar_smoke.py tests/rpc_contract/test_stdout_zero_pollution.py tests/rpc_contract/test_shutdown_coordinator.py -q` 初始失败，失败原因为 `python_core.sidecar_main` 尚不存在、`ShutdownCoordinator` 尚未支持 Task 1.2 依赖注入和进程树关闭。
- 聚焦验证：`python -m pytest tests/rpc_contract/test_sidecar_smoke.py tests/rpc_contract/test_stdout_zero_pollution.py tests/rpc_contract/test_shutdown_coordinator.py -q`：通过，`11 passed in 4.24s`。
- 全量 RPC contract：`python -m pytest tests/rpc_contract/ -q`：通过，`71 passed in 4.58s`。
- 计划指定命令：`python -m pytest tests/rpc_contract/test_sidecar_smoke.py tests/rpc_contract/test_stdout_zero_pollution.py tests/rpc_contract/test_shutdown_coordinator.py tests/rpc_contract/ -q`：通过，`71 passed in 5.05s`。

### Task 1.2A：冻结 RuntimePaths、stdout 静态扫描和 sidecar 无 Qt 基线

**Files:**
- Create: `scripts/trace_sidecar_import_graph.py`
- Create: `scripts/check_no_stdout_in_sidecar.py`
- Create: `tests/rpc_contract/test_runtime_paths.py`
- Create: `tests/rpc_contract/test_no_stdout_static.py`
- Create: `tests/rpc_contract/test_no_pyside6_import_static.py`
- Create: `tests/rpc_contract/test_sidecar_import_graph_no_qt.py`
- Modify: `python_core/runtime_paths.py`
- Modify: `python_core/sidecar_main.py`

- [x] **Step 1: 写 RuntimePaths 边界测试**

Create: `tests/rpc_contract/test_runtime_paths.py`

Test coverage:

- Windows dev 模式允许显式传入 repo-local `data/`，发布模式拒绝仓库内运行期目录。
- `config_dir`、`log_dir`、`memory_dir`、`vision_dir`、`browser_sessions_dir`、`temp_dir`、`resource_dir`、`models_dir` 全部经过 `resolve()`。
- 拒绝 `..`、驱动器前缀逃逸、UNC 逃逸、符号链接逃逸。
- 外部模型目录必须来自 Tauri 用户选择 scope。
- 默认资源只允许从 `resources/defaults` 复制到 per-user app data，不允许原地写默认资源目录。

Run:

```powershell
python -m pytest tests/rpc_contract/test_runtime_paths.py -q
```

Expected:

```text
失败，提示 RuntimePaths 边界校验尚未实现。
```

- [x] **Step 2: 补强 RuntimePaths**

Modify: `python_core/runtime_paths.py`

实现要求：

- `RuntimePaths.from_json(payload: dict, mode: Literal["dev", "release"])` 只接受 Tauri 注入的路径。
- `assert_in_scope(path, allowed_roots)` 先 resolve 再比较父子关系。
- 发布模式下任何路径落在仓库根目录、`data/config`、`data/logs`、`data/memory` 都失败。
- default config / default character 只能从只读 resource dir 复制到 app data。

- [x] **Step 3: 创建 sidecar import graph 追踪脚本**

Create: `scripts/trace_sidecar_import_graph.py`

实现要求：

- 以 `python_core.sidecar_main` 为唯一根，运行 import hook 记录实际导入图。
- 输出 sidecar import graph JSON，包含 module、file、importer、是否属于项目路径。
- Phase 1-4 只扫描 import graph 中被 sidecar 实际触达的文件，不扫描仍由旧 PySide6 UI 独立使用的全目录。
- Phase 5 改为扫描最终 sidecar artifact / 发布包。
- 命中 `PySide6`、`QApplication`、`QObject`、`QThread`、`Signal`、`ui.` 导入时退出码为 1，并输出导入链。
- 同时扫描动态导入和字符串形式 Qt 加载：`importlib.import_module("PySide6")`、`__import__("PySide6")`、`QtWebEngine`、`PySide6` 字符串常量；命中时输出 suspect file。

- [x] **Step 4: 写 sidecar import graph no-Qt 测试**

Create: `tests/rpc_contract/test_sidecar_import_graph_no_qt.py`

Test coverage:

- `python_core.sidecar_main` import graph 不包含 `PySide6`、`QApplication`、`QObject`、`QThread`、`Signal`、`ui.*`。
- `core/ui_event_bridge.py`、`main.py`、`ui/**` 可以存在，但不得被 sidecar import graph 触达。
- 如果 `agent/`、`tts/`、`vision/`、`core/` 中仍有旧 Qt import，只要未被 sidecar graph 触达，Phase 1-4 不失败；Phase 5 发布 artifact 扫描必须失败。

- [x] **Step 5: 写 stdout 静态扫描测试**

Create: `tests/rpc_contract/test_no_stdout_static.py`

Test coverage:

- 扫描 `scripts/trace_sidecar_import_graph.py` 输出的 sidecar import graph。
- 命中裸 `print(`、`sys.stdout.write(`、`logging.StreamHandler(sys.stdout)` 时失败。
- 测试 fixture、迁移归档目录和未被 sidecar graph 触达的旧 PySide6 UI 路径不计入 Phase 1-4。
- 允许通过 `sidecar_stderr_logger` 或标准 logging stderr handler 输出非协议日志。

- [x] **Step 6: 创建 stdout 静态扫描脚本**

Create: `scripts/check_no_stdout_in_sidecar.py`

实现要求：

- Phase 1-4 默认扫描 sidecar import graph。
- Phase 5 使用 `--artifact` 扫描最终 sidecar artifact / 发布包。
- 输出命中文件、行号和命中片段。
- 检测 `tts/adapters/gptsovits.py` 中遗留 `print()`，要求迁移为 stderr logger。
- 任一命中退出码为 1。

- [x] **Step 7: 写 no-PySide6 静态导入基线测试**

Create: `tests/rpc_contract/test_no_pyside6_import_static.py`

Test coverage:

- sidecar import graph 不得新增 `from PySide6` 或 `import PySide6`。
- sidecar import graph 不得出现 `importlib.import_module("PySide6")`、`__import__("PySide6")`、`QtWebEngine`、`PySide6` 字符串形式动态加载。
- Phase 1-4 旧 UI 路径 `ui/`、`main.py` 可以继续存在，但不能被 `python_core.sidecar_main` 导入链触达。
- 命中时输出导入链或最近的 suspect import 文件。

- [x] **Step 8: 验证**

Run:

```powershell
python -m pytest tests/rpc_contract/test_runtime_paths.py tests/rpc_contract/test_sidecar_import_graph_no_qt.py tests/rpc_contract/test_no_stdout_static.py tests/rpc_contract/test_no_pyside6_import_static.py -q
python scripts/trace_sidecar_import_graph.py
python scripts/check_no_stdout_in_sidecar.py
```

Expected:

```text
全部通过；sidecar import graph 没有 stdout 污染点，也没有 PySide6 / Qt / ui 导入。
```

#### Task 1.2A 验证结果

- 运行日期：2026-05-30
- 新增测试红灯确认：`python -m pytest tests/rpc_contract/test_runtime_paths.py tests/rpc_contract/test_sidecar_import_graph_no_qt.py tests/rpc_contract/test_no_stdout_static.py tests/rpc_contract/test_no_pyside6_import_static.py -q` 初始失败，失败原因为 RuntimePaths 尚缺少 1.2A 边界 API，`scripts/trace_sidecar_import_graph.py` 和 `scripts/check_no_stdout_in_sidecar.py` 尚未创建。
- 聚焦验证：`python -m pytest tests/rpc_contract/test_runtime_paths.py tests/rpc_contract/test_sidecar_import_graph_no_qt.py tests/rpc_contract/test_no_stdout_static.py tests/rpc_contract/test_no_pyside6_import_static.py -q`：通过，`15 passed in 4.29s`。
- import graph 脚本：`python scripts/trace_sidecar_import_graph.py`：通过，输出 JSON graph；sidecar 实际触达的项目模块仅为 `python_core/**` RPC/runtime/sidecar 文件，未触达 `ui/`、`main.py` 或 `core/ui_event_bridge.py`。
- stdout 静态扫描：`python scripts/check_no_stdout_in_sidecar.py`：通过，输出 `sidecar stdout scan ok`。
- 全量 RPC contract：`python -m pytest tests/rpc_contract/ -q`：通过，`86 passed in 8.80s`。

### Task 1.1A：冻结共享 RPC schema 和 method catalog

**Files:**
- Create: `python_core/rpc/schema/catalog.json`
- Create: `python_core/rpc/schema/schema_hash.py`
- Create: `python_core/rpc/schema/validate.py`
- Create: `python_core/rpc/errors.py`
- Create: `python_core/rpc/registry.py`
- Create: `python_core/rpc/protocol.py`
- Create: `python_core/runtime_paths.py`
- Create: `scripts/check_rpc_schema_contract.py`
- Create: `tests/rpc_contract/test_method_catalog.py`
- Create: `tests/rpc_contract/test_registry_matches_catalog.py`
- Create: `tests/rpc_contract/test_protocol_negotiation.py`
- Create: `tests/rpc_contract/test_runtime_paths_schema.py`
- Create: `tests/fixtures/runtime_paths/windows_dev.json`
- Create: `tests/fixtures/runtime_paths/windows_release.json`
- Create: `tests/fixtures/runtime_paths/invalid_repo_release.json`
- Create: `apps/desktop/frontend/src/client/catalog.spec.ts`
- Create: `apps/desktop/frontend/src/client/types/rpc.ts`
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/scripts/check-catalog.mjs`
- Create: `apps/desktop/src-tauri/Cargo.toml`
- Create: `apps/desktop/src-tauri/src/lib.rs`
- Create: `apps/desktop/src-tauri/src/rpc_schema.rs`
- Create: `apps/desktop/src-tauri/tests/command_catalog.rs`
- Create: `apps/desktop/src-tauri/tests/runtime_paths_schema.rs`

- [x] **Step 1: 写 method catalog 测试**

Create: `tests/rpc_contract/test_method_catalog.py`

Test coverage:

- catalog 必须逐 method 包含设计稿完整首版 method，不允许只按域通配。
- 必须硬编码并校验以下 method：
  - `sidecar.hello`、`sidecar.health`、`sidecar.shutdown`、`sidecar.cancel`、`sidecar.task_snapshot`
  - `config.get_all`、`config.save_api`、`config.save_system`、`config.save_memory`、`config.save_agent`、`config.save_mcp`、`config.validate`
  - `character.list`、`character.get`、`character.save`、`character.sync_assets`、`character.delete`、`character.protect_core_files`
  - `chat.send`、`chat.retry`、`chat.proactive_state`
  - `proactive.start`、`proactive.stop`、`proactive.notify_interaction`、`proactive.update_context`
  - `tts.synthesize`、`stt.begin_recording`、`stt.stop_recording`、`stt.transcribe`
  - `ocr.capture`、`ocr.recognize`、`ocr.cleanup`
  - `logs.query`、`logs.subscribe`、`logs.export`、`logs.open_location`
  - `tools.list`、`tools.call`、`tools.audit_query`
  - `plugins.refresh`、`plugins.enable`、`plugins.disable`、`plugins.import`、`plugins.status`
  - `mcp.list_servers`、`mcp.save_server`、`mcp.refresh`、`mcp.call_tool`、`mcp.stop_server`
  - `security.approve`、`security.deny`、`security.revoke_grant`、`security.list_grants`
  - `diagnostics.run`、`diagnostics.export`、`diagnostics.open_report`
  - `handles.read_range`、`handles.read_page`、`handles.release`、`handles.stat`
- 每个 method 都必须声明 `params`、`result` 或 `accepted`、`events`、`errors`、`redaction`、`long_task`。
- `security.confirm_required` 是 event-only 协议事件，不是 invoke method；它必须出现在 event catalog、TS event types、Rust event enum 和 Python `RpcEventPublisher` 事件集合中，且不得出现在 method 列表。
- Task 1.1A 执行时必须同步更新设计稿 method catalog 口径：把 `security.confirm_required` 标记为 event-only security event，避免设计稿和实施 catalog 漂移。
- `sidecar.cancel` 是唯一取消 wire method。
- 领域生命周期类 `.stop` method 允许存在，但必须标记为 `long_task=false`、`cancels_request=false`，不得接收任意 `request_id`，不得发送 `*.cancelled` 终态事件。
- 首版允许的 `.stop` method 只有 `proactive.stop`、`stt.stop_recording`、`mcp.stop_server`：
  - `proactive.stop` 只停止主动调度器，不取消聊天、TTS、OCR、MCP 或插件 request。
  - `stt.stop_recording` 只结束录音采集并产出 audio handle，不取消 RPC 任务。
  - `mcp.stop_server` 只关闭指定 MCP server session，不取消任意 `mcp.call_tool` request；取消工具调用必须走 `sidecar.cancel(target_request_id)`。
- 如果某个业务动作需要取消长任务、终止任意 request 或产生 `*.cancelled` 终态事件，必须删除对应业务 `.stop` wire method，统一改用 `sidecar.cancel(target_request_id)`。

Run:

```powershell
python -m pytest tests/rpc_contract/test_method_catalog.py -q
```

Expected:

```text
失败，提示 catalog 文件尚不存在。
```

- [x] **Step 2: 创建 catalog.json**

Create: `python_core/rpc/schema/catalog.json`

实现要求：

- 使用 JSON 作为 Phase 1 的共享 schema 源。
- catalog 顶层必须包含 `schema_version`、`protocol_version`、`min_compatible_protocol_version`、`generated_from_design` 字段，并作为 schema hash 输入。
- 完整 method 列表必须与 Step 1 的硬编码列表完全一致。
- event catalog 必须逐 event 声明所有首版事件，至少包含 `security.confirm_required`、`chat.started`、`chat.delta`、`chat.done`、`chat.error`、`chat.cancelled`、`log.appended`、`diagnostics.progress`、`diagnostics.done`、`diagnostics.error`、`tool.audit`、`sidecar.crashed`、`sidecar.restarted`。
- 所有 method `events` 引用的事件必须全部在 event catalog 中声明；除 supervisor / security 系统事件外，不允许未被任何 method、supervisor 或 security flow 引用的 orphan event。
- 每个 method 至少包含：

```json
{
  "method": "chat.send",
  "long_task": true,
  "params": {
    "text": {"type": "string", "required": true, "nullable": false, "redaction": "summary"},
    "session_id": {"type": "string", "required": true, "nullable": false, "redaction": "id"},
    "visual_handle": {"type": "handle", "required": false, "nullable": true, "default": null, "redaction": "handle"}
  },
  "accepted": {
    "status": {"type": "literal", "value": "accepted", "required": true, "nullable": false, "redaction": "none"},
    "request_id": {"type": "string", "required": true, "nullable": false, "redaction": "id"},
    "task_type": {"type": "literal", "value": "chat.send", "required": true, "nullable": false, "redaction": "none"}
  },
  "events": ["chat.started", "chat.delta", "chat.done", "chat.error", "chat.cancelled"],
  "errors": ["chat.*", "llm.*", "tool.*", "rpc.*"],
  "redaction": ["text:summary", "visual_handle:handle"]
}
```

- 业务 handler 可在 Phase 1 使用 stub，但 catalog 字段不得缺失。
- 每个 `params`、`result`、`accepted`、event `payload` 字段都必须声明 `type`、`required`、`redaction`，并且必须声明 `default` 或 `nullable` 之一；必填且不可空字段使用 `nullable=false`。
- 长任务 terminal event payload 必须声明 terminal state、terminal summary 和 `RpcError` schema；`error` 终态必须引用 canonical `RpcError`。
- `long_task=true` 的 method 必须声明 `accepted`，不得声明同步业务 `result`；`long_task=false` 的 method 必须声明 `result`，不得声明 `accepted`。
- catalog validator 必须拒绝 `{"params": {"x": "string"}}`、`{"result": "object"}`、空 `errors`、空 `redaction` 这类不可执行占位 schema。
- `security.confirm_required` 的 event payload 必须声明 `request_id`、`confirm_token`、`capability`、`scope_hash`、`expires_at_ms`、`user_message` 和脱敏审计摘要；payload 不得包含命令全文、env、cwd 原文或 token 原文。

- [x] **Step 3: 写 registry 与 catalog 一致性测试**

Create: `tests/rpc_contract/test_registry_matches_catalog.py`

Test coverage:

- `python_core/rpc/registry.py` 注册 method 集合必须与 `catalog.json` 完全一致。
- 已迁移业务 handler 和未迁移 stub handler 都必须注册。
- catalog method 缺 handler 时失败。
- 非 catalog method 返回 `rpc.method_not_found`。
- 未迁移 stub handler 返回 `sidecar.not_ready`，不能返回 `rpc.method_not_found`。

- [x] **Step 4: 写 schema hash 与协议协商测试**

Create: `tests/rpc_contract/test_protocol_negotiation.py`

Test coverage:

- `schema_hash` 由 catalog 稳定生成。
- catalog 内容改变时 hash 改变。
- `sidecar.hello` 无共同协议版本时返回 `rpc.protocol_unsupported`。
- 版本交集选择最高兼容版本。
- `min_compatible_protocol_version` 高于 sidecar 支持时失败。
- `sidecar.hello.result` 必含 `selected_protocol_version`、`min_compatible_protocol_version`、`sidecar_version`、`capabilities`、`runtime_paths_ready`、`schema_hash`。
- 未知必填字段返回 `rpc.invalid_params`。
- 未知可选字段被忽略，并写 trace 级日志。
- schema hash 不一致时 dev 模式允许启动但 contract test 失败；release 模式阻塞。

- [x] **Step 5: 写 RuntimePaths schema 一致性测试**

Create:

- `tests/rpc_contract/test_runtime_paths_schema.py`
- `tests/fixtures/runtime_paths/windows_dev.json`
- `tests/fixtures/runtime_paths/windows_release.json`
- `tests/fixtures/runtime_paths/invalid_repo_release.json`
- `apps/desktop/src-tauri/tests/runtime_paths_schema.rs`

Test coverage:

- Rust 生成的 RuntimePaths JSON 可被 Python `RuntimePaths.from_json()` 接受。
- Python dataclass 必填字段和 Rust struct 字段完全一致。
- 字段名漂移、缺字段、危险额外根、release 模式 repo data 都失败。
- fixture 同时覆盖 Windows dev、Windows release 和 invalid repo release。

- [x] **Step 6: 实现 schema hash 和校验器**

Create:

- `python_core/rpc/schema/schema_hash.py`
- `python_core/rpc/schema/validate.py`
- `scripts/check_rpc_schema_contract.py`

实现要求：

- 按 canonical JSON 排序生成 hash。
- 校验 catalog 中无独立取消 method。
- 校验所有 `*.cancel`、`cancel_*` wire method 不存在，允许例外只有 `sidecar.cancel`。
- 校验所有业务 `.stop` method 都同时满足 `long_task=false`、`cancels_request=false`、不接收任意 `request_id`、不发 `*.cancelled` 终态事件；不满足时失败。
- 校验 `security.confirm_required` 只存在于 event catalog，不存在于 method catalog；三端投影必须把它作为 event 类型处理。
- 校验 `long_task=true` method 禁止声明同步业务 `result`，只允许 `accepted` response 和 terminal event。
- 校验每个 `params`、`result`、`accepted`、event `payload` 字段都有 `type`、`required`、`redaction`、`default` 或 `nullable`，拒绝字符串占位 schema。
- 校验 Python redaction policy、TS error normalizer、Rust error mapping 对同一组敏感样例输出一致，防止 `RpcError.details` 跨端脱敏漂移。
- 校验所有错误码都存在于 `errors.py`。
- 校验 Python registry、Rust `rpc_schema.rs`、Rust command tests、TS `rpc.ts`、typed client `commands/`、typed client `events/`、release manifest 中的 hash、method、event、error 集合一致。
- 任一三端投影缺 method、event、error、helper 或 hash 不一致时退出码为 1。

- [x] **Step 7: 创建 TS / Rust schema 投影和 contract 测试**

Create:

- `apps/desktop/frontend/src/client/types/rpc.ts`
- `apps/desktop/frontend/src/client/catalog.spec.ts`
- `apps/desktop/src-tauri/src/rpc_schema.rs`
- `apps/desktop/src-tauri/tests/command_catalog.rs`

实现要求：

- 暂不要求自动生成，但必须记录 `SCHEMA_HASH`。
- TS / Rust contract test 校验常量、method、event、error 集合与 Python catalog 一致。
- Rust `command_catalog.rs` 校验 Tauri command 目录与 catalog 投影一致；业务 command 不得绕开 catalog。
- TS `catalog.spec.ts` 校验 typed helpers 与 catalog method/event 完全一致。
- 后续如引入生成器，不能改变 wire 字段名。

- [x] **Step 8: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/rpc_contract/test_method_catalog.py tests/rpc_contract/test_registry_matches_catalog.py tests/rpc_contract/test_protocol_negotiation.py tests/rpc_contract/test_runtime_paths_schema.py -q
python scripts/check_rpc_schema_contract.py
Set-Location apps/desktop/src-tauri
cargo test --test command_catalog
cargo test --test runtime_paths_schema
Set-Location ..
pnpm test -- catalog
```

Expected:

```text
全部通过。
```

#### Task 1.1A 验证结果

- 运行日期：2026-05-30
- `python -m pytest tests/rpc_contract/test_method_catalog.py tests/rpc_contract/test_registry_matches_catalog.py tests/rpc_contract/test_protocol_negotiation.py tests/rpc_contract/test_runtime_paths_schema.py -q`：通过，`20 passed in 0.19s`。
- `python scripts/check_rpc_schema_contract.py`：通过，输出 `rpc schema contract ok (60 methods, schema_hash=ee71fbdbf2a94a2696a62b696641ed75265c31adc0f34ffcfd69270b9e3a60a9)`。
- `cargo test --test command_catalog --test runtime_paths_schema`：通过，`4 passed`。
- `pnpm test -- catalog`：通过，输出 `frontend catalog ok (60 methods, 32 events)`。

### Task 1.1B：实现状态机、事件背压和句柄基础设施

**Files:**
- Create: `python_core/rpc/tasks.py`
- Create: `python_core/rpc/backpressure.py`
- Create: `python_core/rpc/event_publisher.py`
- Create: `python_core/rpc/event_bus_shim.py`
- Create: `python_core/resources/__init__.py`
- Create: `python_core/resources/handle_registry.py`
- Create: `tests/rpc_contract/test_task_state_machine.py`
- Create: `tests/rpc_contract/test_event_backpressure.py`
- Create: `tests/rpc_contract/test_event_publisher.py`
- Create: `tests/rpc_contract/test_handles.py`
- Create: `tests/rpc_contract/test_handle_registry_security.py`
- Create: `tests/rpc_contract/test_shutdown_process_tree.py`

- [x] **Step 1: 写状态机表驱动测试**

Create: `tests/rpc_contract/test_task_state_machine.py`

Test coverage:

- 短任务：`created -> running -> done/error`。
- 短任务 deadline 后迟到 response 被丢弃。
- 长任务：`created -> accepted -> streaming -> cancelling -> done/error/cancelled`。
- `accepted` 后直接 `done` 合法。
- `long_task=true` 的 invoke response 只能是 `accepted`，禁止直接返回业务 `result`。
- 长任务首个 response 必须包含 `accepted.status="accepted"`、`request_id`、`task_type` 和 `sidecar_generation`。
- 长任务 `done`、`error`、`cancelled` 终态只能由 event 表达，不能由 invoke response 表达。
- terminal event 必须携带 `request_id`、递增 `sequence`、`payload.state`、`payload.summary`；`error` 终态必须携带 canonical `RpcError`。
- 乱序事件返回 `rpc.event_out_of_order`。
- 重复终态返回 `rpc.duplicate_terminal`。
- cancel 和 timeout 竞争只产生一个终态。
- sidecar restart 将 pending request 标记为 `error(sidecar.restarted)`。

- [x] **Step 2: 实现 TaskRegistry**

Create: `python_core/rpc/tasks.py`

实现要求：

- 维护 `request_id -> TaskHandle`。
- `TaskHandle` 包含 request_id、task_type、state、created_at、deadline、owner、sidecar_generation。
- `TaskRegistry.accept_long_task(request_id, task_type)` 只能生成 accepted response，不允许携带业务 result。
- `TaskRegistry.publish_terminal_event(...)` 是唯一终态出口，必须先 CAS 终态再发布 event。
- 终态 CAS：同一 request 只能进入一次 `done/error/cancelled`。
- `sidecar.cancel` 幂等；已终态 request 返回终态摘要。
- cancel 和 timeout 竞争时只产生一个终态事件。
- sidecar restart 时批量标记 pending request 为 `error(sidecar.restarted)`。
- TaskRegistry 是 `RpcEventPublisher` 和 shutdown coordinator 的唯一终态仲裁点。

- [x] **Step 3: 写事件背压测试**

Create: `tests/rpc_contract/test_event_backpressure.py`

Test coverage:

- 默认单 request 队列达到 512 条或 8 MiB 后触发背压。
- 默认全局队列达到 5000 条或 32 MiB 后触发降级。
- 自定义 backpressure budget 生效，调参不需要改协议字段。
- 进度事件可覆盖旧值。
- 终态事件不可丢，且优先级高于队列满载。
- 默认文本 delta 按 30-80 ms 合帧。
- 默认慢消费者 2 秒未消费时产生摘要事件。

- [x] **Step 4: 实现背压配置和 RpcEventPublisher**

Create:

- `python_core/rpc/backpressure.py`
- `python_core/rpc/event_publisher.py`

实现要求：

- `BackpressureConfig` 定义默认值和 override 入口。
- 只接受带 `RpcContext` 的事件。
- 单 request 内 sequence 递增。
- 终态 CAS 由 TaskRegistry 保护。
- 支持队列上限、合帧、慢消费者降级。
- 可桥接旧 `EventBus`，替代 `core/ui_event_bridge.py` 的 sidecar 路径。

- [x] **Step 5: 写 EventBus shim 测试**

Create: `tests/rpc_contract/test_event_publisher.py`

Test coverage:

- fake `EventBus` 事件转换为 RPC event。
- `RpcContext` 必填，缺少 context 时拒绝发布。
- 单 request sequence 递增。
- 背压降级和 unsubscribe 生效。
- 重复终态被 TaskRegistry 拒绝。
- `core/ui_event_bridge.py` 不在 sidecar import graph 中。

- [x] **Step 6: 实现 EventBus shim**

Create: `python_core/rpc/event_bus_shim.py`

实现要求：

- 只在 Python Core / sidecar 路径中把旧 `EventBus` 事件转发给 `RpcEventPublisher`。
- 不导入 `PySide6`、`QObject`、`Signal` 或 `core/ui_event_bridge.py`。
- 订阅解除必须释放旧 EventBus listener。
- 迟到事件只写日志，不更新已销毁 owner。

- [x] **Step 7: 写 HandleRegistry 测试**

Create: `tests/rpc_contract/test_handles.py`

Test coverage:

- 创建 audio/image/text/file/json handle。
- `handles.read_range`、`handles.read_page`、`handles.stat`、`handles.release`。
- handle 不暴露真实路径。
- TTL 过期返回 `filesystem.handle_expired`。
- request 取消、失败、sidecar shutdown 时清理 owner handles。

- [x] **Step 8: 写 HandleRegistry 安全和释放测试**

Create: `tests/rpc_contract/test_handle_registry_security.py`

Test coverage:

- 跨 request / 跨 owner 读取 handle 被拒绝。
- TTL 过期后真实临时文件被删除。
- `handles.release` 幂等。
- request cancel、request error、sidecar shutdown 都删除 owner 临时资源。
- handle id 不含路径、用户名、文件名原文。

- [x] **Step 9: 实现 HandleRegistry**

Create: `python_core/resources/handle_registry.py`

实现要求：

- handle id 不含真实路径。
- 所有文件 handle 必须在 RuntimePaths scope 内。
- 支持按 owner request 清理。
- 支持 shutdown 全量清理。

- [x] **Step 10: 写 shutdown 进程树释放测试**

Create: `tests/rpc_contract/test_shutdown_process_tree.py`

Test coverage:

- fake plugin / MCP worker 创建子进程。
- `sidecar.cancel`、worker close、sidecar shutdown 后无残留子进程。
- worker crash 后迟到 stdout/stderr 不进入当前 generation。
- shutdown 超时写审计摘要。

- [x] **Step 11: 验证**

Run:

```powershell
python -m pytest tests/rpc_contract/test_task_state_machine.py tests/rpc_contract/test_event_backpressure.py tests/rpc_contract/test_event_publisher.py tests/rpc_contract/test_handles.py tests/rpc_contract/test_handle_registry_security.py tests/rpc_contract/test_shutdown_process_tree.py -q
```

Expected:

```text
全部通过。
```

#### Task 1.1B 验证结果

- 运行日期：2026-05-30
- `python -m pytest tests/rpc_contract/test_task_state_machine.py tests/rpc_contract/test_event_backpressure.py tests/rpc_contract/test_event_publisher.py tests/rpc_contract/test_handles.py tests/rpc_contract/test_handle_registry_security.py tests/rpc_contract/test_shutdown_process_tree.py -q`：通过，`22 passed in 0.38s`。
- `python -m pytest tests/rpc_contract/ -q`：通过，`60 passed in 0.58s`。
- `python scripts/check_rpc_schema_contract.py`：通过，输出 `rpc schema contract ok (60 methods, schema_hash=ee71fbdbf2a94a2696a62b696641ed75265c31adc0f34ffcfd69270b9e3a60a9)`。
- `cargo test`（`apps/desktop/src-tauri`）：通过，`6 passed`。
- `pnpm test -- catalog`（`apps/desktop`）：通过，输出 `frontend catalog ok (60 methods, 32 events)` 和 `frontend error codes ok (34 codes)`。

### Task 1.3：创建 Tauri shell 骨架和 supervisor

**Files:**
- Create: `apps/desktop/src-tauri/Cargo.toml`
- Create: `apps/desktop/src-tauri/tauri.conf.json`
- Create: `apps/desktop/src-tauri/src/main.rs`
- Create: `apps/desktop/src-tauri/src/rpc.rs`
- Create: `apps/desktop/src-tauri/src/sidecar.rs`
- Create: `apps/desktop/src-tauri/src/runtime_paths.rs`
- Create: `apps/desktop/src-tauri/tests/sidecar_contract.rs`
- Create: `apps/desktop/src-tauri/tests/supervisor_lifecycle.rs`
- Create: `tests/rpc_contract/test_sidecar_generation.py`

- [x] **Step 1: 创建 Tauri Rust 工程骨架**

Run:

```powershell
New-Item -ItemType Directory -Force apps/desktop/src-tauri/src apps/desktop/src-tauri/tests
```

Expected:

```text
目录存在。
```

- [x] **Step 2: 写 Rust supervisor 测试**

Create: `apps/desktop/src-tauri/tests/sidecar_contract.rs`

Test coverage:

- 构造 `RuntimePaths`。
- 向 Python sidecar 发送 `sidecar.hello`。
- 非法 frame 被识别为协议错误。
- sidecar 崩溃后 pending request 被标记为 `sidecar.restarted`。
- hello/ready 版本握手必须校验 `supported_protocol_versions`、`min_compatible_protocol_version`、`schema_hash`。
- health ping 失败后进入 degraded。
- sidecar stdin 写入阻塞、写入超时或 broken pipe 时，pending request 必须进入单一 `error(sidecar.restarted)` 或 `error(sidecar.not_ready)`，不得悬挂 waiter。
- request deadline 到期后 Rust request registry 必须释放 waiter；迟到 response 必须被 generation 和 request state 拒绝。
- stdout reader 遇到非法 frame、半帧超时或 decode error 时，不得阻塞 stdin writer；必须进入 degraded 或按 restart 策略处理。
- 频繁崩溃触发指数退避和熔断。
- shutdown 超时后清理 Windows 子进程树。
- restart generation 自增。
- pending request 只收到一次 `error(sidecar.restarted)`。
- 旧 generation 的 stdout、stderr、event 被隔离，不更新 UI。
- restart 后旧 confirm token、handle、plugin worker id、MCP server session 全部失效。

- [x] **Step 3: 实现 Rust RPC types**

Create: `apps/desktop/src-tauri/src/rpc.rs`

实现要求：

- `RequestEnvelope`
- `ResponseEnvelope`
- `EventEnvelope`
- `RpcError`
- `request_id` 是唯一主键。
- 不序列化 `id` 字段。

- [x] **Step 4: 实现 RuntimePaths 注入**

Create: `apps/desktop/src-tauri/src/runtime_paths.rs`

实现要求：

- Windows 使用 Tauri app data dir。
- dev 模式允许 repo-local `data/`，发布模式禁止。
- 路径 scope 统一 resolve。

- [ ] **Step 5: 实现 SidecarSupervisor**

Create: `apps/desktop/src-tauri/src/sidecar.rs`

实现要求：

- spawn Python sidecar。
- stdout reader 只解析协议帧。
- stderr drain 独立处理。
- request registry 支持 deadline。
- stdin writer 必须有有界队列和写入 deadline；写入阻塞、broken pipe、child stdin closed 都要触发统一失败路径。
- Rust request registry 在 deadline、sidecar restart、write failure、shutdown 时释放 waiter，迟到 response 只能写 trace 日志。
- stdout reader parse error 不能与 writer 共用锁造成 deadlock；reader 失败后 supervisor 标记 degraded 并按策略重启 sidecar。
- hello 不兼容时返回 `rpc.protocol_unsupported`，不初始化业务服务。
- crash restart 后所有 pending request 只进入一次 `error(sidecar.restarted)`。
- 每次启动和重启都生成递增 `sidecar_generation`，所有 request、event、handle、confirm token、worker session 必须绑定 generation。
- shutdown 超时后 kill 进程树。

- [x] **Step 6: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/rpc_contract/test_sidecar_generation.py -q
Set-Location apps/desktop/src-tauri
cargo test
cargo test --test supervisor_lifecycle
```

Expected:

```text
cargo test 通过。
```

#### Task 1.3 部分进展

- 运行日期：2026-05-30
- 新增测试红灯确认：`cargo test --test sidecar_contract --test supervisor_lifecycle` 初始失败，失败原因为 `yumetsuki_desktop::rpc`、`runtime_paths`、`sidecar` 模块尚不存在。
- 已完成：Rust crate 骨架、`tauri.conf.json`、`main.rs`、RPC envelope 基础类型、dev `RuntimePaths` JSON 注入、request registry generation/deadline 基础测试、Python `test_sidecar_generation.py`。
- 当前验证：`python -m pytest tests/rpc_contract/test_sidecar_generation.py -q`：通过，`1 passed in 0.11s`。
- 当前验证：`cargo test`（`apps/desktop/src-tauri`）：通过，包含既有 schema/error tests、新增 `sidecar_contract` 和 `supervisor_lifecycle`。
- 当前验证：`cargo test --test supervisor_lifecycle`：通过，`3 passed`。
- 追加修正：Rust dev `RuntimePaths` 注入会规范化 Windows `\\?\` 扩展路径，避免 Python sidecar 将其误判为 UNC 逃逸。
- 追加验证：`cargo test --test sidecar_contract --test supervisor_lifecycle`：通过，`sidecar.hello` 和非法 frame 已走真实 Python sidecar one-shot stdio 路径。
- 未完成项：`SidecarSupervisor` 已切到真实 Python one-shot stdio 路径并可通过当前 contract 测试，但长驻 async reader/writer、有界队列、restart/backoff/circuit breaker、Windows 进程树清理和 generation 隔离仍待后续 Phase 硬化。因此 Step 5 仍暂不勾选；Step 6 仅代表当前 one-shot contract 与生命周期测试通过。

### Task 1.3A：冻结 Tauri capability、URL/path 安全和性能基线

**Files:**
- Create: `apps/desktop/src-tauri/capabilities/main.json`
- Create: `apps/desktop/src-tauri/capabilities/pet.json`
- Create: `apps/desktop/src-tauri/capabilities/settings.json`
- Create: `apps/desktop/src-tauri/capabilities/diagnostics.json`
- Create: `apps/desktop/src-tauri/src/capability_manifest.rs`
- Create: `apps/desktop/src-tauri/src/path_scope.rs`
- Create: `apps/desktop/src-tauri/src/url_safety.rs`
- Create: `apps/desktop/src-tauri/tests/capability_manifest.rs`
- Create: `apps/desktop/src-tauri/tests/url_path_safety.rs`
- Create: `tests/security/test_tauri_capabilities.py`
- Create: `tests/security/test_url_path_safety.py`
- Create: `apps/desktop/perf/budgets.json`

- [x] **Step 1: 写 capability manifest 测试**

Test coverage:

- 每个 Tauri command 必须出现在一个窗口 capability 中。
- `apps/desktop/src-tauri/tests/capability_manifest.rs` 必须解析 `#[tauri::command]`、`invoke_handler!`、`tauri.conf.json` 插件权限和 `capabilities/*.json`，交叉校验实际暴露面。
- 新 command 没有安全分类时失败。
- command 在 capability 中但未注册时失败。
- `pet` window 获得 settings / diagnostics 权限时失败。
- `file`、`shell`、`opener`、`http`、`clipboard` 权限不得宽开。
- `main`、`pet`、`settings`、`diagnostics` 四类窗口 scope 与设计稿一致。
- `pet` 只允许窗口拖拽、缩放、聊天发送和 `sidecar_cancel`。

- [x] **Step 2: 创建 capability manifest**

Create:

- `apps/desktop/src-tauri/capabilities/main.json`
- `apps/desktop/src-tauri/capabilities/pet.json`
- `apps/desktop/src-tauri/capabilities/settings.json`
- `apps/desktop/src-tauri/capabilities/diagnostics.json`

实现要求：

- 默认 deny 任意 shell、任意 filesystem、任意 URL open。
- 文件 scope 只来自 RuntimePaths 或用户选择目录。
- URL scope 默认只允许 `http` / `https`，并经过 `url_safety.rs` 二次校验。

- [x] **Step 3: 写 URL/path 安全测试**

Test coverage:

- 拒绝 `file://`。
- 私网、localhost、DNS rebinding 和 redirect 后私网都需要显式确认。
- 文件名只允许安全字符集。
- 拒绝 `..`、绝对路径、驱动器前缀、UNC 逃逸、符号链接逃逸。
- 外部模型目录必须通过用户选择目录 scope。

- [x] **Step 4: 实现 PathScope 和 UrlSafety**

Create:

- `apps/desktop/src-tauri/src/path_scope.rs`
- `apps/desktop/src-tauri/src/url_safety.rs`

实现要求：

- 所有路径先 resolve 再比较 scope。
- URL 先 normalize，再校验 scheme、host、redirect 结果和解析 IP。
- 错误码映射到 `filesystem.path_out_of_scope` 或 `security.permission_denied`。

- [x] **Step 5: 冻结性能预算文件**

Create: `apps/desktop/perf/budgets.json`

内容必须包含：

```json
{
  "startup_cold_ms": 3000,
  "startup_warm_ms": 1500,
  "sidecar_hello_ms": 10000,
  "idle_cpu_percent": 2,
  "sidecar_baseline_memory_mib": 500,
  "chat_mock_first_token_ms": 300,
  "tts_mock_first_segment_ms": 500,
  "log_10k_min_fps": 30,
  "bundle_size_budget_bytes": 0,
  "frontend_size_budget_bytes": 0,
  "sidecar_artifact_size_budget_bytes": 0,
  "resource_size_budget_bytes": 0,
  "installer_size_budget_bytes": 0
}
```

说明：

- size budget 为 0 表示 Phase 1 只记录基线，不阻塞；Phase 5 必须全部设置为真实阈值。
- 超阈值要么失败，要么要求显式批准记录进入 release manifest。

- [x] **Step 6: 验证**

Run:

```powershell
python -m pytest tests/security/test_tauri_capabilities.py tests/security/test_url_path_safety.py -q
Set-Location apps/desktop/src-tauri
cargo test --test capability_manifest
cargo test --test url_path_safety
```

Expected:

```text
全部通过。
```

#### Task 1.3A 验证结果

- 运行日期：2026-05-30
- 新增测试红灯确认：`cargo test --test capability_manifest --test url_path_safety` 初始失败，失败原因为 `capability_manifest.rs`、`path_scope.rs`、`url_safety.rs` 和 capability 文件尚不存在。
- Python 红灯确认：`python -m pytest tests/security/test_tauri_capabilities.py tests/security/test_url_path_safety.py -q` 初始失败，失败原因为 capability 文件缺失。
- 聚焦验证：`cargo test --test capability_manifest --test url_path_safety`：通过。
- Python 验证：`python -m pytest tests/security/test_tauri_capabilities.py tests/security/test_url_path_safety.py -q`：通过，`5 passed in 0.16s`。
- 全量验证：`cargo test`：通过。
- 全量验证：`python -m pytest tests/rpc_contract/ tests/security/ -q`：通过，`92 passed in 10.90s`。
- 门禁脚本：`python scripts/check_no_stdout_in_sidecar.py`：通过，输出 `sidecar stdout scan ok`。

### Task 1.4：创建 Vue3 / Pinia 前端骨架

**Files:**
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/frontend/package.json`
- Create: `apps/desktop/frontend/vite.config.ts`
- Create: `apps/desktop/frontend/tsconfig.json`
- Create: `apps/desktop/frontend/src/main.ts`
- Create: `apps/desktop/frontend/src/App.vue`
- Create: `apps/desktop/frontend/src/client/types/rpc.ts`
- Create: `apps/desktop/frontend/src/client/tauriClient.ts`
- Create: `apps/desktop/frontend/src/stores/appStore.ts`
- Create: `apps/desktop/frontend/src/stores/windowStore.ts`
- Create: `apps/desktop/frontend/src/stores/themeStore.ts`
- Create: `apps/desktop/frontend/src/stores/configStore.ts`
- Create: `apps/desktop/frontend/src/stores/chatStore.ts`
- Create: `apps/desktop/frontend/src/stores/audioStore.ts`
- Create: `apps/desktop/frontend/src/stores/sttStore.ts`
- Create: `apps/desktop/frontend/src/stores/logStore.ts`
- Create: `apps/desktop/frontend/src/stores/toolStore.ts`
- Create: `apps/desktop/frontend/src/stores/pluginStore.ts`
- Create: `apps/desktop/frontend/src/stores/mcpStore.ts`
- Create: `apps/desktop/frontend/src/stores/diagnosticStore.ts`
- Create: `apps/desktop/frontend/src/stores/characterStore.ts`
- Create: `apps/desktop/frontend/src/components/ChatPanel.vue`
- Create: `apps/desktop/frontend/src/components/VirtualLogList.vue`
- Test: `apps/desktop/frontend/src/stores/*.spec.ts`

- [x] **Step 1: 创建 Vite + Vue + Pinia 项目文件**

Create minimal frontend with:

- `vue`
- `pinia`
- `@tauri-apps/api`
- `typescript`
- `vitest`
- `@vue/test-utils`
- `playwright` 或 `@playwright/test`

- [x] **Step 2: 实现 typed Tauri client**

Create: `apps/desktop/frontend/src/client/tauriClient.ts`

实现要求：

- 只暴露 typed command helper。
- 生成或接收 `request_id`、`trace_id`。
- 长任务 accepted 后注册状态。
- 提供 fake client 供 Vitest 使用。
- event unsubscribe 由调用者持有。

- [x] **Step 3: 实现最小 stores**

Create:

- `appStore`
- `windowStore`
- `themeStore`
- `configStore`
- `chatStore`
- `audioStore`
- `sttStore`
- `logStore`
- `toolStore`
- `pluginStore`
- `mcpStore`
- `diagnosticStore`
- `characterStore`

实现要求：

- Phase 1 创建所有 store 的 lifecycle / persistence 空壳，业务字段可为空，但文件、类型和测试必须真实存在。
- 每个 store 都有 `init()`、`dispose()`、`resetOnSidecarRestart()`。
- 每个 store 的重复 `init()` 必须幂等，`dispose()` 必须释放 event subscription。
- `diagnosticStore` 不持久化报告路径。
- `chatStore` 只处理一次终态事件。
- `pluginStore`、`mcpStore` 在 Phase 1 只实现 lifecycle、筛选空状态和 persistence 禁区；Phase 4 再填业务状态。
- `configStore`、`characterStore` 在 Phase 1 只实现 lifecycle 和空快照；Phase 2 再填业务状态。
- `audioStore`、`sttStore` 在 Phase 1 只实现 lifecycle 和不持久化约束；Phase 3 再填业务状态。

- [x] **Step 4: 实现最小 UI**

Create:

- `ChatPanel.vue`
- `VirtualLogList.vue`
- `App.vue`

实现要求：

- 输入、发送、mock streaming、停止、失败保留输入、重试。
- 日志列表批量 append、follow-bottom、拖选暂停刷新。

- [x] **Step 5: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
```

Expected:

```text
store 和组件单元测试通过。
```

### Task 1.4A：冻结前端分层、Sakura Web、typed client 和 E2E 基础设施

**Files:**
- Create: `apps/desktop/package.json`
- Create: `apps/desktop/playwright.config.ts`
- Create: `apps/desktop/e2e/startup.spec.ts`
- Create: `apps/desktop/e2e/smoke.spec.ts`
- Create: `apps/desktop/e2e/a11y.spec.ts`
- Create: `apps/desktop/e2e/responsive.spec.ts`
- Create: `apps/desktop/frontend/src/client/commands/index.ts`
- Create: `apps/desktop/frontend/src/client/events/index.ts`
- Create: `apps/desktop/frontend/src/client/types/rpc.ts`
- Create: `apps/desktop/frontend/src/client/tauriClient.spec.ts`
- Create: `apps/desktop/frontend/src/client/import-boundary.spec.ts`
- Create: `apps/desktop/frontend/src/persistence/allowlist.ts`
- Create: `apps/desktop/frontend/src/persistence/allowlist.spec.ts`
- Create: `apps/desktop/frontend/src/router/index.ts`
- Create: `apps/desktop/frontend/src/composables/useRpcTask.ts`
- Create: `apps/desktop/frontend/src/composables/useEventSubscription.ts`
- Create: `apps/desktop/frontend/src/composables/useConfirmDialog.ts`
- Create: `apps/desktop/frontend/src/styles/tokens.css`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraButton.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraIconButton.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraInput.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraSelect.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraRadioGroup.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraSegmentedControl.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraSpinBox.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraToggle.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraTabs.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraSlider.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraToast.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraDialog.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraTooltip.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraContextMenu.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraSplitter.vue`
- Create: `apps/desktop/frontend/src/components/sakura/SakuraSettingsSection.vue`
- Create: `apps/desktop/frontend/src/stores/*.spec.ts`

- [x] **Step 1: 创建统一桌面脚本入口**

Create: `apps/desktop/package.json`

脚本必须包含：

```json
{
  "scripts": {
    "test": "pnpm --dir frontend test",
    "test:a11y": "playwright test e2e/a11y.spec.ts",
    "e2e:startup": "playwright test e2e/startup.spec.ts",
    "e2e:smoke": "playwright test e2e/smoke.spec.ts",
    "e2e:settings": "playwright test e2e/settings.spec.ts",
    "e2e:chat": "playwright test e2e/chat.spec.ts",
    "e2e:logs-tools": "playwright test e2e/logs-tools.spec.ts",
    "e2e:stress": "playwright test e2e/stress.spec.ts",
    "e2e:responsive": "playwright test e2e/responsive.spec.ts",
    "perf:startup": "playwright test e2e/startup.spec.ts --grep @perf"
  }
}
```

约束：

- 所有 E2E、a11y 和性能脚本都从 `apps/desktop` 执行。
- `apps/desktop/frontend/package.json` 只承载 Vite、Vitest 和前端开发脚本。
- 计划中的 E2E 命令不得从 `frontend` 子目录或 `src-tauri` 子目录发起。

- [x] **Step 2: 写 typed client 单元测试**

Create: `apps/desktop/frontend/src/client/tauriClient.spec.ts`

Test coverage:

- `commands/` 只暴露 catalog 中已声明 method 的 typed helper。
- `events/` 只暴露 catalog 中已声明 event 的 typed subscription helper。
- `request_id`、`trace_id`、`parent_trace_id` 由 client 注入或透传。
- timeout 后本地 request 进入 `error`，迟到 `done` 被丢弃。
- 重复终态只处理第一次。
- 乱序 delta 触发 `rpc.event_out_of_order`。
- `unsubscribe()` 被调用后不再更新 store。
- `import-boundary.spec.ts` 禁止页面、组件和 store 直接 import `@tauri-apps/api`。
- `import-boundary.spec.ts` 禁止 `apps/desktop/frontend/src` 中出现 `axios`、任意 HTTP client、业务代码直接 `fetch()`、页面 / 组件 / store 直接 import `@tauri-apps/api`。
- typed client 层只允许使用 `@tauri-apps/api/core.invoke` 和 typed event subscription，不允许用 `fetch()` 或 axios 访问 sidecar。
- `fetch()` 只允许测试 fake 和明确标记的外部网页调试 fixture，禁止进入桌面 RPC / sidecar 主链路。
- `commands/`、`events/`、`types/` 只能从 catalog 投影或统一类型入口导出。

- [x] **Step 3: 拆分 typed client 目录**

Create:

- `apps/desktop/frontend/src/client/commands/index.ts`
- `apps/desktop/frontend/src/client/events/index.ts`
- `apps/desktop/frontend/src/client/types/rpc.ts`

实现要求：

- 前端不拼 sidecar 原始协议帧。
- Tauri invoke command 名称按业务域收口，不暴露通用任意 RPC passthrough。
- long task helper 返回 `{ accepted: true, requestId, taskType }`。
- event subscription 返回 `Promise<UnlistenFn>`，调用方必须在 store dispose 中释放。

- [x] **Step 4: 冻结 Pinia store lifecycle 和持久化 allowlist**

Create:

- `apps/desktop/frontend/src/persistence/allowlist.ts`
- `apps/desktop/frontend/src/persistence/allowlist.spec.ts`

持久化 allowlist 必须按 store/key/version 实现：

| Store | storage key | 允许字段 | 禁止字段 |
|---|---|---|---|
| `windowStore` | `yumetsuki.window.v1` | 位置、尺寸、缩放、置顶、透明偏好 | request、句柄、截图路径 |
| `themeStore` | `yumetsuki.theme.v1` | 主题名、字体族、字号倍率 | token 临时覆盖、运行态错误 |
| `logStore` | `yumetsuki.logs.v1` | channel、source、level、follow-bottom、列宽 | 日志正文、详情、trace 全量 |
| `toolStore` | `yumetsuki.tools.v1` | grant_id 摘要、筛选、展开状态 | 命令全文、env、cwd、token |
| `pluginStore` | `yumetsuki.plugins.v1` | 筛选、展开状态、已启用插件 id 摘要 | 插件 stdout/stderr 原文、manifest 完整本地路径、confirm token |
| `mcpStore` | `yumetsuki.mcp.v1` | server id 摘要、筛选、展开状态 | argv 原文、cwd、env、stdio 输出、confirm token |
| `diagnosticStore` | `yumetsuki.diagnostics.v1` | 最近 check 选择、导出格式偏好 | 诊断包路径、日志正文、敏感扫描命中内容 |
| `characterStore` | `yumetsuki.character.v1` | 最近角色 id、显示偏好 | 角色文件正文、完整本地路径 |

禁止持久化：API key 原文、authorization、cookie、完整模型路径、截图路径、长 OCR 原文、工具命令全文、运行中 request、confirm token、音频 / STT 临时状态、浏览器 profile 路径、诊断包路径。

`chat.inputDraft` 默认不持久化；如后续决定允许，必须先更新设计稿并说明为何不构成敏感状态泄漏。

为这些 store 写生命周期测试：

- `appStore`
- `windowStore`
- `themeStore`
- `configStore`
- `chatStore`
- `audioStore`
- `sttStore`
- `logStore`
- `toolStore`
- `pluginStore`
- `mcpStore`
- `diagnosticStore`
- `characterStore`

每个 store 必须测试 `init()`、`dispose()`、`resetOnSidecarRestart()`、重复 init 幂等和订阅释放。

`resetOnSidecarRestart()` 必须按 store 写入语义断言：

| Store | restart 后必须断言 |
|---|---|
| `appStore` | sidecar 状态转 degraded，清空全局 running request，保留非敏感启动偏好 |
| `windowStore` | 保留窗口位置、缩放、置顶，清空拖拽和托盘运行态 |
| `themeStore` | 重新应用已持久化 token，清空临时 token override |
| `configStore` | 清 saving，保留草稿并标记 needsReload |
| `chatStore` | pending request 全部转 `sidecar.restarted`，流式草稿停止更新 |
| `audioStore` | 停止播放投影，清空队列运行态 |
| `sttStore` | 录音 / 识别状态转 failed，可重新开始 |
| `logStore` | 退订旧事件，保留筛选条件，下一次 init 重新 query |
| `toolStore` | 清 running / pending confirmation，保留目录摘要和筛选 |
| `pluginStore` | 清扫描和导入运行态，保留插件 id 摘要 |
| `mcpStore` | 清连接中和刷新中状态，保留 server id 摘要 |
| `diagnosticStore` | running 转 failed(`sidecar.restarted`)，清 report handle |
| `characterStore` | 资源状态置 stale，保留最近角色 id |

- [x] **Step 5: 冻结 Vue 组合式和路由边界**

Create:

- `apps/desktop/frontend/src/router/index.ts`
- `apps/desktop/frontend/src/composables/useRpcTask.ts`
- `apps/desktop/frontend/src/composables/useEventSubscription.ts`
- `apps/desktop/frontend/src/composables/useConfirmDialog.ts`

实现要求：

- 页面组件统一使用 `<script setup lang="ts">`。
- 业务请求只通过 composable 或 store 调用 typed client。
- 路由按 `chat`、`settings`、`logs`、`tools`、`diagnostics` 分组。
- 组件不直接 import Tauri API，例外只允许 typed client 层。

页面落点矩阵：

| 页面 | route | owner store | E2E 文件 | a11y 覆盖 | 设置页入口关系 |
|---|---|---|---|---|---|
| 设置中心 | `/settings/:section?` | `configStore`、`characterStore` | `apps/desktop/e2e/settings.spec.ts` | `apps/desktop/e2e/a11y.spec.ts` settings 段 | 设置页主页面 |
| 聊天 / 桌宠 | `/chat` | `chatStore`、`audioStore`、`sttStore`、`windowStore` | `apps/desktop/e2e/chat.spec.ts` | `apps/desktop/e2e/a11y.spec.ts` chat 段 | 设置页只提供系统 / Agent 配置入口 |
| 对话日志 / 平台日志 | `/logs/conversation`、`/logs/system` | `logStore` | `apps/desktop/e2e/logs-tools.spec.ts`、`apps/desktop/e2e/stress.spec.ts` | `apps/desktop/e2e/a11y.spec.ts` logs 段 | 设置页侧栏入口跳转到独立 route，Phase 2 为禁用占位 |
| 插件 | `/tools/plugins` | `pluginStore` | `apps/desktop/e2e/logs-tools.spec.ts` | `apps/desktop/e2e/a11y.spec.ts` confirm dialog 段 | 设置页侧栏入口跳转到独立 route，Phase 2 为禁用占位 |
| MCP | `/tools/mcp` | `mcpStore` | `apps/desktop/e2e/logs-tools.spec.ts` | `apps/desktop/e2e/a11y.spec.ts` confirm dialog 段 | 设置页侧栏入口跳转到独立 route，Phase 2 为禁用占位 |
| 诊断 | `/diagnostics` | `diagnosticStore` | `apps/desktop/e2e/logs-tools.spec.ts` | `apps/desktop/e2e/a11y.spec.ts` diagnostics 段 | 设置页不内嵌诊断，只提供状态链接 |

禁止同一页面同时由设置页内嵌实现和独立 route 实现两套状态。设置侧栏中的未迁移入口只允许展示 disabled 状态或跳转到已迁移独立 route。

- [x] **Step 6: 创建 Sakura Web 基础组件和 design tokens**

Create:

- `apps/desktop/frontend/src/styles/tokens.css`
- `apps/desktop/frontend/src/components/sakura/SakuraButton.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraIconButton.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraInput.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraSelect.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraRadioGroup.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraSegmentedControl.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraSpinBox.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraToggle.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraTabs.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraSlider.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraToast.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraDialog.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraTooltip.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraContextMenu.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraSplitter.vue`
- `apps/desktop/frontend/src/components/sakura/SakuraSettingsSection.vue`

实现要求：

- tokens 包含颜色、间距、半径、阴影、字体、motion duration，不使用单一紫色或深蓝单色主题。
- 组件支持 keyboard focus、disabled、busy、danger、aria label。
- Toast 使用 `aria-live`。
- Dialog 支持 focus trap、Escape 关闭、背景 inert。
- Tooltip、ContextMenu、Splitter、Tabs、RadioGroup、SegmentedControl 都必须有键盘路径和 aria 状态。
- 每个 Sakura 组件都有 `*.spec.ts`，覆盖 disabled、busy、danger、focus、keyboard、reduced motion 和基本 a11y。
- `prefers-reduced-motion` 下禁用非必要动画。

- [x] **Step 7: 创建 E2E 和 a11y 夹具**

Create:

- `apps/desktop/playwright.config.ts`
- `apps/desktop/e2e/startup.spec.ts`
- `apps/desktop/e2e/smoke.spec.ts`
- `apps/desktop/e2e/a11y.spec.ts`
- `apps/desktop/e2e/responsive.spec.ts`

Test coverage:

- `e2e:startup`：窗口启动、sidecar hello、schema hash 展示在诊断状态、首屏非空。
- `e2e:smoke`：chat mock send/stop/retry、日志列表、设置入口可访问。
- `test:a11y` 按阶段递增覆盖：
  - Phase 1：shell、chat mock、VirtualLogList 最小视图、禁用入口、toast、dialog、focus trap、reduced motion、WCAG AA 对比度。
  - Phase 2：增加 settings 侧栏 / 分组键盘导航、表单 label、错误回读。
  - Phase 3：增加完整 chat、发送 / 停止、重试、TTS/STT 按钮、流式状态 live region 不逐 token 朗读。
  - Phase 4：增加 logs 筛选 / 虚拟列表 / 详情复制 / 拖选暂停、diagnostics 运行 / 取消 / 导出 / `redaction-failed`、插件 / MCP confirm dialog。
  - Phase 5：全量覆盖所有已迁移页面，不允许跳过未迁移占位。
- `e2e:responsive` 按阶段递增覆盖：
  - Phase 1：主窗口最小尺寸、shell、chat mock、VirtualLogList 最小视图、禁用入口、长中文文案和英文长单词不溢出。
  - Phase 2：增加 settings sidebar、表单、分组布局在 360px、768px、1280px 宽度下无重叠。
  - Phase 3：增加桌宠窗口、ChatPanel、TTS/STT controls、被动气泡和立绘占位。
  - Phase 4：增加 logs / tools / diagnostics 的 splitter、虚拟列表、详情面板、权限确认弹窗，小窗口下 focus trap 可见且按钮文本不截断。
  - Phase 5：全量响应式回归，键盘焦点不被 sticky toolbar、toast 或 dialog 遮挡。
- Playwright web server 从 `apps/desktop` 启动，不依赖人工手动打开 dev server。
- 关键页面必须有轻量 screenshot / visual stability 断言：聊天窗、设置页表单、日志 splitter、诊断导出状态、权限确认弹窗在固定 viewport 下无重叠、无空白首屏、主要按钮可见。

- [x] **Step 8: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:responsive
```

Expected:

```text
前端单元测试、a11y、启动 E2E 和 smoke E2E 全部通过。
```

### Task 1.5：Phase 1 出口验证

- [x] **Step 1: 运行 Phase 1 聚焦验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/rpc_contract/ -q
python scripts/check_rpc_schema_contract.py
Set-Location apps/desktop/src-tauri
cargo test
cargo test --test command_catalog
cargo test --test runtime_paths_schema
Set-Location ..
pnpm test
pnpm test -- catalog
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:responsive
```

Expected:

```text
全部通过。
```

- [x] **Step 2: 运行全量 Python 回归**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/ -q
python scripts/check_replacement_status.py --phase 1 --record-from-last-run
```

Expected:

```text
全量 pytest 通过。
```

## Phase 2：设置中心迁移

**目标:** 迁移 API、系统、记忆、Agent、角色基础设置页，保留现有保存语义、失败回滚、脱敏读取和配置广播。

### Task 2.1：实现 ConfigService / CharacterService facade

**Files:**
- Create: `python_core/services/__init__.py`
- Create: `python_core/services/config_service.py`
- Create: `python_core/services/character_service.py`
- Modify: `python_core/rpc/registry.py`
- Test: `tests/rpc_contract/test_config_methods.py`
- Test: `tests/rpc_contract/test_character_methods.py`

- [ ] **Step 1: 写配置 RPC 测试**

Test coverage:

- `config.get_all(scope=api|system|memory|agent|mcp)` 返回脱敏快照。
- `config.save_api` / `config.save_system` / `config.save_memory` / `config.save_agent` / `config.save_mcp` 必须带 `base_version` 和 `confirm_token`。
- 保存失败回滚内存态。
- `RuntimePaths` 注入 config dir，不默认写仓库 `data/config`。

- [ ] **Step 2: 实现 ConfigService**

实现要求：

- 包装现有 `config/manager.py`。
- API key 只返回 mask。
- 模型路径默认 basename/hash。
- 保存前校验 deadline 和 confirm token。
- 保存失败保留旧内存配置。

- [ ] **Step 3: 写角色 RPC 测试**

Test coverage:

- `character.list`
- `character.get`
- `character.save`
- `character.sync_assets`
- `character.delete`
- 核心文件保护。

- [ ] **Step 4: 实现 CharacterService**

实现要求：

- 复用 `core/character.py`。
- 删除核心角色文件时返回 `security.permission_denied`。
- 本地资源路径只返回摘要。

- [ ] **Step 5: 验证**

Run:

```powershell
python -m pytest tests/rpc_contract/test_config_methods.py tests/rpc_contract/test_character_methods.py tests/test_config.py tests/test_config_agent.py tests/test_character.py -q
```

Expected:

```text
全部通过。
```

### Task 2.2：实现 Vue 设置中心

**Files:**
- Create: `apps/desktop/frontend/src/pages/settings/SettingsLayout.vue`
- Create: `apps/desktop/frontend/src/pages/settings/ApiSettings.vue`
- Create: `apps/desktop/frontend/src/pages/settings/SystemSettings.vue`
- Create: `apps/desktop/frontend/src/pages/settings/MemorySettings.vue`
- Create: `apps/desktop/frontend/src/pages/settings/AgentSettings.vue`
- Create: `apps/desktop/frontend/src/pages/settings/CharacterSettings.vue`
- Modify: `apps/desktop/frontend/src/stores/configStore.ts`
- Modify: `apps/desktop/frontend/src/stores/characterStore.ts`
- Create: `apps/desktop/e2e/settings.spec.ts`
- Test: `apps/desktop/frontend/src/pages/settings/*.spec.ts`

- [ ] **Step 1: 实现设置页 store**

要求：

- 草稿、dirty、saving、error、rollback。
- 同一页保存中禁止二次保存。
- 切页时按旧语义放弃未保存草稿。
- sidecar 重启中禁止保存。

- [ ] **Step 2: 实现页面组件**

要求：

- 导航顺序：API / 角色 / 记忆 / Agent / 插件 / MCP / 对话日志 / 平台日志 / 系统。
- Phase 2 只启用 API / 角色 / 记忆 / Agent / 系统。
- 未迁移页面显示禁用入口和状态说明，不提供假功能。

- [ ] **Step 3: 实现保存反馈**

要求：

- 保存成功 toast。
- 保存失败保留草稿，显示错误详情入口。
- 高风险保存走 ConfirmDialog。

- [ ] **Step 4: 验证**

`apps/desktop/e2e/settings.spec.ts` 必须覆盖：

- API：脱敏、测试连接、保存失败保留草稿。
- 角色：资源同步、核心文件删除保护。
- 记忆：模型不可用回滚。
- Agent：主动行为配置保存失败恢复旧策略。
- 系统：保存成功广播到聊天窗，失败回滚聊天窗投影。

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
pnpm run test:a11y
pnpm run e2e:settings
```

Expected:

```text
设置页单元测试和 E2E 通过。
```

### Task 2.3：Phase 2 出口验证

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/test_config.py tests/test_config_agent.py tests/test_character.py tests/rpc_contract/test_config_methods.py tests/rpc_contract/test_character_methods.py -q
python -m pytest tests/ -q
Set-Location apps/desktop/src-tauri
cargo test
Set-Location ..
pnpm test
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:settings
pnpm run e2e:responsive
Set-Location E:/Project/Yumetsuki
python scripts/check_replacement_status.py --phase 2 --record-from-last-run
```

Expected:

```text
全部通过。
```

## Phase 3：聊天窗迁移

**目标:** 迁移聊天主窗口、立绘、流式回复、停止、重试、状态条、TTS/STT/OCR 职责切分和被动状态第一版。

### 旧接口 shim 清单

| 旧接口 / 文件 | 新入口 | 允许保留阶段 | sidecar 约束 | 退场检查 |
|---|---|---|---|---|
| `core/ui_event_bridge.py` | `python_core/rpc/event_publisher.py` | Phase 1-4 | 不得被 sidecar import graph 触达 | `tests/rpc_contract/test_event_publisher.py`、`tests/rpc_contract/test_sidecar_import_graph_no_qt.py` |
| `agent/proactive.py` | `python_core/services/proactive_service.py`、`python_core/services/proactive_policy.py` | Phase 3-4 | 只允许保留策略兼容 shim，不导入 Qt Signal / QObject | `tests/test_proactive.py`、`tests/rpc_contract/test_chat_methods.py` |
| `ui/chat/tts_pipeline.py` | `python_core/services/speech_service.py` + Rust audio | Phase 3-4 | sidecar 不导入 UI 编排层，不播放音频 | `tests/rpc_contract/test_speech_vision_methods.py`、`apps/desktop/src-tauri/tests/media_contract.rs` |
| `vision/screen_capture.py` | `apps/desktop/src-tauri/src/screenshot.rs` + `python_core/services/vision_service.py` | Phase 3-4 | Python 只消费 image handle，不主动截图 | `tests/rpc_contract/test_speech_vision_methods.py`、路径 scope 测试 |

### PySide6 文件级退场矩阵

| 旧文件 | 当前 UI / Qt 职责 | Phase 3 替代归属 | 兼容策略 | 退场验证 |
|---|---|---|---|---|
| `main.py` | PySide6 应用入口和 QApplication 生命周期 | `apps/desktop/src-tauri/src/main.rs` + `python_core/sidecar_main.py` | Phase 1-4 保留旧入口双跑 | Phase 5 no-PySide6 环境 smoke 通过后从主入口退场 |
| `core/ui_event_bridge.py` | EventBus 到 Qt signal 桥 | `python_core/rpc/event_publisher.py` | Phase 3 保留旧 bridge，但 sidecar 只使用 `RpcEventPublisher` | `tests/rpc_contract/test_event_publisher.py` 证明 sidecar 不导入 Qt bridge |
| `agent/proactive.py` | `QObject/QThread/Signal` 主动消息调度 | `python_core/services/proactive_service.py` | 保留策略代码，替换调度器和事件出口 | `tests/test_proactive.py` 覆盖 headless start/stop、passive state、无线程残留 |
| `vision/screen_capture.py` | Qt / 平台截图入口 | `apps/desktop/src-tauri/src/screenshot.rs` + `python_core/services/vision_service.py` | Python 只识别 image handle，不截图 | `apps/desktop/src-tauri/tests/media_contract.rs` 和 `tests/rpc_contract/test_speech_vision_methods.py` 通过 |
| `ui/chat/stt_recorder.py` | Qt 录音控件和录音线程 | `apps/desktop/src-tauri/src/recorder.rs` + `sttStore` | Python STT 只收 audio handle | STT stop、timeout、cancel 互斥终态测试通过 |
| `ui/chat/audio_backends.py` | Qt / 本地音频播放 | `apps/desktop/src-tauri/src/audio.rs` + `audioStore` | Python TTS 不播放音频，只产出 audio handle | 播放、停止、临时文件清理和迟到事件丢弃测试通过 |
| `ui/chat/web_view.py` | Qt WebView / 聊天窗口容器 | Vue `ChatPanel.vue` + Tauri window | Phase 3 双跑视觉和交互 parity | `pnpm run e2e:chat` 截图和交互测试通过 |
| `ui/chat/tts_pipeline.py` | Qt 聊天 UI 对 TTS pipeline 的编排 | `python_core/services/speech_service.py` + `chatStore` + `audioStore` | TTS pipeline 领域代码保留，UI 触发和播放编排迁出 Qt | TTS 首段、取消、播放失败、sidecar restart 测试通过 |

### Task 3.1：实现 ChatService / ProactiveService

**Files:**
- Create: `python_core/services/chat_service.py`
- Create: `python_core/services/proactive_service.py`
- Create: `python_core/services/proactive_policy.py`
- Modify: `agent/manager.py`
- Modify: `agent/proactive.py`
- Test: `tests/rpc_contract/test_chat_methods.py`
- Test: `tests/test_proactive.py`

- [ ] **Step 1: 写聊天 RPC 测试**

Test coverage:

- `chat.send` 返回 accepted。
- `chat.delta` sequence 单 request 内递增。
- `chat.retry` 生成新 `request_id` 和 `parent_trace_id`。
- `sidecar.cancel` 取消 chat request 后只发一次 `chat.cancelled`。
- sidecar restart 把 pending chat 标记为 `sidecar.restarted`。
- `core/ui_event_bridge.py` 不在 sidecar 导入链中。
- 旧 `EventBus` 事件通过兼容 shim 转成 `RpcEventPublisher` 事件。
- `python_core/services/proactive_policy.py` 只包含可单元测试的策略判断，不导入 Qt 或 RPC。

- [ ] **Step 2: 实现 ChatService**

要求：

- 包装现有 `AgentManager -> LLMManager -> ToolRegistry -> SessionContext -> LogService` 链路。
- 接收 `RpcContext`。
- 接收 `CancelToken`。
- 不依赖 Qt signal。

- [ ] **Step 3: 写 ProactiveService 测试**

Test coverage:

- `start` / `stop` 幂等。
- `notify_interaction` 刷新空闲计时。
- `update_context` 接收角色摘要和视觉摘要 handle。
- `set_passive_state(true|false)` 更新主动策略，并向前端发布 `chat.passive_state_changed`。
- `proactive_policy.can_fire` 覆盖窗口不可见、被动状态开启、上下文缺失、冷却未到、sidecar degraded、用户刚交互；任一不满足都不得发主动事件。
- sidecar hello/ready 未完成时 `start` 不启动调度线程。
- 连续 `start` / `stop` 100 次后无线程残留。
- shutdown 之后迟到 proactive event 被丢弃并写审计摘要。
- shutdown wait 后无线程残留。

- [ ] **Step 4: 实现 ProactiveService shim**

要求：

- `proactive_message` 改为 `chat.proactive` event。
- `can_fire` 同时依赖前端运行态投影和 Python 策略。
- sidecar 不可用时禁止主动发言。
- `agent/proactive.py` 只保留迁移兼容 shim；策略判断迁到 `python_core/services/proactive_policy.py`。
- 移除 sidecar 路径上的 `QObject`、`QThread`、`Signal` 依赖。

### Task 3.2：实现 SpeechService / VisionService 和 Tauri 桌面能力

**Files:**
- Create: `python_core/services/speech_service.py`
- Create: `python_core/services/tts_pipeline.py`
- Create: `python_core/services/vision_service.py`
- Modify: `stt/manager.py`
- Modify: `tts/`
- Modify: `tests/test_tts_pipeline.py`
- Modify: `vision/manager.py`
- Create: `apps/desktop/src-tauri/src/audio.rs`
- Create: `apps/desktop/src-tauri/src/recorder.rs`
- Create: `apps/desktop/src-tauri/src/screenshot.rs`
- Test: `tests/rpc_contract/test_speech_vision_methods.py`
- Test: `apps/desktop/src-tauri/tests/media_contract.rs`

- [ ] **Step 1: 写 TTS/STT/OCR 取消测试**

Test coverage:

- TTS 取消后不再发播放事件。
- STT 超时和取消互斥终态。
- OCR 长文本走 handle。
- `stt.stop_recording` 不是 RPC 任务取消。
- audio/image/text handle 被 owner request 取消、失败或 shutdown 时释放。
- TTS first segment 超过预算时生成 `speech.tts_slow_first_segment` 诊断事件。
- `tts/adapters/gptsovits.py` 不再使用 stdout `print()` 输出调试信息。
- `ui/chat/tts_pipeline.py` 的 UI 编排迁入 `SpeechService`、`chatStore` 和 `audioStore` 后，旧文件不在 sidecar 导入链中。
- `tests/test_tts_pipeline.py` 导入 `python_core.services.tts_pipeline`，不再导入 `ui.chat.tts_pipeline`。

- [ ] **Step 2: 实现 SpeechService**

要求：

- TTS 保留 GPT-SoVITS 原版兼容和当前模式边界。
- STT 只处理 Tauri 传入的 audio handle。
- 不在 Python sidecar 播放音频。
- `TTSPipelineController` 归属 `python_core/services/tts_pipeline.py`，只负责文本分段、请求 TTS adapter、生成 audio handle 和发布事件。
- `SpeechService` 只编排 RPC request、cancel token、handle owner 和 `TTSPipelineController`，不包含 UI 播放状态。
- 播放、暂停、停止、设备错误由 Tauri `audio.rs` 和前端 `audioStore` 处理。

- [ ] **Step 3: 实现 VisionService**

要求：

- 不截图，只识别 Tauri 传入 image handle。
- OCR 原文超长时返回 handle。
- 截图清理由 Tauri 受控目录执行。

- [ ] **Step 4: 实现 Rust 桌面能力**

要求：

- `audio.rs` 播放音频 handle。
- `recorder.rs` 录音生成 audio handle。
- `screenshot.rs` 截图生成 image handle。
- 所有 handle 都在 RuntimePaths scope 内。
- 录音、播放和截图命令都必须出现在 capability manifest 中。
- 录音设备不可用、截图被拒绝、播放失败都返回结构化错误并释放临时 handle。

### Task 3.3：实现 Vue ChatPanel 和桌宠窗口

**Files:**
- Modify: `apps/desktop/frontend/src/components/ChatPanel.vue`
- Create: `apps/desktop/frontend/src/components/PassiveBubble.vue`
- Create: `apps/desktop/frontend/src/components/SpriteView.vue`
- Modify: `apps/desktop/frontend/src/stores/audioStore.ts`
- Modify: `apps/desktop/frontend/src/stores/sttStore.ts`
- Modify: `apps/desktop/frontend/src/stores/chatStore.ts`
- Create: `apps/desktop/e2e/chat.spec.ts`
- Test: `apps/desktop/frontend/src/components/ChatPanel.spec.ts`

- [ ] **Step 1: 实现聊天状态**

要求：

- idle、streaming、busy、error、retryable。
- 发送按钮忙碌态表示停止当前 request。
- 停止动作内部调用 `sidecar.cancel`。
- 失败保留输入。

- [ ] **Step 2: 实现立绘和被动气泡**

要求：

- 角色资源通过 `characterStore` 获取。
- 情绪切换不依赖 Qt。
- 被动气泡可点击恢复主对话。

- [ ] **Step 3: 实现音频和 STT store**

要求：

- `audioStore` 不持久化音频状态。
- `sttStore` 不持久化录音状态。
- sidecar restart 后进入可重试错误态。
- ChatPanel、PassiveBubble、SpriteView 全部使用 `<script setup lang="ts">`。
- 停止、重试、TTS 播放和 STT 录音按钮都有键盘焦点态和 aria label。

- [ ] **Step 4: 创建聊天 E2E**

`apps/desktop/e2e/chat.spec.ts` 必须覆盖：

- chat mock send / streaming / stop / retry。
- 被动气泡点击恢复主对话。
- TTS 首段事件、播放失败、停止播放和迟到事件丢弃。
- STT 录音开始、停止、超时和取消互斥终态。
- sidecar restart 后 UI 进入 retryable，不保留旧 request pending。
- 桌宠窗口缩放、立绘资源加载失败占位、键盘焦点顺序和 aria label。

### Task 3.4：Phase 3 出口验证

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/test_agent_manager.py tests/test_llm_manager_tools.py tests/test_tts_pipeline.py tests/test_stt_adapter.py tests/test_vision.py tests/rpc_contract/test_chat_methods.py tests/rpc_contract/test_speech_vision_methods.py -q
python -m pytest tests/rpc_contract/test_stdout_zero_pollution.py -q
python -m pytest tests/ -q
Set-Location apps/desktop/src-tauri
cargo test
Set-Location ..
pnpm test
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:chat
pnpm run e2e:responsive
Set-Location E:/Project/Yumetsuki
python scripts/check_replacement_status.py --phase 3 --record-from-last-run
```

Expected:

```text
全部通过。
```

## Phase 4：日志、插件、MCP、诊断迁移

**目标:** 迁移日志工作台、插件页、MCP 页和诊断页，完成权限确认、插件 / MCP worker 治理、诊断包脱敏和高频日志压测。

### Task 4.1：实现 LogService / DiagnosticService RPC

**Files:**
- Create: `python_core/services/log_service.py`
- Create: `python_core/services/diagnostic_service.py`
- Modify: `core/log_service.py`
- Modify: `core/diagnostic_bundle.py`
- Test: `tests/rpc_contract/test_logs_diagnostics_methods.py`
- Test: `tests/security/test_diagnostic_redaction.py`

- [ ] **Step 1: 写日志和诊断 RPC 测试**

Test coverage:

- `logs.query` 分页。
- `logs.subscribe` 批量事件。
- `logs.export` 输出 allowlist。
- `diagnostics.run` 返回 accepted。
- `diagnostics.export` 敏感扫描失败时删除临时包。
- 诊断包只允许包含固定文件名：`metadata.json`、`events.jsonl`、`manifest.json`、`config_health_summary.json`、`tool_audit_summary.json`、`runtime_summary.json`。
- 任意额外文件、符号链接、绝对路径、隐藏文件、压缩包嵌套都使导出失败。

- [ ] **Step 2: 实现 LogService facade**

要求：

- 查询和导出都脱敏。
- 订阅支持 pause / resume。
- 慢消费者降级为摘要事件。

- [ ] **Step 3: 实现 DiagnosticService facade**

要求：

- `include_sensitive=true` 首版拒绝。
- 导出只包含 allowlist。
- 扫描命中敏感项时导出失败并删除临时目录。
- `metadata.json` 只包含 app version、schema hash、platform、timestamp、feature flags 摘要。
- `events.jsonl` 只包含已脱敏事件，单行超过 64 KiB 时转摘要。
- `config_health_summary.json` 不包含真实配置值。
- `tool_audit_summary.json` 不包含工具原始输出。
- `runtime_summary.json` 不包含用户名完整路径；路径只保留 basename/hash。

### Task 4.2：实现 Tool / Plugin / MCP / Security 服务

**Files:**
- Create: `python_core/services/tool_service.py`
- Create: `python_core/services/plugin_service.py`
- Create: `python_core/services/mcp_service.py`
- Create: `python_core/services/security_confirmation_service.py`
- Create: `python_core/services/worker_stdio.py`
- Modify: `core/tool_registry.py`
- Modify: `core/plugin_host.py`
- Modify: `core/mcp_host.py`
- Modify: `plugins/system_control/command.py`
- Test: `tests/rpc_contract/test_tools_plugins_mcp_methods.py`
- Test: `tests/rpc_contract/test_worker_stdio_capture.py`
- Test: `tests/security/test_tool_confirmation.py`

- [ ] **Step 1: 写权限确认测试**

Test coverage:

- 高风险工具发出 `security.confirm_required` event。
- approve/deny 必须携带 `confirm_token`。
- token 单次使用。
- sidecar restart 取消 pending confirmation。
- 命令执行参数必须是 argv 数组。
- 权限确认矩阵覆盖配置保存、打开 URL、OCR 截图、MCP stdio、外部插件、命令执行、文件保存。
- 每个 capability 都覆盖 allow、deny、confirm、audit、revoke。
- confirm token 负向用例覆盖 expired、reused、request mismatch、capability mismatch、scope mismatch、sidecar restart invalid。
- URL 安全覆盖 `file://`、私网 redirect、DNS rebinding、localhost、IPv6 私网、混淆主机名。
- path 安全覆盖 UNC、符号链接、路径穿越、驱动器前缀、保留设备名、用户选择 scope 外写入。

- [ ] **Step 2: 实现 SecurityConfirmationService**

要求：

- 状态机：created -> pending_user -> approved / denied / expired / cancelled。
- 持久授权可撤销。
- 审计字段包含 request_id、trace_id、capability、scope。
- confirm token 绑定 request_id、capability、scope hash、deadline 和 sidecar generation。
- sidecar restart 后所有 token 失效。
- token 不进入 Pinia 持久化，不写入诊断包。

- [ ] **Step 2A: 冻结权限确认矩阵**

Create: `tests/security/confirmation_matrix.md`

内容必须包含：

| 操作 | capability | 默认策略 | 必须确认 | 审计字段 | 撤销策略 |
|---|---|---|---|---|---|
| 配置保存 | `config.write` | confirm | API、MCP、外部路径变更 | request_id、trace_id、scope_hash、base_version | 取消持久授权并恢复逐次确认 |
| 打开 URL | `opener.open_url` | deny 私网 / confirm 外部 | 外部浏览器、私网、redirect | normalized_url_hash、resolved_ip_class | 清除 host allowlist |
| OCR 截图 | `desktop.screenshot` | confirm | 首次截图、跨显示器截图 | display_id、image_handle、scope | 清除截图授权 |
| MCP stdio | `mcp.spawn` | confirm | 启动外部 MCP server | command_hash、argv_hash、cwd_scope | 停止 worker 并撤销 server 授权 |
| 外部插件 | `plugin.external` | confirm | 导入、启用、执行 | plugin_id、manifest_hash、permissions | 禁用插件并撤销 permission |
| 命令执行 | `tool.command` | deny 默认 | 每次高风险命令 | argv_hash、cwd_scope、env_policy | 无持久授权，逐次确认 |
| 文件保存 | `filesystem.write` | confirm scope | 用户目录外、覆盖文件 | target_hash、scope_id、overwrite | 清除目录授权 |

- [ ] **Step 3: 实现 ToolService / PluginService / McpService**

要求：

- 外部插件 worker stdout/stderr 不污染 sidecar stdout。
- 内置插件和 Python tool 调用也必须通过 `worker_stdio.capture_stdio()` 包裹，捕获到的 stdout/stderr 只进入插件日志或审计摘要。
- `worker_stdio.capture_stdio()` 必须使用上下文管理器或 `try/finally` 恢复原 stdout/stderr；即使插件导入、工具执行、MCP 启动或日志写入中途抛异常，也不能把捕获管道泄漏到后续 sidecar 请求。
- MCP stdout reader 和 stderr drain 独立。
- worker 崩溃产生结构化事件。
- 工具结果进入前先做大小限制和不可信标记。
- stdout 大输出转 handle 或摘要，不允许单 frame 超过 256 KiB。
- stderr flood 不阻塞 stdout reader。
- timeout cancel 后 worker 子进程树必须退出。
- close worker 后不得遗留子进程。
- worker generation 必须绑定 request_id；worker crash 后迟到 stdout/stderr 不能写入新 generation。
- `tests/rpc_contract/test_worker_stdio_capture.py` 必须覆盖外部插件、内置插件、MCP stdio、大 stdout、stderr flood、worker crash、capture 上下文异常后 stdout/stderr 恢复、cancel 后迟到输出和 sidecar stdout 零污染。

- [ ] **Step 4: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/rpc_contract/test_tools_plugins_mcp_methods.py tests/rpc_contract/test_worker_stdio_capture.py tests/rpc_contract/test_stdout_zero_pollution.py tests/security/test_tool_confirmation.py tests/security/test_url_path_safety.py -q
```

Expected:

```text
全部通过。
```

### Task 4.3：实现前端日志页

**Files:**
- Create: `apps/desktop/frontend/src/pages/logs/ConversationLogPage.vue`
- Create: `apps/desktop/frontend/src/pages/logs/SystemLogPage.vue`
- Modify: `apps/desktop/frontend/src/stores/logStore.ts`
- Create: `apps/desktop/e2e/logs-tools.spec.ts`
- Create: `apps/desktop/e2e/stress.spec.ts`
- Test: `apps/desktop/frontend/src/pages/logs/*.spec.ts`

- [ ] **Step 1: 实现 VirtualLogList 完整状态**

要求：

- loading、empty、streaming、paused、filtering、error。
- 10k 日志批量进入时详情区稳定。
- 拖选文本时暂停刷新。
- 复制日志详情时复制脱敏文本。
- 导出日志时调用 `logs.export`，不直接读文件。

- [ ] **Step 2: 验证**

`apps/desktop/e2e/logs-tools.spec.ts` 必须覆盖：

- 对话日志和平台日志分页、筛选、拖选暂停、复制脱敏文本、导出。
- 插件导入、权限确认、stdout/stderr 日志展示、崩溃审计 id。
- MCP server 启动确认、stderr flood 摘要、timeout cancel 和 close 终态。
- 诊断运行、取消、导出、redaction-failed 和打开目录权限。

`apps/desktop/e2e/stress.spec.ts` 必须覆盖：

- 10k 日志批量进入时列表 FPS 不低于 `apps/desktop/perf/budgets.json`。
- 日志订阅 pause/resume 后无重复行、无详情区抖动。
- 慢消费者触发摘要事件，不阻塞 UI 主线程。

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
pnpm run e2e:logs-tools
pnpm run e2e:stress
```

Expected:

```text
日志页单元测试、日志工具 E2E 和 10k 日志压力测试通过。
```

### Task 4.3A：实现前端插件页

**Files:**
- Create: `apps/desktop/frontend/src/pages/tools/PluginPage.vue`
- Modify: `apps/desktop/frontend/src/stores/pluginStore.ts`
- Modify: `apps/desktop/e2e/logs-tools.spec.ts`
- Test: `apps/desktop/frontend/src/pages/tools/PluginPage.spec.ts`

- [ ] **Step 1: 实现插件页面状态**

要求：

- 状态覆盖 loading、empty、permission-required、running、failed、retryable、disabled。
- 插件导入必须展示 manifest 摘要、权限列表和确认对话。
- 插件 stdout/stderr 只作为插件日志展示，不显示为 sidecar 协议消息。
- 插件崩溃时显示结构化错误和审计 id。

- [ ] **Step 2: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
pnpm run e2e:logs-tools
```

Expected:

```text
插件页单元测试和 E2E 通过。
```

### Task 4.3B：实现前端 MCP 页

**Files:**
- Create: `apps/desktop/frontend/src/pages/tools/McpPage.vue`
- Modify: `apps/desktop/frontend/src/stores/mcpStore.ts`
- Modify: `apps/desktop/e2e/logs-tools.spec.ts`
- Test: `apps/desktop/frontend/src/pages/tools/McpPage.spec.ts`

- [ ] **Step 1: 实现 MCP 页面状态**

要求：

- 状态覆盖 disconnected、starting、connected、degraded、failed、stopping。
- 启动外部 MCP server 必须展示 argv 摘要、cwd scope、env policy 和确认对话。
- stderr flood 显示为 MCP 诊断摘要。
- timeout cancel 和 close 后 UI 必须进入终态，不保留 pending 状态。

- [ ] **Step 2: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
pnpm run e2e:logs-tools
```

Expected:

```text
MCP 页单元测试和 E2E 通过。
```

### Task 4.3C：实现前端诊断页

**Files:**
- Create: `apps/desktop/frontend/src/pages/diagnostics/DiagnosticsPage.vue`
- Modify: `apps/desktop/frontend/src/stores/diagnosticStore.ts`
- Modify: `apps/desktop/e2e/logs-tools.spec.ts`
- Test: `apps/desktop/frontend/src/pages/diagnostics/DiagnosticsPage.spec.ts`

- [ ] **Step 1: 实现诊断页**

要求：

- idle、running、cancelling、failed、exported、redaction-failed。
- `redaction-failed` 不提供继续导出按钮。
- 不持久化报告路径。
- 展示 allowlist 文件名，不展示真实本地路径。
- 导出完成只展示文件 basename/hash 和打开目录按钮。
- 打开目录按钮走 Tauri capability 和 path scope。

- [ ] **Step 2: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki/apps/desktop
pnpm test
pnpm run test:a11y
pnpm run e2e:logs-tools
```

Expected:

```text
诊断页单元测试、a11y 和 E2E 通过。
```

### Task 4.4：Phase 4 出口验证

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/test_log_service.py tests/test_mcp_host.py tests/test_tool_registry.py tests/test_diagnostic_bundle.py tests/rpc_contract/test_logs_diagnostics_methods.py tests/rpc_contract/test_tools_plugins_mcp_methods.py -q
python -m pytest tests/rpc_contract/test_worker_stdio_capture.py tests/rpc_contract/test_stdout_zero_pollution.py -q
python -m pytest tests/security/ -q
python -m pytest tests/ -q
Set-Location apps/desktop/src-tauri
cargo test
Set-Location ..
pnpm test
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:logs-tools
pnpm run e2e:stress
pnpm run e2e:responsive
Set-Location E:/Project/Yumetsuki
python scripts/check_replacement_status.py --phase 4 --record-from-last-run
```

Expected:

```text
全部通过。
```

## Phase 5：PySide6 完全退场

**目标:** 在 Tauri/Vue 主线覆盖旧行为并通过双跑验证后，删除 PySide6 依赖、旧 Qt 入口、旧 UI 主实现和旧 PySide6 绑定测试。

**强制执行顺序:** `Task 5.1 -> Task 5.1A -> Task 5.4 -> Task 5.4A -> Task 5.2 -> Task 5.3`。`Task 5.4` 必须在删除旧 PySide6 主线前证明 sidecar 在无 PySide6 隔离环境可运行；`Task 5.4A` 必须在删除前补齐 Phase 4-only 替代测试的 Phase 5 pre-delete 记录；`Task 5.3` 是最终出口，必须在 no-PySide6 隔离环境 smoke、删除前替代验证、旧主线删除和发布包生成后执行。

### Task 5.1：实现退场检查脚本

**Files:**
- Create: `scripts/check_no_pyside6_in_sidecar.py`
- Create: `schemas/release_manifest.schema.json`
- Create: `scripts/check_release_manifest.py`
- Create: `scripts/check_release_forbidden_content.py`
- Create: `scripts/check_release_reproducibility.py`
- Create: `scripts/check_final_capabilities_match_build.py`
- Create: `scripts/check_perf_budgets.py`
- Create: `requirements-sidecar.txt`
- Test: `tests/security/test_release_manifest.py`
- Test: `tests/security/test_release_forbidden_content.py`
- Test: `tests/security/test_release_reproducibility.py`
- Test: `tests/perf/test_perf_budgets.py`

- [ ] **Step 1: 写 no-PySide6 检查**

要求：

- 扫描 `python_core/`、迁移后可达的 `agent/`、`llm/`、`tts/`、`stt/`、`vision/`、`core/`、`config/`、`session/`、`memory/`。
- 使用 AST / import graph 扫描真实可达导入链，同时使用文本 suspect 扫描兜底动态加载和字符串引用。
- 命中 `PySide6` import 失败。
- 命中 `QApplication`、`QObject`、`QThread`、`Signal`、`QtWebEngine`、`ui.` sidecar 导入链时失败。
- 命中 `importlib.import_module("PySide6")`、`__import__("PySide6")`、`QtWebEngine`、`PySide6` 字符串形式动态加载时失败，并输出 suspect file。
- import graph 扫描必须以 `python_core.sidecar_main`、首版 facade 和 RPC registry 为入口，输出每条命中链路。
- 文本 suspect 扫描命中时不得自动豁免；必须加入显式 allowlist，allowlist 只能用于迁移归档和测试 fixture。
- 不扫描归档目录。
- 同时运行 `scripts/check_no_stdout_in_sidecar.py`，保证退场后的 sidecar 仍无 stdout 污染。

- [ ] **Step 2: 写 release manifest 检查**

要求：

- 输入 Tauri bundle、resources、sidecar、frontend dist、配置样例。
- 命中 PySide6 wheel、Qt DLL、QtWebEngine、真实 `data/config/*.yaml`、日志、截图、浏览器 profile、记忆库、模型缓存时失败。
- 输出 `release_manifest`。
- `schemas/release_manifest.schema.json` 必须固化 manifest 字段、类型、必填项、hash 正则、size 正整数约束和 `approval_records` 脱敏约束。
- `scripts/check_release_manifest.py` 必须先用 `schemas/release_manifest.schema.json` 校验 manifest，再做 artifact 重算、禁止内容和预算检查。
- `release_manifest` schema 必须包含：

```json
{
  "app_version": "string",
  "schema_hash": "string",
  "generated_at": "ISO-8601 string",
  "target_triple": "string",
  "build_profile": "release",
  "build_inputs": {
    "git_commit": "string",
    "source_tree_status": "clean",
    "catalog_path": "python_core/rpc/schema/catalog.json",
    "frontend_dist": "path",
    "sidecar_artifact": "path",
    "tauri_bundle": "path",
    "resources": "path"
  },
  "toolchain_versions": {
    "python": "string",
    "node": "string",
    "pnpm": "string",
    "rustc": "string",
    "cargo": "string",
    "tauri": "string"
  },
  "lockfile_hashes": {
    "requirements_sidecar": "sha256",
    "package_lock": "sha256",
    "cargo_lock": "sha256"
  },
  "artifact_hashes": {
    "tauri_bundle": "sha256",
    "sidecar_artifact": "sha256",
    "frontend_dist": "sha256",
    "resources": "sha256",
    "capability_manifest": "sha256"
  },
  "scanned_artifacts": [
    {
      "path": "string",
      "artifact_sha256": "sha256",
      "type": "bundle|sidecar|frontend|resource"
    }
  ],
  "bundle_size_bytes": 1,
  "sidecar_size_bytes": 1,
  "frontend_size_bytes": 1,
  "resource_size_bytes": 1,
  "installer_size_bytes": 1,
  "scan_rule_version": "string",
  "scanner_version": "string",
  "forbidden_content_rules": ["string"],
  "perf_measurement_source": "apps/desktop/perf/results.json",
  "dependency_summary": {
    "python": "string",
    "node": "string",
    "rust": "string",
    "tauri": "string"
  },
  "forbidden_paths_scan": {
    "passed": true,
    "matches": []
  },
  "pyside6_import_scan": {
    "passed": true,
    "matches": []
  },
  "stdout_scan": {
    "passed": true,
    "matches": []
  },
  "reproducibility_scan": {
    "passed": true,
    "matches": []
  },
  "approval_records": []
}
```

- `approval_records` 只允许记录批准摘要、预算例外和审计 id，不允许记录个人路径或真实 token。
- manifest 中所有 hash 字段必须是 sha256，且与当前 artifact 重算值一致。
- manifest 中 `schema_hash` 必须与 `scripts/check_rpc_schema_contract.py` 校验的 catalog hash 一致。
- manifest 中 `artifact_hashes.capability_manifest` 必须由最终 `tauri build` 实际使用的 `capabilities/*.json`、`tauri.conf.json` capability 相关配置和注册 command 集合生成。
- `perf_measurement_source` 指向本次构建的实测结果文件 `apps/desktop/perf/results.json`，该文件必须记录测量命令、机器摘要、时间戳、各预算项实测值和脱敏规则版本。
- 真实 manifest 中 `bundle_size_bytes`、`sidecar_size_bytes`、`frontend_size_bytes`、`resource_size_bytes`、`installer_size_bytes` 必须是重算后的正整数，不能保留示例值。

- [ ] **Step 2A: 写 forbidden content 检查**

Create: `scripts/check_release_forbidden_content.py`

禁止发布包、resources、frontend dist、sidecar artifact 中出现：

- `.env`、`.env.local`、`.env.*`。
- SSH key、private key、OpenAI / Anthropic / Gemini / Azure token。
- PEM 私钥块、JWT、Bearer token、Azure/OpenAI/Anthropic/Gemini 常见 key 前缀和高熵 token。
- cookie、authorization header、browser profile。
- 真实 `data/config/*.yaml`、`data/logs/**`、`data/memory/**`、截图、音频、OCR 原文。
- 私有 URL 的 path/query、localhost 调试服务地址、个人 Windows 用户目录。
- PySide6 wheel、Qt DLL、Qt plugin、QtWebEngine、旧 `ui/` 运行时代码。

扫描要求：

- 递归扫描 `zip`、`asar`、NSIS 解包目录、wheel、resources、SQLite/Chroma 目录和文本资源。
- 对二进制文件执行可打印字符串扫描。
- URL 扫描必须检查 query、fragment、embedded credential、localhost、私网 IP、IPv6 私网和混淆主机名。
- 命中 SQLite/Chroma 运行期数据库、缓存、日志或本地记忆库时失败。
- 命中压缩包嵌套时必须展开扫描，无法展开时失败。

命中时输出文件路径、规则 id 和脱敏片段，退出码为 1。

- [ ] **Step 2B: 写发布可复现检查**

Create: `scripts/check_release_reproducibility.py`

要求：

- 输入 `--bundle <path>`，读取 release manifest 并重算 artifact sha256。
- 校验 `requirements-sidecar.txt`、Node lockfile、`Cargo.lock` hash。
- 校验 Python / Node / Rust / Tauri toolchain 版本与 manifest 一致。
- 校验 `catalog.json` schema hash、TS/Rust/Python schema 投影和 release manifest 一致。
- 校验构建输入路径不包含个人目录、临时目录或仓库外未声明资源。
- 校验同一输入重复执行两次时 manifest 中稳定字段一致；`generated_at` 只能影响允许变动字段。
- 任一 hash 漂移、lockfile 缺失、toolchain 缺失、artifact 未扫描或 schema hash 不一致时退出码为 1。

- [ ] **Step 2C: 写最终 capability 构建一致性检查**

Create: `scripts/check_final_capabilities_match_build.py`

要求：

- 解析 `apps/desktop/src-tauri/tauri.conf.json`、`apps/desktop/src-tauri/capabilities/*.json` 和最终 `tauri build` 输入目录。
- 校验最终构建使用的 capability 文件 sha256 与 `release_manifest.artifact_hashes.capability_manifest` 一致。
- 校验安全复审时扫描的 capability 集合与最终构建集合一致，不允许 build 时新增未审 command、plugin permission 或 path scope。
- 校验 `invoke_handler!` 注册 command、`#[tauri::command]` 定义和 capability allowlist 三者一致。
- 任一文件漂移、未扫描 capability 参与构建、capability 中出现未注册 command 或 command 未分类时退出码为 1。

- [ ] **Step 2D: 写性能预算检查**

Create: `scripts/check_perf_budgets.py`

使用 `apps/desktop/perf/budgets.json` 和 `apps/desktop/perf/results.json` 校验：

- cold startup。
- warm startup。
- sidecar hello。
- idle CPU。
- sidecar baseline memory。
- chat mock first token。
- TTS mock first segment。
- 10k logs FPS。
- frontend bundle size。
- sidecar artifact size。
- resource size。
- installer size。

`apps/desktop/perf/results.json` 必须由 `pnpm run e2e:startup`、`pnpm run e2e:stress`、诊断 perf report 和发布包扫描结果生成，记录 cold/warm startup、idle CPU、sidecar baseline memory、10k logs FPS、各 artifact size 的实测值；禁止手写空结果。

Phase 5 必须把所有 size budget 从 0 调整为真实阈值：

- `frontend_size_budget_bytes`
- `sidecar_artifact_size_budget_bytes`
- `resource_size_budget_bytes`
- `installer_size_budget_bytes`
- `bundle_size_budget_bytes`

任一 size budget 仍为 0 时失败。超阈值失败，除非 `release_manifest.approval_records` 有用户确认的预算例外。

- [ ] **Step 3: 创建 requirements-sidecar.txt**

要求：

- 包含 sidecar 必需 Python 依赖。
- 不包含 PySide6。
- 迁移期 `requirements.txt` 可保留旧 UI 依赖；Phase 5 发布 gate 使用 `requirements-sidecar.txt`。

- [ ] **Step 4: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python scripts/check_no_pyside6_in_sidecar.py
python scripts/check_no_stdout_in_sidecar.py
python scripts/check_rpc_schema_contract.py
python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_release_forbidden_content.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_release_reproducibility.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_final_capabilities_match_build.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_perf_budgets.py
python -m pytest tests/security/test_release_manifest.py tests/security/test_release_forbidden_content.py tests/security/test_release_reproducibility.py tests/perf/test_perf_budgets.py -q
```

Expected:

```text
退场检查、发布包检查、敏感内容检查和性能预算检查全部通过。
```

### Task 5.1A：冻结打包和升级策略

**Files:**
- Create: `docs/release/desktop-packaging.md`
- Create: `scripts/install_release_artifact_for_smoke.ps1`
- Create: `scripts/smoke_windows_clean_machine.ps1`
- Modify: `apps/desktop/package.json`
- Modify: `apps/desktop/src-tauri/tauri.conf.json`
- Modify: `apps/desktop/src-tauri/Cargo.toml`
- Modify: `requirements-sidecar.txt`
- Test: `tests/security/test_release_manifest.py`
- Test: `tests/release/test_windows_clean_machine_smoke.py`

- [ ] **Step 1: 写打包策略文档**

Create: `docs/release/desktop-packaging.md`

内容必须包含：

- Python 版本、Node 版本、Rust toolchain 版本和 Tauri 版本。
- Python lock 策略：`requirements-sidecar.txt` 为发布依赖入口，禁止发布 gate 从旧 `requirements.txt` 打包 PySide6。
- Node lock 策略：`apps/desktop/package-lock.json` 或项目选定 lockfile 必须提交并由 CI / 本地 gate 使用。
- Rust lock 策略：`apps/desktop/src-tauri/Cargo.lock` 必须固定。
- Python sidecar 构建步骤：生成 artifact、嵌入 schema hash、复制只读 resources。
- native DLL / wheel 策略：只包含 sidecar 必需依赖，禁止 Qt / PySide6 / QtWebEngine。
- Playwright browser 策略：E2E 依赖不进入生产 bundle。
- Windows 干净机 smoke：无开发环境、无 repo、无 PySide6 环境变量时启动并通过 no-PySide6 smoke。
- 依赖升级流程：升级前记录 baseline，升级后运行全量 Phase 5 gate，失败时回滚 lockfile。

- [ ] **Step 2: 写 Windows 干净机 smoke 脚本**

Create: `scripts/install_release_artifact_for_smoke.ps1`

脚本要求：

- 参数：`-Installer <NSIS 或 MSI artifact>`、可选 `-InstallRoot <empty temp dir>`。
- 在空安装目录安装发布包，不读取仓库工作区文件。
- 返回安装后的 `Yumetsuki.exe` 绝对路径。
- 校验安装目录内不存在 PySide6 wheel、Qt DLL、QtWebEngine、旧 `ui/` 运行时代码和真实运行期数据。
- 失败时输出脱敏摘要，退出码为 1。

Create: `scripts/smoke_windows_clean_machine.ps1`

脚本要求：

- 参数：`-Exe <installed exe>`、可选 `-WorkingDir <empty temp dir>`。
- 清理 `PYTHONPATH`、`VIRTUAL_ENV`、`QT_PLUGIN_PATH`、`PYSIDE*`、repo 相关环境变量。
- 在空临时目录启动安装后的 `Yumetsuki.exe`。
- 执行 smoke commands 并解析结构化输出。
- smoke commands 必须覆盖 sidecar、设置读取、日志查询、聊天 mock、诊断 mock 和关闭。
- 检查进程退出后无 sidecar、worker、MCP 子进程残留。
- 将 smoke 摘要写入 release manifest 的 `approval_records` 或独立 smoke report，摘要不得包含个人路径。

脚本必须包含：

```powershell
& $Exe --smoke sidecar.hello
& $Exe --smoke sidecar.health
& $Exe --smoke config.get_all
& $Exe --smoke logs.query
& $Exe --smoke chat.send.mock
& $Exe --smoke diagnostics.run.mock
& $Exe --smoke diagnostics.export.mock
& $Exe --smoke sidecar.shutdown
```

Expected:

```text
所有 smoke 命令返回结构化成功结果；环境中未安装 PySide6 时仍通过。
```

- [ ] **Step 3: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
Select-String -Path 'docs/release/desktop-packaging.md' -Pattern 'Python','Node','Rust','Tauri','requirements-sidecar','Cargo.lock','Windows 干净机','Playwright'
python -m pytest tests/security/test_release_manifest.py tests/release/test_windows_clean_machine_smoke.py -q
$InstalledExe = powershell -ExecutionPolicy Bypass -File scripts/install_release_artifact_for_smoke.ps1 -Installer apps/desktop/src-tauri/target/release/bundle/nsis/Yumetsuki-setup.exe
powershell -ExecutionPolicy Bypass -File scripts/smoke_windows_clean_machine.ps1 -Exe $InstalledExe
```

Expected:

```text
打包策略关键项全部命中，release manifest 测试通过。
```

### Task 5.4：No-PySide6 隔离环境 smoke

**Files:**
- Create: `scripts/run_no_pyside6_sidecar_smoke.ps1`
- Create: `tests/migration/test_no_pyside6_environment_smoke.py`
- Modify: `scripts/check_no_pyside6_in_sidecar.py`

- [ ] **Step 1: 写无 PySide6 环境 smoke 测试**

Create: `tests/migration/test_no_pyside6_environment_smoke.py`

Test coverage:

- `importlib.util.find_spec("PySide6") is None`。
- 在不安装 PySide6 的 Python 环境中 import `python_core.sidecar_main`。
- `sidecar.hello` 返回 selected protocol、schema hash 和 capabilities。
- `sidecar.health` 返回 healthy。
- `config.get_all` 返回脱敏配置快照。
- 首版 facade 路径至少各执行一次，防止业务 facade 延迟导入 Qt 只在业务路径暴露：`chat.send.mock`、`tts.synthesize.mock`、`ocr.recognize.mock`、`config.get_all`、`character.list`、`logs.query`、`diagnostics.run.mock`、`diagnostics.export.mock`、`tools.list`、`tools.call --dry-run`、`plugins.status`、`mcp.list_servers`、`security.list_grants`、`proactive.start`、`proactive.stop`。
- 至少一次 `plugins.status` 或 `tools.call --dry-run` 必须触发 fake worker stdout/stderr 捕获异常后恢复；恢复后立即执行 `sidecar.hello` 和 `config.get_all`，证明 `worker_stdio.capture_stdio()` 异常路径不污染后续请求。
- `sidecar.shutdown` 正常释放 handle 和 worker。
- sidecar stdout 每一行都能被 `decode_frame()` 解析。
- stderr 可以包含诊断日志，但不得包含真实 token、个人路径或未脱敏配置值。

- [ ] **Step 2: 写隔离 venv 执行脚本**

Create: `scripts/run_no_pyside6_sidecar_smoke.ps1`

脚本要求：

- 创建临时 venv。
- 只安装 `requirements-sidecar.txt`。
- 不读取开发机已有 venv、全局 site-packages 或旧 `requirements.txt`。
- 在隔离 venv 中运行 `tests/migration/test_no_pyside6_environment_smoke.py`。
- 运行完成后删除临时 venv，失败时保留脱敏日志路径。

- [ ] **Step 3: 验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
powershell -ExecutionPolicy Bypass -File scripts/run_no_pyside6_sidecar_smoke.ps1
```

Expected:

```text
隔离 venv 中未安装 PySide6，sidecar smoke 通过，stdout 只包含协议帧。
```

### Task 5.4A：Phase 5 删除前替代测试验证

**Files:**
- Modify: `tests/migration/replacement_status.json`
- Modify: `scripts/check_replacement_status.py`

此任务是删除旧 PySide6 主线前的硬 gate。它用于补齐 Phase 4-only 替代项在 Phase 5 的 pre-delete 通过记录，避免这些替代项因为只在 Phase 4 首次出现而无法满足“连续两个阶段通过”。

Phase 4-only 替代项必须在本任务中显式覆盖：

- `tests/test_diagnostics_page.py`
- `tests/test_conversation_log_page.py`
- `tests/test_system_log_page.py`
- `tests/test_plugin_import.py`

- [ ] **Step 1: 运行 Phase 4-only 替代项聚焦验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python -m pytest tests/rpc_contract/test_logs_diagnostics_methods.py tests/rpc_contract/test_tools_plugins_mcp_methods.py -q
Set-Location apps/desktop/src-tauri
cargo test --test media_contract
Set-Location ..
pnpm test
pnpm run test:a11y
pnpm run e2e:logs-tools
pnpm run e2e:stress
pnpm run e2e:responsive
```

Expected:

```text
日志、诊断、插件、MCP、前端 a11y、压力和响应式替代验证全部通过。
```

- [ ] **Step 2: 运行删除前全量替代验证**

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python scripts/check_test_inventory.py
python scripts/check_pyside6_test_replacement.py
python -m pytest tests/rpc_contract/test_logs_diagnostics_methods.py tests/rpc_contract/test_tools_plugins_mcp_methods.py -q
Set-Location apps/desktop/src-tauri
cargo test --test media_contract
Set-Location ..
pnpm test
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:settings
pnpm run e2e:chat
pnpm run e2e:logs-tools
pnpm run e2e:stress
pnpm run e2e:responsive
Set-Location E:/Project/Yumetsuki
python scripts/check_replacement_status.py --phase 5 --record-from-last-run --pre-delete
python scripts/check_replacement_status.py --phase 5 --pre-delete
```

Expected:

```text
每个 PySide6 绑定测试替代项都有连续两个阶段通过记录，Phase 4-only 替代项已有 Phase 5 pre-delete 记录。
```

- [ ] **Step 3: 锁定 delete_approved 转正规则**

要求：

- `delete_approved` 只能在 Step 2 通过后转为 `true`。
- 转正前必须向用户列出将删除或改写的旧测试、`main.py`、`ui/**`、`requirements.txt` PySide6 依赖和相关文档入口。
- 用户确认删除范围后，脚本才能把对应条目的 `delete_approved` 从 `false` 改为 `true`。
- `delete_approved=false` 的条目不得删除 legacy test，也不得删除其旧 UI 参考实现。
- Phase 4-only 替代项不得只凭 Phase 4 单次记录删除；缺少 Phase 5 pre-delete 记录时脚本必须失败。
- 手工编辑 `replacement_status.json` 跳过 Step 2 的行为必须被 `scripts/check_replacement_status.py --phase 5 --pre-delete` 判定为失败。

### Task 5.2：删除旧 PySide6 主线

**Files:**
- Modify/Delete after confirmation: `main.py`
- Modify/Delete after confirmation: `ui/**`
- Modify: `requirements.txt`
- Create: `scripts/check_docs_no_stale_ui_status.py`
- Modify: `docs/architecture.md`
- Modify: `docs/development.md`
- Modify: `docs/ui-guidelines.md`
- Modify: `docs/README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 逐项确认删除范围**

执行前必须向用户说明：

- 删除路径。
- 替代实现。
- 回滚方式。
- 旧测试文件替代状态。
- 发布依赖移除状态。
- 删除前置 gate 已通过：
  - `powershell -ExecutionPolicy Bypass -File scripts/run_no_pyside6_sidecar_smoke.ps1`
  - `python scripts/check_replacement_status.py --phase 5 --pre-delete`
  - `python scripts/check_no_pyside6_in_sidecar.py`
  - `python scripts/check_no_stdout_in_sidecar.py`
  - `python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle`
  - `python scripts/check_final_capabilities_match_build.py --bundle apps/desktop/src-tauri/target/release/bundle`

不得在未确认时删除 `main.py` 或 `ui/**`。

- [ ] **Step 2: 删除或归档旧 UI**

要求：

- 主线不再保留 PySide6 运行时依赖。
- 文档不再把 PySide6 描述为当前主 UI。
- 历史迁移记录保留在 docs。
- `requirements.txt` 中 PySide6 相关项删除或移入迁移归档说明。
- `main.py` 若保留，只能作为 Tauri launcher 或迁移说明入口，不得创建 QApplication。

- [ ] **Step 3: 替换旧 PySide6 绑定测试**

要求：

- `tests/migration/test_inventory.md` 中每个替换测试都有新测试文件。
- 旧 PySide6 绑定测试只在替代测试连续两个阶段通过、Phase 5 pre-delete gate 通过、且 `delete_approved=true` 后删除。
- 运行 `scripts/check_test_inventory.py` 确认测试清单无缺失。
- 运行 `scripts/check_pyside6_test_replacement.py` 确认所有 PySide6 绑定测试已有替代。
- 运行 `scripts/check_replacement_status.py --phase 5` 确认每个替换项已有连续两个阶段通过记录。
- `scripts/check_replacement_status.py --phase 5` 必须同时校验已删除 legacy test 对应条目 `delete_approved=true`，且旧路径已写入 `tests/migration/test_inventory.md` 的“已退场旧测试”。
- 删除旧测试后，Phase 5 全量测试仍覆盖设置、聊天、日志、插件、MCP、诊断、启动外观和事件桥。

- [ ] **Step 4: 文档入口切换**

Modify:

- `docs/README.md`
- `CLAUDE.md`
- `docs/architecture.md`
- `docs/development.md`
- `docs/ui-guidelines.md`

要求：

- 当前主 UI 改为 Tauri / Vue。
- PySide6 状态改为已退场或迁移归档。
- 运行命令、开发命令和测试命令指向 `apps/desktop`、`apps/desktop/src-tauri`、`python_core`。
- 删除“尚未实施”“等待实施计划”等过期状态。
- 全 docs 扫描不得再命中过期主线描述，迁移归档目录除外；归档例外必须写在脚本 allowlist 中，不能靠人工解释裸命令输出。

Run:

```powershell
python scripts/check_docs_no_stale_ui_status.py
```

Expected:

```text
除明确标记为历史迁移归档的文件外无输出。
```

### Task 5.3：Phase 5 出口验证

此任务必须在 `Task 5.4A` 和 `Task 5.2` 之后执行。

Run:

```powershell
Set-Location E:/Project/Yumetsuki
python scripts/check_test_inventory.py
python scripts/check_pyside6_test_replacement.py
python scripts/check_replacement_status.py --phase 5
python scripts/check_docs_no_stale_ui_status.py
python scripts/check_no_pyside6_in_sidecar.py
python scripts/check_no_stdout_in_sidecar.py
python scripts/check_rpc_schema_contract.py
python scripts/check_release_manifest.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_release_forbidden_content.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_release_reproducibility.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_final_capabilities_match_build.py --bundle apps/desktop/src-tauri/target/release/bundle
python scripts/check_perf_budgets.py
python -m pytest tests/rpc_contract/test_method_catalog.py tests/rpc_contract/test_registry_matches_catalog.py tests/rpc_contract/test_protocol_negotiation.py tests/rpc_contract/test_error_catalog.py -q
python -m pytest tests/rpc_contract/test_task_state_machine.py tests/rpc_contract/test_event_backpressure.py tests/rpc_contract/test_event_publisher.py -q
python -m pytest tests/rpc_contract/test_sidecar_smoke.py tests/rpc_contract/test_runtime_paths.py tests/rpc_contract/test_no_pyside6_import_static.py tests/rpc_contract/test_stdout_zero_pollution.py tests/rpc_contract/test_worker_stdio_capture.py -q
python -m pytest tests/migration/test_no_pyside6_environment_smoke.py -q
python -m pytest tests/ -q
Set-Location apps/desktop/src-tauri
cargo test
Set-Location ..
pnpm test
pnpm run test:a11y
pnpm run e2e:startup
pnpm run e2e:smoke
pnpm run e2e:settings
pnpm run e2e:chat
pnpm run e2e:logs-tools
pnpm run e2e:stress
pnpm run e2e:responsive
powershell -ExecutionPolicy Bypass -File E:/Project/Yumetsuki/scripts/run_no_pyside6_sidecar_smoke.ps1
$InstalledExe = powershell -ExecutionPolicy Bypass -File E:/Project/Yumetsuki/scripts/install_release_artifact_for_smoke.ps1 -Installer E:/Project/Yumetsuki/apps/desktop/src-tauri/target/release/bundle/nsis/Yumetsuki-setup.exe
powershell -ExecutionPolicy Bypass -File E:/Project/Yumetsuki/scripts/smoke_windows_clean_machine.ps1 -Exe $InstalledExe
```

Expected:

```text
除历史迁移归档扫描项外全部通过；最终发布包不含 PySide6、Qt DLL、旧 ui 运行时代码、真实运行期数据和敏感信息；隔离 venv 与 Windows 干净机 smoke 均通过。
```

## 并行执行建议

适合并行的工作包：

- Phase 1 的 Python RPC contract、Tauri supervisor、Vue skeleton 可以并行，但必须共享冻结的 envelope schema。
- Phase 2 的 ConfigService / CharacterService 和 Vue 设置页可以并行，但 schema 先冻结。
- Phase 3 的 ChatService、Speech/VisionService、Vue ChatPanel 可以并行，但取消语义统一走 `sidecar.cancel`。
- Phase 4 的日志诊断、工具安全、前端页面可以并行，但 capability 和错误码先冻结。

不适合并行的工作包：

- 同一 schema 文件的编辑。
- 同一 store 的实现与测试。
- Phase 5 删除旧 UI 与替代测试补齐。
- 发布包扫描和依赖拆分。

## 审核 Gate

计划复审必须按以下五类打分，每项 90+ 才能进入实施：

| 类别 | 必须检查 |
|---|---|
| 架构 / RPC | envelope、method catalog、错误码、取消语义、版本协商、sidecar supervisor |
| 前端 / UI | Vue/Pinia 分层、store lifecycle、持久化 allowlist、Sakura 组件、设置和诊断 parity、a11y |
| Python Core / Qt 剥离 | headless facade、旧接口 shim、stdout 纪律、TTS/STT/OCR、Proactive、插件/MCP |
| 测试 / 文档 / 退场 | 测试命令、文件级映射、双跑阶段、文档入口、Phase 1-5 可验证性 |
| 发布 / 安全 / 性能 | capability manifest、权限确认、路径/URL 安全、诊断包、发布包、性能预算 |

## 自检

- 本计划没有实施代码迁移。
- 本计划按 Phase 0-5 拆分，每个 Phase 都有聚焦验证和出口验证。
- 本计划保留 PySide6 双跑窗口，并把完全移除放到 Phase 5。
- 本计划把 `sidecar.cancel` 保持为唯一取消 wire method。
- 本计划明确每阶段合并前运行全量 Python 回归。
- 本计划等待并行 agent 90+ 复审后再进入实施。
