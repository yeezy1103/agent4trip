"""多智能体旅行规划系统"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from hello_agents import SimpleAgent
from hello_agents.tools import MCPTool
from ..services.llm_service import get_llm
from ..models.schemas import (
    Attraction,
    Budget,
    DayPlan,
    Hotel,
    Location,
    Meal,
    TripPlan,
    TripRequest,
    WeatherInfo,
)
from ..services.weather_planning_service import (
    build_trip_dates,
    build_weather_constraint_text,
    is_indoor_attraction,
    is_outdoor_attraction,
    parse_weather_response,
)
from ..config import get_settings

# ============ Agent提示词 ============


def _ensure_mcp_expandable(tool: MCPTool) -> MCPTool:
    """兼容当前项目环境中的旧版 ToolRegistry 展开判断。"""
    if getattr(tool, "auto_expand", False) and not hasattr(tool, "expandable"):
        tool.expandable = True
    return tool


def _register_amap_tools(agent: SimpleAgent, tool: MCPTool) -> None:
    """显式注册展开后的 MCP 子工具，避免不同 hello_agents 版本的兼容问题。"""
    expanded_tools = tool.get_expanded_tools() if getattr(tool, "auto_expand", False) else []

    if expanded_tools:
        for expanded_tool in expanded_tools:
            agent.add_tool(expanded_tool, auto_expand=False)
        print(f"✅ Agent '{agent.name}' 已注册 {len(expanded_tools)} 个 AMap 子工具")
        return

    agent.add_tool(tool, auto_expand=True)
    print(f"⚠️ Agent '{agent.name}' 未获取到展开工具，已回退注册总工具 '{tool.name}'")

ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

**重要提示:**
你必须使用工具来搜索景点!不要自己编造景点信息!

**工具调用格式:**
使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`

**示例:**
用户: "搜索北京的历史文化景点"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=北京]

用户: "搜索上海的公园"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=公园,city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 参数用逗号分隔
"""

WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是查询指定城市的天气信息。

**重要提示:**
你必须使用工具来查询天气!不要自己编造天气信息!

**工具调用格式:**
使用maps_weather工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_weather:city=城市名]`

**示例:**
用户: "查询北京天气"
你的回复: [TOOL_CALL:amap_maps_weather:city=北京]

用户: "上海的天气怎么样"
你的回复: [TOOL_CALL:amap_maps_weather:city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
"""

HOTEL_AGENT_PROMPT = """你是酒店推荐专家。你的任务是根据城市和景点位置推荐合适的酒店。

**重要提示:**
你必须使用工具来搜索酒店!不要自己编造酒店信息!

**工具调用格式:**
使用maps_text_search工具搜索酒店时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]`

**示例:**
用户: "搜索北京的酒店"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=北京]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 关键词使用"酒店"或"宾馆"
4. 选择和推荐酒店时,考虑距离、价格、评分、类型等因素,确保推荐酒店的多样性与用户偏好相符
"""

PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级",
      "risk_level": "low",
      "risk_score": 15,
      "planning_advice": "低风险天气,可正常规划"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
8. 高风险天气日只安排1-2个室内或半室内景点,避免公园、步行街、远距离跨区移动
9. 中风险天气日优先安排同一区域的室内景点,减少长时间户外停留
10. weather_info必须与输入的天气约束保持一致,包含risk_level、risk_score和planning_advice
"""


