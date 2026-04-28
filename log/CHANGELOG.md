# 更新日志 (Changelog)

基于最新一次代码提交的对比，以下是项目中更新的功能与修复的 Bug 总结：

## 2026-04-19

### 🚀 更新的功能 (New Features & Enhancements)

1. **天气约束与规划逻辑前置**
   - **重构多智能体流程**：将天气信息的查询与评估提到最前面。景点搜索 Agent 和行程规划 Agent 现已能够根据天气风险（如高风险、中风险）优先搜索和安排室内/半室内景点，大幅提升行程的合理性。
   - **新增风险评估字段**：后端接口数据结构中新增了 `risk_level`（风险等级）、`risk_score`（风险分值）和 `planning_advice`（天气建议），使前端能够直接获取结构化的天气指导。

2. **支持“停止生成”行程**
   - **前端请求中断**：在首页进度条下方新增了“停止生成”按钮。
   - **API 优化**：底层请求接入了 `AbortController`，用户可以在漫长的规划过程中随时取消请求，优化了交互体验。

3. **每日行程天气 UI 重构**
   - **可视化天气建议**：在结果页（Result.vue）的每日行程模块顶部，新增了独立的结构化天气建议框。
   - **动态风险警示**：根据后端的 `risk_level`，天气建议框会自动呈现不同的视觉效果（低风险为绿色提示，中风险为橙色警告，高风险为红色警报），并配以相应的图标，提升了美观度与警示作用。

4. **总体建议排版优化**
   - 优化了结果概览中“总体建议”的文本解析逻辑，去除了多余的 Markdown 标记（如 `**`），支持多行文本的优雅渲染，显著提升了可读性。
   - 后端不再把“天气校正说明”强行追加到总体建议中，实现了天气建议与总体建议的逻辑解耦。

5. **地图展示能力增强**
   - **新增酒店标记**：结果页的高德地图中，现在不仅会绘制景点坐标，还会把每日推荐的“住宿酒店”以特殊标记的形式展示在地图上，并在点击时弹出酒店详细信息。

### 🐛 修复的 Bug (Bug Fixes)

1. **日期选择与表单校验 Bug**
   - **修复日期倒挂**：修复了用户可以“选择结束日期早于开始日期”的交互漏洞（通过在组件层添加 `disabled-date` 限制）。
   - **增强前置拦截**：在点击“开始规划我的旅行”时，若未填写目的地城市或未正确选择日期，系统会第一时间弹出拦截警告，阻止非法请求发往后端。

2. **天气数据解析遗漏**
   - 修复了 `amap_service.py` 中天气查询结果始终返回空数组 `[]` 的占位问题，现已正确调用 `parse_weather_response` 提取真实的预报数据。

3. **地图渲染异常**
   - 修复了由于大模型幻觉可能生成缺失经纬度（坐标失效）的景点或酒店，导致高德地图初始化/绘制路线崩溃的问题（加入了严格的 `hasValidLocation` 安全校验）。

4. **冗余文件清理**
   - 移除了项目根目录下已废弃的 `MIGRATION_ARGON.md` 文档。

## 2026-04-19

1. 问题：实现：大模型接口超时,系统提示生成失败或稍后重试，不出现死循环;如何进行测试？
当前后端在任意异常下都会返回“安全回退方案”，这会把真正的 LLM 超时伪装成“成功”；我准备把“大模型超时”单独识别成失败态，并让前端明确提示“生成失败/稍后重试”。
我会把“超时”从普通异常里剥离出来，让它直接走失败分支而不是回退成功，同时补一个后端测试覆盖这个场景。
我现在开始改后端异常分支：识别超时、停止回退、返回 504，再补单测验证不会继续进入“成功回退”路径。
API 层对超时单独返回 504 ，文案固定为“ 大模型接口超时，生成失败，请稍后重试 ”，见 trip.py 。

