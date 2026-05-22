# system_control

系统控制插件，为 AI 提供操作系统级"打开/执行"能力。

## 权限等级

在 `data/config/agent.yaml` 中配置：

```yaml
system_control:
  permission_level: low  # low / medium / high
```

| 等级 | 允许操作 |
|------|---------|
| low | 打开已知应用、浏览器、文件管理器 |
| medium | + 打开任意文件、打开任意 URL |
| high | + 执行任意系统命令 |

## Tools

- `open_application(name)` — 打开指定应用程序
- `open_browser()` — 打开默认浏览器
- `open_file_manager(path="")` — 打开文件管理器
- `open_file(path)` — 用默认程序打开文件
- `open_url(url)` — 用默认浏览器打开 URL
- `run_command(command, timeout=30)` — 执行系统命令
