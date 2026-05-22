# web_automation

网页自动化插件，基于 Playwright + Edge。

## 依赖

pip install playwright
playwright install msedge

## 配置

data/config/agent.yaml:

```yaml
web_automation:
  permission_level: medium
  default_engine: bing
  screenshot_dir: data/screenshots
```

## 工具

| 工具名 | 描述 | 最低权限 |
|--------|------|---------|
| web_search | 后台搜索 | low |
| web_search_visible | 可见浏览器搜索 | low |
| web_extract | 提取网页文本 | medium |
| web_screenshot | 截图网页 | high |
