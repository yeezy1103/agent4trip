# HelloAgents Trip Planner

一个基于 `HelloAgents + FastAPI + Vue 3` 的多智能体旅行规划系统。项目目标不是单纯生成一段“旅游文案”，而是把天气、地图 POI、酒店候选、预算信息和前端可编辑展示串成一条完整链路，输出结构化的多日旅行计划。

当前仓库由两个核心部分组成：

- `backend/`：负责多智能体协作、地图工具接入、旅行计划生成、结构化校验与回退。
- `frontend/`：负责用户输入、生成进度展示、结果可视化、地图展示、导出和前端侧二次编辑。

---

## 1. 项目概览

### 1.1 这个项目解决什么问题

用户输入目的地、日期、交通方式、住宿偏好、旅行偏好和额外要求后，系统会生成一份结构化行程，包含：

- 每日景点安排
- 每日餐饮建议
- 酒店建议
- 天气信息与风险提示
- 总体出行建议
- 预算汇总

与常见“纯 LLM 输出”方案不同，这个项目在后端加入了多层约束与校验：

- 先查天气，再根据天气风险决定景点搜索倾向
- 使用高德地图 MCP 工具查询真实候选景点和酒店
- 要求规划 Agent 返回严格 JSON
- 对生成结果做结构修正、候选对齐、预算重算和天气一致性检查
- 解析失败或流程异常时自动生成安全回退行程

### 1.2 当前架构特点

- 后端 API 框架：`FastAPI`
- 智能体框架：`hello-agents`
- 地图工具接入方式：`MCPTool + amap-mcp-server`
- 前端框架：`Vue 3 + TypeScript + Vite`
- UI：`Ant Design Vue`
- 地图展示：`高德 JS API`
- 导出能力：`html2canvas + jsPDF`

---

## 2. 整体架构

### 2.1 高层结构

```text
用户表单输入
    ↓
frontend/Home.vue
    ↓
POST /api/trip/plan
    ↓
backend FastAPI 路由
    ↓
MultiAgentTripPlanner
    ↓
天气 Agent / 景点 Agent / 酒店 Agent / 行程规划 Agent
    ↓
解析服务 + 后处理服务 + 天气风险校验
    ↓
结构化 TripPlan JSON
    ↓
frontend/Result.vue 展示、编辑、地图渲染、导出
```

### 2.2 一次请求的实际处理流程

`POST /api/trip/plan` 的主流程位于 `backend/app/api/routes/trip.py` 与 `backend/app/agents/trip_planner_agent.py`：

1. 前端提交旅行请求。
2. 后端先校验城市名、日期范围和基本参数。
3. 创建 `PlanningCancellationToken`，支持前端停止生成。
4. `MultiAgentTripPlanner.plan_trip()` 启动多智能体协作：
   - 天气 Agent 查询天气
   - 根据天气风险构造景点搜索 query
   - 景点 Agent 搜索候选景点
   - 酒店 Agent 搜索候选酒店
   - 行程规划 Agent 综合上述上下文生成最终 JSON
5. `TripPlanningParsingService` 负责从模型输出中提取 JSON 并解析为 `TripPlan`。
6. `TripPlanningPostProcessService` 对结果做后处理：
   - 补齐缺失天数
   - 纠正日期与 day index
   - 确保每天有三餐结构
   - 校验天气风险与景点安排是否匹配
   - 尝试优化景点顺序和酒店位置合理性
   - 重算预算
7. 如果解析失败或流程报错，生成 `fallback` 安全回退行程。
8. 前端接收结果后写入 `sessionStorage`，跳转结果页展示。

---

## 3. 目录与文件职责

## 3.1 后端目录

```text
backend/
├── app/
│   ├── agents/
│   │   └── trip_planner_agent.py
│   ├── api/
│   │   ├── main.py
│   │   └── routes/
│   │       ├── trip.py
│   │       ├── map.py
│   │       └── poi.py
│   ├── models/
│   │   └── schemas.py
│   ├── services/
│   │   ├── llm_service.py
│   │   ├── amap_service.py
│   │   ├── unsplash_service.py
│   │   ├── weather_planning_service.py
│   │   ├── trip_planning_parsing_service.py
│   │   └── trip_planning_postprocess_service.py
│   ├── __init__.py
│   └── config.py
├── logs/
├── tests/
│   └── test_weather_planning.py
├── prompt.md
├── requirements.txt
├── run.py
└── .env
```

