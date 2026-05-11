# 智行伴侣


## 第一页

AMap JS SDK（高德地图 JavaScript 开发工具包）

## 研究背景与目标

### 研究背景

自由行规划需要同时整合天气、景点、酒店、路线、预算和用户偏好。
传统平台以单点查询为主，用户仍需在多个应用之间切换和人工组合信息。
单纯依赖大语言模型生成行程，容易出现事实不稳、路线折返和实时约束缺失。
智能体与工具调用机制为“真实数据 + 约束规划 + 结构化输出”提供了实现路径。

- 自由行增长
- 规划复杂（景点+天气+酒店+预算）
- 现有平台：以单点查询为主，用户仍需在多个应用之间切换和人工组合信息。

截至2026年一季度，国内居民出游人次已达到19.01亿，同比增长6.0%，国内居民出游总花费1.86万亿元，同比增长2.9%。同时，中国旅游研究院预测2026年全年国内旅游人数将达到69.49亿人次，国内旅游总花费将达到6.68万亿元。

### 研究目的

如何面向个性化自由行需求，生成一份可展示、可编辑、可导出的多日旅行计划。

## 系统架构设计

### 系统架构

### 核心机制：多智能体（⭐重点页）

讲清三点：

为什么不用单模型？
👉 太复杂、容易乱
怎么拆？
👉 天气 / 景点 / 酒店 / 行程
怎么协作？
👉 顺序执行 + 上下文传递

👉 把复杂问题拆成多个可控子任务

### 核心机制：天气约束（⭐加分页）

讲：

天气 → 风险评分
风险 → 行程限制

举例：

高风险：室内
中风险：同区域
低风险：正常


### 数据可信性设计（⭐非常加分）

不让模型编造景点
必须用地图API
结构化校验

👉 真实数据 + 约束生成

## 系统流程（1页）


用户输入 → 后端 → 多Agent → 生成 → 前端展示

## 系统功能展示（2~3页）

👉 放截图（非常重要！！）


首页输入
生成过程（进度条）
结果页
地图


## 关键技术（1页）

快速列：

Vue3
FastAPI
HelloAgents
高德地图


## 系统测试（1页）

功能正常 ✔
异常可处理 ✔
支持编辑导出 ✔

## 创新点（⭐必问）

多智能体拆分复杂任务
天气风险参与规划
基于真实POI的数据约束生成
支持可视化 + 编辑 + 导出

## 不足与改进（老师必问）

依赖API（不稳定）
规划还不够精细
无长期用户建模

👉 +未来：

强化推荐
加用户画像
路径优化算法

## 结束页

👉 本系统实现了一个“可落地的智能旅行规划Agent系统”

帮你写“讲稿（逐页讲什么）”

帮你做“老师可能提问 + 标准回答”

---

# Agent 为什么调用工具，而不是直接调用 API

这一部分可以作为答辩时“关键实现一：Agent 的实现”的讲稿。核心要讲清楚三件事：

1. Agent 为什么要调用工具，而不是后端直接调用 API。
2. Agent 是如何调用工具的，底层逻辑是什么。
3. 这个逻辑在本项目中具体落在哪里。

## 一、为什么 Agent 要调用工具，而不是直接调用 API

### 观点 1：直接调用 API 会把 Agent 变成普通函数，失去自主决策能力

如果后端代码直接调用高德 API，那么“查什么关键词、什么时候查、用哪个查询入口”都是程序员提前写死的。这样模型只是在 API 返回结果之后做文本整理，本质上不是 Agent，而是“API + 文案生成器”。

直接调用 API 的伪代码大概是这样：

```python
def search_attractions(city: str):
    # 后端写死了：只搜索“景点”
    result = amap_api.search_poi(
        keywords="景点",
        city=city
    )
    return result
```

这个写法的问题是：如果用户说“我喜欢历史文化，不喜欢爬山”，程序仍然只会搜索“景点”。它不会自己判断应该搜索“历史文化”“博物馆”“古迹”，也不会根据天气风险避开户外景点。

在本项目中，景点 Agent 的提示词明确要求它根据用户偏好和天气风险自主选择关键词：

