import json
import sys
import types
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.schemas import Attraction, DayPlan, Hotel, Location, Meal, TripPlan, TripRequest
from app.services.weather_planning_service import parse_weather_response

try:
    from app.agents.trip_planner_agent import MultiAgentTripPlanner
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

    from app.agents.trip_planner_agent import MultiAgentTripPlanner


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


class TripPlannerValidationTest(unittest.TestCase):
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

        query = planner._build_planner_query(
            request,
            candidate_attractions,
            weather="天气原始结果",
            hotels="酒店原始结果",
            weather_info=weather_info,
            raw_attractions="景点原始结果",
        )

        self.assertIn("真实景点候选(只允许从以下列表中选择)", query)
        self.assertIn('"candidate_attractions"', query)
        self.assertIn("首都博物馆", query)
        self.assertIn("景山公园", query)
        self.assertIn('"suitability": [\n        "high",\n        "medium",\n        "low"\n      ]', query)
        self.assertIn("景点原始搜索结果", query)

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
        self.assertEqual(adjusted.days[0].description, "暴雨天外出散步")
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
        self.assertEqual(adjusted.days[0].description, "小雨天气以室内参观为主，方便避雨并灵活调整。")

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
        self.assertEqual(adjusted.days[0].description, "晴天户外游览")
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
        self.assertEqual(adjusted.days[1].description, "第2天行程待确认")
        self.assertTrue(any("缺少原始日程" in warning for warning in adjusted.warnings))
        self.assertTrue(any("未生成景点安排" in warning for warning in adjusted.warnings))


if __name__ == "__main__":
    unittest.main()