### 3.1.1 `backend/app/api/main.py`

后端应用入口，主要职责：

- 创建 `FastAPI` 应用
- 配置 CORS
- 注册三个路由模块：
  - `trip`
  - `poi`
  - `map`
- 在启动阶段打印配置并校验必要环境变量
- 提供 `/` 与 `/health` 健康检查接口

### 3.1.2 `backend/app/config.py`

统一配置中心，使用 `pydantic-settings` 管理配置。特点：

- 先加载当前目录 `.env`
- 再尝试加载上级 `HelloAgents/.env`
- 维护应用名、端口、CORS、高德密钥、Unsplash 密钥、LLM 配置等
- `validate_config()` 当前强制要求 `AMAP_API_KEY`
- LLM Key 只做警告，不会在启动前强制阻断

### 3.1.3 `backend/app/models/schemas.py`

后端核心数据模型定义，覆盖整个请求与响应链路：

- 输入模型：
  - `TripRequest`
  - `POISearchRequest`
  - `RouteRequest`
- 领域模型：
  - `Location`
  - `Attraction`
  - `Meal`
  - `Hotel`
  - `DayPlan`
  - `WeatherInfo`
  - `Budget`
  - `TripPlan`
- 输出模型：
  - `TripPlanResponse`
  - `POISearchResponse`
  - `RouteResponse`
  - `WeatherResponse`

这是 README、接口文档和前端类型对齐时最重要的一层。

### 3.1.4 `backend/app/api/routes/trip.py`

旅行规划主入口。

关键点：

- 路由前缀：`/api/trip`
- 主接口：`POST /api/trip/plan`
- 会检查客户端是否断开连接
- 一旦前端取消或断连，会触发后端协作式取消
- 返回值统一包装为：

```json
{
  "success": true,
  "message": "旅行计划生成成功",
  "data": { "..." : "TripPlan" }
}
```

还提供 `GET /api/trip/health` 用于检查旅行规划服务本身是否可用。

### 3.1.5 `backend/app/api/routes/map.py`

地图服务聚合路由，前缀 `/api/map`：

- `GET /api/map/poi`：搜索 POI
- `GET /api/map/weather`：查询天气
- `POST /api/map/route`：路线规划
- `GET /api/map/health`：地图服务健康检查

这部分主要面向调试或将来扩展，不是当前前端主流程的核心入口。

### 3.1.6 `backend/app/api/routes/poi.py`

POI 与图片相关接口，前缀 `/api/poi`：

- `GET /api/poi/detail/{poi_id}`：获取 POI 详情
- `GET /api/poi/search`：根据关键词搜索 POI
- `GET /api/poi/photo?name=...`：从 Unsplash 获取景点图片

结果页加载景点卡片图片时会调用 `photo` 接口。

### 3.1.7 `backend/app/agents/trip_planner_agent.py`

这是后端最核心的文件，负责搭建整个多智能体系统。

主要组成：

- `PlanningCancellationToken`
  - 用于生成过程中的协作式取消
- `TripPlanningCancelledError`
  - 表示规划过程被中止
- `InvalidTripRequestError`
  - 表示输入请求本身不合法
- 四个 Agent：
  - `景点搜索专家`
  - `天气查询专家`
  - `酒店推荐专家`
  - `行程规划专家`
- 一个共享的 `MCPTool(amap)`
  - 通过 `uvx amap-mcp-server` 接入高德能力

这个类不是简单“串行调用模型”，而是在做以下事情：

- 兼容不同 `hello_agents` 版本对 MCP 工具展开行为的差异
- 基于天气风险动态调整景点搜索 query
- 从景点/酒店 Agent 输出中抽取结构化候选
- 为最终规划 Agent 注入候选池和空间约束
- 对最终生成结果做解析与回退处理

### 3.1.8 `backend/app/services/llm_service.py`

LLM 单例工厂。

特点：

- 使用 `HelloAgentsLLM()`
- 实际 provider/model 读取环境变量
- 代码里虽然保留了 `openai_base_url`、`openai_model` 等字段，但真正使用时主要依赖 `HelloAgentsLLM` 自己读取配置