class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(self):
        """初始化多智能体系统"""
        print("🔄 开始初始化多智能体旅行规划系统...")

        try:
            settings = get_settings()
            self.llm = get_llm()

            # 创建共享的MCP工具(只创建一次)
            print("  - 创建共享MCP工具...")
            self.amap_tool = MCPTool(
                name="amap",
                description="高德地图服务",
                server_command=["uvx", "amap-mcp-server"],
                env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
                auto_expand=True
            )
            _ensure_mcp_expandable(self.amap_tool)

            # 创建景点搜索Agent
            print("  - 创建景点搜索Agent...")
            self.attraction_agent = SimpleAgent(
                name="景点搜索专家",
                llm=self.llm,
                system_prompt=ATTRACTION_AGENT_PROMPT
            )
            _register_amap_tools(self.attraction_agent, self.amap_tool)

            # 创建天气查询Agent
            print("  - 创建天气查询Agent...")
            self.weather_agent = SimpleAgent(
                name="天气查询专家",
                llm=self.llm,
                system_prompt=WEATHER_AGENT_PROMPT
            )
            _register_amap_tools(self.weather_agent, self.amap_tool)

            # 创建酒店推荐Agent
            print("  - 创建酒店推荐Agent...")
            self.hotel_agent = SimpleAgent(
                name="酒店推荐专家",
                llm=self.llm,
                system_prompt=HOTEL_AGENT_PROMPT
            )
            _register_amap_tools(self.hotel_agent, self.amap_tool)

            # 创建行程规划Agent(不需要工具)
            print("  - 创建行程规划Agent...")
            self.planner_agent = SimpleAgent(
                name="行程规划专家",
                llm=self.llm,
                system_prompt=PLANNER_AGENT_PROMPT
            )

            print(f"✅ 多智能体系统初始化成功")
            print(f"   景点搜索Agent: {len(self.attraction_agent.list_tools())} 个工具")
            print(f"   天气查询Agent: {len(self.weather_agent.list_tools())} 个工具")
            print(f"   酒店推荐Agent: {len(self.hotel_agent.list_tools())} 个工具")

        except Exception as e:
            print(f"❌ 多智能体系统初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def plan_trip(self, request: TripRequest) -> TripPlan:
        """
        使用多智能体协作生成旅行计划

        Args:
            request: 旅行请求

        Returns:
            旅行计划
        """
        weather_info: List[WeatherInfo] = []
        try:
            print(f"\n{'='*60}")
            print(f"🚀 开始多智能体协作规划旅行...")
            print(f"目的地: {request.city}")
            print(f"日期: {request.start_date} 至 {request.end_date}")
            print(f"天数: {request.travel_days}天")
            print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
            print(f"{'='*60}\n")

            # 步骤1: 天气查询Agent查询天气
            print("🌤️  步骤1: 查询天气...")
            weather_query = f"请查询{request.city}的天气信息"
            weather_response = self.weather_agent.run(weather_query)
            print(f"天气查询结果: {weather_response[:200]}...\n")
            weather_info = parse_weather_response(
                raw_weather=weather_response,
                start_date=request.start_date,
                travel_days=request.travel_days,
            )
            self._print_weather_risk_summary(weather_info)

            # 步骤2: 景点搜索Agent根据天气优先搜索合适景点
            print("📍 步骤2: 搜索景点...")
            attraction_query = self._build_attraction_query(request, weather_info)
            attraction_response = self.attraction_agent.run(attraction_query)
            print(f"景点搜索结果: {attraction_response[:200]}...\n")
            candidate_attractions = self._extract_candidate_attractions(
                attraction_response,
                request.city,
                weather_info,
            )
            print(f"结构化景点候选数: {len(candidate_attractions)}\n")

            # 步骤3: 酒店推荐Agent搜索酒店
            print("🏨 步骤3: 搜索酒店...")
            hotel_query = f"请搜索{request.city}的{request.accommodation}酒店"
            hotel_response = self.hotel_agent.run(hotel_query)
            print(f"酒店搜索结果: {hotel_response[:200]}...\n")

            # 步骤4: 行程规划Agent整合信息生成计划
            print("📋 步骤4: 生成行程计划...")
            planner_query = self._build_planner_query(
                request,
                candidate_attractions,
                weather_response,
                hotel_response,
                weather_info,
                raw_attractions=attraction_response,
            )
            planner_response = self.planner_agent.run(planner_query)
            print(f"行程规划结果: {planner_response[:300]}...\n")

            # 解析最终计划
            trip_plan = self._parse_response(planner_response, request, weather_info)
            trip_plan = self._post_validate_trip_plan(
                trip_plan,
                request,
                weather_info,
                candidate_attractions=candidate_attractions,
            )

            print(f"{'='*60}")
            print(f"✅ 旅行计划生成完成!")
            print(f"{'='*60}\n")

            return trip_plan

        except Exception as e:
            print(f"❌ 生成旅行计划失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_plan(request, weather_info=weather_info, reason=str(e))

    def _build_attraction_query(
        self,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
    ) -> str:
        """构建景点搜索查询,让搜索阶段就参考天气风险."""
        primary_keyword = request.preferences[0] if request.preferences else "景点"
        weather_info = weather_info or []
        high_risk_days = [item.date for item in weather_info if item.risk_level == "high"]
        medium_risk_days = [item.date for item in weather_info if item.risk_level == "medium"]

        if high_risk_days:
            return (
                f"请优先为{request.city}搜索适合雨天或强对流天气的室内、半室内景点。"
                f"本次行程中以下日期风险较高: {', '.join(high_risk_days)}。"
                f"请优先搜索与“{primary_keyword}”相关的博物馆、美术馆、科技馆、纪念馆、商场、室内展馆等，"
                f"并避免把公园、步行街、山岳、湖滨等明显户外景点作为主要候选。"
                f"如有必要可多次调用工具补充候选，但输出必须基于工具结果。\n"
                f"[TOOL_CALL:amap_maps_text_search:keywords={primary_keyword} 博物馆,city={request.city}]"
            )

        if medium_risk_days:
            return (
                f"请为{request.city}搜索与“{primary_keyword}”相关、且适合中风险天气的景点。"
                f"以下日期存在降雨或出行不稳定因素: {', '.join(medium_risk_days)}。"
                f"请优先考虑同一区域、可快速避雨的室内或半室内景点，并减少远距离户外候选。\n"
                f"[TOOL_CALL:amap_maps_text_search:keywords={primary_keyword} 室内景点,city={request.city}]"
            )

        return (
            f"请使用amap_maps_text_search工具搜索{request.city}的{primary_keyword}相关景点,并优先返回真实可到达、"
            f"坐标完整的候选。\n"
            f"[TOOL_CALL:amap_maps_text_search:keywords={primary_keyword},city={request.city}]"
        )

    def _build_planner_query(
        self,
        request: TripRequest,
        candidate_attractions: List[Attraction],
        weather: str,
        hotels: str = "",
        weather_info: Optional[List[WeatherInfo]] = None,
        raw_attractions: str = "",
    ) -> str:
        """构建行程规划查询"""
        weather_info = weather_info or []
        weather_constraints = build_weather_constraint_text(weather_info)
        structured_weather = json.dumps(
            [item.model_dump() for item in weather_info],
            ensure_ascii=False,
            indent=2,
        )
        structured_candidates = self._build_attraction_candidates_payload(
            candidate_attractions,
            weather_info,
        )
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**真实景点候选(只允许从以下列表中选择):**
{structured_candidates}

**天气信息:**
{weather}

**结构化天气风险:**
{structured_weather}

**天气约束:**
{weather_constraints}

**酒店信息:**
{hotels}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
4. 考虑景点之间的距离和交通方式
5. 返回完整的JSON格式数据
6. 景点的经纬度坐标要真实准确,且必须直接来自真实景点候选列表
7. 高风险天气日只安排1-2个室内或半室内景点,并让餐饮、酒店尽量靠近
8. 中风险天气日优先安排室内景点或同一区域景点,减少跨区移动
9. weather_info字段必须以结构化天气风险为准,不要自行编造额外日期
10. overall_suggestions必须给出天气相关出行建议
11. day.description只能概述当天实际写入attractions数组和hotel字段中的地点,不要提及未出现在结构化字段里的额外景点名称
12. 高风险天气日若可选景点不足,优先减少景点数量并保留真实地点,不要编造新的地点、经纬度或酒店
13. attractions数组中的每个景点名称、地址、经纬度、类别必须与真实景点候选一致,不要改名或补造
14. 若候选列表中没有足够景点,宁可少安排,也不要补充候选列表之外的地点
"""
        if raw_attractions.strip():
            query += f"\n**景点原始搜索结果(仅供校对,以真实景点候选为准):**\n{raw_attractions}\n"
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query

    def _parse_response(
        self,
        response: str,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
    ) -> TripPlan:
        """
        解析Agent响应

        Args:
            response: Agent响应文本
            request: 原始请求

        Returns:
            旅行计划
        """
        try:
            json_candidate = self._extract_json_candidate(response)
            data = self._load_trip_plan_json(json_candidate)
            return TripPlan(**data)

        except Exception as e:
            print(f"⚠️  解析响应失败: {str(e)}")
            self._dump_failed_response(response)
            print(f"   将使用备用方案生成计划")
            return self._create_fallback_plan(request, weather_info=weather_info, reason=f"解析失败: {e}")

    def _extract_json_candidate(self, response: str) -> str:
        """从模型输出中尽量稳定地提取 JSON 片段。"""
        fenced_json = re.findall(r"```json\s*(.*?)\s*```", response, flags=re.DOTALL | re.IGNORECASE)
        if fenced_json:
            return fenced_json[-1].strip()

        fenced_block = re.findall(r"```\s*(.*?)\s*```", response, flags=re.DOTALL)
        if fenced_block:
            return fenced_block[-1].strip()

        if "{" in response and "}" in response:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            return response[json_start:json_end].strip()

        raise ValueError("响应中未找到JSON数据")

    def _load_trip_plan_json(self, json_candidate: str) -> Dict[str, Any]:
        """尝试用多种方式把模型输出解析为严格 JSON。"""
        parse_errors = []

        for candidate in (
            json_candidate,
            self._sanitize_json_text(json_candidate),
        ):
            try:
                return json.loads(candidate)
            except Exception as exc:
                parse_errors.append(str(exc))

        repaired_json = self._repair_json_with_llm(json_candidate)
        try:
            return json.loads(repaired_json)
        except Exception as exc:
            parse_errors.append(f"LLM修复后仍失败: {exc}")
            raise ValueError("；".join(parse_errors))

    def _sanitize_json_text(self, text: str) -> str:
        """修正常见的非严格 JSON 写法。"""
        sanitized = text.strip()
        sanitized = sanitized.replace("\u201c", '"').replace("\u201d", '"')
        sanitized = sanitized.replace("\u2018", "'").replace("\u2019", "'")
        sanitized = re.sub(r"//.*", "", sanitized)
        sanitized = re.sub(r"/\*.*?\*/", "", sanitized, flags=re.DOTALL)
        sanitized = re.sub(r",\s*([}\]])", r"\1", sanitized)
        sanitized = re.sub(r"\bNone\b", "null", sanitized)
        sanitized = re.sub(r"\bTrue\b", "true", sanitized)
        sanitized = re.sub(r"\bFalse\b", "false", sanitized)
        return sanitized

    def _repair_json_with_llm(self, broken_json: str) -> str:
        """让 LLM 只负责把接近 JSON 的文本修成严格 JSON。"""
        repair_prompt = (
            "请将下面的旅行计划内容修复为严格合法的 JSON。"
            "只返回 JSON 本身，不要加解释，不要加 Markdown 代码块。"
            "保留原有字段结构，确保字段名使用双引号，去掉尾逗号，"
            "把非法值改成合理的 JSON 值。"
        )
        repaired = self.llm.invoke(
            [
                {"role": "system", "content": repair_prompt},
                {"role": "user", "content": broken_json},
            ]
        )
        return self._extract_json_candidate(repaired)

    def _dump_failed_response(self, response: str) -> None:
        """保存解析失败的原始输出，便于后续定位。"""
        try:
            dump_path = Path(__file__).resolve().parents[2] / "logs"
            dump_path.mkdir(parents=True, exist_ok=True)
            failed_file = dump_path / "last_trip_plan_response.txt"
            failed_file.write_text(response, encoding="utf-8")
            print(f"📝 已保存解析失败的原始响应: {failed_file}")
        except Exception as exc:
            print(f"⚠️  保存失败响应时出错: {exc}")

    def _post_validate_trip_plan(
        self,
        trip_plan: TripPlan,
        request: TripRequest,
        weather_info: List[WeatherInfo],
        candidate_attractions: Optional[List[Attraction]] = None,
    ) -> TripPlan:
        """对模型输出做结构校验与天气场景验证,不再自动重排或回退日程."""
        warnings: List[str] = []
        expected_dates = build_trip_dates(request.start_date, request.travel_days)
        candidate_attractions = candidate_attractions or []

        normalized_days: List[DayPlan] = []
        for index, expected_date in enumerate(expected_dates):
            if index < len(trip_plan.days):
                day = trip_plan.days[index]
            else:
                day = self._create_structural_placeholder_day(request, expected_date, index)
                warnings.append(f"{expected_date} 缺少原始日程,已补齐基础结构字段")

            day.date = expected_date
            day.day_index = index
            day.transportation = day.transportation or request.transportation
            day.accommodation = day.accommodation or request.accommodation
            day.description = day.description or f"第{index + 1}天行程待确认"
            day.hotel = day.hotel or self._build_default_hotel(request, index)
            day.meals = self._ensure_daily_meals(day.meals, index)

            if not day.attractions:
                warnings.append(f"{expected_date} 未生成景点安排,保留空景点列表供前端提示")

            warnings.extend(
                self._validate_generated_weather_alignment(
                    day,
                    weather_info[index],
                    candidate_attractions,
                )
            )

            normalized_days.append(day)

        if len(trip_plan.days) > request.travel_days:
            warnings.append("原始计划天数多于请求天数,已按请求天数截断")

        trip_plan.city = request.city
        trip_plan.start_date = request.start_date
        trip_plan.end_date = request.end_date
        trip_plan.days = normalized_days
        trip_plan.weather_info = weather_info
        trip_plan.warnings = warnings

        trip_plan.budget = self._recalculate_budget(trip_plan.days)
        trip_plan.overall_suggestions = self._merge_weather_suggestions(
            trip_plan.overall_suggestions,
            weather_info,
        )
        trip_plan.validation_status = "warning" if warnings else "validated"
        trip_plan.fallback_used = False
        trip_plan.warnings = warnings
        return trip_plan

    def _create_structural_placeholder_day(
        self,
        request: TripRequest,
        date: str,
        day_index: int,
    ) -> DayPlan:
        """只补齐返回结构,不伪造天气安全景点或替换模型结果."""
        return DayPlan(
            date=date,
            day_index=day_index,
            description=f"第{day_index + 1}天行程待确认",
            transportation=request.transportation,
            accommodation=request.accommodation,
            hotel=self._build_default_hotel(request, day_index),
            attractions=[],
            meals=self._ensure_daily_meals([], day_index),
        )

    def _print_weather_risk_summary(self, weather_info: List[WeatherInfo]) -> None:
        """打印天气风险摘要,便于排查规划结果."""
        print("🛡️  天气风险分类结果:")
        for item in weather_info:
            print(
                f"   - {item.date}: {item.day_weather}/{item.night_weather}, "
                f"风险={item.risk_level}, 分值={item.risk_score}"
            )
        print("")

    def _validate_generated_weather_alignment(
        self,
        day: DayPlan,
        weather: WeatherInfo,
        candidate_attractions: Optional[List[Attraction]] = None,
    ) -> List[str]:
        """校验生成阶段是否体现天气影响,只记录告警不修改结果."""
        warnings: List[str] = []
        outdoor_count = sum(1 for attraction in day.attractions if is_outdoor_attraction(attraction))
        indoor_count = sum(1 for attraction in day.attractions if is_indoor_attraction(attraction))
        attraction_count = len(day.attractions)
        candidate_keys = {
            self._candidate_key(attraction)
            for attraction in (candidate_attractions or [])
        }

        if candidate_keys:
            unmatched = [
                attraction.name
                for attraction in day.attractions
                if self._candidate_key(attraction) not in candidate_keys
            ]
            if unmatched:
                warnings.append(
                    f"{day.date} 使用了候选列表之外的景点: {', '.join(unmatched)}"
                )

        if weather.risk_level == "high":
            if outdoor_count > 0:
                warnings.append(f"{day.date} 高风险天气仍安排了明显户外景点")
            if attraction_count > 2:
                warnings.append(f"{day.date} 高风险天气景点数量超过 2 个")
            if attraction_count > 0 and indoor_count == 0:
                warnings.append(f"{day.date} 高风险天气缺少室内或半室内景点")

        if weather.risk_level == "medium":
            if outdoor_count >= 2:
                warnings.append(f"{day.date} 中风险天气户外景点偏多")
            if attraction_count > 3:
                warnings.append(f"{day.date} 中风险天气景点数量超过 3 个")
            hint_text = " ".join(
                part for part in [day.description, weather.planning_advice] if part
            )
            if hint_text and not any(keyword in hint_text for keyword in ("避雨", "室内", "灵活", "调整", "机动")):
                warnings.append(f"{day.date} 中风险天气缺少避雨或灵活调整提示")

        return warnings

    def _needs_weather_adjustment(self, day: DayPlan, weather: WeatherInfo) -> bool:
        """检查某日安排是否违反天气约束."""
        outdoor_count = sum(1 for attraction in day.attractions if is_outdoor_attraction(attraction))
        indoor_count = sum(1 for attraction in day.attractions if is_indoor_attraction(attraction))
        transport_text = day.transportation or ""

        if weather.risk_level == "high":
            if outdoor_count > 0:
                return True
            if "步行" in transport_text or "骑行" in transport_text:
                return True
            if len(day.attractions) > 2 and indoor_count < len(day.attractions):
                return True

        if weather.risk_level == "medium":
            if outdoor_count >= 2:
                return True
            if len(day.attractions) > 3:
                return True

        return False

    def _create_weather_safe_day(
        self,
        request: TripRequest,
        date: str,
        day_index: int,
        weather: WeatherInfo,
        base_day: Optional[DayPlan] = None,
    ) -> DayPlan:
        """生成满足天气约束的单日安全回退方案."""
        risk_level = weather.risk_level or "unknown"
        attraction_count = 2 if risk_level != "high" else 1
        preference_text = request.preferences[0] if request.preferences else "文化体验"

        safe_attractions: List[Attraction] = []
        for offset in range(attraction_count):
            longitude = 116.4 + day_index * 0.01 + offset * 0.005
            latitude = 39.9 + day_index * 0.01 + offset * 0.005
            if risk_level == "high":
                name = f"{request.city}{preference_text}博物馆"
                category = "室内景点"
                description = "天气风险较高,优先安排室内参观和就近休憩。"
            elif risk_level == "medium":
                name = f"{request.city}{preference_text}体验馆" if offset == 0 else f"{request.city}城市文化馆"
                category = "室内/半室内景点"
                description = "考虑天气影响,安排易于避雨避风的同区域行程。"
            else:
                name = f"{request.city}{preference_text}核心景点{offset + 1}"
                category = "景点"
                description = "天气条件较平稳,安排常规城市游览。"

            safe_attractions.append(
                Attraction(
                    name=name,
                    address=f"{request.city}市中心区域",
                    location=Location(longitude=longitude, latitude=latitude),
                    visit_duration=120,
                    description=description,
                    category=category,
                    ticket_price=60 if risk_level != "high" else 40,
                )
            )

        meals = self._ensure_daily_meals(base_day.meals if base_day else [], day_index)
        hotel = base_day.hotel if base_day and base_day.hotel else self._build_default_hotel(request, day_index)
        transportation = self._safe_transportation(request.transportation, weather.risk_level)
        description_prefix = {
            "high": "高风险天气日,以室内活动和就近休整为主",
            "medium": "中风险天气日,控制跨区移动并优先安排可避雨行程",
            "low": "低风险天气日,可正常安排城市观光",
        }.get(risk_level, "天气信息有限,采用稳妥行程")

        return DayPlan(
            date=date,
            day_index=day_index,
            description=f"{description_prefix}。{weather.planning_advice}",
            transportation=transportation,
            accommodation=request.accommodation,
            hotel=hotel,
            attractions=safe_attractions,
            meals=meals,
        )

    def _build_default_hotel(self, request: TripRequest, day_index: int) -> Hotel:
        """生成默认酒店信息."""
        return Hotel(
            name=f"{request.city}{request.accommodation}",
            address=f"{request.city}市中心便捷住宿区",
            location=Location(longitude=116.35 + day_index * 0.01, latitude=39.90 + day_index * 0.01),
            price_range="300-500元",
            rating="4.5",
            distance="距离主要景点约2公里",
            type=request.accommodation,
            estimated_cost=380,
        )

    def _align_day_description(self, day: DayPlan, weather: WeatherInfo) -> str:
        """让描述与实际结构化景点、酒店信息保持一致,避免地图与文案脱节."""
        attraction_names = [attraction.name for attraction in day.attractions[:3] if attraction.name]
        hotel_name = day.hotel.name if day.hotel and day.hotel.name else "酒店"
        weather_hint = {
            "high": "受天气影响,以稳妥出行为主",
            "medium": "结合天气情况灵活安排行程",
            "low": "天气较稳定,可正常游览",
        }.get(weather.risk_level, "根据当日天气安排行程")

        if not attraction_names:
            return f"第{day.day_index + 1}天{weather_hint}，建议以{hotel_name}周边休整和就近活动为主。"

        joined_names = "、".join(attraction_names)
        return (
            f"第{day.day_index + 1}天{weather_hint}，主要游览{joined_names}，"
            f"并结合{day.transportation}衔接行程，住宿安排为{hotel_name}。"
        )

    def _extract_candidate_attractions(
        self,
        attraction_response: str,
        city: str,
        weather_info: List[WeatherInfo],
    ) -> List[Attraction]:
        """把景点搜索结果解析为带坐标的真实候选景点."""
        raw_candidates = self._extract_candidate_records(attraction_response)
        candidates: List[Attraction] = []
        seen_keys: Set[str] = set()

        for record in raw_candidates:
            attraction = self._record_to_attraction(record, city)
            if not attraction:
                continue
            candidate_key = self._candidate_key(attraction)
            if candidate_key in seen_keys:
                continue
            seen_keys.add(candidate_key)
            candidates.append(attraction)

        ranked = sorted(
            candidates,
            key=lambda item: self._score_candidate_attraction(item, weather_info),
            reverse=True,
        )
        return ranked[: max(6, len(weather_info) * 3)]

    def _extract_candidate_records(self, text: str) -> List[Dict[str, Any]]:
        """从 JSON 或文本中抽取疑似 POI 记录."""
        records: List[Dict[str, Any]] = []
        for candidate in self._collect_json_candidates(text):
            try:
                data = json.loads(candidate)
            except Exception:
                continue
            records.extend(self._walk_poi_records(data))

        if records:
            return records

        return self._extract_candidate_records_from_text(text)

    def _collect_json_candidates(self, text: str) -> List[str]:
        """收集文本中的 JSON 候选片段."""
        candidates: List[str] = []
        fenced_json = re.findall(r"```json\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        fenced_block = re.findall(r"```\s*(.*?)\s*```", text, flags=re.DOTALL)
        if fenced_json:
            candidates.extend(fenced_json)
        if fenced_block:
            candidates.extend(fenced_block)
        json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if json_match:
            candidates.append(json_match.group(1))
        candidates.append(text)
        return candidates

    def _walk_poi_records(self, data: Any) -> List[Dict[str, Any]]:
        """递归提取可能的 POI 节点."""
        if isinstance(data, list):
            records: List[Dict[str, Any]] = []
            for item in data:
                records.extend(self._walk_poi_records(item))
            return records

        if not isinstance(data, dict):
            return []

        records: List[Dict[str, Any]] = []
        if self._looks_like_poi_record(data):
            records.append(data)

        for key in ("pois", "data", "results", "items", "list", "suggestions", "tips"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    records.extend(self._walk_poi_records(item))

        for value in data.values():
            if isinstance(value, (dict, list)):
                records.extend(self._walk_poi_records(value))

        return records

    def _looks_like_poi_record(self, record: Dict[str, Any]) -> bool:
        """判断字典是否像一条景点 POI 记录."""
        name = record.get("name") or record.get("title")
        if not name:
            return False

        has_location = any(
            key in record for key in ("location", "longitude", "latitude", "lng", "lat", "lon")
        )
        has_context = any(
            key in record for key in ("address", "addr", "type", "category", "typecode", "business_area")
        )
        return bool(has_location or has_context)

    def _extract_candidate_records_from_text(self, text: str) -> List[Dict[str, Any]]:
        """兜底解析非 JSON 文本中的景点列表."""
        records: List[Dict[str, Any]] = []
        for line in text.replace("\\n", "\n").splitlines():
            stripped = line.strip(" -*\t")
            if not stripped:
                continue

            location_match = re.search(r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)", stripped)
            name_match = re.search(r"(?:名称|景点)[:：]\s*([^,，;；|]+)", stripped)
            address_match = re.search(r"(?:地址|地点)[:：]\s*([^|]+?)(?:\s+坐标|$)", stripped)
            category_match = re.search(r"(?:类型|类别)[:：]\s*([^,，;；|]+)", stripped)
            if not name_match or not location_match:
                continue

            records.append(
                {
                    "name": name_match.group(1).strip(),
                    "address": address_match.group(1).strip() if address_match else "",
                    "location": f"{location_match.group(1)},{location_match.group(2)}",
                    "type": category_match.group(1).strip() if category_match else "",
                }
            )

        return records

    def _record_to_attraction(self, record: Dict[str, Any], city: str) -> Optional[Attraction]:
        """把原始 POI 记录转成 Attraction."""
        name = str(record.get("name") or record.get("title") or "").strip()
        if not name:
            return None

        location = self._parse_record_location(record)
        if location is None:
            return None

        address = str(
            record.get("address")
            or record.get("addr")
            or record.get("business_area")
            or f"{city}市内"
        ).strip()
        category = str(
            record.get("type")
            or record.get("category")
            or record.get("typecode")
            or "景点"
        ).strip()
        rating = self._safe_float(record.get("rating") or record.get("score"))
        photos = self._parse_photos(record.get("photos") or record.get("images") or [])
        description_parts = [part for part in [category, address] if part]
        poi_id = str(record.get("id") or record.get("poi_id") or record.get("uid") or "").strip()

        return Attraction(
            name=name,
            address=address,
            location=location,
            visit_duration=self._estimate_visit_duration(category),
            description="，".join(description_parts) or f"{city}真实景点候选",
            category=category or "景点",
            rating=rating,
            photos=photos,
            poi_id=poi_id,
            image_url=photos[0] if photos else None,
            ticket_price=0,
        )

    def _parse_record_location(self, record: Dict[str, Any]) -> Optional[Location]:
        """解析多种常见格式的经纬度."""
        location_value = record.get("location")
        if isinstance(location_value, str):
            match = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", location_value)
            if match:
                return Location(longitude=float(match.group(1)), latitude=float(match.group(2)))

        if isinstance(location_value, dict):
            longitude = location_value.get("longitude") or location_value.get("lng") or location_value.get("lon")
            latitude = location_value.get("latitude") or location_value.get("lat")
            if longitude is not None and latitude is not None:
                return Location(longitude=float(longitude), latitude=float(latitude))

        longitude = record.get("longitude") or record.get("lng") or record.get("lon")
        latitude = record.get("latitude") or record.get("lat")
        if longitude is not None and latitude is not None:
            return Location(longitude=float(longitude), latitude=float(latitude))

        return None

    def _parse_photos(self, photo_value: Any) -> List[str]:
        """统一提取图片 URL 列表."""
        if isinstance(photo_value, list):
            parsed: List[str] = []
            for item in photo_value:
                if isinstance(item, str) and item.strip():
                    parsed.append(item.strip())
                elif isinstance(item, dict):
                    url = item.get("url") or item.get("src")
                    if isinstance(url, str) and url.strip():
                        parsed.append(url.strip())
            return parsed
        if isinstance(photo_value, str) and photo_value.strip():
            return [photo_value.strip()]
        return []

    def _estimate_visit_duration(self, category: str) -> int:
        """根据类别粗略估算游览时长."""
        if any(keyword in category for keyword in ("博物馆", "美术馆", "纪念馆", "科技馆", "艺术馆")):
            return 150
        if any(keyword in category for keyword in ("公园", "街区", "古镇", "湖", "山")):
            return 180
        return 120

    def _safe_float(self, value: Any) -> Optional[float]:
        """安全转换评分."""
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _score_candidate_attraction(
        self,
        attraction: Attraction,
        weather_info: List[WeatherInfo],
    ) -> Tuple[int, float]:
        """根据天气场景对候选景点排序."""
        has_high_risk = any(item.risk_level == "high" for item in weather_info)
        has_medium_risk = any(item.risk_level == "medium" for item in weather_info)
        indoor = is_indoor_attraction(attraction)
        outdoor = is_outdoor_attraction(attraction)
        score = 0

        if indoor:
            score += 50
        elif not outdoor:
            score += 25
        else:
            score += 10

        if has_high_risk:
            score += 40 if indoor else -30 if outdoor else 10
        elif has_medium_risk:
            score += 20 if not outdoor else -10
        else:
            score += 15 if outdoor else 5

        return score, attraction.rating or 0.0

    def _build_attraction_candidates_payload(
        self,
        candidate_attractions: List[Attraction],
        weather_info: List[WeatherInfo],
    ) -> str:
        """构建给 Planner 使用的结构化候选景点上下文."""
        trip_has_high_risk = any(item.risk_level == "high" for item in weather_info)
        trip_has_medium_risk = any(item.risk_level == "medium" for item in weather_info)
        payload = {
            "selection_rules": {
                "high_risk": "只能选择 suitability 包含 high 的候选,且每天 1-2 个",
                "medium_risk": "优先选择 suitability 包含 medium 的候选,减少跨区移动",
                "low_risk": "优先复用 low 候选,但仍需控制动线",
            },
            "weather_profile": {
                "has_high_risk_day": trip_has_high_risk,
                "has_medium_risk_day": trip_has_medium_risk,
            },
            "candidate_attractions": [
                {
                    "name": attraction.name,
                    "address": attraction.address,
                    "location": attraction.location.model_dump(),
                    "category": attraction.category,
                    "description": attraction.description,
                    "rating": attraction.rating,
                    "poi_id": attraction.poi_id,
                    "suitability": self._build_candidate_suitability(attraction),
                }
                for attraction in candidate_attractions
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_candidate_suitability(self, attraction: Attraction) -> List[str]:
        """生成候选景点适用天气标签."""
        indoor = is_indoor_attraction(attraction)
        outdoor = is_outdoor_attraction(attraction)
        if indoor:
            return ["high", "medium", "low"]
        if outdoor:
            return ["low"]
        return ["medium", "low"]

    def _create_candidate_backed_day(
        self,
        request: TripRequest,
        date: str,
        day_index: int,
        weather: WeatherInfo,
        candidate_attractions: List[Attraction],
        base_day: Optional[DayPlan] = None,
        used_candidate_keys: Optional[Set[str]] = None,
    ) -> Tuple[DayPlan, bool]:
        """优先用真实候选景点生成符合天气约束的单日行程."""
        selected = self._select_day_candidates(
            candidate_attractions,
            weather,
            used_candidate_keys or set(),
        )
        if not selected:
            fallback_day = self._create_weather_safe_day(
                request,
                date,
                day_index,
                weather,
                base_day=base_day,
            )
            return fallback_day, False

        if used_candidate_keys is not None:
            used_candidate_keys.update(self._candidate_key(attraction) for attraction in selected)

        meals = self._ensure_daily_meals(base_day.meals if base_day else [], day_index)
        hotel = base_day.hotel if base_day and base_day.hotel else self._build_default_hotel(request, day_index)
        candidate_day = DayPlan(
            date=date,
            day_index=day_index,
            description=f"第{day_index + 1}天行程",
            transportation=self._safe_transportation(request.transportation, weather.risk_level),
            accommodation=request.accommodation,
            hotel=hotel,
            attractions=selected,
            meals=meals,
        )
        candidate_day.description = self._align_day_description(candidate_day, weather)
        return candidate_day, True

    def _select_day_candidates(
        self,
        candidate_attractions: List[Attraction],
        weather: WeatherInfo,
        used_candidate_keys: Set[str],
    ) -> List[Attraction]:
        """为某一天挑选天气合适的真实候选景点."""
        attraction_limit = 1 if weather.risk_level == "high" else 2
        eligible = [
            attraction
            for attraction in candidate_attractions
            if self._candidate_matches_weather(attraction, weather)
        ]
        if not eligible and weather.risk_level != "low":
            eligible = [
                attraction
                for attraction in candidate_attractions
                if not is_outdoor_attraction(attraction)
            ]
        if not eligible:
            eligible = list(candidate_attractions)

        fresh_candidates = [
            attraction for attraction in eligible
            if self._candidate_key(attraction) not in used_candidate_keys
        ]
        pool = fresh_candidates or eligible
        ranked = sorted(
            pool,
            key=lambda item: self._score_candidate_for_day(item, weather, used_candidate_keys),
            reverse=True,
        )
        return ranked[:attraction_limit]

    def _candidate_matches_weather(self, attraction: Attraction, weather: WeatherInfo) -> bool:
        """判断候选景点是否满足某日天气约束."""
        indoor = is_indoor_attraction(attraction)
        outdoor = is_outdoor_attraction(attraction)
        if weather.risk_level == "high":
            return indoor or not outdoor
        if weather.risk_level == "medium":
            return not outdoor or indoor
        return True

    def _score_candidate_for_day(
        self,
        attraction: Attraction,
        weather: WeatherInfo,
        used_candidate_keys: Set[str],
    ) -> Tuple[int, float]:
        """按单日天气和复用情况为候选打分."""
        score = 0
        indoor = is_indoor_attraction(attraction)
        outdoor = is_outdoor_attraction(attraction)

        if weather.risk_level == "high":
            score += 60 if indoor else 20 if not outdoor else -100
        elif weather.risk_level == "medium":
            score += 40 if indoor else 15 if not outdoor else -20
        else:
            score += 30 if outdoor else 20

        if self._candidate_key(attraction) in used_candidate_keys:
            score -= 40

        return score, attraction.rating or 0.0

    def _candidate_key(self, attraction: Attraction) -> str:
        """生成候选景点唯一键."""
        return attraction.poi_id or f"{attraction.name}|{attraction.address}"

    def _ensure_daily_meals(self, meals: List[Meal], day_index: int) -> List[Meal]:
        """补齐早餐、午餐、晚餐."""
        meal_map = {meal.type: meal for meal in meals if meal.type}
        defaults = {
            "breakfast": Meal(type="breakfast", name=f"第{day_index + 1}天早餐", description="酒店附近早餐", estimated_cost=25),
            "lunch": Meal(type="lunch", name=f"第{day_index + 1}天午餐", description="景点周边简餐", estimated_cost=45),
            "dinner": Meal(type="dinner", name=f"第{day_index + 1}天晚餐", description="当地特色晚餐", estimated_cost=70),
        }
        return [meal_map.get(meal_type, default_meal) for meal_type, default_meal in defaults.items()]

    def _safe_transportation(self, preferred: str, risk_level: str) -> str:
        """根据天气风险调整交通建议."""
        if risk_level == "high":
            return "公共交通/打车优先,减少步行和跨区换乘"
        if risk_level == "medium":
            return f"{preferred}为主,尽量选择地铁或短距离接驳"
        return preferred

    def _recalculate_budget(self, days: List[DayPlan]) -> Budget:
        """根据每日安排重新汇总预算."""
        total_attractions = sum(
            attraction.ticket_price or 0
            for day in days
            for attraction in day.attractions
        )
        total_hotels = sum(
            (day.hotel.estimated_cost if day.hotel else 0)
            for day in days
        )
        total_meals = sum(
            meal.estimated_cost or 0
            for day in days
            for meal in day.meals
        )
        total_transportation = 80 * len(days)
        return Budget(
            total_attractions=total_attractions,
            total_hotels=total_hotels,
            total_meals=total_meals,
            total_transportation=total_transportation,
            total=total_attractions + total_hotels + total_meals + total_transportation,
        )

    def _merge_weather_suggestions(
        self,
        original_text: str,
        weather_info: List[WeatherInfo],
    ) -> str:
        """把天气风险摘要和校正结果合并到总体建议."""
        base_text = re.sub(r"\*\*", "", (original_text or "").replace("\\n", "\n")).strip()
        lines: List[str] = []

        if base_text:
            for segment in re.split(r"\n+|(?<=[。；！？])", base_text):
                cleaned = segment.strip(" \n\t-•")
                if cleaned:
                    lines.append(cleaned)

        return "\n".join(lines).strip()

    def _create_fallback_plan(
        self,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
        reason: str = "",
    ) -> TripPlan:
        """创建天气约束友好的备用计划."""
        weather_info = weather_info or parse_weather_response(
            raw_weather="",
            start_date=request.start_date,
            travel_days=request.travel_days,
        )
        trip_dates = build_trip_dates(request.start_date, request.travel_days)
        days = [
            self._create_weather_safe_day(request, trip_date, index, weather_info[index])
            for index, trip_date in enumerate(trip_dates)
        ]
        warnings = [f"已启用安全回退方案: {reason}"] if reason else ["已启用安全回退方案"]

        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=weather_info,
            overall_suggestions=self._merge_weather_suggestions(
                f"已为您生成稳妥的 {request.city} {request.travel_days} 日备用行程。",
                weather_info,
            ),
            budget=self._recalculate_budget(days),
            validation_status="fallback",
            fallback_used=True,
            warnings=warnings,
        )


# 全局多智能体系统实例
_multi_agent_planner = None


def get_trip_planner_agent() -> MultiAgentTripPlanner:
    """获取多智能体旅行规划系统实例(单例模式)"""
    global _multi_agent_planner

    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()

    return _multi_agent_planner