> 已实现
>
> - 后端新增超时识别与统一异常类型，在 llm_service.py 中递归判断异常链里的 timeout/read timeout/超时 等信号。
> - 旅行规划主链路改为对每个 Agent 调用加超时保护，在 trip_planner_agent.py 中一旦识别到大模型超时，直接抛出 LLMRequestTimeoutError ，不再走 fallback 成功分支。
> - JSON 修复阶段也加了同样保护，在 trip_planner_agent.py 中避免“主生成超时后又继续修 JSON”这类兜底链路把超时吞掉。
> - API 层对超时单独返回 504 ，文案固定为“ 大模型接口超时，生成失败，请稍后重试 ”，见 trip.py 。
> - 前端原有错误处理已能接住这个 504 并结束 loading，所以不会继续卡在生成中；相关逻辑在 api.ts 和 Home.vue 。
>   已验证
>
> - 新增了“超时不回退”和“接口返回 504”的测试，见 test_weather_planning.py 和 test_weather_planning.py 。
> - 已执行测试命令： python3 -m unittest backend.tests.test_weather_planning
> - 测试结果： Ran 12 tests ... OK
>   如何测试
>
> - 自动测试：
>   - 在项目根目录执行 python3 -m unittest backend.tests.test_weather_planning
>   - 重点看新增 2 个用例是否通过： test_plan_trip_raises_timeout_instead_of_returning_fallback 、 test_trip_route_returns_504_when_llm_times_out
> - 接口手工测试：
>   - 临时把某个 LLM 调用 mock 成 TimeoutError("read timeout") ，或让模型网关不可达/超时
>   - 调用 POST /api/trip/plan
>   - 预期结果：HTTP 状态码 504 ，响应 detail 为 大模型接口超时，生成失败，请稍后重试
> - 前端手工测试：
>   - 启动前后端后，在首页发起生成请求
>   - 人为制造 LLM 超时
>   - 预期结果：页面出现失败提示，停留在当前页，不跳转结果页，loading 结束，不会一直转圈
>     预期表现
>
> - 超时时：提示“生成失败，请稍后重试”
> - 非超时普通异常时：仍保留原有 fallback 兜底逻辑
> - 不会再把 LLM 超时伪装成“生成成功，已启用安全回退方案”
>   如果你愿意，我可以继续帮你补一个“前端 E2E 手工回归清单”或直接把这个超时场景做成可切换的测试开关。


2. 计时器

> 1. 首页（ Home.vue ）计时器 ：
>
>    - 增加了一个秒级更新的定时器，当用户点击“开始规划我的旅行”时开始计时。
>    - 格式化展示为 MM:SS ，位置放置于加载状态文字（如“正在搜索景点...”）下方，配合了 ClockCircleOutlined 图标。
>    - 计时器字体使用了具有等宽数字特性的字体效果（ tabular-nums ），使数字变动时不会抖动，保持界面美观。
>    - 请求结束（不论是成功、抛出异常还是停止生成），均会自动停止并清理计时器。
>    - 生成成功时，会将结果存入浏览器的 sessionStorage (key为 generationTime )。
> 2. 结果页（ Result.vue ）展示耗时 ：
>
>    - 从 sessionStorage 获取耗时秒数，并在初始化时格式化为 MM:SS 。
>    - 在顶部的概览卡片（Overview）中的指标统计部分，新增了“生成耗时”的独立统计卡片，由于使用的是 grid 布局且支持自适应堆叠，添加后会自动按照相同的圆角、半透明和阴影风格显示，完美契合原有卡片。
>    代码静态检查已通过，现在您可以在前端界面发起一个旅行计划并测试这一项规划，在生成过程中就能看到实时计时的效果，并在生成后的结果页面直观地看到本次规划总共花费了多长时间。

3. 非法字符和地名检测

> - 前端校验（快速拦截）：
>
> - 目的地（ city ）必须满足：
>   - 不能只包含标点符号或特殊字符。
>   - 至少包含 2 个汉字或有效的英文字母组合（考虑到有些地方名字较短或者有字母缩写）。
>   - 提供清晰的错误提示（例如：“请输入有效的城市名称，不能包含特殊符号”）。
> - 后端校验（安全兜底）：
>
> - 在 Pydantic schema 中利用正则表达式对 city 字段做相同的严格验证。
> - 若验证失败，抛出 422 Unprocessable Entity 错误，接口会立即返回并在前端弹窗报错。

4. 前端中止，后端也终止