### 3.1.9 `backend/app/services/amap_service.py`

高德 MCP 工具的服务封装。

当前用途有两类：

- 给多智能体系统提供 MCPTool 实例
- 给 FastAPI 普通接口提供 `search_poi`、`get_weather`、`plan_route`、`get_poi_detail` 等服务方法

需要注意：

- `get_weather()` 已经会把原始天气结果转成结构化 `WeatherInfo`
- `get_poi_detail()` 会尝试从文本中提取 JSON
- `search_poi()`、`plan_route()`、`geocode()` 目前存在明显的 `TODO`，有些接口返回的是空列表或空对象，说明这部分更偏“预留/半成品能力”

### 3.1.10 `backend/app/services/weather_planning_service.py`

天气相关逻辑的核心文件，包含：

- 旅行日期序列生成
- 非结构化天气文本解析
- 天气 JSON 结构抽取
- 风险评分
- 风险等级分类
- 针对高/中/低风险天气生成规划建议
- 室内/户外景点判断
- 把天气约束转成提示词文本

这个模块决定了“天气不是展示信息，而是规划约束”的能力。

### 3.1.11 `backend/app/services/trip_planning_parsing_service.py`

负责“把模型输出变成可落库、可展示、可验证的结构化计划”。

核心能力：

- 从 Markdown 代码块或自由文本中提取 JSON 片段
- 解析 `TripPlan`
- 失败时保存原始响应到 `backend/logs/last_trip_plan_response.txt`
- 从景点/酒店搜索结果中提取候选记录
- 候选去重
- 候选景点/酒店 payload 构建

注意：

- 代码里明确写了“JSON 修复逻辑已禁用”，也就是当前版本更强调验证模型是否能稳定输出严格 JSON
- 如果解析失败，会直接走 fallback，而不是尽力修 JSON

### 3.1.12 `backend/app/services/trip_planning_postprocess_service.py`

后处理与兜底模块，负责把“可能不完美的模型输出”进一步变成“更安全、更稳定的成品”。

主要处理内容：

- 补齐缺失天数
- 对齐日期与 day index
- 自动补全每日三餐结构
- 校验景点是否来自候选池
- 校验天气风险与景点安排是否匹配
- 调整景点顺路性
- 对齐酒店和今明两日动线关系
- 重算预算
- 合并总体建议
- 生成回退行程

如果从工程视角看，这个模块是项目鲁棒性的关键。

### 3.1.13 `backend/app/services/unsplash_service.py`

封装 Unsplash 图片搜索。

主要用于：

- 根据景点名称搜索图片
- 返回单张图片 URL

结果页展示时，如果图片接口失败，前端还会自动回退到本地图库或 SVG 占位图。

### 3.1.14 `backend/tests/test_weather_planning.py`

当前测试主要覆盖天气解析与风险分级逻辑，包括：

- JSON 格式天气预报解析
- Markdown 文本天气预报解析
- “今天/明天/后天”格式解析
- 中文完整日期头解析
- 风险等级与建议文本校验

说明当前测试重点在“天气到规划约束”这条链路，而不是整个端到端系统。

---

## 3.2 前端目录

```text
frontend/
├── public/
├── src/
│   ├── assets/
│   │   ├── images/
│   │   └── argon-scss/
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   │   └── index.ts
│   ├── views/
│   │   ├── Home.vue
│   │   └── Result.vue
│   ├── App.vue
│   ├── main.ts
│   ├── design-system.css
│   └── vite-env.d.ts
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
└── .env
```

### 3.2.1 `frontend/src/main.ts`

前端入口，负责：

- 创建 Vue 应用
- 创建 Vue Router
- 注册 `Home` 与 `Result` 两个页面
- 注册 `Ant Design Vue`
- 挂载全局样式 `design-system.css`

### 3.2.2 `frontend/src/App.vue`

应用壳层。

主要职责：

- 渲染统一背景和顶部 Header
- 提供全局布局容器
- 通过 `<router-view />` 承载页面切换

### 3.2.3 `frontend/src/views/Home.vue`

首页表单页，也是整个交互流程的起点。

主要功能：

- 收集目的地、日期、天数、交通、住宿、偏好、额外要求
- 基于日期自动计算 `travel_days`
- 对城市名进行前端格式校验
- 发起 `generateTripPlan()` 请求
- 展示生成进度条与状态文案
- 使用 `AbortController` 支持停止生成
- 记录生成耗时
- 把结果写入 `sessionStorage`
- 成功后跳转到 `/result`

