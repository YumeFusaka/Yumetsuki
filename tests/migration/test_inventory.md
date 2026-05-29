# UI 重构测试迁移清单

> 状态：Phase 5 退场后。新增或删除测试文件时必须同步更新本文。
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

> 旧 PySide6 绑定测试已删除；历史映射保留在“已退场旧测试”和下方替换表。

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

- `tests/rpc_contract/test_character_methods.py`
- `tests/rpc_contract/test_chat_methods.py`
- `tests/rpc_contract/test_config_methods.py`
- `tests/rpc_contract/test_envelope.py`
- `tests/rpc_contract/test_errors.py`
- `tests/rpc_contract/test_event_publisher.py`
- `tests/rpc_contract/test_framing.py`
- `tests/rpc_contract/test_logs_diagnostics_methods.py`
- `tests/rpc_contract/test_method_catalog.py`
- `tests/rpc_contract/test_no_pyside6_import_static.py`
- `tests/rpc_contract/test_no_stdout_static.py`
- `tests/rpc_contract/test_protocol_negotiation.py`
- `tests/rpc_contract/test_registry_matches_catalog.py`
- `tests/rpc_contract/test_runtime_paths.py`
- `tests/rpc_contract/test_runtime_paths_schema.py`
- `tests/rpc_contract/test_speech_vision_methods.py`
- `tests/rpc_contract/test_sidecar_smoke.py`
- `tests/rpc_contract/test_shutdown_coordinator.py`
- `tests/rpc_contract/test_sidecar_import_graph_no_qt.py`
- `tests/rpc_contract/test_stdout_zero_pollution.py`
- `tests/rpc_contract/test_task_state_machine.py`
- `tests/rpc_contract/test_tools_plugins_mcp_methods.py`

### Security / release / perf / migration

- `tests/security/test_capability_manifest.py`
- `tests/security/test_docs_stale_scan.py`
- `tests/security/test_release_forbidden_content.py`
- `tests/security/test_final_capabilities_match_build.py`
- `tests/security/test_release_manifest.py`
- `tests/security/test_release_reproducibility.py`
- `tests/security/test_tauri_supervisor_static.py`
- `tests/perf/test_perf_budgets.py`
- `tests/migration/test_gate_scripts.py`
- `tests/migration/test_no_pyside6_environment_smoke.py`

## 已退场旧测试

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

## PySide6 绑定测试替换表