> 已实现
>
> - 前端点击“停止生成”后，浏览器会继续用现有 AbortController 中断请求；后端现在也会感知这次断开，不再继续完整跑完后续规划链路。
> - 在 trip.py 中， /trip/plan 改为轮询检查 Request.is_disconnected() ；一旦发现客户端断开，立即标记取消并返回 499 。
> - 在 trip_planner_agent.py 中新增了协作式取消令牌 PlanningCancellationToken 和异常 TripPlanningCancelledError 。
> - 规划器会在天气、景点、酒店、行程生成，以及 JSON 修复前后的阶段切换点检查取消状态；一旦取消，就停止后续阶段执行，不再继续往下生成。
> 关键变化
>
> - 路由层： plan_trip() 现在把规划工作放到后台线程执行，同时保持主协程每 0.2s 检查一次客户端是否已断开，见 trip.py 。
> - 规划层： plan_trip() 现在支持接收取消令牌，并通过 _check_cancellation() / _run_agent_with_cancellation() 在各阶段停止，见 trip_planner_agent.py 。
> - 解析层：如果已经点击停止，不会再继续走 JSON 修复或 fallback 生成，避免“前端停了，后端还在补救生成”。
> 验证结果
>
> - 新增了“取消令牌生效”和“客户端断开返回 499”的测试，见 test_weather_planning.py 。
> - 已执行： python3 -m pytest backend/tests/test_weather_planning.py
> - 结果： 12 passed
> 当前边界
>
> - 这次实现的是“协作式停止”，能确保后端在阶段切换点停止，不再继续天气后面的景点、酒店、行程、JSON 修复等后续流程。
> - 如果某一个底层 agent.run() / MCP / LLM 调用本身已经发出且处于阻塞中，Python 线程无法安全地强杀这一次正在执行的底层调用；它会在当前这一步返回后立刻停止，不再进入下一阶段。
> - 也就是说：现在已经从“前端停了但后端继续完整跑完”变成了“前端停了，后端尽快停，并且不会继续后续阶段”。
> 你现在能看到的效果
>
> - 首页点击“停止生成”后，前端会立即结束等待。
> - 后端日志会打印检测到客户端断开并取消生成。
> - 不会再继续完整跑完整个四阶段旅行规划流程

5.  规划不合理问题

> 已完成
>
> - 我已经按 /spec 落地了“行程空间连续性优化”，并完成实现、任务勾选与验收清单勾选。
> - 规格文件保留在： spec.md 、 tasks.md 、 checklist.md
> 核心改动
>
> - 在 trip_planner_agent.py 的 PLANNER_AGENT_PROMPT 和 _build_planner_query() 中，把“同日聚合、避免回头路、跨日顺接、酒店兼顾今明两天景点”写成了显式约束，不再只停留在“考虑距离”。
> - 在 trip_planner_agent.py 中重构了候选池组织方式，新增按 area_tag 和 nearest_candidates 的空间化 payload，让候选景点分天不再只是按天气和评分截断。
> - 在 _post_validate_trip_plan() 中加入了后处理校正：单日顺路重排、酒店今明两天联动校正、跨日片区跳转检测和说明文本补强。
> - 在 trip_planner_agent.py 的后半段新增了空间辅助方法，用于距离计算、区域标记、酒店锚点、回头路识别和跨日流向检查。
> - 在 test_weather_planning.py 中补了针对“相近景点拆天”“北边-南边-北边”“酒店不邻近今明两天景点”的回归测试。
> 我对问题的结论
>
> - 根因 1：原先的单日候选挑选主要看天气和评分， _select_day_candidates() 缺少“已选景点与待选景点的空间关系”这一硬约束。
> - 根因 2：原先的规划提示词只要求“考虑景点之间距离”，这对大模型来说约束太弱，不能稳定避免跨区折返。
> - 根因 3：原先默认酒店逻辑偏固定， _build_default_hotel() 没有围绕当日末段景点和次日首段景点做双日平衡。
> - 根因 4：原先缺少“跨日空间连续性”的显式校验，所以容易出现今天北、明天南、后天再北的片区跳转。
> 验证结果
>
> - 已运行： python -m pytest backend/tests/test_weather_planning.py
> - 结果： 14 passed
> - 抽查通过： tasks.md 和 checklist.md 已全部勾选。
> - 诊断残留：Pylance 仍提示 trip_planner_agent.py 中 hello_agents 、 hello_agents.tools 无法解析，这是现有环境级告警，不是这次改动引入的语法或测试失败。
> 下一步建议
>
> - 您现在可以直接重新生成一版真实行程，重点观察： 同片区景点是否被放到同一天 、 相邻两天是否仍有明显跳区 、 酒店是否更靠近当天收尾或次日首站 。
> - 如果您愿意，我下一步可以继续帮您做一件事：
>   针对真实生成样例再加一层“距离阈值”约束，把“多远算跨区、酒店多远算不合理”进一步量化。

