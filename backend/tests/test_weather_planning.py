import asyncio
import json
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.schemas import Attraction, DayPlan, Hotel, Location, Meal, TripPlan, TripRequest
from app.services.weather_planning_service import parse_weather_response

try:
    from app.agents.trip_planner_agent import (
        MultiAgentTripPlanner,
        PlanningCancellationToken,
        TripPlanningCancelledError,
    )
except Exception:  # pragma: no cover - 环境缺少依赖时允许跳过 agent 级测试
    hello_agents_module = types.ModuleType("hello_agents")
    hello_agents_tools_module = types.ModuleType("hello_agents.tools")
    pydantic_settings_module = types.ModuleType("pydantic_settings")
    dotenv_module = types.ModuleType("dotenv")

    class DummySimpleAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            return ""

        def add_tool(self, *args, **kwargs):
            return None

        def list_tools(self):
            return []

    class DummyMCPTool:
        def __init__(self, *args, **kwargs):
            self.name = "dummy"

        def get_expanded_tools(self):
            return []

    class DummyHelloAgentsLLM:
        provider = "stub"
        model = "stub"

        def invoke(self, *args, **kwargs):
            return "{}"

    class DummyBaseSettings:
        def __init__(self, **kwargs):
            for name, value in self.__class__.__dict__.items():
                if name.startswith("_") or name == "Config" or callable(value):
                    continue
                setattr(self, name, kwargs.get(name, value))

    def dummy_load_dotenv(*args, **kwargs):
        return False

    hello_agents_module.SimpleAgent = DummySimpleAgent
    hello_agents_module.HelloAgentsLLM = DummyHelloAgentsLLM
    hello_agents_tools_module.MCPTool = DummyMCPTool
    pydantic_settings_module.BaseSettings = DummyBaseSettings
    dotenv_module.load_dotenv = dummy_load_dotenv
    sys.modules["hello_agents"] = hello_agents_module
    sys.modules["hello_agents.tools"] = hello_agents_tools_module
    sys.modules["pydantic_settings"] = pydantic_settings_module
    sys.modules["dotenv"] = dotenv_module

    from app.agents.trip_planner_agent import (
        MultiAgentTripPlanner,
        PlanningCancellationToken,
        TripPlanningCancelledError,
    )

from app.api.routes import trip as trip_route