```python
# backend/app/agents/trip_planner_agent.py
ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

你必须使用工具来搜索景点!不要自己编造景点信息!
你需要根据用户提供的天气风险、喜欢关键词、不喜欢关键词、额外需求，自主决定搜索关键词并调用工具。
如果用户没有特别偏好或限制，请优先搜索当地热门景点。

使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`
"""
```

例子：

```text
用户需求：广州三日游，喜欢历史文化，不喜欢户外暴晒

如果直接 API：
后端可能固定调用 keywords=景点

如果 Agent 调工具：
Agent 可以生成：
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]
或者：
[TOOL_CALL:amap_maps_text_search:keywords=博物馆,city=广州]
```

所以，工具调用的意义不是“换一种方式调用 API”，而是把“选择调用什么能力”的权力交给 Agent。

### 观点 2：工具调用可以减少大模型编造信息

旅游规划里最怕的是模型凭记忆编造景点、酒店、天气。比如模型可能说“广州今天晴”，但天气是实时变化的；也可能推荐已经不存在或位置不准确的酒店。

本项目通过工具约束 Agent：天气、景点、酒店必须来自高德工具结果。

天气 Agent 的提示词：

```python
# backend/app/agents/trip_planner_agent.py
WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是查询指定城市的天气信息。

你必须使用工具来查询天气!不要自己编造天气信息!

使用maps_weather工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_weather:city=城市名]`
"""
```

酒店 Agent 的提示词：

```python
# backend/app/agents/trip_planner_agent.py
HOTEL_AGENT_PROMPT = """你是酒店推荐专家。你的任务是根据城市和景点位置推荐合适的酒店。

你必须使用工具来搜索酒店!不要自己编造酒店信息!
你输出的酒店必须来自工具结果,并且必须保留工具结果中的坐标信息。

使用maps_text_search工具搜索酒店时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]`
"""
```

例子：

```text
用户：帮我规划广州旅游。

不使用工具时：
模型可能直接说“推荐住在某某酒店”，但这些酒店可能没有坐标、价格和真实地址。

使用工具时：
酒店 Agent 必须先调用：
[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=广州]

然后只能基于工具返回的酒店列表生成 JSON。
```

这就是“真实数据 + 模型规划”的设计：模型负责理解需求和组织结果，工具负责提供事实数据。

### 观点 3：直接调用 API 会让后端代码变复杂，工具可以统一封装 API 细节

高德 API 不只有一个接口。它可能包含：

- POI 搜索
- 天气查询
- 地理编码
- 逆地理编码
- 路线规划
- POI 详情查询

如果后端为每个 API 都手写一个函数，再手动告诉 Agent 每个函数怎么用，代码会越来越散。

工具封装后的思路是：后端只创建一个 MCP 工具，让 MCP 工具自动发现高德 MCP server 提供的子工具。

本项目代码：

```python
# backend/app/agents/trip_planner_agent.py
self.amap_tool = MCPTool(
    name="amap",
    description="高德地图服务",
    server_command=["uvx", "amap-mcp-server"],
    env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
    auto_expand=True
)
```

这里的关键是 `auto_expand=True`。它表示：不是只给 Agent 一个笼统的 `amap` 工具，而是让 `MCPTool` 去发现高德 MCP server 中有哪些工具，然后展开成多个独立工具，例如：

```text
amap_maps_text_search
amap_maps_weather
amap_maps_geo
amap_maps_search_detail
amap_maps_direction_walking_by_address
...
```

这样 Agent 看见的是一个个语义清晰的工具，而不是一堆底层 HTTP API。

### 观点 4：工具调用更适合“让模型决定参数”

旅行规划里，参数不是完全固定的。用户偏好会影响搜索关键词，天气会影响景点类型，住宿偏好会影响酒店搜索。

本项目不是简单写死查询，而是构造 query 交给不同 Agent：

```python
# backend/app/agents/trip_planner_agent.py
weather_query = f"请查询{request.city}的天气信息"
weather_response = self._run_agent_with_cancellation(
    self.weather_agent,
    weather_query,
    cancellation_token,
    "天气查询",
)

attraction_query = self._build_attraction_query(request, weather_info)
attraction_response = self._run_agent_with_cancellation(
    self.attraction_agent,
    attraction_query,
    cancellation_token,
    "景点搜索",
)

hotel_query = (
    f"请搜索{request.city}的{request.accommodation}酒店。"
    f"如果工具返回里包含价格、价格区间、priceLevel、评分、酒店类型，请原样保留，"
    f"以便后续规划阶段生成 hotel.estimated_cost 和 budget.total_hotels。"
)
hotel_response = self._run_agent_with_cancellation(
    self.hotel_agent,
    hotel_query,
    cancellation_token,
    "酒店推荐",
)
```

例子：

```text
用户 A：喜欢历史文化
景点 Agent 可能调用：
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]

用户 B：亲子游
景点 Agent 可能调用：
[TOOL_CALL:amap_maps_text_search:keywords=亲子,city=广州]

用户 C：下雨天出行
景点 Agent 可能调用：
[TOOL_CALL:amap_maps_text_search:keywords=博物馆,city=广州]
```

这就是 Agent 和普通 API 调用最大的区别：API 是能力，Agent 决定如何使用能力。

## 二、Agent 如何调用工具：底层逻辑是什么

本项目使用的是 HelloAgents 的 `SimpleAgent` + `MCPTool`。它的工具调用链路可以概括为：

```text
用户需求
  ↓
SimpleAgent 读取 system_prompt 和工具描述
  ↓
LLM 生成工具调用标记 [TOOL_CALL:工具名:参数]
  ↓
SimpleAgent 解析工具调用标记
  ↓
ToolRegistry 找到对应 Tool 对象
  ↓
Tool.run(parameters)
  ↓
如果是 MCP 工具，则转成 MCP call_tool 请求
  ↓
