"""多智能体旅行规划系统"""

import json
import re
import threading
from typing import Any, Dict, List, Optional
from hello_agents import SimpleAgent
from hello_agents.tools import MCPTool
from ..services.llm_service import get_llm
from ..models.schemas import (
    Attraction,
    Hotel,
    TripPlan,
    TripRequest,
    WeatherInfo,
)
from ..services.trip_planning_parsing_service import TripPlanningParsingService
from ..services.trip_planning_postprocess_service import TripPlanningPostProcessService
from ..services.weather_planning_service import (
    build_weather_constraint_text,
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


class TripPlanningCancelledError(Exception):
    """旅行规划已被取消。"""


class InvalidTripRequestError(Exception):
    """旅行请求参数无效。"""


class PlanningCancellationToken:
    """线程安全的协作式取消令牌。"""

    def __init__(self) -> None:
        self._event = threading.Event()
        self.reason = "已停止生成当前行程"

    def cancel(self, reason: str = "已停止生成当前行程") -> None:
        self.reason = reason
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

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

**输出格式要求:**
当工具返回结果后，你必须只输出一个 JSON 数组（不要输出 Markdown/解释文字），数组每一项为一个景点对象，字段如下：
- name: 景点名称
- address: 地址
- location: { "longitude": <float>, "latitude": <float> }
- type: 类型/类别（可选）
- rating: 评分（可选）
- id: POI id（可选）

必须保证每一项都包含可解析的经纬度坐标。
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

**输出格式要求:**
当工具返回结果后，你必须只输出一个 JSON 数组（不要输出 Markdown/解释文字），数组每一项为一个酒店对象，字段如下：
- name: 酒店名称
- address: 地址（可选）
- location: { "longitude": <float>, "latitude": <float> }（可选，但推荐给出）
- type: 酒店类型（可选）
- rating: 评分（可选）
- price_range: 价格范围（可选）
- id: POI id（可选）
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
10. 同一天内优先把相近景点放在一起,并按顺路动线排序,避免明显回头路
11. 多日行程要保持空间连续性,避免出现“北边-南边-北边”这类往返跳区
12. 酒店要同时考虑当天最后景点与次日首段景点,优先住在当天收尾点附近或今明两天中间
13. day.description与overall_suggestions需要解释当天为何这样排序、酒店为何放在该位置
14. weather_info必须与输入的天气约束保持一致,包含risk_level、risk_score和planning_advice
"""


class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(self):
        """初始化多智能体系统"""
        print("🔄 开始初始化多智能体旅行规划系统...")

        try:
            settings = get_settings()
            self.llm = get_llm()
            self.parsing_service = TripPlanningParsingService(
                llm=self.llm,
                cancellation_exception_cls=TripPlanningCancelledError,
            )
            self.postprocess_service = TripPlanningPostProcessService()

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

    def _get_parsing_service(self) -> TripPlanningParsingService:
        """懒加载解析服务,兼容测试中直接通过 __new__ 构造实例的场景。"""
        service = getattr(self, "parsing_service", None)
        if service is None:
            service = TripPlanningParsingService(
                llm=getattr(self, "llm", None),
                cancellation_exception_cls=TripPlanningCancelledError,
            )
            self.parsing_service = service
        elif getattr(service, "llm", None) is None and getattr(self, "llm", None) is not None:
            service.set_llm(self.llm)
        return service

    def _get_postprocess_service(self) -> TripPlanningPostProcessService:
        """懒加载后处理服务,兼容测试和旧调用路径。"""
        service = getattr(self, "postprocess_service", None)
        if service is None:
            service = TripPlanningPostProcessService()
            self.postprocess_service = service
        return service

    def plan_trip(
        self,
        request: TripRequest,
        cancellation_token: Optional[PlanningCancellationToken] = None,
    ) -> TripPlan:
        """
        使用多智能体协作生成旅行计划

        Args:
            request: 旅行请求

        Returns:
            旅行计划
        """
        self._validate_trip_request(request)
        weather_info: List[WeatherInfo] = []
        try:
            self._check_cancellation(cancellation_token, "开始规划前")
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
            weather_response = self._run_agent_with_cancellation(
                self.weather_agent,
                weather_query,
                cancellation_token,
                "天气查询",
            )
            print(f"天气查询结果: {weather_response[:200]}...\n")
            self._guard_weather_response(weather_response, request.city)
            weather_info = parse_weather_response(
                raw_weather=weather_response,
                start_date=request.start_date,
                travel_days=request.travel_days,
            )
            self._print_weather_risk_summary(weather_info)
            self._check_cancellation(cancellation_token, "天气查询后")

            # 步骤2: 景点搜索Agent根据天气优先搜索合适景点
            print("📍 步骤2: 搜索景点...")
            attraction_query = self._build_attraction_query(request, weather_info)
            attraction_response = self._run_agent_with_cancellation(
                self.attraction_agent,
                attraction_query,
                cancellation_token,
                "景点搜索",
            )
            print(f"景点搜索结果: {attraction_response[:200]}...\n")
            candidate_attractions = self._extract_candidate_attractions(
                attraction_response,
                request.city,
                weather_info,
            )
            print(f"结构化景点候选数: {len(candidate_attractions)}\n")
            self._check_cancellation(cancellation_token, "景点搜索后")

            # 步骤3: 酒店推荐Agent搜索酒店
            print("🏨 步骤3: 搜索酒店...")
            hotel_query = f"请搜索{request.city}的{request.accommodation}酒店"
            hotel_response = self._run_agent_with_cancellation(
                self.hotel_agent,
                hotel_query,
                cancellation_token,
                "酒店推荐",
            )
            print(f"酒店搜索结果: {hotel_response[:200]}...\n")
            candidate_hotels = self._extract_candidate_hotels(hotel_response, request.city)
            print(f"结构化酒店候选数: {len(candidate_hotels)}\n")
            self._check_cancellation(cancellation_token, "酒店推荐后")

            # 步骤4: 行程规划Agent整合信息生成计划
            print("📋 步骤4: 生成行程计划...")
            planner_query = self._build_planner_query(
                request,
                candidate_attractions,
                candidate_hotels,
                weather_response,
                hotel_response,
                weather_info,
                raw_attractions=attraction_response,
            )
            planner_response = self._run_agent_with_cancellation(
                self.planner_agent,
                planner_query,
                cancellation_token,
                "行程生成",
            )
            print(f"行程规划结果: {planner_response[:300]}...\n")

            # 解析最终计划
            self._check_cancellation(cancellation_token, "行程生成后")
            trip_plan = self._parse_response(
                planner_response,
                request,
                weather_info,
                cancellation_token=cancellation_token,
            )
            trip_plan = self._post_validate_trip_plan(
                trip_plan,
                request,
                weather_info,
                candidate_attractions=candidate_attractions,
                candidate_hotels=candidate_hotels,
            )

            print(f"{'='*60}")
            print(f"✅ 旅行计划生成完成!")
            print(f"{'='*60}\n")

            return trip_plan

        except TripPlanningCancelledError:
            print("🛑 旅行计划生成已取消")
            raise
        except InvalidTripRequestError:
            raise
        except Exception as e:
            print(f"❌ 生成旅行计划失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_plan(request, weather_info=weather_info, reason=str(e))

    def _check_cancellation(
        self,
        cancellation_token: Optional[PlanningCancellationToken],
        stage: str = "",
    ) -> None:
        """在阶段切换点检查是否已取消。"""
        if cancellation_token and cancellation_token.is_cancelled():
            stage_text = f"（{stage}）" if stage else ""
            raise TripPlanningCancelledError(f"{cancellation_token.reason}{stage_text}")

    def _run_agent_with_cancellation(
        self,
        agent: SimpleAgent,
        query: str,
        cancellation_token: Optional[PlanningCancellationToken],
        stage: str,
    ) -> str:
        """执行单个 Agent，并在前后检查取消状态。"""
        self._check_cancellation(cancellation_token, f"{stage}开始前")
        result = agent.run(query)
        self._check_cancellation(cancellation_token, f"{stage}完成后")
        return result

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
        candidate_hotels: List[Hotel],
        weather: str,
        hotels: str = "",
        weather_info: Optional[List[WeatherInfo]] = None,
        raw_attractions: str = "",
    ) -> str:
        """构建行程规划查询"""
        weather_info = weather_info or []
        parsing_service = self._get_parsing_service()
        weather_constraints = build_weather_constraint_text(weather_info)
        structured_weather = json.dumps(
            [item.model_dump() for item in weather_info],
            ensure_ascii=False,
            indent=2,
        )
        structured_candidates = (
            parsing_service.build_attraction_candidates_payload(candidate_attractions, weather_info)
            if candidate_attractions
            else ""
        )
        structured_hotels = (
            parsing_service.build_hotel_candidates_payload(candidate_hotels, candidate_attractions)
            if candidate_hotels
            else ""
        )
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息（来自工具搜索结果，供参考与编排）:**
{raw_attractions or "（无）"}

**结构化景点候选（若有，包含坐标，建议优先使用以便地图展示）:**
{structured_candidates or "（无）"}

**天气信息:**
{weather}

**结构化天气风险:**
{structured_weather}

**天气约束:**
{weather_constraints}

**酒店信息（来自工具搜索结果，供参考与编排）:**
{hotels or "（无）"}

**结构化酒店候选（若有，包含坐标/价格等，建议优先使用）:**
{structured_hotels or "（无）"}

**要求:**
1. 每天安排2-3个景点;高风险天气日只安排1-2个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店;若无法确定可核验酒店信息可返回hotel=null并在description说明原因
4. 同一天优先把相近景点放在一起,并按顺路动线排序,避免明显回头路
5. 多日行程尽量保持片区推进连续性,减少跨日往返跳区
6. 返回完整的JSON格式数据
7. weather_info字段必须以结构化天气风险为准,不要自行编造额外日期
8. overall_suggestions必须给出天气相关出行建议,并说明多日片区衔接逻辑
9. day.description需要解释路线组织逻辑,例如“同片区顺路串联”“酒店便于衔接次日上午景点”
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query

    @staticmethod
    def _validate_trip_request(request: TripRequest) -> None:
        city = (request.city or "").strip()
        if not city:
            raise InvalidTripRequestError("目的地城市不能为空")
        if len(city) > 40:
            raise InvalidTripRequestError("目的地城市过长，请输入真实城市名")
        if not re.match(r"^[\u4e00-\u9fffA-Za-z0-9·\-\s]+$", city):
            raise InvalidTripRequestError("目的地城市包含非法字符，请输入真实城市名，例如：北京/上海/Guangzhou")

    @staticmethod
    def _guard_weather_response(weather_response: str, city: str) -> None:
        text = (weather_response or "").strip()
        if not text:
            raise InvalidTripRequestError(f"无法获取 {city} 的天气信息，请检查城市名称是否正确")
        keywords = ("输入的城市名称有误", "无法获取到该地区的天气", "无法获取", "天气预报数据")
        if all(keyword in text for keyword in ("天气", "无法获取")) or any(keyword in text for keyword in keywords):
            raise InvalidTripRequestError(f"无法获取 {city} 的天气信息，请检查城市名称是否正确")

    def _parse_response(
        self,
        response: str,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
        cancellation_token: Optional[PlanningCancellationToken] = None,
    ) -> TripPlan:
        """
        解析Agent响应

        Args:
            response: Agent响应文本
            request: 原始请求

        Returns:
            旅行计划
        """
        return self._get_parsing_service().parse_trip_plan_response(
            response=response,
            request=request,
            weather_info=weather_info,
            cancellation_token=cancellation_token,
            check_cancellation=self._check_cancellation,
            fallback_factory=self._create_fallback_plan,
        )

    def _print_weather_risk_summary(self, weather_info: List[WeatherInfo]) -> None:
        """打印天气风险摘要,便于排查编排阶段输入是否符合预期。"""
        print("🛡️  天气风险分类结果:")
        for item in weather_info:
            print(
                f"   - {item.date}: {item.day_weather}/{item.night_weather}, "
                f"风险={item.risk_level}, 分值={item.risk_score}"
            )
        print("")

    # Backward-compatible delegates for tests and older call sites.
    def _extract_json_candidate(self, response: str) -> str:
        """兼容旧调用路径: 委托给解析服务提取 JSON 片段。"""
        return self._get_parsing_service().extract_json_candidate(response)

    def _load_trip_plan_json(
        self,
        json_candidate: str,
        cancellation_token: Optional[PlanningCancellationToken] = None,
    ) -> Dict[str, Any]:
        """兼容旧调用路径: 委托给解析服务加载与修复 JSON。"""
        return self._get_parsing_service().load_trip_plan_json(
            json_candidate,
            cancellation_token=cancellation_token,
            check_cancellation=self._check_cancellation,
        )

    @staticmethod
    def _sanitize_json_text(text: str) -> str:
        """兼容旧调用路径: 委托给解析服务清洗 JSON 文本。"""
        return TripPlanningParsingService.sanitize_json_text(text)

    def _repair_json_with_llm(
        self,
        broken_json: str,
        cancellation_token: Optional[PlanningCancellationToken] = None,
    ) -> str:
        """兼容旧调用路径: 委托给解析服务调用 LLM 修复 JSON。"""
        return self._get_parsing_service().repair_json_with_llm(
            broken_json,
            cancellation_token=cancellation_token,
            check_cancellation=self._check_cancellation,
        )

    @staticmethod
    def _dump_failed_response(response: str) -> None:
        """兼容旧调用路径: 委托给解析服务保存失败响应。"""
        TripPlanningParsingService.dump_failed_response(response)

    def _post_validate_trip_plan(
        self,
        trip_plan: TripPlan,
        request: TripRequest,
        weather_info: List[WeatherInfo],
        candidate_attractions: Optional[List[Attraction]] = None,
        candidate_hotels: Optional[List[Hotel]] = None,
    ) -> TripPlan:
        """对模型输出做结构校验,并补足空间连续性、酒店联动与说明文本."""
        return self._get_postprocess_service().post_validate_trip_plan(
            trip_plan=trip_plan,
            request=request,
            weather_info=weather_info,
            candidate_attractions=candidate_attractions,
            candidate_hotels=candidate_hotels,
        )

    def _extract_candidate_attractions(
        self,
        attraction_response: str,
        city: str,
        weather_info: List[WeatherInfo],
    ) -> List[Attraction]:
        """把景点搜索结果解析为带坐标的真实候选景点."""
        return self._get_parsing_service().extract_candidate_attractions(
            attraction_response=attraction_response,
            city=city,
            weather_info=weather_info,
        )

    def _extract_candidate_hotels(
        self,
        hotel_response: str,
        city: str,
    ) -> List[Hotel]:
        """把酒店搜索结果解析为带坐标的真实候选酒店."""
        return self._get_parsing_service().extract_candidate_hotels(
            hotel_response=hotel_response,
            city=city,
        )

    def _create_fallback_plan(
        self,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
        reason: str = "",
    ) -> TripPlan:
        """创建天气约束友好的备用计划."""
        return self._get_postprocess_service().create_fallback_plan(
            request=request,
            weather_info=weather_info,
            reason=reason,
        )


# 全局多智能体系统实例
_multi_agent_planner = None


def get_trip_planner_agent() -> MultiAgentTripPlanner:
    """获取多智能体旅行规划系统实例(单例模式)"""
    global _multi_agent_planner

    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()

    return _multi_agent_planner