## 记录

下面我先用一条主线把这四个文件串起来，然后分模块讲清楚“谁干什么”和“有哪些约束/安全网”，最后给你一个“如果想删功能或放宽约束，可以改哪里”的索引，方便你后面动刀。

一、整体协作流程（一句话版）

- MultiAgentTripPlanner 负责 orchestrate：
  - 让天气 Agent 查天气 → 用 weather_planning_service 解析并打上风险标签
  - 让景点 Agent / 酒店 Agent 调高德工具 → 用 TripPlanningParsingService 把原始文本解析为候选景点/酒店
  - 汇总：把候选+天气+各种约束打包成一个复杂的 prompt → 让 Planner Agent 产出一份 JSON 行程
  - 用 TripPlanningParsingService 把 JSON 文本解析成 TripPlan 数据模型
  - 用 TripPlanningPostProcessService 做一轮“校验+修正+补全”，保证结构完整、路线合理、酒店/预算/说明文本齐全
  - 如果中间任何一步炸了，就用 TripPlanningPostProcessService.create_fallback_plan 生成一个“安全兜底行程”
    也就是：
     Agent 负责调用工具+生成草稿 → 三个 service 负责“解析 + 施加约束 + 后处理” 。

二、各文件职责 & 调用关系

1. weather_planning_service.py
   weather_planning_service.py

   - 功能：
     - 解析天气原始输出 → 逐日 WeatherInfo ：
       - parse_weather_response ：优先尝试 JSON，失败就用文本正则拆分每天。
       - _parse_weather_entries_* 一系列函数做 JSON/text/fenced code block 解析。
     - 根据天气文字+温度+风力，计算风险：
       - apply_weather_risk ：打 risk_level （high/medium/low）、 risk_score 和 planning_advice 。
       - 高温 ≥35/低温 ≤0、大风≥4/6 级都会加分，强对流天气关键词直接高风险。
     - 生成给 Planner 的“天气约束文案”：
       - build_weather_constraint_text ：前几行是通用约束说明，后面每一天一条。
     - 基于中文关键词判断景点是“偏户外/偏室内”：
       - is_outdoor_attraction / is_indoor_attraction ：后面会被候选筛选、风控校验用。
   - 被谁用：
     - 在 Agent 流程里：
       MultiAgentTripPlanner.plan_trip 第一步调用 parse_weather_response ，并打印 risk_level 概览。
       build_weather_constraint_text 在 _build_planner_query 里嵌入到 Planner Prompt 中。
     - 在候选筛选 / 后处理里：
       - TripPlanningParsingService.score_candidate_attraction / build_candidate_suitability 用 is_indoor_* / is_outdoor_* 做“候选适配天气”的打分和标签。
       - TripPlanningPostProcessService._validate_generated_weather_alignment 用 is_indoor_* / is_outdoor_* 检查“高/中风险天气日是否安排太多户外”等。

