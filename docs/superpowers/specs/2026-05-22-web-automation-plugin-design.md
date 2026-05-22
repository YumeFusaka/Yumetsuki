# Web 自动化插件设计（第一期）

> 日期：2026-05-22

## 概述

`plugins/web_automation/` 为 AI 提供浏览器自动化能力，基于 Playwright + Edge。第一期实现只读操作：搜索、提取文本、截图。

## 分期规划

- **第一期（本次）：** 搜索、提取文本、截图（只读操作）
- **第二期（未来）：** 填写表单、点击元素、复合交互序列

## 设计决策

- 新插件 `plugins/web_automation/`，不放入 system_control
- Playwright 控制 Edge（`channel="msedge"`）
- 无状态模式：每次操作启动浏览器实例，完成后关闭（headless）
- 可见模式：用户明确要求时打开可见浏览器，操作完不关闭
- 搜索引擎可配置，默认 Bing

## 目录结构

```
plugins/web_automation/
├── plugin.py       # 入口：Plugin 类，@tool 方法，权限检查
├── browser.py      # Playwright 浏览器生命周期管理（headless / visible）
├── search.py       # 搜索引擎操作（Bing / Google）
├── page.py         # 页面文本提取、截图
└── README.md
```

## 权限模型

三级权限制，配置在 `data/config/agent.yaml`：

```yaml
web_automation:
  permission_level: medium  # low / medium / high
  default_engine: bing      # bing / google
  screenshot_dir: data/screenshots
```

| 等级 | 允许操作 |
|------|---------|
| low | 搜索并返回结果摘要 |
| medium | + 打开网页提取文本 |
| high | + 截图页面 |

## Tools 定义

| Tool 名 | 描述 | 最低权限 | 模式 | 参数 |
|---------|------|---------|------|------|
| `web_search` | 后台搜索，返回结果摘要 | low | headless | `query: str, engine: str = "", count: int = 5` |
| `web_search_visible` | 打开可见浏览器搜索 | low | visible | `query: str, engine: str = ""` |
| `web_extract` | 提取指定 URL 的页面文本 | medium | headless | `url: str, max_length: int = 2000` |
| `web_screenshot` | 截图指定 URL 保存到本地 | high | headless | `url: str, filename: str = ""` |

## 两种浏览器模式

### Headless 模式（后台）

- 用户说"帮我搜索xxx" → `web_search`
- 启动 headless Edge → 执行操作 → 提取结果 → 关闭浏览器 → 返回文本
- 用户看不到浏览器窗口

### Visible 模式（可见）

- 用户说"打开浏览器搜索xxx" → `web_search_visible`
- 启动可见 Edge 窗口 → 执行搜索 → 返回结果文本
- 浏览器窗口保持打开，用户可继续使用
- 不自动关闭

## 实现要点

### browser.py

- `run_headless(callback)` — 启动 headless Edge，执行回调，关闭
- `run_visible(callback)` — 启动可见 Edge，执行回调，不关闭
- 内部使用 `playwright.sync_api`（插件 call_tool 是同步的）
- `chromium.launch(channel="msedge", headless=True/False)`

### search.py

- `search_bing(page, query, count)` — 导航到 Bing 搜索页，提取结果
  - URL: `https://www.bing.com/search?q={query}`
  - 选择器: `.b_algo` 下的标题、链接、摘要
- `search_google(page, query, count)` — 导航到 Google 搜索页，提取结果
  - URL: `https://www.google.com/search?q={query}`
  - 选择器: `.g` 下的标题、链接、摘要
- 返回格式化文本：`1. [标题](url)\n   摘要内容\n`

### page.py

- `extract_text(page, url, max_length)` — 导航到 URL，移除 script/style，提取 body 文本，截断到 max_length
- `screenshot(page, url, save_path)` — 导航到 URL，全页截图保存为 PNG

### plugin.py

- 权限检查逻辑同 system_control（PermissionLevel enum + _check_permission）
- 从 `agent.yaml` 读取 `web_automation` 配置
- 每个 @tool 方法调用 browser.py 的对应模式

## 配置集成

`config/schema.py` 新增：

```python
class WebAutomationConfig(BaseModel):
    permission_level: str = "medium"
    default_engine: str = "bing"
    screenshot_dir: str = "data/screenshots"
```

加入 `AgentConfig`：

```python
class AgentConfig(BaseModel):
    ...
    web_automation: WebAutomationConfig = WebAutomationConfig()
```

## 依赖

新增 pip 依赖：
- `playwright`

安装后需执行：`playwright install msedge`（下载 Edge 浏览器驱动）

## 插件边界

**属于 web_automation 的（第二期可追加）：**
- 填写表单
- 点击页面元素
- 复合交互序列
- 页面等待/轮询

**不属于（应在其他插件）：**
- 单纯打开浏览器/URL（已在 system_control）
- 下载文件管理
- 网络请求/API 调用

## 平台

第一版仅支持 Windows（Edge 路径）。Playwright 本身跨平台，未来适配只需调整 channel 参数。