amap-mcp-server 调用高德 HTTP API
  ↓
工具结果返回给 Agent
  ↓
Agent 基于工具结果生成最终 JSON 或文本
```

这里要特别注意一个容易误解的点：

```text
LLM 负责：
读 query、理解任务、决定要不要调用工具、生成 [TOOL_CALL:工具名:参数]

SimpleAgent 的 Python 代码负责：
解析 [TOOL_CALL:工具名:参数]、查找工具对象、执行工具、把工具结果再交给 LLM
```

也就是说，不是“LLM 自己解析工具调用标记”。LLM 只生成一段符合格式的文本，真正解析这段文本的是 `SimpleAgent` 里的正则表达式和普通 Python 逻辑。

可以把它理解成：

```text
LLM：我认为现在应该调用天气工具，所以我输出：
     [TOOL_CALL:amap_maps_weather:city=广州]

SimpleAgent：我在模型输出里检测到了 TOOL_CALL 标记，
             于是把工具名和参数取出来，去工具注册表里找工具并执行。
```

再具体到“每个 Agent 是否都有自己的 LLM”：在本项目代码里，四个 Agent 都传入了同一个 `self.llm` 实例：

```python
# backend/app/agents/trip_planner_agent.py
self.llm = get_llm()

self.attraction_agent = SimpleAgent(
    name="景点搜索专家",
    llm=self.llm,
    system_prompt=ATTRACTION_AGENT_PROMPT
)

self.weather_agent = SimpleAgent(
    name="天气查询专家",
    llm=self.llm,
    system_prompt=WEATHER_AGENT_PROMPT
)
```

所以更准确的说法是：每个 Agent 都持有一个 `llm` 引用，并使用自己的 `system_prompt` 去调用这个 LLM。它们可以共享同一个底层 LLM 服务，但因为提示词不同，所以表现出来的角色不同：

```text
天气 Agent + 天气提示词 → 更倾向调用 amap_maps_weather
景点 Agent + 景点提示词 → 更倾向调用 amap_maps_text_search 搜索景点
酒店 Agent + 酒店提示词 → 更倾向调用 amap_maps_text_search 搜索酒店
行程 Agent + 行程提示词 → 不调用工具，只整合结构化结果
```

### 第一步：工具被注册到 Agent

在本项目初始化时，会先创建一个共享的高德 MCP 工具：

```python
# backend/app/agents/trip_planner_agent.py
self.amap_tool = MCPTool(
    name="amap",
    description="高德地图服务",
    server_command=["uvx", "amap-mcp-server"],
    env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
    auto_expand=True
)
```

然后把这个工具注册给景点、天气、酒店三个 Agent：

```python
# backend/app/agents/trip_planner_agent.py
self.attraction_agent = SimpleAgent(
    name="景点搜索专家",
    llm=self.llm,
    system_prompt=ATTRACTION_AGENT_PROMPT
)
_register_amap_tools(self.attraction_agent, self.amap_tool)

self.weather_agent = SimpleAgent(
    name="天气查询专家",
    llm=self.llm,
    system_prompt=WEATHER_AGENT_PROMPT
)
_register_amap_tools(self.weather_agent, self.amap_tool)

self.hotel_agent = SimpleAgent(
    name="酒店推荐专家",
    llm=self.llm,
    system_prompt=HOTEL_AGENT_PROMPT
)
_register_amap_tools(self.hotel_agent, self.amap_tool)
```

注意：行程规划 Agent 没有注册工具：

```python
# backend/app/agents/trip_planner_agent.py
self.planner_agent = SimpleAgent(
    name="行程规划专家",
    llm=self.llm,
    system_prompt=PLANNER_AGENT_PROMPT
)
```

原因是行程规划 Agent 不负责查实时数据，它只负责整合前面三个 Agent 已经拿到的天气、景点、酒店结果。这样可以让职责更清晰。

### 第二步：MCPTool 自动发现并展开子工具

本项目中 `_register_amap_tools()` 会优先拿到 MCP 展开后的子工具，然后逐个注册：

```python
# backend/app/agents/trip_planner_agent.py
def _register_amap_tools(agent: SimpleAgent, tool: MCPTool) -> None:
    """显式注册展开后的 MCP 子工具，确保 Agent 能直接拿到 AMap 子工具名。"""
    expanded_tools = tool.get_expanded_tools() if getattr(tool, "auto_expand", False) else []

    if expanded_tools:
        for expanded_tool in expanded_tools:
            agent.add_tool(expanded_tool, auto_expand=False)
        print(f"✅ Agent '{agent.name}' 已注册 {len(expanded_tools)} 个 AMap 子工具")
        return

    agent.add_tool(tool, auto_expand=True)
    print(f"⚠️ Agent '{agent.name}' 未获取到展开工具，已回退注册总工具 '{tool.name}'")