当前首页的“进度条”是前端模拟进度，不是后端真实分阶段流式状态。

### 3.2.4 `frontend/src/views/Result.vue`

结果页是前端最复杂的页面。

主要能力：

- 从 `sessionStorage` 读取行程与耗时
- 渲染行程概览、预算、地图、每日安排
- 显示天气和风险建议
- 加载景点图片
- 支持前端侧编辑景点信息
- 支持调整景点顺序
- 支持删除景点
- 支持把修改结果重新写回 `sessionStorage`
- 支持导出为图片
- 支持导出为 PDF
- 使用高德 JS API 渲染地图

注意：

- 结果页的编辑是前端本地编辑，不会回写后端
- 图片优先走后端 `poi/photo` 接口，失败时回退本地图片或占位图

### 3.2.5 `frontend/src/services/api.ts`

API 访问层，当前最重要的方法是：

- `generateTripPlan(formData, signal?)`
- `healthCheck()`

特点：

- 基于 `axios.create()` 创建客户端
- 支持 `AbortSignal`
- 支持前端超时配置
- 对取消请求和超时做了自定义报错提示

### 3.2.6 `frontend/src/types/index.ts`

定义前端使用的 TypeScript 领域类型，和后端 `schemas.py` 基本对应：

- `TripFormData`
- `TripPlan`
- `DayPlan`
- `Attraction`
- `Meal`
- `Hotel`
- `Budget`
- `WeatherInfo`

这层决定了前后端数据结构协作是否稳定。

### 3.2.7 `frontend/vite.config.ts`

主要配置：

- `@` 指向 `src`
- 本地开发端口：`5173`
- 代理 `/api -> http://localhost:8000`

### 3.2.8 `frontend/src/assets/argon-scss/`

这是项目中保留的大量样式资源目录，包含 Bootstrap/Argon Design System 的 SCSS 文件。

从当前代码使用情况看：

- 实际运行的核心样式主要还是 `design-system.css` 和页面内样式
- `argon-scss` 更像是设计资源沉淀或可选样式资产，不是当前主渲染逻辑的核心

---

## 4. 技术栈

### 4.1 后端

- Python
- FastAPI
- Uvicorn
- Pydantic / pydantic-settings
- hello-agents
- MCPTool
- amap-mcp-server
- python-dotenv
- httpx / aiohttp

### 4.2 前端

- Vue 3
- TypeScript
- Vite
- Vue Router
- Ant Design Vue
- Axios
- `@amap/amap-jsapi-loader`
- `@wxperia/liquid-glass-vue`
- `html2canvas`
- `jspdf`

---

## 5. 后端核心设计说明

## 5.1 多智能体分工

系统目前拆成四类 Agent：

- 天气查询 Agent
  - 强制通过高德工具获取天气
- 景点搜索 Agent
  - 强制通过高德工具搜索候选景点
- 酒店推荐 Agent
  - 强制通过高德工具搜索酒店候选
- 行程规划 Agent
  - 不直接调工具，负责整合信息并输出严格 JSON

这种拆法的好处是：

- 每个 Agent 的任务边界更清晰
- 规划前能拿到更真实的约束信息
- 更方便在后续替换某一环的策略

## 5.2 为什么先查天气

代码里不是“最后附上一段天气说明”，而是在景点搜索阶段就把天气作为约束条件。

例如：

- 高风险天气：优先博物馆、展馆、室内景点
- 中风险天气：优先同区域、可灵活调整的景点
- 低风险天气：正常规划，但仍要保证动线紧凑

这让天气真正参与了规划逻辑。

## 5.3 候选池机制

项目不会直接让规划 Agent 自由编造全部内容，而是尽量先构造候选池：

- 从景点搜索结果提取候选景点
- 从酒店搜索结果提取候选酒店
- 把候选的坐标、类别、邻近关系、区域标签喂给规划 Agent

这一步的意义是：

- 降低胡编景点的概率
- 提升空间连续性
- 为后处理阶段提供对齐依据

## 5.4 回退机制

如果任一步骤失败，后端不会直接 500 结束，而是尽量返回一个“可展示、可用但更保守”的 fallback 行程。

