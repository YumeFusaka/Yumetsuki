# Agent 增强：分层智能架构设计

日期：2026-05-21

## 目标

在不增加简单对话负担的前提下，增强 Agent 模块的四个方向：

1. Planner 使用 LLM 参与意图判断（分层触发）
2. Reflector 异步反哺记忆系统
3. 多步推理按需激活
4. 主动行为（定时 + 事件驱动）

核心原则：**简单对话零额外开销，复杂场景按需升级。**

## 范围

本设计涵盖：

- Planner 分层路由机制
- Reflector 异步记忆反哺
- 多步推理循环
- 主动行为调度引擎
- 所有新增功能的配置模型
- 设置中心 Agent 页面扩展

本设计不涵盖：

- 主对话 LLM 替换为本地模型
- 语音输入/输出集成
- 多角色协作

## 设计

### 1. Planner 增强：分层触发

#### 快速路由层（零开销）

保留现有关键词匹配逻辑作为第一层筛选。未命中任何模式时直接进入对话模式，不产生额外 API 调用。

#### LLM 精判层（按需）

当快速路由命中工具关键词或检测到复杂模式时，调用 LLM 做精确意图判断。

精判 prompt 设计：
- 极短 system prompt（< 100 token）
- 输出结构化 JSON
- 限制 max_tokens = 200

精判输出格式：

```json
{
  "mode": "chat" | "tool" | "multi_step",
  "goal": "用户意图描述",
  "tool_name": "工具名（可选）",
  "needs_multi_step": false,
  "steps": []
}
```

#### 复杂模式检测

除关键词外，以下情况也触发 LLM 精判：
- 用户输入包含多个动作意图（"先...然后..."、"帮我...并且..."）
- 用户输入引用了之前的工具结果
- 输入长度超过配置阈值

#### 配置

```yaml
# data/config/agent.yaml
planner:
  # LLM 精判触发条件
  llm_judge_enabled: true
  # 输入长度超过此值时触发精判（字符数）
  complexity_threshold: 80
  # 精判使用的 max_tokens
  judge_max_tokens: 200
  # 额外触发关键词（用户可自定义）
  extra_trigger_keywords: []
```

### 2. Reflector 增强：异步记忆反哺

#### 分层反思

Reflector 根据对话复杂度决定反思深度：

- **轻量反思**（规则提取）：回复 < 30 字或纯闲聊，仅做简单规则提取（情感标签、关键词）
- **深度反思**（LLM 分析）：回复较长、涉及工具调用、或用户表达了偏好/事实信息时，调用 LLM 提取结构化记忆

#### 深度反思输出

LLM 提取以下类型的记忆：
- 用户偏好（"我喜欢..."、"我不喜欢..."）
- 事实信息（"我住在..."、"我的工作是..."）
- 情感状态（用户当前情绪）
- 对话主题标签

#### 异步执行

```
回复完成 → yield 最终结果给用户（无阻塞）
         → 后台线程启动 Reflector
            → 判断反思深度
            → 轻量：规则提取 → 写入记忆
            → 深度：LLM 分析 → 结构化提取 → 写入记忆
            → 发布 EventBus 事件（供 Agent 日志页面显示）
```

#### 配置

```yaml
# data/config/agent.yaml
reflector:
  enabled: true
  # 深度反思触发阈值（回复字符数）
  deep_threshold: 30
  # 深度反思使用的 max_tokens
  reflect_max_tokens: 300
  # 提取的记忆类型
  extract_types:
    - preference
    - fact
    - emotion
    - topic
```

### 3. 多步推理：按需激活

#### 触发条件

Planner LLM 精判输出 `needs_multi_step: true` 时进入多步推理循环。

#### 执行循环

```
Plan（LLM 生成下一步计划）
→ Execute（执行工具调用）
→ Observe（收集结果）
→ 判断：是否完成？
   ├─ 否 → 回到 Plan（携带之前的结果作为上下文）
   └─ 是 → 生成最终回复
```

#### 安全边界

- 最大步数上限（可配置，默认 3）
- 单步超时（可配置，默认 30 秒）
- 总耗时上限（可配置，默认 60 秒）
- 超限时优雅降级：用已有结果生成部分回复

#### 流式反馈

多步推理过程中，每完成一步向 UI 推送中间状态（通过 EventBus），Agent 日志页面实时显示进度。

#### 配置

```yaml
# data/config/agent.yaml
multi_step:
  enabled: true
  # 最大推理步数
  max_steps: 3
  # 单步超时（秒）
  step_timeout: 30
  # 总耗时上限（秒）
  total_timeout: 60
```

### 4. 主动行为：定时 + 事件引擎

#### ProactiveScheduler

后台线程运行的调度器，负责：
- 定时检查是否该主动发言
- 监听自定义事件
- 触发时调用 LLM 生成主动消息
- 通过信号推送到 ChatWindow

#### 定时闲聊

用户一段时间没互动后，桌宠主动打招呼。触发条件：
- 距离上次交互超过 `idle_interval_minutes`
- 距离上次主动行为超过 `min_interval_minutes`
- 当前时间在活跃时段内

#### 事件驱动

支持自定义事件，每个事件包含：
- `name`：事件标识
- `type`：触发类型（`timer` 定时 / `system` 系统事件）
- `condition`：触发条件描述
- `prompt_template`：生成主动消息时的 prompt 模板
- `cooldown_minutes`：该事件的冷却时间

