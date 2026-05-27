# web_automation

网页自动化插件，基于 Playwright + Edge。完整维护文档以 `docs/plugin-web-automation.md` 为准，本文件只保留插件目录内的快速索引。

## 依赖

```bash
pip install playwright
playwright install msedge
```

## 配置

`data/config/agent.yaml`：

```yaml
web_automation:
  permission_level: medium
  default_engine: bing
  screenshot_dir: data/screenshots
  browser_headless: false
  browser_timeout_ms: 15000
  page_wait_timeout_ms: 10000
  session_screenshot_dir: data/browser_sessions
  max_extract_length: 4000
```

## 工具

| 工具名 | 描述 | 最低权限 |
|--------|------|---------|
| `web_search` | 后台搜索并返回摘要 | low |
| `web_search_visible` | 可见 Playwright 自动化浏览器搜索 | low |
| `web_extract` | 提取网页文本 | medium |
| `web_screenshot` | 截图网页 | high |
| `web_session_open` | 打开持续浏览器会话 | medium |
| `web_session_navigate` | 在持续会话中导航 URL | medium |
| `web_session_wait` | 等待 CSS selector 出现 | medium |
| `web_session_extract` | 提取当前持续会话页面文本 | medium |
| `web_session_status` | 查看持续会话状态 | low |
| `web_session_close` | 关闭持续浏览器会话 | medium |
| `web_session_click` | 点击 CSS selector | high |
| `web_session_fill` | 填写 CSS selector 输入框 | high |