```

底层 `MCPTool` 的展开逻辑在 HelloAgents 源码里。它会把 MCP server 中的每个工具包装成一个 `MCPWrappedTool`：

```python
# hello_agents/tools/builtin/protocol_tools.py
def get_expanded_tools(self) -> List['Tool']:
    if not self.auto_expand:
        return []

    from .mcp_wrapper_tool import MCPWrappedTool

    expanded_tools = []
    for tool_info in self._available_tools:
        wrapped_tool = MCPWrappedTool(
            mcp_tool=self,
            tool_info=tool_info,
            prefix=self.prefix
        )
        expanded_tools.append(wrapped_tool)
```

`prefix=self.prefix` 很关键。本项目创建时 `name="amap"`，所以展开后的工具名前面会带 `amap_` 前缀，例如：

```text
MCP 原始工具：maps_text_search
展开后工具名：amap_maps_text_search

MCP 原始工具：maps_weather
展开后工具名：amap_maps_weather
```

这就是为什么提示词里写的是：

```text
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]
[TOOL_CALL:amap_maps_weather:city=广州]
```

### 第三步：SimpleAgent 把工具说明加入 system prompt

HelloAgents 的 `SimpleAgent` 会在运行时构建增强版 system prompt，把可用工具列表和工具调用格式告诉模型。

源码逻辑：

```python
# hello_agents/agents/simple_agent.py
def _get_enhanced_system_prompt(self) -> str:
    base_prompt = self.system_prompt or "你是一个有用的AI助手。"

    if not self.enable_tool_calling or not self.tool_registry:
        return base_prompt

    tools_description = self.tool_registry.get_tools_description()

    tools_section = "\n\n## 可用工具\n"
    tools_section += "你可以使用以下工具来帮助回答问题：\n"
    tools_section += tools_description + "\n"

    tools_section += "\n## 工具调用格式\n"
    tools_section += "当需要使用工具时，请使用以下格式：\n"
    tools_section += "`[TOOL_CALL:{tool_name}:{parameters}]`\n\n"

    return base_prompt + tools_section
```

例子：天气 Agent 最终看到的提示词大概包含两部分：

```text
你是天气查询专家。你的任务是查询指定城市的天气信息。
你必须使用工具来查询天气!不要自己编造天气信息!

## 可用工具
- amap_maps_weather: 查询城市天气
- amap_maps_text_search: 关键词搜索 POI
- ...

## 工具调用格式
[TOOL_CALL:{tool_name}:{parameters}]
```

这样模型才知道“我有哪些工具可以用”和“应该用什么格式调用”。

### 第四步：LLM 生成工具调用标记

当天气 Agent 收到：

```text
请查询广州的天气信息
```

根据提示词，它不会直接回答“广州天气晴”，而是先输出：

```text
[TOOL_CALL:amap_maps_weather:city=广州]
```

当景点 Agent 收到：

```text
请搜索广州的历史文化景点
```

它会输出：

```text
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]
```

这里的工具调用标记本质上是一段特殊格式的文本，不是 Python 函数调用。真正执行工具的是 HelloAgents 框架。

### 第五步：SimpleAgent 解析工具调用标记

SimpleAgent 用正则表达式从模型输出中找出工具调用：

```python
# hello_agents/agents/simple_agent.py
def _parse_tool_calls(self, text: str) -> list:
    pattern = r'\[TOOL_CALL:([^:]+):([^\]]+)\]'
    matches = re.findall(pattern, text)

    tool_calls = []
    for tool_name, parameters in matches:
        tool_calls.append({
            'tool_name': tool_name.strip(),
            'parameters': parameters.strip(),
            'original': f'[TOOL_CALL:{tool_name}:{parameters}]'
        })

    return tool_calls
```

例子：

```text
模型输出：
[TOOL_CALL:amap_maps_weather:city=广州]

解析结果：
tool_name = "amap_maps_weather"
parameters = "city=广州"
```

如果是景点搜索：

```text
模型输出：
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]

解析结果：
tool_name = "amap_maps_text_search"
parameters = "keywords=历史文化,city=广州"
```

### 第六步：SimpleAgent 把参数字符串转成字典

工具实际执行时需要参数字典，所以 SimpleAgent 会把 `key=value` 字符串解析成 Python 字典：

```python
# hello_agents/agents/simple_agent.py
def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict:
    param_dict = {}

    if '=' in parameters:
        if ',' in parameters:
            pairs = parameters.split(',')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    param_dict[key.strip()] = value.strip()
        else:
            key, value = parameters.split('=', 1)
            param_dict[key.strip()] = value.strip()

        param_dict = self._convert_parameter_types(tool_name, param_dict)

    return param_dict
