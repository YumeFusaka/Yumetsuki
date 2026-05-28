# Web 自动化插件

> 插件路径：`plugins/web_automation/`

## 功能

为 AI 提供浏览器自动化能力：搜索、提取网页文本、截图和持续浏览器会话。基于 Playwright + Edge。

## 权限等级

在 `data/config/agent.yaml` 中配置：

```yaml
web_automation:
  permission_level: medium  # low / medium / high
  default_engine: bing      # bing / google
  screenshot_dir: data/screenshots
  browser_headless: false
  browser_timeout_ms: 15000
  page_wait_timeout_ms: 10000
  session_screenshot_dir: data/browser_sessions
  max_extract_length: 4000
```

| 等级 | 允许操作 |
|------|---------|
| low | 搜索并返回结果摘要 |
| medium | + 打开网页提取文本、持续浏览器会话打开 / 导航 / 等待 / 提取 / 关闭 |
| high | + 截图页面、持续浏览器会话点击 / 填写 |

## 工具列表

| 工具名 | 描述 | 最低权限 | 模式 | 参数 |
|--------|------|---------|------|------|
| `web_search` | 后台搜索，返回结果摘要 | low | headless | `query`, `engine`(可选), `count`(可选) |
| `web_search_visible` | 启动可见 Playwright 自动化浏览器搜索 | low | visible | `query`, `engine`(可选) |
| `web_extract` | 提取指定 URL 的页面文本 | medium | headless | `url`, `max_length`(可选) |
| `web_screenshot` | 截图指定 URL 保存到本地 | high | headless | `url`, `filename`(可选) |
| `web_session_open` | 打开持续浏览器会话 | medium | visible/headless | `headless`(可选) |
| `web_session_navigate` | 在持续会话中导航到 URL | medium | session | `url` |
| `web_session_wait` | 等待 CSS selector 出现 | medium | session | `selector` |
| `web_session_extract` | 提取当前会话页面文本 | medium | session | `max_length`(可选) |
| `web_session_status` | 查看当前持续会话状态 | low | session | 无 |
| `web_session_close` | 关闭当前持续浏览器会话 | medium | session | 无 |
| `web_session_click` | 点击 CSS selector | high | session | `selector` |
| `web_session_fill` | 填写 CSS selector 输入框 | high | session | `selector`, `text` |

## 两种浏览器模式

### Headless 模式（后台）

- 用户说"帮我搜索xxx" → `web_search`
- 启动 headless Edge → 执行操作 → 提取结果 → 关闭浏览器 → 返回文本
- 用户看不到浏览器窗口
- 适用于“把结果告诉我”“帮我总结搜索结果”这类场景

### Visible 模式（可见）

- 仅当用户明确要求展示自动化搜索过程时使用 `web_search_visible`
- 启动可见 Edge 窗口 → 执行搜索 → 返回结果文本
- 这是 Playwright 控制的自动化浏览器，不复用用户当前系统默认浏览器窗口

### 持续浏览器会话

- `web_session_open` 会打开一个 Playwright 控制的持续会话。
- 后续 `web_session_navigate`、`web_session_click`、`web_session_fill`、`web_session_wait`、`web_session_extract` 都作用于同一个会话页面。
- `web_session_status` 返回当前 URL 和标题。
- `web_session_close` 负责释放浏览器和 Playwright 资源。
- 持续会话不复用用户系统默认浏览器窗口；需要系统默认浏览器时仍走 `system_control`。
- Planner、AgentManager 和 LLM 工具调用边界都会拦截未明确要求自动化浏览器的 `web_session_open`，避免“点击默认浏览器里的条目”“看看你搜索的这个页面”误开一个空白 Playwright 会话。

## 与系统默认浏览器的分工

- 普通桌面操作：
  - “打开浏览器” → `system_control.open_browser`
  - “用浏览器搜索 xxx” → `system_control.search_in_browser`
- 网页自动化：
  - “后台搜索并返回结果” → `web_search`
  - “提取网页正文” → `web_extract`
  - “截图网页” → `web_screenshot`
  - “展示自动化搜索过程” → `web_search_visible`
  - “在自动化浏览器里继续操作这个网页” → `web_session_*`
- 默认浏览器上下文：
  - “打开第二个条目”“点第二个”“看看这个结果”这类短句如果发生在默认浏览器打开 / 搜索之后，会优先走屏幕 OCR 和当前页面上下文，不自动接管为 Playwright 会话

## 内部结构

```
plugins/web_automation/
├── plugin.py       # 入口：Plugin 类，权限检查，@tool 方法
├── browser.py      # Playwright 浏览器生命周期管理（headless / visible / 持续会话）
├── session.py      # 持续浏览器会话状态与动作结果模型
├── search.py       # 搜索引擎操作（Bing / Google）
├── page.py         # 页面文本提取、截图、当前页面动作
└── README.md
```

## 依赖

新增 pip 依赖：
- `playwright>=1.40`

安装后需执行：`playwright install msedge`

## 搜索引擎

支持 Bing（默认）和 Google。通过 `default_engine` 配置默认引擎，也可在每次调用时通过 `engine` 参数指定。

## 安全说明

- 权限检查在插件内部完成
- 文本提取有 max_length 截断保护（默认 2000 字符）
- 页面导航有 15 秒超时保护
- 截图保存到配置的本地目录
- 持续会话中点击和填写是高权限操作
- `data/browser_sessions/` 属于运行期产物，默认不提交

## 平台

当前仅支持 Windows（Edge 路径）。Playwright 本身跨平台，未来适配只需调整 channel 参数。