2. trip_planning_parsing_service.py
   trip_planning_parsing_service.py

   - 功能一： 解析 Planner Agent 的 JSON 行程响应

     - parse_trip_plan_response ：
       - 从大模型响应中抽出 JSON 片段 extract_json_candidate （支持 json fenced block、普通 block、甚至全文里第一个 {...} / [...] ）。
       - load_trip_plan_json ：先直接 json.loads ，失败再 sanitize_json_text （修双引号、尾逗号、 None/True/False 等），还不行就用 LLM repair_json_with_llm 让模型帮忙修 JSON。
       - 失败会把原始响应 dump_failed_response 到 logs，最后回调 fallback_factory （由 MultiAgentTripPlanner._create_fallback_plan 传进来）。
   - 功能二： 把景点/酒店搜索结果解析为“真实候选池”

     - extract_candidate_attractions / extract_candidate_hotels ：
       - 从 Agent 返回的文本中抽 JSON 或 Markdown 或半结构化文本，尽量解析出多条 POI 记录。
       - 做去重（ candidate_key / hotel_candidate_key ），并根据天气 & 地理位置选择一个“平衡候选池”：
         - 景点： select_trip_candidate_pool + score_candidate_attraction
           利用 is_indoor_attraction / is_outdoor_attraction + weather high/medium/low 调整得分，同时按区域 build_area_tag 做分片轮询抽样，控制每片区候选数量。
         - 酒店： extract_candidate_hotels 里按 (有没有价格、价格、评分) 排序，取前 12 个。
   - 功能三： 为 Planner Agent 构造结构化 payload（让它“只能在这些候选里挑”）

     - build_attraction_candidates_payload ：
       - 生成 JSON：包含
         - selection_rules ：高/中/低风险天气的选择规则（只/优先某些 suitability 标签）。
         - spatial_constraints ：同日同片区/顺路动线/跨日片区顺接/酒店联动等约束描述。
         - candidate_attractions ：每个景点附带：
           - suitability : build_candidate_suitability 得出 ["high","medium","low"]/["medium","low"]/["low"]
           - area_tag : build_area_tag 按候选经纬度切成“东部/西部/中心”等片区。
           - nearest_candidates : build_nearest_candidate_payload 给出最近的若干景点及距离。
     - build_hotel_candidates_payload ：
       - 生成真实酒店候选 JSON，带 area_tag 和 nearest_attractions （用 distance_km 计算）。
   - 被谁用：

     - MultiAgentTripPlanner._parse_response 调 parse_trip_plan_response 。
     - MultiAgentTripPlanner._extract_candidate_attractions/_extract_candidate_hotels 调对应提取函数。
     - MultiAgentTripPlanner._build_planner_query 调 build_attraction_candidates_payload 、 build_hotel_candidates_payload 。

3. trip_planning_postprocess_service.py
   trip_planning_postprocess_service.py

   这个文件基本就是“第二道保险”和“后处理器”。

   - 核心入口：

     - post_validate_trip_plan ：
       - 先按请求日期 build_trip_dates 把 TripPlan.days 补齐/截断：
         - 缺少的天用 _create_structural_placeholder_day 填一个空壳 Day，写入默认交通/住宿/description/三餐。
       - 对每一天做一系列处理：
         1. _align_day_attractions_with_candidates ：尽量把 Planner 生成的景点对齐到真实候选（用 name/address fuzzy 匹配），并去重。
            → 如果使用了候选之外的景点，会记录 warning。
         2. _reorder_attractions_for_flow ：按地理距离贪心重排当日景点路线，减少折返。如果整体路程缩短 ≥15% 才生效。
         3. _ensure_hotel_alignment ：
            - 如果没有酒店，而有候选酒店，就选一个“兼顾当日末尾景点 + 次日首景点”的真实酒店回填；
            - 如果有酒店但不在候选里，会尝试替换为真实候选；
            - 如果酒店距离今明两天重点景点都很远，也会尝试替换；否则给 warning 但不造假。
         4. _align_day_description ：根据当日景点+酒店+天气，为 day.description 生成一段解释（路线逻辑+酒店逻辑）。
         5. _validate_generated_weather_alignment ：
            - 检查高风险天气日是否安排了户外景点、是否多于 2 个景点、是否没有室内景点；
            - 中风险天气日是否户外太多/景点太多/描述中是否提到“避雨、灵活调整”等提示；
            - 还会检查景点是否都来自候选池。
         6. _validate_spatial_day_plan ：
            - 单日折返：如果首尾直线距离 <4km，整条路径却 >2.2 倍，会给“折返风险” warning。
            - 与前一日衔接：首尾距离 >12km，给“跨区跳转风险” warning。
            - 酒店与今明两日景点距离都 >8km，给“酒店未形成有效衔接” warning。
       - 全部天处理完后：
         - 如果原始天数>请求天数，截断并加 warning。
         - 写回 trip_plan.city/start_date/end_date/days/weather_info 。
         - _validate_cross_day_spatial_flow ：检查是否三天形成“北-南-北”类似往返，>10km/日但首日和第 3 日中心点 <6km。
         - _recalculate_budget ：根据 attractions.ticket_price + hotel.estimated_cost + meals.estimated_cost + 80/天交通，算一份预算。
         - _merge_weather_suggestions ：把整体建议 + 天气高/中风险提示 + 空间分布总结 _build_spatial_summary 合并成 overall_suggestions 。
         - validation_status ：如果有 warning → "warning" ，否则 "validated" ； fallback_used=False 。
   - 备用行程：

     - create_fallback_plan ：
       - 当 JSON 解析失败或总体流程异常时调用。
       - 调 parse_weather_response （如果上游没算好）拿天气，再调用 _create_weather_safe_day ：
         - 高风险每天生成 1 个“室内博物馆类景点”，中/低风险生成 2 个“体验馆/核心景点”；
         - 所有位置用合成坐标（116.4/39.9 等）但保持大致递增，让路线看起来合理；
         - 交通字段用 _safe_transportation ，高风险日强制“公共交通/打车优先,减少步行和跨区换乘”。
       - 产出一份结构完整但偏“保守安全”的 TripPlan，并标记 validation_status="fallback" , fallback_used=True 。
   - 被谁用：

     - MultiAgentTripPlanner._post_validate_trip_plan → post_validate_trip_plan 。
     - MultiAgentTripPlanner._create_fallback_plan → create_fallback_plan 。

