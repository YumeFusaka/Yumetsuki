# 系统控制插件

> 插件路径：`plugins/system_control/`

## 功能

为 AI 提供操作系统级"打开/执行"能力。

## 权限等级

在 `data/config/agent.yaml` 中配置：

```yaml
system_control:
  permission_level: low  # low / medium / high
```

| 等级 | 允许操作 |
|------|---------|
| low | 打开已知应用、系统默认浏览器、默认浏览器搜索、文件管理器 |
| medium | + 打开任意文件、打开任意 URL |
| high | + 执行任意系统命令 |

## 工具列表

| 工具名 | 描述 | 最低权限 | 参数 |
|--------|------|---------|------|
| `open_application` | 打开指定应用程序 | low | `name` — 应用名称（如 notepad、edge、chrome） |
| `open_browser` | 打开系统默认浏览器首页 | low | 无 |
| `search_in_browser` | 使用系统默认浏览器搜索关键词 | low | `query` — 搜索关键词；`engine`（可选）— `bing` / `google` |
| `open_file_manager` | 打开文件管理器 | low | `path`（可选）— 目录路径 |
| `open_file` | 用默认程序打开文件 | medium | `path` — 文件完整路径 |
| `open_url` | 用默认浏览器打开 URL | medium | `url` — 网址 |
| `run_command` | 执行系统命令 | high | `command` — 命令内容；`timeout`（可选）— 超时秒数 |

## 内部结构

```
plugins/system_control/
├── plugin.py      # 入口：Plugin 类，权限检查
├── open.py        # 打开类操作（含应用别名映射）
├── command.py     # 命令执行（带超时和输出截断）
└── README.md
```

## 应用别名

`open_application` 支持常见应用别名，无需输入完整路径：

- `edge` → msedge.exe
- `chrome` → chrome.exe
- `firefox` → firefox.exe
- `vscode` / `code` → code.exe
- `notepad`、`calc`、`paint` 等系统工具

## 浏览器行为说明

- `open_browser`
  使用系统默认浏览器打开首页，并尽量请求复用已有浏览器窗口 / 进程；具体是否开新标签仍由系统默认浏览器决定
- `search_in_browser`
  使用系统默认浏览器直接发起搜索，适用于“用浏览器搜索 xxx”“打开浏览器搜索 xxx”这类场景
  路由器会提取真正的搜索关键词，不把“使用浏览器搜索”“打开浏览器搜索”“搜索”这类意图前缀原样塞进搜索语料；“重新搜索 xxx”仍会作为新搜索处理
- 默认浏览器打开或搜索后，后续“打开第二个条目”“看看这个结果”“看看你搜索的这个页面有什么内容”这类指令会优先走当前屏幕 OCR / 当前页面上下文，不会再次调用 `search_in_browser`，也不会自动打开 Playwright 会话
- 如果用户需要“返回搜索结果文本摘要”而不是只打开浏览器，应优先使用 `web_automation.web_search`

## 安全说明

- 权限检查在插件内部完成
- `run_command` 使用 `shell=True`，仅在 high 权限下可用
- 命令输出截断为 4096 字符，防止上下文溢出
- 命令执行带超时保护（默认 30 秒）
