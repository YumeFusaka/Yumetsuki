# 开发流程

## 环境

- Python:
  `E:/Tool/Miniconda/envs/ai/python.exe`
- 安装依赖：
  `pip install -r requirements.txt`
- 运行：
  `python main.py`
- 测试：
  `python -m pytest tests/ -q`

## 配置文件

- `data/config/api.yaml`
  API 配置
  含 key，不应提交
  其中 TTS 的 `ref_audio_path`、`reference_mode`、`prompt_lang`、`output_lang`、`prompt_text` 可能包含本地语音素材路径或私有参考文本，也按本地敏感配置处理
- `data/config/system_config.yaml`
  系统配置
- `data/config/mcp.yaml`
  MCP 实际配置
- `data/config/mcp.example.yaml`
  MCP 示例模板
- `data/config/memory.yaml`
  记忆配置
  含本地模型路径，不应提交
- `data/config/agent.yaml`
  Agent 默认配置
  可提交默认值，但个人临时调参不应随意提交

## Git 约定

- 不提交真实 API key
- 不提交个人本地配置变更，除非明确需要
- 不提交 `data/models/`（向量模型目录）
- 不提交 `data/memory/`（运行时向量数据库）
- 提交信息沿用：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`

## 兼容性约束

- 原版兼容优先：涉及 GPT-SoVITS、MCP 或其他第三方系统时，必须先保证原版接口、默认行为和返回格式不变
- 魔改支持只能通过显式扩展实现：
  - 可选字段
  - 扩展端点语义
  - 向后兼容的新增响应字段或响应头
- 禁止为了兼容桌宠端或其他魔改客户端而：
  - 修改原版默认参数值
  - 改写原版必填项约束
  - 破坏原版成功 / 失败响应格式
- 文档、设计稿和实现计划都必须显式遵循以上原则，避免出现“以桌宠端为主导致原版失配”的表述

## 测试策略

- 单元测试用 `pytest`
- 外部依赖优先 mock
- 浏览器相关行为优先区分：
  - 系统默认浏览器打开 / 搜索
  - Playwright 后台自动化 / 可见自动化
- 记忆相关改动优先覆盖非阻塞行为，避免对话结束后额外卡顿
- Agent 日志相关改动优先覆盖事件发布与日志页入口逻辑
- UI 变更至少保证：
  - 行为测试
  - `py_compile`
  - 必要时 Qt offscreen 实例化
  - 聊天窗缩放 / 滚动类调整优先补回归测试
- TTS 相关改动优先覆盖：
  - 原版 GPT-SoVITS 无 `session_id` 请求时的旧行为兼容
  - 新增扩展字段时不得改变原版 `wav` / 非流式默认路径
  - `SettingsWindow -> ChatWindow` 配置透传
  - `reference_mode` 持久化与 GPT-SoVITS 预热 / 回退策略
  - `GET /set_refer_audio?refer_audio_path=...` 调用方式与错误回退识别
  - `auto` 模式的进程内能力探测缓存，避免同一服务端在单次运行里重复首句试错
  - 句级切分边界（`。！？；` / 换行）
  - 长句软切分阈值与翻译模式更保守的分段策略
  - 情绪标签不得进入最终 TTS 文本
  - `prompt_lang` / `output_lang` 透传与语言别名兼容
  - 逐句翻译、旧轮失效、失败跳过与顺序播放
  - 拟声词、语气词、拖长音、重复音节在翻译时优先保留音感，不被语义意译破坏
  - 避免依赖真实 GPT-SoVITS 服务或真实音频设备

## 页面保存语义

### API 页面

- 只有 API 页面显示 `保存配置`
- 点击后需确认
- 只保存 API 配置
- 切页即放弃未保存编辑

### 系统页面

- 不显示保存按钮
- 配置实时写入

### 插件 / 角色页面

- 操作即时生效
- 成功 / 失败要有反馈

## 第三阶段进度

已完成：
1. 本地记忆系统（Mem0 OSS + Chroma + 本地向量模型）
2. 记忆设置页 UI
3. 记忆异步加载
4. Agent 模块（planner + executor + reflector + manager）
5. Agent 设置页日志混合时间线（用户输入 / 角色回复 / Thinking）
6. 聊天窗长文本滚动与整体缩放
7. 工具重复执行修复与聊天窗边框统一
8. 句级增量 TTS 播报接入（GPT-SoVITS）
9. 输出语言强约束与句级翻译播报
10. TTS 参考模式、会话预热与长句软切分优化
