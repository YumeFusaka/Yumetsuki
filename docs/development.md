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
- `data/config/system_config.yaml`
  系统配置
- `data/config/mcp.yaml`
  MCP 实际配置
- `data/config/mcp.example.yaml`
  MCP 示例模板
- `data/config/memory.yaml`
  记忆配置
  含本地模型路径，不应提交

## Git 约定

- 不提交真实 API key
- 不提交个人本地配置变更，除非明确需要
- 不提交 `data/models/`（向量模型目录）
- 不提交 `data/memory/`（运行时向量数据库）
- 提交信息沿用：
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`

## 测试策略

- 单元测试用 `pytest`
- 外部依赖优先 mock
- UI 变更至少保证：
  - 行为测试
  - `py_compile`
  - 必要时 Qt offscreen 实例化

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
