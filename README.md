# Yumetsuki

Yumetsuki（梦月）是一个 Python / PySide6 桌宠 AI 伴侣项目，核心体验是角色演出、自然对话、本地配置可控，以及可扩展的工具、语音、记忆、MCP、浏览器自动化和 OCR 能力。

## 快速开始

- Python 环境：`E:/Tool/Miniconda/envs/ai/python.exe`
- 安装依赖：`pip install -r requirements.txt`
- 启动：`python main.py`
- 测试：`python -m pytest tests/ -q`

## 文档入口

- [文档总览](./docs/README.md)
- [代码架构](./docs/architecture.md)
- [UI 规范](./docs/ui-guidelines.md)
- [开发流程](./docs/development.md)
- [插件与 MCP](./docs/plugin-mcp.md)
- [Web 自动化插件](./docs/plugin-web-automation.md)
- [系统控制插件](./docs/plugin-system-control.md)
- [OCR 与视觉输入](./docs/vision-ocr.md)
- [服务端 TTS 对接规范](./docs/service-tts-compatibility.md)

## 本地数据与敏感配置

`data/config/api.yaml`、`data/config/memory.yaml`、本地模型、运行日志、浏览器会话、OCR 截图和记忆数据库默认都属于本地运行期或敏感数据，不应提交。

当前真实浏览器、OCR、第三方 MCP、STT / TTS / API 的完整实机验收仍暂缓；离线自动化测试覆盖核心配置、UI 状态机和主要适配边界。
