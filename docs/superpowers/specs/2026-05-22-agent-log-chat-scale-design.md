# Agent 日志对话显示 + 桌宠窗口缩放优化

> 日期：2026-05-22

## 概述

两项优化：
1. Agent 设置页日志 Tab 增加用户/角色对话和 LLM thinking 显示
2. 桌宠 ChatWindow 解决长文本溢出 + 全元素等比缩放 + 对话框区域扩大

## 一、Agent 日志 — 混合时间线

### 新增事件

在 `core/event_bus.py` 的 `AgentEvents` 中新增：
- `USER_INPUT` — 用户发送消息时发布，payload: `{"text": str}`
- `ASSISTANT_REPLY` — 角色回复完成时发布，payload: `{"text": str, "character_name": str}`
- `THINKING` — LLM thinking tokens 发布，payload: `{"text": str}`

### 事件发布位置

- `USER_INPUT`：在 `llm/manager.py` 或 `agent/manager.py` 中用户消息进入时发布
- `ASSISTANT_REPLY`：在 LLM 流式输出完成后发布
- `THINKING`：在 LLM 适配器收到 thinking block 时发布

### 日志格式

QTextEdit 使用 HTML 富文本，按时间顺序混合显示：

```
[12:03:01] [User] 帮我搜索一下今天的天气
[12:03:01] [Planner] 路由决策: tool
[12:03:02] [Thinking] 用户想知道天气，需要调用搜索工具...（展开）
[12:03:02] [Tool] 执行: web_search → 成功
[12:03:03] [夕月] 今天天气晴朗，气温25°C...
```

### 样式

- `[User]` — 颜色 `#5f6fb2`（蓝色系）
- `[角色名]` — 颜色 `#9b3060`（玫瑰色）
- `[Thinking]` — 颜色 `#888888`，斜体
- 系统事件（Planner/Tool/LLM/Memory 等）— 保持现有样式

### Thinking 折叠

- 默认截断显示前 80 字符，末尾显示"…[展开]"
- 点击"[展开]"显示全文，变为"[收起]"
- 实现方式：QTextEdit 中插入 HTML anchor，通过 `anchorClicked` 信号处理展开/收起逻辑
- 展开后的内容用 `<div>` 包裹，收起时替换回截断版本

### 时间戳

每条日志前增加时间戳 `[HH:MM:SS]`，灰色小字。

## 二、桌宠 ChatWindow 优化

### 2.1 对话框区域扩大

- `panel_h` 从 `int(h * 0.38)` 改为 `int(h * 0.50)`
- 立绘尺寸保持不变
- 其他布局排版不变

### 2.2 长文本滚动

- `dialog_label`（QLabel）外包一层 `QScrollArea`
- QScrollArea 设置：
  - `setWidgetResizable(True)`
  - `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)`
  - 垂直滚动条按需显示
- 滚动条样式（与樱花主题一致）：
  - 宽度 6px
  - 滑块：半透明粉色 `rgba(212, 86, 122, 0.4)`，圆角
  - 轨道：透明
  - hover 时滑块加深 `rgba(212, 86, 122, 0.6)`
- 新消息到达时自动滚到顶部（单条消息从头阅读）

### 2.3 全元素等比缩放

定义基准常量：

```python
BASE_FONT = 17
BASE_NAME_FONT = 15
BASE_INPUT_FONT = 14
BASE_PADDING = 12
BASE_RADIUS = 16
BASE_BTN_SIZE = 36
BASE_INPUT_HEIGHT = 38
BASE_SCROLLBAR_WIDTH = 6
```

`_apply_scale()` 方法扩展：

1. 计算缩放后的值：`scaled_value = int(BASE * self._scale)`
2. 调用 `_rebuild_stylesheet()` 生成新 stylesheet 并应用到所有子组件
3. 影响范围：
   - `name_label` 字号
   - `dialog_label` 字号、行高
   - 输入框字号、高度、padding
   - 发送按钮尺寸、字号
   - 滚动条宽度
   - 所有 border-radius
   - 所有 padding/margin

### 2.4 不变的部分

- 窗口整体布局结构不变
- 立绘加载和显示逻辑不变
- 右键菜单、拖拽、置顶行为不变
- 毛玻璃效果不变
- 颜色主题不变

## 涉及文件

- `core/event_bus.py` — 新增事件类型
- `agent/manager.py` — 发布 USER_INPUT / ASSISTANT_REPLY 事件
- `llm/manager.py` 或 `llm/adapters/openai_compat.py` — 发布 THINKING 事件
- `ui/settings/pages/agent_page.py` — 订阅新事件、富文本格式化、折叠逻辑
- `ui/chat/window.py` — QScrollArea、等比缩放、panel 比例调整
