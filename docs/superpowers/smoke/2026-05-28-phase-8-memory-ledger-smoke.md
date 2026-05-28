# Phase 8-A 记忆账本实机验收待补记录

> 状态：Phase 8-A 已完成，本地自动化验证已通过；真实 Mem0 本地向量库写入联调待补。

## 已完成的本地验证

- `python -m pytest tests/test_memory_ledger.py tests/test_session_context.py tests/test_mem0_store.py -q`
  - 结果：`18 passed`
- `python -m pytest tests/test_agent_manager.py tests/test_logging_integration.py tests/test_system_log_page.py -q`
  - 结果：`56 passed`
- `python -m py_compile memory/ledger.py memory/mem0_store.py session/policy.py agent/manager.py ui/settings/pages/system_log_page.py`
  - 结果：通过
- `python -m pytest tests/ -q`
  - 结果：`528 passed`

## 待补实机验收矩阵

| 项目 | 状态 | 记录 |
|---|---|---|
| 真实 Mem0 写入 | 待补 | 使用本地 `data/config/memory.yaml` 与真实 embedding 模型，确认显式“记住”会写入长期记忆。 |
| 重复候选跳过 | 待补 | 连续两次输入同一显式记忆，确认只写入一次，并在平台日志看到 `memory.candidate_skipped`。 |
| 短期约束不升格 | 待补 | 输入“先不要改代码，只讨论方案”，确认不写入长期记忆。 |
| 失败日志 | 待补 | 使用无效 Mem0 / embedding 配置触发写入失败，确认平台日志记录 `memory.candidate_failed`，且不标记已升格。 |
| 平台日志筛选 | 待补 | 设置中心平台日志选择“记忆”链路，确认能看到 `memory.ledger` 事件。 |

## 记录规则

- 不记录真实本地模型完整路径、私有用户内容全文或运行期向量库文件。
- 只记录候选摘要、事件类型、错误类型和可复现步骤。
- 失败项保留为 `待修复` 或 `待复测`，不要用“理论上通过”替代实机结果。