class WeatherPlanningServiceTest(unittest.TestCase):
    def test_parse_weather_response_adds_risk_fields(self):
        raw_weather = json.dumps(
            {
                "forecasts": [
                    {
                        "casts": [
                            {
                                "date": "2026-05-01",
                                "dayweather": "暴雨",
                                "nightweather": "雷阵雨",
                                "daytemp": "29",
                                "nighttemp": "22",
                                "daywind": "东风",
                                "daypower": "6级",
                            },
                            {
                                "date": "2026-05-02",
                                "dayweather": "晴",
                                "nightweather": "多云",
                                "daytemp": "27",
                                "nighttemp": "19",
                                "daywind": "南风",
                                "daypower": "2级",
                            },
                        ]
                    }
                ]
            },
            ensure_ascii=False,
        )

        weather_info = parse_weather_response(raw_weather, "2026-05-01", 2)

        self.assertEqual(len(weather_info), 2)
        self.assertEqual(weather_info[0].risk_level, "high")
        self.assertGreaterEqual(weather_info[0].risk_score, 80)
        self.assertEqual(weather_info[1].risk_level, "low")
        self.assertTrue(weather_info[0].planning_advice)

    def test_parse_weather_response_marks_light_rain_as_medium_risk(self):
        raw_weather = json.dumps(
            {
                "forecasts": [
                    {
                        "casts": [
                            {
                                "date": "2026-05-03",
                                "dayweather": "小雨",
                                "nightweather": "阴",
                                "daytemp": "24",
                                "nighttemp": "18",
                                "daywind": "东风",
                                "daypower": "3级",
                            }
                        ]
                    }
                ]
            },
            ensure_ascii=False,
        )

        weather_info = parse_weather_response(raw_weather, "2026-05-03", 1)

        self.assertEqual(len(weather_info), 1)
        self.assertEqual(weather_info[0].risk_level, "medium")
        self.assertGreaterEqual(weather_info[0].risk_score, 45)
        self.assertIn("中风险天气", weather_info[0].planning_advice)
        self.assertIn("风险原因", weather_info[0].planning_advice)

    def test_parse_weather_response_handles_markdown_forecast_by_day(self):
        raw_weather = """
        **广州市天气预报：**
        1. **4月19日（周日）**：多云，北风1-3级，气温20°C ~ 30°C
        2. **4月20日（周一）**：雷阵雨，北风1-3级，气温21°C ~ 28°C
        3. **4月21日（周二）**：多云，北风1-3级，气温21°C ~ 27°C
        4. **4月22日（周三）**：白天多云，夜间雷阵雨，南风1-3级，气温22°C ~ 29°C
        """

        weather_info = parse_weather_response(raw_weather, "2026-04-19", 4)

        self.assertEqual(len(weather_info), 4)
        self.assertEqual(weather_info[0].date, "2026-04-19")
        self.assertEqual(weather_info[0].day_weather, "多云")
        self.assertEqual(weather_info[0].risk_level, "low")

        self.assertEqual(weather_info[1].date, "2026-04-20")
        self.assertEqual(weather_info[1].day_weather, "雷阵雨")
        self.assertEqual(weather_info[1].risk_level, "high")

        self.assertEqual(weather_info[2].date, "2026-04-21")
        self.assertEqual(weather_info[2].day_weather, "多云")
        self.assertEqual(weather_info[2].risk_level, "low")

        self.assertEqual(weather_info[3].date, "2026-04-22")
        self.assertEqual(weather_info[3].day_weather, "多云")
        self.assertEqual(weather_info[3].night_weather, "雷阵雨")
        self.assertEqual(weather_info[3].risk_level, "high")

    def test_parse_weather_response_handles_today_tomorrow_format(self):
        raw_weather = """
        **广州市天气预报**

        **今天（4月19日，周日）**
        - 天气：多云
        - 温度：20°C ~ 30°C
        - 风向风力：北风1-3级

        **明天（4月20日，周一）**
        - 天气：雷阵雨
        - 温度：21°C ~ 28°C
        - 风向风力：北风1-3级

        **后天（4月21日，周二）**
        - 天气：多云
        - 温度：21°C ~ 27°C
        - 风向风力：北风1-3级

        **4月22日（周三）**
        - 天气：白天多云，夜间雷阵雨
        - 温度：22°C ~ 29°C
        - 风向风力：南风1-3级
        """

        weather_info = parse_weather_response(raw_weather, "2026-04-19", 4)

        self.assertEqual(len(weather_info), 4)
        self.assertEqual(weather_info[0].day_weather, "多云")
        self.assertEqual(weather_info[0].risk_level, "low")
        self.assertEqual(weather_info[1].day_weather, "雷阵雨")
        self.assertEqual(weather_info[1].risk_level, "high")
        self.assertEqual(weather_info[2].day_weather, "多云")
        self.assertEqual(weather_info[2].risk_level, "low")
        self.assertEqual(weather_info[3].day_weather, "多云")
        self.assertEqual(weather_info[3].night_weather, "雷阵雨")
        self.assertEqual(weather_info[3].risk_level, "high")

    def test_parse_weather_response_prefers_markdown_table_over_notes(self):
        raw_weather = """
        **广州市天气预报**

        | 日期 | 白天天气 | 夜间天气 | 白天温度 | 夜间温度 | 风向风力 |
        |------|---------|---------|---------|---------|---------|
        | 4月30日 (周四) | ☁️ 多云 | ☁️ 多云 | 25°C | 18°C | 北风1-3级 |
        | 5月1日 (周五) | ⛈️ 雷阵雨 | ⛈️ 雷阵雨 | 26°C | 19°C | 北风1-3级 |

        备注：4月30日局部也有雷阵雨可能性
        """

        weather_info = parse_weather_response(raw_weather, "2026-04-30", 2)

        self.assertEqual(len(weather_info), 2)
        self.assertEqual(weather_info[0].date, "2026-04-30")
        self.assertEqual(weather_info[0].day_weather, "多云")
        self.assertEqual(weather_info[0].night_weather, "多云")
        self.assertEqual(weather_info[0].risk_level, "low")
        self.assertEqual(weather_info[1].date, "2026-05-01")
        self.assertEqual(weather_info[1].day_weather, "雷阵雨")
        self.assertEqual(weather_info[1].risk_level, "high")

    def test_parse_weather_response_handles_full_chinese_date_headers(self):
        raw_weather = """
        **2026年4月20日（星期一）**
        - 白天：多云，26°C，北风1-3级
        - 夜间：晴，14°C，北风1-3级

        **2026年4月21日（星期二）**
        - 白天：晴，27°C，西风1-3级
        - 夜间：晴，15°C，西风1-3级

        **2026年4月22日（星期三）**
        - 白天：多云，27°C，西风1-3级
        - 夜间：晴，14°C，西风1-3级
        """

        weather_info = parse_weather_response(raw_weather, "2026-04-20", 3)

        self.assertEqual(len(weather_info), 3)
        self.assertEqual(weather_info[0].day_weather, "多云")
        self.assertEqual(weather_info[0].night_weather, "晴")
        self.assertEqual(weather_info[0].day_temp, 26)
        self.assertEqual(weather_info[0].night_temp, 14)
        self.assertEqual(weather_info[0].risk_level, "low")

        self.assertEqual(weather_info[1].day_weather, "晴")
        self.assertEqual(weather_info[1].night_weather, "晴")
        self.assertEqual(weather_info[1].day_temp, 27)
        self.assertEqual(weather_info[1].night_temp, 15)
        self.assertEqual(weather_info[1].risk_level, "low")

        self.assertEqual(weather_info[2].day_weather, "多云")
        self.assertEqual(weather_info[2].night_weather, "晴")
        self.assertEqual(weather_info[2].day_temp, 27)
        self.assertEqual(weather_info[2].night_temp, 14)
        self.assertEqual(weather_info[2].risk_level, "low")