fallback 行程特征：

- 根据天气风险决定景点类型
- 自动生成基础餐饮结构
- 给出稳妥的每日描述
- 自动重算预算
- 标记 `validation_status = "fallback"`

这对 Demo、课程项目和答辩场景尤其重要。

---

## 6. 前端核心交互说明

## 6.1 首页输入体验

首页表单围绕“低门槛输入，高反馈感知”设计：

- 日期变化时自动计算天数
- 城市名非法时弹出错误提示
- 生成阶段显示进度、状态文案、耗时
- 用户可以点击“停止生成”

## 6.2 结果页体验

结果页不是简单文本回显，而是做成了一个完整的旅行概览页面：

- 行程总览卡片
- 预算明细卡片
- 地图板块
- 每日折叠行程
- 天气横幅与风险建议
- 景点图片卡片
- 本地编辑与重排
- 图片/PDF 导出

## 6.3 前端状态存储方式

当前没有引入全局状态管理，而是通过 `sessionStorage` 在页面之间传递：

- `tripPlan`
- `generationTime`

这意味着：

- 刷新结果页后仍能恢复当前会话中的计划
- 但关闭浏览器标签页后数据不会长期保留

---

## 7. 环境变量与配置

## 7.1 后端环境变量

后端代码里实际涉及的关键变量包括：

- `AMAP_API_KEY`
  - 高德地图 API Key，后端启动校验强依赖
- `LLM_API_KEY` 或 `OPENAI_API_KEY`
  - LLM Key，未配置时会警告
- `LLM_BASE_URL`
  - 可选，自定义模型服务地址
- `LLM_MODEL_ID`
  - 可选，指定模型
- `OPENAI_BASE_URL`
  - 配置中保留，兼容某些场景
- `OPENAI_MODEL`
  - 配置中保留，默认值是 `gpt-4`
- `UNSPLASH_ACCESS_KEY`
  - 景点图片搜索用
- `UNSPLASH_SECRET_KEY`
  - 当前代码里基本未直接使用
- `CORS_ORIGINS`
  - 逗号分隔字符串
- `HOST`
- `PORT`
- `LOG_LEVEL`

后端已有 `backend/.env`，实际使用时请根据自己的环境确认内容是否正确。

## 7.2 前端环境变量

前端代码中明确使用了：

- `VITE_API_BASE_URL`
  - 默认值为 `http://localhost:8000`
- `VITE_API_TIMEOUT`
  - 默认 10 分钟
- `VITE_AMAP_WEB_JS_KEY`
  - 结果页初始化高德地图时需要

前端已有 `frontend/.env`，同样建议按本地环境核对。

---

## 8. 安装与运行

## 8.1 环境要求

- Python 3.10 及以上
- Node.js 18 及以上更稳妥
- 可用的高德地图 API Key
- 可用的 LLM API Key
- 本地可执行 `uvx`，因为高德 MCP 服务通过 `uvx amap-mcp-server` 启动

## 8.2 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

或者：

```bash
cd backend
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`
- `http://localhost:8000/health`

## 8.3 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- `http://localhost:5173`

---

## 9. API 说明

## 9.1 旅行计划接口

### `POST /api/trip/plan`

请求体示例：

```json
{
  "city": "北京",
  "start_date": "2026-05-01",
  "end_date": "2026-05-03",
  "travel_days": 3,
  "transportation": "公共交通",
  "accommodation": "经济型酒店",
  "preferences": ["历史文化", "美食"],
  "free_text_input": "希望多安排一些博物馆"
}
```

成功响应结构：

```json
{
  "success": true,
  "message": "旅行计划生成成功",
  "data": {
    "city": "北京",
    "start_date": "2026-05-01",
    "end_date": "2026-05-03",
    "days": [],
    "weather_info": [],
    "overall_suggestions": "",
    "budget": {
      "total_attractions": 0,
      "total_hotels": 0,
      "total_meals": 0,
      "total_transportation": 0,
      "total": 0
    },
    "validation_status": "validated",
    "fallback_used": false,
    "warnings": []
  }
}
```

## 9.2 地图相关接口

- `GET /api/map/poi`
- `GET /api/map/weather`
- `POST /api/map/route`

## 9.3 POI 相关接口