```

例子：

```text
"city=广州"
```

会变成：

```python
{"city": "广州"}
```

再比如：

```text
"keywords=历史文化,city=广州"
```

会变成：

```python
{
    "keywords": "历史文化",
    "city": "广州"
}
```

### 第七步：ToolRegistry 找到工具对象并执行 run()

这一段可以理解成“工具字典查表”。Agent 不是直接知道 `amap_maps_weather` 这个工具的代码在哪里，而是通过 `ToolRegistry` 统一管理工具。

`ToolRegistry` 内部维护了一个字典，结构大概是：

```python
{
    "amap_maps_weather": <MCPWrappedTool object>,
    "amap_maps_text_search": <MCPWrappedTool object>,
    "amap_maps_geo": <MCPWrappedTool object>,
    ...
}
```

在 HelloAgents 源码中，注册表就是用 `_tools` 字典保存工具对象：

```python
# hello_agents/tools/registry.py
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool, auto_expand: bool = True):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)
```

所以当模型输出：

```text
[TOOL_CALL:amap_maps_weather:city=广州]
```

`SimpleAgent` 会做的事情其实是：

```python
tool = self.tool_registry.get_tool("amap_maps_weather")
```

如果找到了，就拿到对应的工具对象；如果找不到，就返回“未找到工具”的错误。

`SimpleAgent` 的执行逻辑如下：

```python
# hello_agents/agents/simple_agent.py
def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
    tool = self.tool_registry.get_tool(tool_name)
    if not tool:
        return f"❌ 错误：未找到工具 '{tool_name}'"

    param_dict = self._parse_tool_parameters(tool_name, parameters)
    result = tool.run(param_dict)
    return f"🔧 工具 {tool_name} 执行结果：\n{result}"
```

例子：

```python
tool_name = "amap_maps_weather"
param_dict = {"city": "广州"}

result = tool.run(param_dict)
```

这里的 `tool.run(param_dict)` 就是统一的工具执行入口。无论底层是计算器、文件读取、搜索服务，还是 MCP 工具，对 Agent 来说都是：

```python
result = tool.run(parameters)
```

在本项目里，这个 `tool` 不是普通 Python 函数，而是 `MCPWrappedTool`，也就是“高德 MCP 子工具的包装对象”。

用天气查询举例，完整变化是：

```text
模型输出文本：
[TOOL_CALL:amap_maps_weather:city=广州]

SimpleAgent 解析得到：
tool_name = "amap_maps_weather"
parameters = "city=广州"

参数转字典：
{"city": "广州"}

ToolRegistry 查表：
self.tool_registry.get_tool("amap_maps_weather")
  → 返回 MCPWrappedTool 对象

执行工具：
tool.run({"city": "广州"})
```

### 第八步：MCPWrappedTool 把普通工具调用转成 MCP 调用

HelloAgents 把每个 MCP 子工具包装成 `MCPWrappedTool`。它的作用是让 Agent 像调用普通 Tool 一样调用 MCP 工具。

为什么需要这一层包装？因为 Agent 看到的工具名是带前缀的：

```text
amap_maps_weather
amap_maps_text_search
```

但高德 MCP server 内部真正认识的工具名通常是不带 `amap_` 前缀的：

```text
maps_weather
maps_text_search
```

所以 `MCPWrappedTool` 要做一次转换：

```text
Agent 调用的 HelloAgents 工具：
amap_maps_weather({"city": "广州"})

转换成 MCPTool 能理解的调用：
{
  "action": "call_tool",
  "tool_name": "maps_weather",
  "arguments": {"city": "广州"}
}
```

源码：

```python
# hello_agents/tools/builtin/mcp_wrapper_tool.py
def run(self, params: Dict[str, Any]) -> str:
    mcp_params = {
        "action": "call_tool",
        "tool_name": self.mcp_tool_name,
        "arguments": params
    }

    return self.mcp_tool.run(mcp_params)
```

例子：

```python
# Agent 层调用的是展开后的工具名
tool_name = "amap_maps_weather"
params = {"city": "广州"}

# MCPWrappedTool 内部会转成：
mcp_params = {
    "action": "call_tool",
    "tool_name": "maps_weather",
    "arguments": {
        "city": "广州"
    }
}
```

注意：这里会把 `amap_maps_weather` 还原成 MCP server 认识的原始工具名 `maps_weather`。

再用景点搜索举例：

```text
Agent 输出：
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]

SimpleAgent 执行：
tool.run({
    "keywords": "历史文化",
    "city": "广州"
})

MCPWrappedTool 转换：
{
    "action": "call_tool",
    "tool_name": "maps_text_search",
    "arguments": {
        "keywords": "历史文化",
        "city": "广州"
    }
}
```

这一步的意义是：Agent 不需要知道 MCP 协议的细节，也不需要知道高德 MCP server 内部原始工具名如何调用。它只需要知道“我可以调用 `amap_maps_text_search`”。

### 第九步：MCPTool 调用 MCP server，再由 MCP server 调用高德 API

`MCPTool.run()` 收到 `action=call_tool` 后，会创建 MCP client，并调用 MCP server 的工具。

这里可以把 `MCPTool` 理解成“HelloAgents 和 MCP server 之间的适配器”：

```text
SimpleAgent / ToolRegistry
  ↓
MCPWrappedTool
  ↓
MCPTool
  ↓
MCPClient
  ↓
amap-mcp-server
  ↓
