# 工具重复执行与聊天窗边框修复设计

> 日期：2026-05-22

## 概述

本次修复包含两个紧邻问题：

1. 聊天窗输入框和圆形按钮的顶边高光过白，导致视觉上像是“上边缘没有主题色”
2. 用户请求触发浏览器 / 文件等工具时，副作用工具会被执行两次

目标是在不重构整体架构的前提下，用最小改动修复这两个问题，并补上对应回归测试。

## 根因结论

### 一、边框顶边颜色问题

当前聊天窗样式先设置了统一主题边框颜色，但又单独覆写了：

- `border-top: 1px solid rgba(255, 255, 255, ...)`
- `border-bottom: 1px solid rgba(155, 48, 96, ...)`

由于顶边高光接近纯白，在浅色半透明背景上会被视觉上“冲掉”，造成顶边像是没有主题色，而左右和底边仍有明显颜色。

### 二、工具重复执行问题

当前存在两套工具执行入口：

1. `AgentManager.chat_stream()` 在 `plan.mode == "tool"` 时，先通过 `AgentExecutor.execute()` 真正执行一次工具
2. 同一轮请求随后仍进入 `LLMManager.chat_stream()`，而 `LLMManager` 仍向模型暴露 `tool_specs()`，模型会再次发起同一 tool call

因此重复执行的根因不是插件自身，也不是按钮重复点击，而是：

**Agent 预执行一次 + LLM tool-calling 再执行一次**

## 方案选择

### 方案 A：Agent 已执行工具后，禁用后续 LLM 的 tools

做法：

- 给 `LLMManager.chat_stream()` 增加一个显式开关，例如 `allow_tools: bool = True`
- 普通对话和需要 LLM 自主 tool-calling 的路径保持默认行为
- 当 `AgentManager` 已在 `tool` 模式下执行过工具时，后续调用 `LLMManager.chat_stream()` 时传入 `allow_tools=False`

优点：

- 直接修复根因
- 与当前分层架构一致
- 对浏览器、文件、命令这类副作用工具最安全
- 改动面小

本次采用该方案。

### 不采用的方案

- 工具去重：属于补丁思路，规则复杂且不稳
- 删除 Agent 预执行：会改动当前分层职责，不适合作为本次 bugfix

## 设计细节

### 一、聊天窗样式修复

仅调整 `ui/chat/window.py` 中输入框和圆形按钮样式：

- 保留顶边“更亮一档”的层次
- 但不再使用接近纯白的顶边
- 改为同主题的浅粉高光，让顶边仍属于 sakura 色系

目标效果：

- 顶边仍然更轻，但不会消失
- 左右下和上边缘保持统一色系
- 输入框和圆形按钮表现一致

### 二、禁止二次工具调用

#### `LLMManager`

- `chat_stream()` 新增 `allow_tools` 参数
- 当 `allow_tools=False` 时，不向 adapter 传递工具 schema
- 保持其余历史记录、thinking 事件、流式文本逻辑不变

#### `AgentManager`

- 如果当前轮由 `AgentExecutor` 已经执行过工具，则后续调用 `LLMManager.chat_stream()` 时传入 `allow_tools=False`
- `chat` 模式和 `multi_step` 模式维持现状

这样可以保证：

- 工具只在 Agent 决定的执行阶段调用一次
- LLM 仍能读取 `extra_context` 中的工具结果并正常组织回复

## 涉及文件

- `ui/chat/window.py`
  - 调整输入框和按钮的顶边颜色
- `llm/manager.py`
  - 增加 `allow_tools` 开关
- `agent/manager.py`
  - 已执行工具时调用 `LLMManager.chat_stream(..., allow_tools=False)`
- `tests/test_chat_window_scale.py`
  - 增加顶边主题色回归测试
- `tests/test_agent_manager.py`
  - 增加“tool 模式不再向 LLM 暴露 tools”回归测试

## 验证方式

### 自动化验证

- 聊天窗样式测试通过
- Agent/LLM 工具路径测试通过
- 全量 `pytest` 通过

### 手动验证

运行 `python main.py` 后确认：

1. 输入框和圆形按钮顶边能看到浅粉主题高光，而不是发白消失
2. 让角色执行“打开浏览器”“打开文件”等操作时，只触发一次副作用

## 范围边界

本次不包含：

- 重构 Agent / LLM 工具职责
- 引入工具调用去重缓存
- 调整聊天窗其他视觉参数