4. trip_planner_agent.py
   trip_planner_agent.py

   - 负责多 Agent 系统：
     - 初始化：
       - 共享一个高德 MCP 工具 amap ，注册到：
         - 景点 Agent（ATTRACTION_AGENT_PROMPT）
         - 天气 Agent（WEATHER_AGENT_PROMPT）
         - 酒店 Agent（HOTEL_AGENT_PROMPT）
       - Planner Agent 只用 LLM，不用工具（接收 structured payload + 约束）。
   - 四类 Prompt 都很强调“必须用工具、不要编造”，并给出 [TOOL_CALL:...] 固定格式。
   - Planner Prompt（ PLANNER_AGENT_PROMPT ）直接在系统层定义了大量硬约束：
     - 每天 2–3 个景点（高风险 1–2 个）、每天三餐、必须有预算字段、weather_info 必须包含 risk_level/score/advice 等。
     - 高/中风险天气日的行程策略、同日/跨日动线连续性、hotel 兼顾今明两天等。
   - plan_trip 主流程已经在上面总结过，就不重复。
     三、目前实现的主要“功能 + 约束”一览

你说“需要删除一些功能和约束”，可以参考下面这个清单来定位：

1. 天气相关的约束

   - 风险评分规则：
     - 关键词高/中/低风险 → apply_weather_risk
     - 温度/风力对风险分数的影响同样在这里。
   - Planner Prompt 中的天气规则：
     - PLANNER_AGENT_PROMPT 第 195–214 行左右：
       高风险日 1–2 个室内/半室内景点、中风险日优先室内/同区域等。
   - Planner 查询时额外的“天气约束说明”：
     - _build_planner_query 里嵌入 build_weather_constraint_text 的文案。
   - Postprocess 的天气校验 & warnings：
     - _validate_generated_weather_alignment ：限定高风险日不超过 2 个景点、不能都是户外等。
2. 候选池 +“禁止编造”约束

   - Planner Prompt：
     - _build_planner_query 里 **真实景点候选(只允许从以下列表中选择)** ，以及要求 9、15–18 条：
       attractions/hotel 必须来自候选列表，不可编造/改名/补造坐标。
   - 候选池构造规则：
     - build_attraction_candidates_payload 里的 selection_rules 与 spatial_constraints 。
     - select_trip_candidate_pool 中最多 max(6, travel_days*3) 个候选按区域轮询。
   - 后处理对“是否来源于候选”的检查：
     - _validate_generated_weather_alignment 中检查 candidate_keys，不在候选池的景点会产生 warning。
   - 酒店对齐/替换逻辑：
     - _match_candidate_hotel + _ensure_hotel_alignment ：如果生成 hotel 不在候选里，会尝试替换为真实候选；候选完全为空则保留 hotel=None。
