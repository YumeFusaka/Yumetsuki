# CLAUDE.md — AI 开发者上下文

## 项目概述

Yumetsuki 是一个 Python 桌宠 AI 伴侣。以无边框透明窗口显示角色立绘，毛玻璃面板承载对话，LLM 驱动角色对白，情绪标签联动立绘切换。

## 环境

- Python: `E:/Tool/Miniconda/envs/ai/python.exe`
- 依赖: `pip install -r requirements.txt`（PySide6, openai, pydantic, pyyaml, requests）
- 运行: `python main.py` → 设置中心 → 点「🚀 启动对话」打开桌宠
- 测试: `python -m pytest tests/ -q`
- Git 推送需代理: `export https_proxy=http://127.0.0.1:7890`

## 架构要点

```
main.py              → 设置中心入口（app-level 全局样式在此设置）
ui/chat/window.py    → 桌宠聊天窗（QWidget, 无边框透明, 毛玻璃面板）
ui/chat/sprite.py    → 立绘管理（加载/缩放/情绪切换）
ui/settings/         → 设置中心（樱花粉白主题）
llm/                 → LLM 对话（OpenAI 兼容协议, 流式输出）
llm/text_processor.py → 提取 [emotion:xxx] 标签
core/character.py    → 角色加载器
config/              → Pydantic schema + YAML 读写
data/config/         → api.yaml（含 API key，勿提交）, system_config.yaml
data/characters/     → 角色包目录
```

## 角色目录规范

```
角色名/
├── prompt.md        # 核心提示词
├── soul.md          # 灵魂设定
├── SKILL.md         # 技能说明
├── sprites.yaml     # 立绘情绪配置
├── resource/        # 补充资料 (*.md)
└── sprites/         # 立绘图片 (*.png)
```

## 聊天窗（桌宠模式）

- 无边框 + 全透明背景 (`FramelessWindowHint` + `WA_TranslucentBackground`)
- 默认置顶，右键菜单可切换
- 左键拖拽移动，滚轮缩放 (0.5x~2.0x)
- 底部 38% 区域为 GlassPanel（自绘半透明圆角矩形）
- 面板内：角色名 + 对话文本 + 输入框 + 🎤 + ➤

## UI 风格约定

- 主题色：粉白樱花渐变（#fff5f7 → #ffebf2 → #fae4f0）
- 强调色：#d4567a（玫瑰红）, #9b3060（深粉）
- 文字色：#4a3040（正文）, #6b4a5a（次要）
- 所有子窗口/对话框必须继承主题色（app-level stylesheet 在 main.py）
- SpinBox 数值加减用玫瑰红 `+` / `-` 按钮，右侧同列上下排列，不用图标或三角箭头
- 选中状态：`border: 1px solid #d4567a`，不用黑色 outline

## 代码风格

- 类型注解（Python 3.10+ 语法：`X | None`）
- 信号跨线程用 `Qt.ConnectionType.QueuedConnection`
- 配置用 Pydantic BaseModel，存储用 YAML
- 测试用 pytest，mock 外部依赖

## 已知问题 / TODO

- 聊天窗 LLM 输出正常但需确认用户端网络连通性
- TTS 适配器就绪但需 GPT-SoVITS 服务端运行
- 插件系统：已实现基础 SDK / 宿主 / 设置页展示，下一步接 LLM 工具调用
- Agent 层未实现（第三阶段）

## 下一步工作

1. MCP transport 适配：实现 stdio / SSE 会话连接、工具发现和调用
2. Agent 层：任务规划 + 执行器 + 反思

详细架构和进度见 `docs/README.md`。