高德 HTTP API
```

项目中创建 `MCPTool` 时指定了如何启动高德 MCP server：

```python
# backend/app/agents/trip_planner_agent.py
self.amap_tool = MCPTool(
    name="amap",
    description="高德地图服务",
    server_command=["uvx", "amap-mcp-server"],
    env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
    auto_expand=True
)
```

这段代码的含义是：

```text
server_command=["uvx", "amap-mcp-server"]
  → 用 uvx 启动 amap-mcp-server 这个 MCP 服务

env={"AMAP_MAPS_API_KEY": settings.amap_api_key}
  → 把高德 API Key 交给 MCP server

auto_expand=True
  → 自动把 MCP server 提供的多个工具展开成独立工具
```

也就是说，`SimpleAgent` 不负责启动高德服务，也不负责保存高德 API Key；这些都交给 `MCPTool`。

HelloAgents 源码中，`MCPTool.run()` 的核心逻辑是：

```python
# hello_agents/tools/builtin/protocol_tools.py
elif action == "call_tool":
    tool_name = parameters.get("tool_name")
    arguments = parameters.get("arguments", {})
    result = await client.call_tool(tool_name, arguments)
    return f"工具 '{tool_name}' 执行结果:\n{result}"
```

从逻辑上看，它等价于发起一次 MCP 的 `tools/call` 请求：

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "maps_weather",
    "arguments": {
      "city": "广州"
    }
  }
}
```

然后 `amap-mcp-server` 负责真正访问高德 HTTP API。高德 MCP server 收到上面的 `maps_weather` 调用后，大致会做这些事：

```text
1. 读取工具名 maps_weather
2. 读取参数 {"city": "广州"}
3. 读取环境变量 AMAP_MAPS_API_KEY
4. 拼接或构造高德天气 API 请求
5. 向高德服务器发送 HTTP 请求
6. 拿到高德返回的 JSON
7. 把结果按 MCP 协议返回给 MCPTool
```

如果是景点搜索，则逻辑类似：

```text
1. 读取工具名 maps_text_search
2. 读取参数 {"keywords": "历史文化", "city": "广州"}
3. 调用高德 POI 搜索 API
4. 返回景点名称、地址、类型、经纬度等信息
```

因此这条链路里各组件的职责是很清楚的：

| 组件 | 做什么 | 不做什么 |
| --- | --- | --- |
| LLM | 理解 query，决定输出哪个 `[TOOL_CALL]` | 不执行工具，不发 HTTP 请求 |
| SimpleAgent | 解析工具标记，转参数，组织多轮对话 | 不直接访问高德 API |
| ToolRegistry | 按工具名查找工具对象 | 不理解旅游业务 |
| MCPWrappedTool | 把展开后的工具调用转成 MCPTool 的 `call_tool` 格式 | 不直接调用高德 API |
| MCPTool | 启动/连接 MCP server，发送 MCP 调用 | 不决定搜索关键词 |
| amap-mcp-server | 把 MCP 工具调用转换成高德 HTTP API 请求 | 不做行程规划 |
| 高德 API | 返回真实地图、天气、POI 数据 | 不理解用户完整旅行需求 |

也就是说：

```text
Agent 不直接访问高德 API
SimpleAgent 不直接访问高德 API
MCPTool 也不手写高德 HTTP URL
真正对接高德 API 的是 amap-mcp-server
```

这样后端代码只需要关心“我有一个高德工具”，不用关心每个高德接口的 URL、鉴权参数和返回格式细节。

再把天气例子串起来就是：

```text
1. 天气 Agent 收到 query：
   请查询广州的天气信息

2. LLM 输出文本：
   [TOOL_CALL:amap_maps_weather:city=广州]

3. SimpleAgent 用正则解析：
   工具名：amap_maps_weather
   参数：city=广州

4. SimpleAgent 转成参数字典：
   {"city": "广州"}

5. ToolRegistry 查找：
   amap_maps_weather → MCPWrappedTool

6. MCPWrappedTool 转换：
   {
     "action": "call_tool",
     "tool_name": "maps_weather",
     "arguments": {"city": "广州"}
   }

7. MCPTool 通过 MCPClient 请求 amap-mcp-server

8. amap-mcp-server 调用高德天气 API

9. 高德返回真实天气数据

10. 工具结果回到 SimpleAgent

11. SimpleAgent 把工具结果再次交给 LLM

12. LLM 基于工具结果输出最终天气 JSON 或文本
```

### 第十步：工具结果返回给 Agent，Agent 基于结果继续回答

SimpleAgent 的 `run()` 中，如果发现工具调用，就会执行工具，然后把工具结果重新加入对话，让模型基于工具结果生成最终答案。

源码：

```python
# hello_agents/agents/simple_agent.py
while current_iteration < max_tool_iterations:
    response = self.llm.invoke(messages, **kwargs)
    tool_calls = self._parse_tool_calls(response)

    if tool_calls:
        tool_results = []
        clean_response = response

        for call in tool_calls:
            result = self._execute_tool_call(call['tool_name'], call['parameters'])
            tool_results.append(result)
            clean_response = clean_response.replace(call['original'], "")

        messages.append({"role": "assistant", "content": clean_response})

        tool_results_text = "\n\n".join(tool_results)
        messages.append({
            "role": "user",
            "content": f"工具执行结果：\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"
        })

        current_iteration += 1
        continue
```