3. 空间/路线约束

   - 提供给 Planner 的“空间约束说明”：
     - build_attraction_candidates_payload → spatial_constraints 字典。
   - Planner Prompt 中的空间约束：
     - _build_planner_query 要求 4–7、10、12、14 等。
   - 后处理执行的空间调整和校验：
     - _reorder_attractions_for_flow ：根据距离重新排序当日景点，避免折返。
     - _validate_spatial_day_plan ：单日折返、跨天首尾跳区、酒店与今明两天脱节。
     - _validate_cross_day_spatial_flow ：三日“北-南-北”模式。
     - _build_spatial_summary ：生成整体“第 X 天以某片区为主”的说明。
4. 预算与三餐相关约束

   - Planner Prompt：要求必须输出 budget 字段、所有价格/estimated_cost。
   - 后处理：
     - _ensure_daily_meals ：保证每天至少有早餐/午餐/晚餐三条 Meal（没有就补默认文案和价格）。
     - _recalculate_budget ：重新根据结构化数据算一份预算。
5. JSON 严格性 & 解析修复

   - extract_json_candidate / sanitize_json_text / repair_json_with_llm ：
     - 尽量从不规范大模型输出里找出/修复 JSON。
   - 失败后 fallback：
     - TripPlanningParsingService.parse_trip_plan_response 捕获异常 → 调 fallback_factory 。
6. 安全兜底（fallback 行程）

   - 在多处异常时，最终会回退到：
     - MultiAgentTripPlanner._create_fallback_plan → TripPlanningPostProcessService.create_fallback_plan ：
       - 生成完全由代码合成的、天气安全友好的基础行程。
         四、如果你想“删掉/放宽”某些东西，大致改哪里？

不直接帮你改代码，但给你改动入口的“导航”，你可以按需要删/简化：

- 想减少“天气强约束”：

  - 调整风险评分逻辑 → apply_weather_risk 。
  - 放宽 Planner Prompt 中“高风险日只能 1–2 个景点”等 → PLANNER_AGENT_PROMPT 195–214 行。
  - 不想在后处理阶段再“管天气数量/类型” → 修改或注释
    _validate_generated_weather_alignment 中对应分支。
- 想让模型可以“候选外发挥”（不强制必须来自解析出的 POI 列表）：

  - _build_planner_query 里把“只允许从以下列表中选择”这类说明弱化或删除；
    去掉/修改 15–18 条对 attractions/hotel 必须来自候选列表的文字约束。
  - 后处理里 _validate_generated_weather_alignment 对“候选之外景点”的 warning 可以删除或改为 debug-only。
  - _align_day_attractions_with_candidates 现在会尽量把景点强行对齐到候选；如果想尊重模型输出，可以改成只在明显匹配时才替换，或者直接跳过。
- 想降低“空间动线”约束（不想强制顺路、跨日连续）：

  - Planner Prompt 空间约束文字 → _build_planner_query 要求 4–7。
  - 后处理：
    - 不想自动重排景点顺序 → 直接跳过 _reorder_attractions_for_flow 调用，或让它永远返回 improved=False 。
    - 不想给折返/跨区 warning → 删 _validate_spatial_day_plan 、 _validate_cross_day_spatial_flow 中相关逻辑。
    - 不想自动换酒店 → 简化 _ensure_hotel_alignment ，只做 distance 文本填充，不做替换/回填。
- 想简化预算 / 三餐逻辑：

  - 不强制三餐 → 修改 _ensure_daily_meals ，让它只“原样返回”而不是自动补早餐/午餐/晚餐。
  - 不需要自动预算 → 不调用 _recalculate_budget 或在其中直接返回 0。
- 想关闭 fallback“兜底行程”：

  - 在 TripPlanningParsingService.parse_trip_plan_response 里不传 fallback_factory （或者在 MultiAgentTripPlanner._parse_response 那里传 None ），失败就直接 raise。
  - 或者把 create_fallback_plan 改成返回一个非常简单/标记明显的占位数据。
    如果你能告诉我你准备“砍掉”哪一类约束（比如：只想去掉天气强约束，还是想整体变成“更自由一点的规划器”），我可以直接帮你做一版具体代码修改方案，按文件/函数给出精确 diff。
