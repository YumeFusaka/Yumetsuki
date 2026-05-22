# Web 自动化插件

> 插件路径：`plugins/web_automation/`

## 功能

为 AI 提供浏览器自动化能力：搜索、提取网页文本、截图。基于 Playwright + Edge。

## 权限等级

在 `data/config/agent.yaml` 中配置：

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

## 工具列表

| 工具名 | 描述 | 最低权限 | 模式 | 参数 |
|--------|------|---------|------|------|
| `web_search` | 后台搜索，返回结果摘要 | low | headless | `query`, `engine`(可选), `count`(可选) |
| `web_search_visible` | 启动可见 Playwright 自动化浏览器搜索 | low | visible | `query`, `engine`(可选) |
| `web_extract` | 提取指定 URL 的页面文本 | medium | headless | `url`, `max_length`(可选) |
| `web_screenshot` | 截图指定 URL 保存到本地 | high | headless | `url`, `filename`(可选) |

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

## 与系统默认浏览器的分工

- 普通桌面操作：
  - “打开浏览器” → `system_control.open_browser`
  - “用浏览器搜索 xxx” → `system_control.search_in_browser`
- 网页自动化：
  - “后台搜索并返回结果” → `web_search`
  - “提取网页正文” → `web_extract`
  - “截图网页” → `web_screenshot`
  - “展示自动化搜索过程” → `web_search_visible`

## 内部结构

```
plugins/web_automation/
├── plugin.py       # 入口：Plugin 类，权限检查，@tool 方法
├── browser.py      # Playwright 浏览器生命周期管理（headless / visible）
├── search.py       # 搜索引擎操作（Bing / Google）
├── page.py         # 页面文本提取、截图
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

## 平台

当前仅支持 Windows（Edge 路径）。Playwright 本身跨平台，未来适配只需调整 channel 参数。