内置事件示例：
- `long_work`：检测到用户长时间工作（可通过系统空闲时间判断）
- `time_greeting`：早/午/晚问候
- `weather_remind`：天气提醒（需要天气工具支持）

#### 推送机制

主动消息通过 Qt Signal 推送到 ChatWindow：
- ChatWindow 订阅 `proactive_message` 信号
- 收到后以角色身份显示消息
- 用户可以回复，进入正常对话流程

#### 配置

```yaml
# data/config/agent.yaml
proactive:
  enabled: false
  # 闲置多久后触发闲聊（分钟）
  idle_interval_minutes: 30
  # 两次主动行为最小间隔（分钟）
  min_interval_minutes: 10
  # 活跃时段（24小时制）
  active_hours:
    start: 8
    end: 23
  # 自定义事件
  events:
    - name: morning_greeting
      type: timer
      condition: "每天早上第一次启动时"
      prompt_template: "用温柔的方式跟主人说早安，可以提到今天的日期或天气。"
      cooldown_minutes: 720
    - name: rest_remind
      type: timer
      condition: "用户连续交互超过60分钟"
      prompt_template: "温柔地提醒主人休息一下，关心主人的身体。"
      cooldown_minutes: 60
```

### 5. 配置模型

所有新增配置统一放在 `data/config/agent.yaml`，通过 `ConfigManager` 管理。

```python
@dataclass
class PlannerConfig:
    llm_judge_enabled: bool = True
    complexity_threshold: int = 80
    judge_max_tokens: int = 200
    extra_trigger_keywords: list[str] = field(default_factory=list)

@dataclass
class ReflectorConfig:
    enabled: bool = True
    deep_threshold: int = 30
    reflect_max_tokens: int = 300
    extract_types: list[str] = field(default_factory=lambda: ["preference", "fact", "emotion", "topic"])

@dataclass
class MultiStepConfig:
    enabled: bool = True
    max_steps: int = 3
    step_timeout: int = 30
    total_timeout: int = 60

@dataclass
class ProactiveEventConfig:
    name: str = ""
    type: str = "timer"
    condition: str = ""
    prompt_template: str = ""
    cooldown_minutes: int = 60

@dataclass
class ProactiveConfig:
    enabled: bool = False
    idle_interval_minutes: int = 30
    min_interval_minutes: int = 10
    active_hours_start: int = 8
    active_hours_end: int = 23
    events: list[ProactiveEventConfig] = field(default_factory=list)

@dataclass
class AgentConfig:
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    reflector: ReflectorConfig = field(default_factory=ReflectorConfig)
    multi_step: MultiStepConfig = field(default_factory=MultiStepConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)
```

### 6. 设置中心 Agent 页面扩展

现有 Agent 页面（日志）扩展为多 tab 结构：

- **日志** tab：现有实时日志功能
- **Planner** tab：精判开关、复杂度阈值、自定义关键词
- **记忆反思** tab：反思开关、深度阈值、提取类型
- **多步推理** tab：开关、最大步数、超时设置
- **主动行为** tab：开关、时间间隔、活跃时段、事件列表管理（增删改）

### 7. 对话流程总览

```
用户输入
→ [快速路由] 关键词/模式匹配
   ├─ 未命中 → 直接对话（零额外开销）
   └─ 命中 → [LLM 精判]
              ├─ mode=chat → 对话
              ├─ mode=tool → 单步工具调用
              └─ mode=multi_step → 多步推理循环
→ LLM 生成回复（流式）
→ 回复完成，yield 给用户
→ [异步] Reflector 分析 + 记忆写入
→ [后台] ProactiveScheduler 更新交互时间戳
```

## 错误处理

- LLM 精判超时或失败：降级为关键词路由结果
- 多步推理单步失败：跳过该步，用已有结果继续
- 多步推理总超时：用已有结果生成部分回复，告知用户
- Reflector 后台失败：静默记录错误日志，不影响用户体验
- ProactiveScheduler 异常：静默重启调度器，不影响正常对话

## 测试策略

- Planner 分层路由：测试快速路由不触发 LLM、复杂输入触发 LLM
- Reflector 异步：测试不阻塞主线程、记忆正确写入
- 多步推理：测试步数上限、超时降级
- ProactiveScheduler：测试定时触发、冷却时间、活跃时段过滤
- 配置加载：测试默认值、自定义值、配置热更新

## 实现边界

预期修改文件：
- `config/schema.py` - 新增 AgentConfig 模型
- `config/manager.py` - 新增 agent.yaml 读写
- `agent/planner.py` - 分层路由 + LLM 精判
- `agent/executor.py` - 多步推理循环
- `agent/reflector.py` - 异步反思 + LLM 提取
- `agent/manager.py` - 集成新流程
- `ui/settings/pages/agent_page.py` - 扩展为多 tab

预期新增文件：
- `data/config/agent.yaml` - Agent 配置文件
- `agent/proactive.py` - 主动行为调度器
- `agent/llm_judge.py` - LLM 精判封装

## 成功标准

- 简单对话（"你好"、"今天心情怎么样"）响应时间无变化
- 工具调用场景 LLM 精判准确率 > 90%
- 多步推理不超过配置的时间上限
- Reflector 不阻塞用户下一轮输入
- 主动行为按配置的时间间隔触发
- 所有配置可通过设置中心 UI 修改