- `GET /api/poi/detail/{poi_id}`
- `GET /api/poi/search`
- `GET /api/poi/photo`

---

## 10. 前后端数据流

### 10.1 首页到结果页

1. 用户在 `Home.vue` 填表。
2. 调用 `generateTripPlan()`。
3. 后端返回 `TripPlanResponse`。
4. 前端把 `response.data` 写入 `sessionStorage.tripPlan`。
5. 前端把生成秒数写入 `sessionStorage.generationTime`。
6. 跳转到 `/result`。

### 10.2 结果页展示

1. `Result.vue` 在 `onMounted` 时读取 `sessionStorage`。
2. 先渲染文本和预算。
3. 再初始化高德地图。
4. 并行请求每个景点的图片。
5. 用户如有编辑，修改仅保存在前端会话里。

---

## 11. 当前代码中的亮点

- 后端不是单次模型调用，而是多智能体协作
- 天气信息直接参与规划约束
- 具备取消生成能力
- 有比较完善的后处理和 fallback 机制
- 前端结果页完成度较高，支持地图、图片、编辑、导出
- 前后端类型结构相对统一

---

## 12. 当前已知问题与限制

这部分是根据当前代码实际状态整理的，不是泛泛而谈。

- `README.md` 原文件存在 Git 冲突标记，现已重写修复。
- `backend/app/services/amap_service.py` 中部分通用 API 封装仍有 `TODO`，例如：
  - `search_poi()` 当前打印结果后返回空列表
  - `plan_route()` 当前打印结果后返回空对象
  - `geocode()` 当前返回 `None`
- 当前结果页编辑仅保存在前端 `sessionStorage`，不会同步回后端。
- 首页进度条是模拟进度，不代表后端真实执行百分比。
- 行程生成仍高度依赖模型输出严格 JSON；当前 JSON 自动修复逻辑被显式禁用。
- 前端对地图的依赖需要单独配置 `VITE_AMAP_WEB_JS_KEY`，否则地图板块无法正常初始化。
- Unsplash 图片能力依赖外部 Key，未配置时会退回本地图库或占位图。

---

## 13. 建议后续演进方向

- 补完 `AmapService` 中 `search_poi`、`route`、`geocode` 的真实结构化解析
- 给前端编辑结果增加“保存到后端”能力
- 为旅行计划主流程补充端到端测试
- 引入流式生成或阶段性事件推送，让进度条变成真实进度
- 恢复或替换更稳健的 JSON 修复策略
- 增加行程持久化与历史记录

---

## 14. 快速定位关键文件

- 后端入口：[backend/app/api/main.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/api/main.py)
- 旅行规划路由：[backend/app/api/routes/trip.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/api/routes/trip.py)
- 多智能体主逻辑：[backend/app/agents/trip_planner_agent.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/agents/trip_planner_agent.py)
- 数据模型：[backend/app/models/schemas.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/models/schemas.py)
- 天气规划服务：[backend/app/services/weather_planning_service.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/services/weather_planning_service.py)
- 解析服务：[backend/app/services/trip_planning_parsing_service.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/services/trip_planning_parsing_service.py)
- 后处理服务：[backend/app/services/trip_planning_postprocess_service.py](/Users/yeezy/Desktop/helloagents-trip-planner/backend/app/services/trip_planning_postprocess_service.py)
- 前端入口：[frontend/src/main.ts](/Users/yeezy/Desktop/helloagents-trip-planner/frontend/src/main.ts)
- 首页表单：[frontend/src/views/Home.vue](/Users/yeezy/Desktop/helloagents-trip-planner/frontend/src/views/Home.vue)
- 结果页：[frontend/src/views/Result.vue](/Users/yeezy/Desktop/helloagents-trip-planner/frontend/src/views/Result.vue)
- 前端 API 封装：[frontend/src/services/api.ts](/Users/yeezy/Desktop/helloagents-trip-planner/frontend/src/services/api.ts)
- 前端类型：[frontend/src/types/index.ts](/Users/yeezy/Desktop/helloagents-trip-planner/frontend/src/types/index.ts)

---

## 15. 许可证

仓库原 README 中声明为：

`CC BY-NC-SA 4.0`

如果后续要正式开源，建议再确认一次仓库根目录是否需要单独补充 `LICENSE` 文件。