这一步非常关键：工具调用不是最终答案。工具结果会再次喂给模型，模型再把结果整理成项目需要的 JSON。

例子：

```text
第一轮模型输出：
[TOOL_CALL:amap_maps_weather:city=广州]

框架执行工具，得到天气结果。

第二轮模型输入中加入：
工具执行结果：
广州未来几天天气...
请基于这些结果给出完整的回答。

第二轮模型输出：
[
  {
    "date": "2026-05-11",
    "day_weather": "小雨",
    "night_weather": "阴",
    "day_temp": 26,
    "night_temp": 21
  }
]
```

## 三、本项目里 Agent 工具调用的完整例子

### 例子 1：天气查询

用户请求进入后端后，系统先执行天气 Agent：

```python
# backend/app/agents/trip_planner_agent.py
weather_query = f"请查询{request.city}的天气信息"
weather_response = self._run_agent_with_cancellation(
    self.weather_agent,
    weather_query,
    cancellation_token,
    "天气查询",
)
```

假设 `request.city = "广州"`，天气 Agent 会收到：

```text
请查询广州的天气信息
```

根据提示词，它生成：

```text
[TOOL_CALL:amap_maps_weather:city=广州]
```

底层执行链路：

```text
amap_maps_weather
  ↓
MCPWrappedTool
  ↓
MCPTool.run({
    "action": "call_tool",
    "tool_name": "maps_weather",
    "arguments": {"city": "广州"}
  })
  ↓
amap-mcp-server
  ↓
高德天气 API
  ↓
返回天气结果
```

本项目还做了一个可靠性处理：天气解析优先使用工具原始结果，而不是 Agent 整理后的文本。

```python
# backend/app/agents/trip_planner_agent.py
def _select_weather_parsing_source(self, weather_response: str) -> str:
    """天气解析优先使用 maps_weather 工具原始结果，避免受 Agent 表格文案影响。"""
    stage_results = self._ensure_stage_tool_results().get("天气查询", [])
    for item in reversed(stage_results):
        tool_name = item.get("tool_name", "")
        payload = item.get("result", "")
        if "weather" not in tool_name.lower():
            continue
        if payload and any(keyword in payload for keyword in ('"forecasts"', '"dayweather"', '"nightweather"', '"date"')):
            return payload
    return weather_response
```

解释：如果 Agent 把天气结果整理成了表格或自然语言，可能会丢字段；所以程序优先解析工具原始返回，这样更稳定。

### 例子 2：景点搜索

景点搜索不是简单地搜索“景点”，而是结合天气和用户偏好构建 query：

```python
# backend/app/agents/trip_planner_agent.py
attraction_query = self._build_attraction_query(request, weather_info)
attraction_response = self._run_agent_with_cancellation(
    self.attraction_agent,
    attraction_query,
    cancellation_token,
    "景点搜索",
)
```

假设用户喜欢“历史文化”，目的地是“广州”，Agent 可能调用：

```text
[TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=广州]
```

如果天气风险较高，Agent 可能更倾向于室内关键词：

```text
[TOOL_CALL:amap_maps_text_search:keywords=博物馆,city=广州]
```

工具返回后，景点 Agent 必须输出项目要求的 JSON 数组：

```json
[
  {
    "name": "广东省博物馆",
    "address": "广东省广州市天河区珠江东路2号",
    "location": {
      "longitude": 113.3275,
      "latitude": 23.1188
    },
    "type": "科教文化服务",
    "rating": "4.6",
    "id": "B00140..."
  }
]
```

这里要求保留 `location`，是因为前端地图展示和后续路线规划都依赖坐标。

### 例子 3：酒店搜索

酒店 Agent 的输入包含用户住宿偏好：

```python
# backend/app/agents/trip_planner_agent.py
hotel_query = (
    f"请搜索{request.city}的{request.accommodation}酒店。"
    f"如果工具返回里包含价格、价格区间、priceLevel、评分、酒店类型，请原样保留，"
    f"以便后续规划阶段生成 hotel.estimated_cost 和 budget.total_hotels。"
)
```

假设用户选择“经济型”，城市是广州，Agent 调用：

```text
[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=广州]
```

然后根据工具结果筛选酒店，并输出：

```json
[
  {
    "name": "某某酒店",
    "address": "广州市天河区...",
    "location": {
      "longitude": 113.32,
      "latitude": 23.13
    },
    "type": "经济型酒店",
    "rating": "4.4",
    "price_range": "200-300元",
    "id": "B0..."
  }
]
```

酒店 Agent 提示词里特别强调：

```text
如果最终输出的酒店对象没有 location,该输出视为不合格
```

原因是行程规划阶段需要判断“酒店离当天最后一个景点近不近、离第二天第一个景点是否方便”。

