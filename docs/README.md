# Yumetsuki 项目总览

> 最后更新：2026-05-20

## 项目简介

Yumetsuki（梦月）是一个 Python 桌面 AI 伴侣项目，以 **桌宠** 形态运行——无边框透明窗口、角色立绘直接显示在桌面上，通过 LLM 驱动角色对话，情绪标签联动立绘切换，支持语音合成/识别，最终目标是具备自主任务执行能力的智能 Agent。

**技术栈：** Python 3.10 · PySide6 · OpenAI 兼容协议 · PyYAML · Pydantic

**本地环境：** `E:\Tool\Miniconda\envs\ai`

---

## 总体架构

```
yumetsuki/
├── main.py                     # 入口 → 设置中心
├── core/
│   ├── event_bus.py            # 发布/订阅事件总线
│   └── character.py            # 角色加载器
├── config/
│   ├── schema.py               # Pydantic 配置模型
│   └── manager.py              # YAML 读写
├── llm/
│   ├── adapter.py              # LLM 适配器基类
│   ├── adapters/openai_compat.py
│   ├── manager.py              # 对话管理（流式+历史）
│   └── text_processor.py       # 情绪标签提取
├── tts/
│   ├── adapter.py              # TTS 适配器基类
│   └── adapters/gptsovits.py
├── ui/
│   ├── chat/
│   │   ├── window.py           # 桌宠聊天窗（无边框透明）
│   │   ├── sprite.py           # 立绘管理与缩放
│   │   └── web_view.py         # WebEngine 聊天视图（备用）
│   └── settings/
│       ├── window.py           # 设置中心主窗口
│       └── pages/              # API / 角色 / 插件 / 系统
├── data/
│   ├── config/                 # api.yaml, system_config.yaml
│   └── characters/             # 角色包（prompt/soul/resource/sprites）
└── tests/                      # 14 个单元测试
```

### 核心流程

```
用户输入 → LLM 流式生成 → TextProcessor 提取 [emotion:xxx]
                                    ↓
                        立绘切换 ← 情绪匹配
                        TTS 播放 ← 台词文本（可选）
                        对话框   ← 显示文本
```

### 角色目录规范

```
角色名/
├── prompt.md           # 核心提示词
├── soul.md             # 灵魂设定
├── SKILL.md            # 技能说明
├── sprites.yaml        # 立绘情绪配置
├── resource/           # 补充资料
│   └── *.md
└── sprites/            # 立绘图片
    └── *.png
```

---

## 当前进度

| 模块 | 状态 | 说明 |
|------|------|------|
| 项目骨架 + 配置系统 | ✅ 完成 | Pydantic schema + YAML 读写 |
| 事件总线 | ✅ 完成 | 轻量 pub/sub |
| LLM 对话（OpenAI 兼容） | ✅ 完成 | 流式输出 + 历史管理 |
| 情绪标签解析 | ✅ 完成 | `[emotion:xxx]` 正则提取 |
| 角色加载器 | ✅ 完成 | 读取完整目录结构 |
| 立绘管理 + 情绪切换 | ✅ 完成 | 支持缩放 |
| 桌宠聊天窗 | ✅ 完成 | 无边框透明 + 毛玻璃面板 + 拖拽 + 滚轮缩放 + 右键菜单 |
| 设置中心 | ✅ 完成 | 樱花主题，4页（API/角色/插件/系统） |
| 角色管理 | ✅ 完成 | 目录树结构 + 增删改查 + AI同步YAML |
| TTS 适配器 | ✅ 就绪 | GPT-SoVITS 适配器，需服务端 |
| 插件系统 | ✅ 完成 | 插件 SDK + 宿主 + 设置页展示 |
| Agent 层 | 🔲 未开始 | 任务规划 + 执行器 + 反思 |
| 记忆系统 | 🔲 未开始 | mem0 长期记忆 |
| MCP 接入 | 🟡 进行中 | 配置读写 + 宿主状态 + LLM工具入口 |
| ASR 语音识别 | 🔲 未开始 | Vosk/Whisper |

---

## 下一阶段计划

### 第二阶段：插件系统 + 工具调用

1. ✅ **插件 SDK** — `sdk/base.py` 提供 `@tool` 装饰器，插件继承基类注册工具
2. ✅ **插件宿主** — `core/plugin_host.py` 热加载 `plugins/` 目录下的插件
3. ✅ **LLM 工具调用** — 复用 OpenAI function calling 协议，工具列表动态注入
4. 🟡 **MCP 接入** — `data/config/mcp.yaml` 配置外部 MCP Server（SSE/stdio），宿主状态已接入，transport 适配待完成

### 第三阶段：Agent 自主执行

1. **任务规划器** — `agent/planner.py` 分解复杂任务
2. **执行器** — Shell / GUI / 浏览器自动化
3. **反思与重试** — `agent/reflector.py` 失败后自动调整策略
4. **记忆** — mem0 语义记忆 + 任务经验存储

---

## 最终目标

一个以角色演出为核心交互形式的桌面智能 Agent：

- **角色伴侣** — 立绘 + 情绪 + 语音，沉浸式对话体验
- **工具使用** — 通过 LLM 工具调用 + MCP 接入各种外部服务
- **自主执行** — 接受复杂任务后自主规划、执行、反思、重试
- **可扩展** — 插件热插拔，社区可贡献角色包和工具插件
- **本地优先** — 数据全部在本地，隐私安全

---

## 开发约定

- 入口：`python main.py` 启动设置中心，点击「🚀 启动对话」打开桌宠
- 测试：`python -m pytest tests/ -q`
- 配置文件：`data/config/` 下的 YAML
- 角色包：`data/characters/` 下按规范目录组织