class TripPlannerValidationTest(unittest.TestCase):
    def test_plan_trip_stops_when_cancellation_token_is_set(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        token = PlanningCancellationToken()

        class CancelAfterWeatherAgent:
            def run(self, *_args, **_kwargs):
                token.cancel("客户端已停止生成请求")
                return "天气晴"

        class UnexpectedAgent:
            def run(self, *_args, **_kwargs):
                raise AssertionError("取消后不应继续执行后续阶段")

        planner.weather_agent = CancelAfterWeatherAgent()
        planner.attraction_agent = UnexpectedAgent()
        planner.hotel_agent = UnexpectedAgent()
        planner.planner_agent = UnexpectedAgent()

        request = TripRequest(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-01",
            travel_days=1,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )

        with self.assertRaises(TripPlanningCancelledError):
            planner.plan_trip(request, cancellation_token=token)

    def test_extract_candidate_attractions_prefers_weather_safe_real_pois(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-01",
                                    "dayweather": "暴雨",
                                    "nightweather": "雷阵雨",
                                    "daytemp": "29",
                                    "nighttemp": "22",
                                    "daywind": "东风",
                                    "daypower": "6级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-01",
            1,
        )
        raw_attractions = json.dumps(
            {
                "pois": [
                    {
                        "id": "museum-1",
                        "name": "首都博物馆",
                        "address": "北京市西城区复兴门外大街16号",
                        "location": "116.3499,39.9072",
                        "type": "博物馆",
                        "rating": "4.8",
                    },
                    {
                        "id": "park-1",
                        "name": "奥林匹克森林公园",
                        "address": "北京市朝阳区科荟路33号",
                        "location": "116.3967,40.0253",
                        "type": "公园",
                        "rating": "4.6",
                    },
                ]
            },
            ensure_ascii=False,
        )

        candidates = planner._extract_candidate_attractions(raw_attractions, "北京", weather_info)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].name, "首都博物馆")
        self.assertEqual(candidates[0].poi_id, "museum-1")
        self.assertAlmostEqual(candidates[0].location.longitude, 116.3499)
        self.assertTrue(all(candidate.location for candidate in candidates))

    def test_extract_candidate_attractions_handles_markdown_blocks(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-04-20",
                                    "dayweather": "晴",
                                    "nightweather": "晴",
                                    "daytemp": "28",
                                    "nighttemp": "20",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-04-20",
            1,
        )
        raw_attractions = """
        **1. 华南国家植物园 (核心推荐)**
        * 地址：天源路1190号
        * 类型：植物园
        * 坐标：113.3615,23.1824
        * 推荐理由：园区面积大，适合半天游览
        """

        candidates = planner._extract_candidate_attractions(raw_attractions, "广州", weather_info)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "华南国家植物园")
        self.assertEqual(candidates[0].address, "天源路1190号")
        self.assertAlmostEqual(candidates[0].location.longitude, 113.3615)
        self.assertAlmostEqual(candidates[0].location.latitude, 23.1824)

    def test_build_planner_query_uses_structured_candidate_payload(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        request = TripRequest(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-02",
            travel_days=2,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-01",
                                    "dayweather": "暴雨",
                                    "nightweather": "雷阵雨",
                                    "daytemp": "29",
                                    "nighttemp": "22",
                                    "daywind": "东风",
                                    "daypower": "6级",
                                },
                                {
                                    "date": "2026-05-02",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "27",
                                    "nighttemp": "20",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-01",
            2,
        )
        candidate_attractions = [
            Attraction(
                name="首都博物馆",
                address="北京市西城区复兴门外大街16号",
                location=Location(longitude=116.3499, latitude=39.9072),
                visit_duration=150,
                description="博物馆,北京市西城区复兴门外大街16号",
                category="博物馆",
                poi_id="museum-1",
            ),
            Attraction(
                name="景山公园",
                address="北京市西城区景山西街44号",
                location=Location(longitude=116.3976, latitude=39.9324),
                visit_duration=180,
                description="公园,北京市西城区景山西街44号",
                category="公园",
                poi_id="park-1",
            ),
        ]
        candidate_hotels = [
            Hotel(
                name="北京西城酒店",
                address="北京市西城区复兴门外大街18号",
                location=Location(longitude=116.3510, latitude=39.9075),
                price_range="320-420元",
                rating="4.6",
                type="经济型酒店",
                estimated_cost=370,
            )
        ]

        query = planner._build_planner_query(
            request,
            candidate_attractions,
            candidate_hotels,
            weather="天气原始结果",
            hotels="酒店原始结果",
            weather_info=weather_info,
            raw_attractions="景点原始结果",
        )

        self.assertIn("景点信息（来自工具搜索结果，供参考与编排）", query)
        self.assertIn("结构化景点候选（若有，包含坐标，建议优先使用以便地图展示）", query)
        self.assertIn('"candidate_attractions"', query)
        self.assertIn("首都博物馆", query)
        self.assertIn("景山公园", query)
        self.assertIn("酒店信息（来自工具搜索结果，供参考与编排）", query)
        self.assertIn("结构化酒店候选（若有，包含坐标/价格等，建议优先使用）", query)
        self.assertIn("北京西城酒店", query)
        self.assertIn('"suitability": [\n        "high",\n        "medium",\n        "low"\n      ]', query)
        self.assertIn('"area_tag"', query)
        self.assertIn('"nearest_candidates"', query)
        self.assertIn('"hotel_rule"', query)
        self.assertIn("景点原始结果", query)
        self.assertIn("减少跨日往返跳区", query)

    def test_extract_candidate_hotels_handles_json_records(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        raw_hotels = json.dumps(
            {
                "pois": [
                    {
                        "id": "hotel-1",
                        "name": "广州天河酒店",
                        "address": "天河区体育东路138号",
                        "location": "113.3272,23.1350",
                        "type": "舒适型酒店",
                        "rating": "4.7",
                        "price_range": "380-520元",
                    }
                ]
            },
            ensure_ascii=False,
        )

        hotels = planner._extract_candidate_hotels(raw_hotels, "广州")

        self.assertEqual(len(hotels), 1)
        self.assertEqual(hotels[0].name, "广州天河酒店")
        self.assertEqual(hotels[0].type, "舒适型酒店")
        self.assertEqual(hotels[0].estimated_cost, 450)
        self.assertAlmostEqual(hotels[0].location.longitude, 113.3272)

    def test_post_validate_replaces_hallucinated_hotel_with_real_candidate(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-04-20",
                                    "dayweather": "晴",
                                    "nightweather": "晴",
                                    "daytemp": "28",
                                    "nighttemp": "20",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-04-20",
            1,
        )
        request = TripRequest(
            city="广州",
            start_date="2026-04-20",
            end_date="2026-04-20",
            travel_days=1,
            transportation="公共交通",
            accommodation="舒适型酒店",
            preferences=["自然风光"],
            free_text_input="",
        )
        attraction = Attraction(
            name="华南国家植物园",
            address="天源路1190号",
            location=Location(longitude=113.3615, latitude=23.1824),
            visit_duration=180,
            description="植物园",
            category="植物园",
            poi_id="plant-garden-1",
        )
        candidate_hotel = Hotel(
            name="广州天河花园酒店",
            address="广州市天河区龙洞路8号",
            location=Location(longitude=113.3580, latitude=23.1805),
            price_range="380-520元",
            rating="4.7",
            type="舒适型酒店",
            estimated_cost=450,
        )
        raw_plan = TripPlan(
            city="广州",
            start_date="2026-04-20",
            end_date="2026-04-20",
            overall_suggestions="原始建议",
            days=[
                DayPlan(
                    date="2026-04-20",
                    day_index=0,
                    description="植物园游览",
                    transportation="公共交通",
                    accommodation="舒适型酒店",
                    hotel=Hotel(
                        name="广州豪华酒店",
                        address="广州行程动线中段便捷住宿区",
                        location=Location(longitude=113.5000, latitude=23.2500),
                        price_range="300-500元",
                        rating="4.5",
                        type="豪华酒店",
                        estimated_cost=380,
                    ),
                    attractions=[attraction],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                )
            ],
            weather_info=[],
        )

        adjusted = planner._post_validate_trip_plan(
            raw_plan,
            request,
            weather_info,
            candidate_attractions=[attraction],
            candidate_hotels=[candidate_hotel],
        )

        self.assertEqual(adjusted.days[0].hotel.name, "广州天河花园酒店")
        self.assertEqual(adjusted.days[0].hotel.address, "广州市天河区龙洞路8号")
        self.assertIn("已替换为真实候选酒店", " ".join(adjusted.warnings))

    def test_post_validate_reorders_day_flow_and_adjusts_hotel_for_next_day(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-01",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "27",
                                    "nighttemp": "20",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                                {
                                    "date": "2026-05-02",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "28",
                                    "nighttemp": "21",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-01",
            2,
        )
        request = TripRequest(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-02",
            travel_days=2,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )
        day1_a = Attraction(
            name="A景点",
            address="北京市东城区A路",
            location=Location(longitude=116.3500, latitude=39.9000),
            visit_duration=90,
            description="文化景点",
            category="博物馆",
            poi_id="a-1",
        )
        day1_b = Attraction(
            name="B景点",
            address="北京市东城区B路",
            location=Location(longitude=116.3600, latitude=39.9010),
            visit_duration=90,
            description="文化景点",
            category="博物馆",
            poi_id="b-1",
        )
        day1_c = Attraction(
            name="C景点",
            address="北京市朝阳区C路",
            location=Location(longitude=116.4500, latitude=39.9500),
            visit_duration=120,
            description="文化景点",
            category="博物馆",
            poi_id="c-1",
        )
        day2_a = Attraction(
            name="次日景点",
            address="北京市朝阳区D路",
            location=Location(longitude=116.4550, latitude=39.9520),
            visit_duration=120,
            description="文化景点",
            category="博物馆",
            poi_id="d-1",
        )
        raw_plan = TripPlan(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-02",
            overall_suggestions="原始建议",
            days=[
                DayPlan(
                    date="2026-05-01",
                    day_index=0,
                    description="原始顺序可能回头",
                    transportation="公共交通",
                    accommodation="经济型酒店",
                    hotel=Hotel(
                        name="偏远酒店",
                        address="北京市远郊",
                        location=Location(longitude=116.2000, latitude=39.7000),
                        estimated_cost=280,
                    ),
                    attractions=[day1_a, day1_c, day1_b],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                ),
                DayPlan(
                    date="2026-05-02",
                    day_index=1,
                    description="第二天继续游览",
                    transportation="公共交通",
                    accommodation="经济型酒店",
                    hotel=None,
                    attractions=[day2_a],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                ),
            ],
            weather_info=[],
        )
        candidates = [day1_a, day1_b, day1_c, day2_a]

        adjusted = planner._post_validate_trip_plan(
            raw_plan,
            request,
            weather_info,
            candidate_attractions=candidates,
        )

        self.assertEqual(
            [item.name for item in adjusted.days[0].attractions],
            ["A景点", "B景点", "C景点"],
        )
        self.assertEqual(adjusted.days[0].hotel.name, "偏远酒店")
        self.assertEqual(adjusted.days[0].hotel.address, "北京市远郊")
        self.assertIn("方便次日上午顺接", adjusted.days[0].description)
        self.assertIn("顺路动线串联A景点、B景点、C景点", adjusted.overall_suggestions)
        self.assertTrue(
            any("已按更顺路的空间动线重排景点顺序" in warning for warning in adjusted.warnings)
        )
        self.assertTrue(
            any("酒店与今明两天主要景点脱节,但未改写为虚构酒店" in warning for warning in adjusted.warnings)
        )

    def test_post_validate_warns_on_cross_day_north_south_north_oscillation(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-10",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "25",
                                    "nighttemp": "18",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                                {
                                    "date": "2026-05-11",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "26",
                                    "nighttemp": "19",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                                {
                                    "date": "2026-05-12",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "27",
                                    "nighttemp": "20",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-10",
            3,
        )
        request = TripRequest(
            city="北京",
            start_date="2026-05-10",
            end_date="2026-05-12",
            travel_days=3,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["城市漫游"],
            free_text_input="",
        )

        def build_day(date_value, day_index, name, longitude, latitude):
            attraction = Attraction(
                name=name,
                address=f"北京市{day_index}号路",
                location=Location(longitude=longitude, latitude=latitude),
                visit_duration=120,
                description="城市景点",
                category="景点",
                poi_id=name,
            )
            return DayPlan(
                date=date_value,
                day_index=day_index,
                description=f"第{day_index + 1}天",
                transportation="公共交通",
                accommodation="经济型酒店",
                hotel=Hotel(name=f"酒店{day_index + 1}", address="北京市", estimated_cost=300),
                attractions=[attraction],
                meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
            )

        raw_plan = TripPlan(
            city="北京",
            start_date="2026-05-10",
            end_date="2026-05-12",
            overall_suggestions="原始建议",
            days=[
                build_day("2026-05-10", 0, "北区景点1", 116.40, 40.02),
                build_day("2026-05-11", 1, "南区景点", 116.40, 39.80),
                build_day("2026-05-12", 2, "北区景点2", 116.41, 40.01),
            ],
            weather_info=[],
        )

        adjusted = planner._post_validate_trip_plan(raw_plan, request, weather_info)

        self.assertEqual(adjusted.validation_status, "warning")
        self.assertTrue(
            any("类似北边-南边-北边的跨日往返" in warning for warning in adjusted.warnings)
        )

    def test_post_validate_only_warns_for_high_risk_outdoor_plan(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-01",
                                    "dayweather": "暴雨",
                                    "nightweather": "雷阵雨",
                                    "daytemp": "29",
                                    "nighttemp": "22",
                                    "daywind": "东风",
                                    "daypower": "6级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-01",
            1,
        )
        request = TripRequest(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-01",
            travel_days=1,
            transportation="步行",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )
        raw_plan = TripPlan(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-01",
            overall_suggestions="原始建议",
            days=[
                DayPlan(
                    date="2026-05-01",
                    day_index=0,
                    description="暴雨天外出散步",
                    transportation="步行",
                    accommodation="经济型酒店",
                    hotel=Hotel(name="测试酒店", address="北京市", estimated_cost=300),
                    attractions=[
                        Attraction(
                            name="城市公园",
                            address="北京市朝阳区",
                            location=Location(longitude=116.4, latitude=39.9),
                            visit_duration=120,
                            description="户外散步",
                            category="公园",
                            ticket_price=0,
                        )
                    ],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                )
            ],
            weather_info=[],
        )
        candidate_attractions = [
            Attraction(
                name="首都博物馆",
                address="北京市西城区复兴门外大街16号",
                location=Location(longitude=116.3499, latitude=39.9072),
                visit_duration=150,
                description="博物馆,北京市西城区复兴门外大街16号",
                category="博物馆",
                poi_id="museum-1",
            ),
            Attraction(
                name="国家自然博物馆",
                address="北京市东城区天桥南大街126号",
                location=Location(longitude=116.4065, latitude=39.8841),
                visit_duration=150,
                description="博物馆,北京市东城区天桥南大街126号",
                category="博物馆",
                poi_id="museum-2",
            ),
        ]

        adjusted = planner._post_validate_trip_plan(
            raw_plan,
            request,
            weather_info,
            candidate_attractions=candidate_attractions,
        )

        self.assertEqual(adjusted.validation_status, "warning")
        self.assertFalse(adjusted.fallback_used)
        self.assertTrue(adjusted.warnings)
        self.assertEqual(adjusted.days[0].transportation, "步行")
        self.assertTrue(all(meal_type in [meal.type for meal in adjusted.days[0].meals] for meal_type in ["breakfast", "lunch", "dinner"]))
        self.assertEqual(adjusted.days[0].attractions[0].name, "城市公园")
        self.assertIn("城市公园", adjusted.days[0].description)
        self.assertIn("测试酒店", adjusted.days[0].description)
        self.assertTrue(any("高风险天气仍安排了明显户外景点" in warning for warning in adjusted.warnings))
        self.assertTrue(any("候选列表之外的景点" in warning for warning in adjusted.warnings))

    def test_post_validate_keeps_medium_risk_indoor_plan_without_replanning(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-03",
                                    "dayweather": "小雨",
                                    "nightweather": "阴",
                                    "daytemp": "24",
                                    "nighttemp": "18",
                                    "daywind": "东风",
                                    "daypower": "3级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-03",
            1,
        )
        request = TripRequest(
            city="北京",
            start_date="2026-05-03",
            end_date="2026-05-03",
            travel_days=1,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )
        raw_plan = TripPlan(
            city="北京",
            start_date="2026-05-03",
            end_date="2026-05-03",
            overall_suggestions="建议携带雨具并灵活调整行程",
            days=[
                DayPlan(
                    date="2026-05-03",
                    day_index=0,
                    description="小雨天气以室内参观为主，方便避雨并灵活调整。",
                    transportation="公共交通",
                    accommodation="经济型酒店",
                    hotel=Hotel(name="测试酒店", address="北京市", estimated_cost=300),
                    attractions=[
                        Attraction(
                            name="首都博物馆",
                            address="北京市西城区复兴门外大街16号",
                            location=Location(longitude=116.3499, latitude=39.9072),
                            visit_duration=150,
                            description="博物馆,适合避雨",
                            category="博物馆",
                            ticket_price=0,
                            poi_id="museum-1",
                        )
                    ],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                )
            ],
            weather_info=[],
        )
        candidate_attractions = [
            Attraction(
                name="首都博物馆",
                address="北京市西城区复兴门外大街16号",
                location=Location(longitude=116.3499, latitude=39.9072),
                visit_duration=150,
                description="博物馆,适合避雨",
                category="博物馆",
                poi_id="museum-1",
            )
        ]

        adjusted = planner._post_validate_trip_plan(
            raw_plan,
            request,
            weather_info,
            candidate_attractions=candidate_attractions,
        )

        self.assertEqual(adjusted.validation_status, "validated")
        self.assertFalse(adjusted.fallback_used)
        self.assertFalse(adjusted.warnings)
        self.assertEqual(adjusted.days[0].attractions[0].name, "首都博物馆")
        self.assertIn("首都博物馆", adjusted.days[0].description)
        self.assertIn("测试酒店", adjusted.days[0].description)

    def test_post_validate_keeps_sunny_outdoor_plan_without_adjustment(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-02",
                                    "dayweather": "晴",
                                    "nightweather": "少云",
                                    "daytemp": "28",
                                    "nighttemp": "20",
                                    "daywind": "东风",
                                    "daypower": "2级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-02",
            1,
        )
        request = TripRequest(
            city="北京",
            start_date="2026-05-02",
            end_date="2026-05-02",
            travel_days=1,
            transportation="步行",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )
        raw_plan = TripPlan(
            city="北京",
            start_date="2026-05-02",
            end_date="2026-05-02",
            overall_suggestions="原始建议",
            days=[
                DayPlan(
                    date="2026-05-02",
                    day_index=0,
                    description="晴天户外游览",
                    transportation="步行",
                    accommodation="经济型酒店",
                    hotel=Hotel(name="测试酒店", address="北京市", estimated_cost=300),
                    attractions=[
                        Attraction(
                            name="颐和园",
                            address="北京市海淀区",
                            location=Location(longitude=116.27, latitude=39.99),
                            visit_duration=180,
                            description="晴天适合户外漫步",
                            category="公园",
                            ticket_price=30,
                        )
                    ],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                )
            ],
            weather_info=[],
        )

        adjusted = planner._post_validate_trip_plan(raw_plan, request, weather_info)

        self.assertEqual(adjusted.validation_status, "validated")
        self.assertFalse(adjusted.fallback_used)
        self.assertFalse(adjusted.warnings)
        self.assertIn("颐和园", adjusted.days[0].description)
        self.assertIn("测试酒店", adjusted.days[0].description)
        self.assertEqual(adjusted.days[0].transportation, "步行")
        self.assertEqual(adjusted.days[0].attractions[0].name, "颐和园")
        self.assertEqual(adjusted.days[0].attractions[0].category, "公园")

    def test_post_validate_fills_missing_day_with_empty_structure_not_fake_itinerary(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-05-01",
                                    "dayweather": "雷阵雨",
                                    "nightweather": "雷阵雨",
                                    "daytemp": "25",
                                    "nighttemp": "20",
                                    "daywind": "东风",
                                    "daypower": "5级",
                                },
                                {
                                    "date": "2026-05-02",
                                    "dayweather": "晴",
                                    "nightweather": "多云",
                                    "daytemp": "27",
                                    "nighttemp": "21",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                },
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-05-01",
            2,
        )
        request = TripRequest(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-02",
            travel_days=2,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )
        raw_plan = TripPlan(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-02",
            overall_suggestions="原始建议",
            days=[
                DayPlan(
                    date="2026-05-01",
                    day_index=0,
                    description="第1天室内参观",
                    transportation="公共交通",
                    accommodation="经济型酒店",
                    hotel=Hotel(name="测试酒店", address="北京市", estimated_cost=300),
                    attractions=[
                        Attraction(
                            name="首都博物馆",
                            address="北京市西城区复兴门外大街16号",
                            location=Location(longitude=116.3499, latitude=39.9072),
                            visit_duration=150,
                            description="博物馆",
                            category="博物馆",
                            ticket_price=0,
                        )
                    ],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                )
            ],
            weather_info=[],
        )

        adjusted = planner._post_validate_trip_plan(raw_plan, request, weather_info)

        self.assertEqual(adjusted.validation_status, "warning")
        self.assertFalse(adjusted.fallback_used)
        self.assertEqual(len(adjusted.days), 2)
        self.assertEqual(adjusted.days[1].date, "2026-05-02")
        self.assertEqual(adjusted.days[1].attractions, [])
        self.assertIsNone(adjusted.days[1].hotel)
        self.assertIn("住宿待确认", adjusted.days[1].description)
        self.assertIn("就近活动为主", adjusted.days[1].description)
        self.assertTrue(any("缺少原始日程" in warning for warning in adjusted.warnings))
        self.assertTrue(any("未生成景点安排" in warning for warning in adjusted.warnings))
        self.assertTrue(any("未生成可核验的真实酒店" in warning for warning in adjusted.warnings))

    def test_post_validate_aligns_attraction_with_real_candidate_for_map(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        weather_info = parse_weather_response(
            json.dumps(
                {
                    "forecasts": [
                        {
                            "casts": [
                                {
                                    "date": "2026-04-20",
                                    "dayweather": "晴",
                                    "nightweather": "晴",
                                    "daytemp": "28",
                                    "nighttemp": "20",
                                    "daywind": "南风",
                                    "daypower": "2级",
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            "2026-04-20",
            1,
        )
        request = TripRequest(
            city="广州",
            start_date="2026-04-20",
            end_date="2026-04-20",
            travel_days=1,
            transportation="公共交通",
            accommodation="舒适型酒店",
            preferences=["自然风光"],
            free_text_input="",
        )
        candidate = Attraction(
            name="华南国家植物园",
            address="天源路1190号",
            location=Location(longitude=113.3615, latitude=23.1824),
            visit_duration=180,
            description="植物园,天源路1190号",
            category="植物园",
            poi_id="plant-garden-1",
        )
        raw_plan = TripPlan(
            city="广州",
            start_date="2026-04-20",
            end_date="2026-04-20",
            overall_suggestions="原始建议",
            days=[
                DayPlan(
                    date="2026-04-20",
                    day_index=0,
                    description="游览植物园",
                    transportation="公共交通",
                    accommodation="舒适型酒店",
                    hotel=None,
                    attractions=[
                        Attraction(
                            name="华南国家植物园（核心推荐）",
                            address="广州市天河区",
                            location=Location(longitude=0, latitude=0),
                            visit_duration=120,
                            description="模型输出景点",
                            category="景点",
                            ticket_price=0,
                        )
                    ],
                    meals=[Meal(type="lunch", name="午餐", estimated_cost=40)],
                )
            ],
            weather_info=[],
        )

        adjusted = planner._post_validate_trip_plan(
            raw_plan,
            request,
            weather_info,
            candidate_attractions=[candidate],
        )

        self.assertEqual(adjusted.days[0].attractions[0].name, "华南国家植物园")
        self.assertEqual(adjusted.days[0].attractions[0].poi_id, "plant-garden-1")
        self.assertAlmostEqual(adjusted.days[0].attractions[0].location.longitude, 113.3615)
        self.assertAlmostEqual(adjusted.days[0].attractions[0].location.latitude, 23.1824)


class FakeRequest:
    def __init__(self, disconnected: bool):
        self.disconnected = disconnected

    async def is_disconnected(self):
        return self.disconnected


class TripPlannerRouteCancellationTest(unittest.TestCase):
    def test_trip_route_cancels_when_client_disconnects(self):
        payload = TripRequest(
            city="北京",
            start_date="2026-05-01",
            end_date="2026-05-01",
            travel_days=1,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )

        class CancelAwarePlanner:
            def plan_trip(self, _request, token=None):
                while token and not token.is_cancelled():
                    time.sleep(0.01)
                raise TripPlanningCancelledError("客户端已停止生成请求")

        with patch.object(trip_route, "get_trip_planner_agent", return_value=CancelAwarePlanner()):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(trip_route.plan_trip(FakeRequest(True), payload))

        self.assertEqual(ctx.exception.status_code, 499)
        self.assertEqual(ctx.exception.detail, "已停止生成当前行程")

    def test_trip_route_returns_400_when_city_is_invalid(self):
        payload = TripRequest(
            city="@@##",
            start_date="2026-05-01",
            end_date="2026-05-01",
            travel_days=1,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=[],
            free_text_input="",
        )

        with patch.object(trip_route, "get_trip_planner_agent", side_effect=AssertionError("不应初始化 Agent")):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(trip_route.plan_trip(FakeRequest(False), payload))

        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