| 旧测试 | Qt / PySide6 依赖点 | 退场动作 | 替代层 | 新测试文件 / 命令 | 双跑阶段 | 删除条件 | 回滚方式 |
|---|---|---|---|---|---|---|---|
| `tests/test_settings_window.py` | 设置窗口和 Qt 控件 | 删除 | Vue 设置页 + ConfigService | `apps/desktop/e2e/settings.spec.ts`、`apps/desktop/frontend/src/pages/settings/*.spec.ts`、`npm run e2e:settings` | Phase 2-4 | replacement status 记录连续两个阶段通过 | 保留旧测试文件并恢复 PySide6 依赖 |
| `tests/test_agent_page_events.py` | Qt Agent 页事件桥 | 删除 | RPC event publisher + Vue Agent store | `tests/rpc_contract/test_event_publisher.py`、`python -m pytest tests/rpc_contract/test_event_publisher.py -q`、`npm test` | Phase 2-4 | replacement status 记录连续两个阶段通过 | 恢复 `core/ui_event_bridge.py` 双跑 |
| `tests/test_diagnostics_page.py` | Qt 诊断页 | 删除 | Vue diagnostics page + DiagnosticService | `apps/desktop/e2e/logs-tools.spec.ts`、`tests/rpc_contract/test_logs_diagnostics_methods.py`、`npm run e2e:logs-tools` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧诊断页测试 |
| `tests/test_conversation_log_page.py` | Qt 对话日志页 | 删除 | Vue ConversationLogPage + LogService | `apps/desktop/e2e/logs-tools.spec.ts`、`npm run e2e:logs-tools` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧日志页测试 |
| `tests/test_system_log_page.py` | Qt 平台日志页 | 删除 | Vue SystemLogPage + VirtualLogList | `apps/desktop/e2e/stress.spec.ts`、`npm run e2e:stress` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧日志页测试 |
| `tests/test_feedback_toast.py` | Qt toast | 删除 | Sakura Toast | `apps/desktop/e2e/a11y.spec.ts`、`npm test`、`npm run test:a11y` | Phase 1-4 | replacement status 记录连续两个阶段通过 | 恢复旧 toast 测试 |
| `tests/test_plugin_import.py` | Qt 插件导入 UI | 删除 | Vue PluginPage + PluginService | `apps/desktop/e2e/logs-tools.spec.ts`、`tests/rpc_contract/test_tools_plugins_mcp_methods.py`、`npm run e2e:logs-tools` | Phase 4 | replacement status 记录连续两个阶段通过 | 恢复旧插件导入测试 |
| `tests/test_chat_tts_flow.py` | Qt ChatWindow + TTS 播放 | 删除 | ChatService + SpeechService + Rust audio | `apps/desktop/e2e/chat.spec.ts`、`tests/rpc_contract/test_speech_vision_methods.py`、`npm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧聊天 TTS 测试 |
| `tests/test_chat_stt_flow.py` | Qt ChatWindow + STT 录音 | 删除 | Rust recorder + SpeechService | `apps/desktop/e2e/chat.spec.ts`、`apps/desktop/src-tauri/tests/media_contract.rs`、`npm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧聊天 STT 测试 |
| `tests/test_chat_passive_bubble.py` | Qt 被动气泡 | 删除 | Vue PassiveBubble + chatStore | `apps/desktop/e2e/chat.spec.ts`、`npm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧被动气泡测试 |
| `tests/test_chat_window_scale.py` | Qt 窗口缩放 | 删除 | Tauri window + Vue ChatPanel | `apps/desktop/e2e/chat.spec.ts`、`npm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧窗口缩放测试 |
| `tests/test_stt_recorder.py` | Qt 录音 | 删除 | Rust recorder | `apps/desktop/src-tauri/tests/media_contract.rs`、`cargo test --test media_contract` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧录音测试 |
| `tests/test_audio_backends.py` | Qt 音频播放 | 删除 | Rust audio playback | `apps/desktop/src-tauri/tests/media_contract.rs`、`cargo test --test media_contract` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧音频后端测试 |
| `tests/test_sprite_manager.py` | Qt pixmap / 立绘 | 删除 | Vue SpriteView | `apps/desktop/e2e/chat.spec.ts`、`npm test`、`npm run e2e:chat` | Phase 3-4 | replacement status 记录连续两个阶段通过 | 恢复旧立绘测试 |
| `tests/test_startup_appearance.py` | Qt 启动窗 | 删除 | Tauri startup view | `apps/desktop/e2e/startup.spec.ts`、`npm run e2e:startup` | Phase 1-4 | replacement status 记录连续两个阶段通过 | 恢复旧启动窗测试 |
| `tests/test_logging_integration.py` | UI 日志桥和 Qt 页面消费 | 同名改写 | Python LogService + RPC logs contract + Vue 日志页 | `tests/test_logging_integration.py`、`python -m pytest tests/test_logging_integration.py -q`、`tests/rpc_contract/test_logs_diagnostics_methods.py`、`npm run e2e:logs-tools` | Phase 2-4 | 同名测试不导入 Qt，replacement status 记录连续两个阶段通过 | 恢复旧日志集成测试 |
| `tests/test_event_bus.py` | `core/ui_event_bridge.py` 路径 | 同名改写 | Python EventBus + RpcEventPublisher | `tests/test_event_bus.py`、`python -m pytest tests/test_event_bus.py -q`、`tests/rpc_contract/test_event_publisher.py` | Phase 1-4 | 同名测试不导入 `core/ui_event_bridge.py`、PySide6 或 Qt bridge，replacement status 记录连续两个阶段通过 | 恢复旧 bridge 双跑 |
| `tests/test_proactive.py` | `QObject/QThread/Signal` scheduler | 同名改写 | ProactiveService headless scheduler | `tests/test_proactive.py`、`python -m pytest tests/test_proactive.py -q`、`tests/rpc_contract/test_chat_methods.py` | Phase 3-4 | 同名测试不导入 Qt，replacement status 记录连续两个阶段通过 | 恢复旧 proactive scheduler |