## 四、本项目有哪些工具可以调用，各自作用是什么

当前项目核心使用的是高德 MCP 工具。由于 `MCPTool(name="amap", auto_expand=True)`，工具会以 `amap_` 作为前缀展开。

| 工具名 | 作用 | 本项目中的用途 |
| --- | --- | --- |
| `amap_maps_text_search` | 按关键词和城市搜索 POI | 搜索景点、搜索酒店 |
| `amap_maps_weather` | 查询城市天气预报 | 生成天气信息、做天气风险评估 |
| `amap_maps_geo` | 地址转经纬度 | 后续可用于坐标补全 |
| `amap_maps_search_detail` | 根据 POI id 查询详情 | 后续可用于补充评分、电话、营业信息等 |
| `amap_maps_direction_walking_by_address` | 步行路线规划 | 后续可用于路线优化 |
| `amap_maps_direction_driving_by_address` | 驾车路线规划 | 后续可用于自驾行程 |
| `amap_maps_direction_transit_integrated_by_address` | 公交/地铁路线规划 | 后续可用于公共交通行程 |

注意：当前核心生成流程主要依赖前两个工具：

```text
amap_maps_text_search：景点和酒店候选
amap_maps_weather：天气查询和风险评估
```

路线规划类工具目前更多是扩展能力。答辩时可以说：本系统已经通过 MCP 接入了路线规划类工具，但当前版本主要将路线合理性放在规划提示词和后处理约束中，后续可以进一步让 Agent 显式调用路线工具做路径优化。

## 五、为什么这个设计适合我的多智能体旅行规划系统

### 1. 每个 Agent 只拿自己需要的工具和任务

本项目有四个 Agent：

```text
天气查询 Agent：查天气
景点搜索 Agent：查景点
酒店推荐 Agent：查酒店
行程规划 Agent：整合信息
```

前三个 Agent 注册高德工具，最后一个不注册工具。

这样拆分的好处是：每个 Agent 的任务简单，提示词也更容易写准确。

### 2. 工具结果作为规划依据，减少幻觉

景点和酒店不是模型凭空生成，而是来自 `amap_maps_text_search`。

天气不是模型猜测，而是来自 `amap_maps_weather`。

所以最终行程是：

```text
真实天气数据
  + 真实 POI 候选
  + 用户偏好
  + 预算/天数/住宿约束
  → 行程规划 Agent 生成结构化计划
```

### 3. 便于调试

本项目专门包装了工具的 `run()` 方法，用来打印工具调用前后的信息：

```python
# backend/app/agents/trip_planner_agent.py
def _debug_capture_agent_tools(self, agent: SimpleAgent, stage: str):
    """临时包装 Agent 工具，打印工具入参与返回值。"""
    registry = getattr(agent, "tool_registry", None)
    tools = registry.get_all_tools() if registry else []

    def make_wrapper(tool: Any, original_run: Any):
        def wrapped_run(parameters: Dict[str, Any]) -> str:
            print(f"   [2/3] 工具调用前 -> {tool.name}")
            print(f"         参数: {_preview_text(parameters, limit=300)}")
            result = original_run(parameters)
            self._ensure_stage_tool_results()[stage].append(
                {
                    "tool_name": getattr(tool, "name", "") or tool.__class__.__name__,
                    "result": str(result),
                }
            )
            print(f"   [2/3] 工具返回后 <- {tool.name}")
            print(f"         返回: {_preview_text(result)}")
            return result
        return wrapped_run
```

这使一次 Agent 调用可以拆成三段看：

```text
[1/3] 发送给 Agent 的 query
[2/3] 工具调用前后的参数和返回
[3/3] Agent 最终输出文本
```

答辩时可以这样讲：

> 我不是只看模型最后生成了什么，而是把 Agent 输入、工具调用参数、工具原始返回、最终输出都记录下来。这样如果结果不合理，可以判断是 query 写得不好、工具返回不完整，还是模型整理结果时出了问题。

## 六、答辩时可以这样总结

可以用下面这段话回答老师：

> 本项目没有让 Agent 直接拼接高德 API URL，而是把高德服务封装成 MCP 工具注册到 HelloAgents 中。这样做有三个原因。第一，Agent 可以根据用户偏好、天气风险和当前任务自主决定调用什么工具、传什么参数，而不是后端写死查询逻辑。第二，景点、酒店、天气这些事实信息来自高德工具返回，可以减少大模型编造。第三，MCPTool 把 API Key、进程通信、工具发现、参数传递和结果返回统一封装，后端只需要注册工具，不需要为每个高德接口写一套调用逻辑。底层流程是：模型输出 `[TOOL_CALL:工具名:参数]`，SimpleAgent 用正则解析工具名和参数，通过 ToolRegistry 找到对应工具，调用 `tool.run()`；如果是 MCP 工具，就转成 `call_tool` 请求交给 `amap-mcp-server`，由它调用高德 API，最后工具结果再回到 Agent，由 Agent 基于真实结果生成结构化 JSON。
