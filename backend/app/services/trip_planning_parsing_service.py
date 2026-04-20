"""Trip planning parsing and candidate extraction services."""

import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

from ..models.schemas import Attraction, Hotel, Location, TripPlan, TripRequest, WeatherInfo
from .weather_planning_service import is_indoor_attraction, is_outdoor_attraction


CancellationChecker = Callable[[Optional[object], str], None]
FallbackFactory = Callable[[TripRequest, Optional[List[WeatherInfo]], str], TripPlan]


class TripPlanningParsingService:
    """Handle candidate extraction, planner payloads, and JSON response parsing."""

    def __init__(
        self,
        llm: Optional[Any] = None,
        cancellation_exception_cls: Optional[Type[Exception]] = None,
    ) -> None:
        self.llm = llm
        self.cancellation_exception_cls = cancellation_exception_cls

    def set_llm(self, llm: Any) -> None:
        self.llm = llm

    def parse_trip_plan_response(
        self,
        response: str,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
        cancellation_token: Optional[object] = None,
        check_cancellation: Optional[CancellationChecker] = None,
        fallback_factory: Optional[FallbackFactory] = None,
    ) -> TripPlan:
        """Parse the planner response into a validated TripPlan or fallback."""
        try:
            self._check_cancellation(check_cancellation, cancellation_token, "解析响应前")
            json_candidate = self.extract_json_candidate(response)
            data = self.load_trip_plan_json(
                json_candidate,
                cancellation_token=cancellation_token,
                check_cancellation=check_cancellation,
            )
            return TripPlan(**data)
        except Exception as exc:  # pragma: no cover - cancellation path is delegated
            if self._is_cancellation_exception(exc):
                raise
            print(f"⚠️  解析响应失败: {str(exc)}")
            self.dump_failed_response(response)
            print("   将使用备用方案生成计划")
            self._check_cancellation(check_cancellation, cancellation_token, "解析失败回退前")
            if fallback_factory is None:
                raise
            return fallback_factory(request, weather_info=weather_info, reason=f"解析失败: {exc}")

    def extract_json_candidate(self, response: str) -> str:
        """Extract the most likely JSON fragment from model output."""
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

    def load_trip_plan_json(
        self,
        json_candidate: str,
        cancellation_token: Optional[object] = None,
        check_cancellation: Optional[CancellationChecker] = None,
    ) -> Dict[str, Any]:
        """Load planner JSON with sanitizing and optional LLM repair."""
        parse_errors = []

        for candidate in (json_candidate, self.sanitize_json_text(json_candidate)):
            try:
                return json.loads(candidate)
            except Exception as exc:
                parse_errors.append(str(exc))

        self._check_cancellation(check_cancellation, cancellation_token, "JSON修复前")
        repaired_json = self.repair_json_with_llm(
            json_candidate,
            cancellation_token=cancellation_token,
            check_cancellation=check_cancellation,
        )
        try:
            return json.loads(repaired_json)
        except Exception as exc:
            parse_errors.append(f"LLM修复后仍失败: {exc}")
            raise ValueError("；".join(parse_errors))

    @staticmethod
    def sanitize_json_text(text: str) -> str:
        """Repair common non-strict JSON patterns."""
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

    def repair_json_with_llm(
        self,
        broken_json: str,
        cancellation_token: Optional[object] = None,
        check_cancellation: Optional[CancellationChecker] = None,
    ) -> str:
        """Use the configured LLM to repair almost-JSON content."""
        if self.llm is None:
            raise ValueError("缺少可用 LLM，无法修复无效 JSON")
        self._check_cancellation(check_cancellation, cancellation_token, "JSON修复调用前")
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
        return self.extract_json_candidate(repaired)

    @staticmethod
    def dump_failed_response(response: str) -> None:
        """Persist the raw model output for debugging parse failures."""
        try:
            dump_path = Path(__file__).resolve().parents[2] / "logs"
            dump_path.mkdir(parents=True, exist_ok=True)
            failed_file = dump_path / "last_trip_plan_response.txt"
            failed_file.write_text(response, encoding="utf-8")
            print(f"📝 已保存解析失败的原始响应: {failed_file}")
        except Exception as exc:  # pragma: no cover - debug helper only
            print(f"⚠️  保存失败响应时出错: {exc}")

    def extract_candidate_attractions(
        self,
        attraction_response: str,
        city: str,
        weather_info: List[WeatherInfo],
    ) -> List[Attraction]:
        """Extract structured attraction candidates from raw agent output."""
        raw_candidates = self.extract_candidate_records(attraction_response)
        candidates: List[Attraction] = []
        seen_keys: Set[str] = set()

        for record in raw_candidates:
            attraction = self.record_to_attraction(record, city)
            if not attraction:
                continue
            candidate_key = self.candidate_key(attraction)
            if candidate_key in seen_keys:
                continue
            seen_keys.add(candidate_key)
            candidates.append(attraction)

        return self.select_trip_candidate_pool(candidates, weather_info)

    def extract_candidate_hotels(self, hotel_response: str, city: str) -> List[Hotel]:
        """Extract structured hotel candidates from raw agent output."""
        raw_candidates = self.extract_candidate_records(hotel_response)
        candidates: List[Hotel] = []
        seen_keys: Set[str] = set()

        for record in raw_candidates:
            hotel = self.record_to_hotel(record, city)
            if not hotel:
                continue
            candidate_key = self.hotel_candidate_key(hotel)
            if candidate_key in seen_keys:
                continue
            seen_keys.add(candidate_key)
            candidates.append(hotel)

        candidates.sort(
            key=lambda item: (
                (item.estimated_cost or 0) <= 0,
                item.estimated_cost or 0,
                -(self.safe_float(item.rating) or 0.0),
            )
        )
        return candidates[:12]

    def build_attraction_candidates_payload(
        self,
        candidate_attractions: List[Attraction],
        weather_info: List[WeatherInfo],
    ) -> str:
        """Build structured attraction context for the planner agent."""
        trip_has_high_risk = any(item.risk_level == "high" for item in weather_info)
        trip_has_medium_risk = any(item.risk_level == "medium" for item in weather_info)
        reference_locations = [
            attraction.location
            for attraction in candidate_attractions
            if attraction.location
        ]
        payload = {
            "selection_rules": {
                "high_risk": "只能选择 suitability 包含 high 的候选,且每天 1-2 个",
                "medium_risk": "优先选择 suitability 包含 medium 的候选,减少跨区移动",
                "low_risk": "优先复用 low 候选,但仍需控制动线",
            },
            "spatial_constraints": {
                "same_day_cluster_rule": "优先选择 area_tag 相同或 nearest_candidates 彼此接近的景点放在同一天",
                "route_rule": "同一天按顺路动线排列,避免明显回头路",
                "cross_day_rule": "相邻两天优先形成片区顺接,避免北边-南边-北边式往返",
                "hotel_rule": "酒店兼顾当天最后景点与次日首段景点,优先住在两者附近或中间",
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
                    "suitability": self.build_candidate_suitability(attraction),
                    "area_tag": self.build_area_tag(attraction.location, reference_locations),
                    "nearest_candidates": self.build_nearest_candidate_payload(
                        attraction,
                        candidate_attractions,
                    ),
                }
                for attraction in candidate_attractions
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def build_hotel_candidates_payload(
        self,
        candidate_hotels: List[Hotel],
        candidate_attractions: List[Attraction],
    ) -> str:
        """Build structured hotel context for the planner agent."""
        reference_locations = [
            attraction.location
            for attraction in candidate_attractions
            if attraction.location
        ]
        payload = {
            "selection_rules": {
                "must_choose_from_candidates": True,
                "empty_candidates_policy": "hotel 允许为 null,不得编造酒店",
                "route_rule": "优先选择靠近当天收尾景点且兼顾次日上午首段景点的酒店",
            },
            "candidate_hotels": [
                {
                    "name": hotel.name,
                    "address": hotel.address,
                    "location": hotel.location.model_dump() if hotel.location else None,
                    "price_range": hotel.price_range,
                    "rating": hotel.rating,
                    "type": hotel.type,
                    "estimated_cost": hotel.estimated_cost,
                    "area_tag": self.build_area_tag(hotel.location, reference_locations),
                    "nearest_attractions": self.build_hotel_nearest_attractions_payload(
                        hotel,
                        candidate_attractions,
                    ),
                }
                for hotel in candidate_hotels
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def extract_candidate_records(self, text: str) -> List[Dict[str, Any]]:
        """Extract POI-like records from JSON or plain text."""
        records: List[Dict[str, Any]] = []
        for candidate in self.collect_json_candidates(text):
            try:
                data = json.loads(candidate)
            except Exception:
                continue
            records.extend(self.walk_poi_records(data))

        if records:
            return records
        return self.extract_candidate_records_from_text(text)

    @staticmethod
    def collect_json_candidates(text: str) -> List[str]:
        """Collect likely JSON fragments from an arbitrary text block."""
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

    def walk_poi_records(self, data: Any) -> List[Dict[str, Any]]:
        """Recursively traverse a JSON object and collect POI-like nodes."""
        if isinstance(data, list):
            records: List[Dict[str, Any]] = []
            for item in data:
                records.extend(self.walk_poi_records(item))
            return records

        if not isinstance(data, dict):
            return []

        records: List[Dict[str, Any]] = []
        if self.looks_like_poi_record(data):
            records.append(data)

        for key in ("pois", "data", "results", "items", "list", "suggestions", "tips"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    records.extend(self.walk_poi_records(item))

        for value in data.values():
            if isinstance(value, (dict, list)):
                records.extend(self.walk_poi_records(value))

        return records

    @staticmethod
    def looks_like_poi_record(record: Dict[str, Any]) -> bool:
        """Check whether a dict resembles a POI record."""
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

    def extract_candidate_records_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Fallback parser for non-JSON attraction or hotel listings."""
        markdown_records = self.extract_candidate_records_from_markdown(text)
        if markdown_records:
            return markdown_records

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

    def extract_candidate_records_from_markdown(self, text: str) -> List[Dict[str, Any]]:
        """Parse Markdown candidate blocks into structured records."""
        lines = [line.rstrip() for line in text.replace("\\n", "\n").splitlines()]
        blocks: List[List[str]] = []
        current_block: List[str] = []

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue

            if self.is_candidate_block_header(stripped):
                if current_block:
                    blocks.append(current_block)
                current_block = [stripped]
                continue

            if current_block:
                current_block.append(stripped)

        if current_block:
            blocks.append(current_block)

        records: List[Dict[str, Any]] = []
        for block in blocks:
            record = self.parse_candidate_markdown_block(block)
            if record:
                records.append(record)
        return records

    @staticmethod
    def is_candidate_block_header(text: str) -> bool:
        """Check whether a line is a candidate block title."""
        normalized = re.sub(r"\*", "", text).strip()
        if re.search(r"(地址|推荐理由|坐标|经纬度|类型|类别|评分)[:：]", normalized):
            return False
        return bool(re.match(r"^(?:\d+[\.、]\s*)?.{2,40}(?:[（(].*?[）)])?$", normalized))

    @classmethod
    def parse_candidate_markdown_block(cls, lines: List[str]) -> Dict[str, Any]:
        """Parse a Markdown candidate block."""
        if not lines:
            return {}

        header = re.sub(r"\*", "", lines[0]).strip()
        header = re.sub(r"^\d+[\.、]\s*", "", header)
        name = cls.normalize_place_name(header, keep_suffix=False)
        if not name:
            return {}

        block_text = "\n".join(lines)
        location_match = re.search(r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)", block_text)
        if not location_match:
            return {}

        address_match = re.search(r"(?:地址|地点)[:：]\s*([^\n]+)", block_text)
        category_match = re.search(r"(?:类型|类别)[:：]\s*([^\n]+)", block_text)
        rating_match = re.search(r"(?:评分|星级)[:：]?\s*([0-9]+(?:\.[0-9]+)?)", block_text)

        return {
            "name": name,
            "address": address_match.group(1).strip(" *") if address_match else "",
            "location": f"{location_match.group(1)},{location_match.group(2)}",
            "type": category_match.group(1).strip(" *") if category_match else "",
            "rating": rating_match.group(1) if rating_match else "",
        }

    def record_to_attraction(self, record: Dict[str, Any], city: str) -> Optional[Attraction]:
        """Convert a raw POI record to an Attraction."""
        name = str(record.get("name") or record.get("title") or "").strip()
        if not name:
            return None

        location = self.parse_record_location(record)
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
        rating = self.safe_float(record.get("rating") or record.get("score"))
        photos = self.parse_photos(record.get("photos") or record.get("images") or [])
        description_parts = [part for part in [category, address] if part]
        poi_id = str(record.get("id") or record.get("poi_id") or record.get("uid") or "").strip()

        return Attraction(
            name=name,
            address=address,
            location=location,
            visit_duration=self.estimate_visit_duration(category),
            description="，".join(description_parts) or f"{city}真实景点候选",
            category=category or "景点",
            rating=rating,
            photos=photos,
            poi_id=poi_id,
            image_url=photos[0] if photos else None,
            ticket_price=0,
        )

    def record_to_hotel(self, record: Dict[str, Any], city: str) -> Optional[Hotel]:
        """Convert a raw POI record to a Hotel."""
        name = str(record.get("name") or record.get("title") or "").strip()
        if not name:
            return None

        location = self.parse_record_location(record)
        if location is None:
            return None

        address = str(
            record.get("address")
            or record.get("addr")
            or record.get("business_area")
            or f"{city}市内"
        ).strip()
        hotel_type = str(
            record.get("type")
            or record.get("category")
            or record.get("typecode")
            or "酒店"
        ).strip()
        rating_value = record.get("rating") or record.get("score") or ""
        rating_float = self.safe_float(rating_value)
        price_range = str(
            record.get("price_range")
            or record.get("price")
            or record.get("priceLevel")
            or ""
        ).strip()
        estimated_cost = self.estimate_hotel_cost(price_range)

        return Hotel(
            name=name,
            address=address,
            location=location,
            price_range=price_range,
            rating=(
                str(rating_value).strip()
                if rating_value not in (None, "")
                else (f"{rating_float:.1f}" if rating_float is not None else "")
            ),
            distance="",
            type=hotel_type or "酒店",
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def parse_record_location(record: Dict[str, Any]) -> Optional[Location]:
        """Parse multiple common longitude/latitude shapes."""
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

    @staticmethod
    def parse_photos(photo_value: Any) -> List[str]:
        """Normalize image URLs from string or list payloads."""
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

    @staticmethod
    def estimate_visit_duration(category: str) -> int:
        """Estimate visit duration based on attraction category."""
        if any(keyword in category for keyword in ("博物馆", "美术馆", "纪念馆", "科技馆", "艺术馆")):
            return 150
        if any(keyword in category for keyword in ("公园", "街区", "古镇", "湖", "山")):
            return 180
        return 120

    @staticmethod
    def safe_float(value: Any) -> Optional[float]:
        """Safely coerce a value to float."""
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def score_candidate_attraction(
        self,
        attraction: Attraction,
        weather_info: List[WeatherInfo],
    ) -> Tuple[int, float]:
        """Score attractions for candidate pool selection."""
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

    def select_trip_candidate_pool(
        self,
        candidates: List[Attraction],
        weather_info: List[WeatherInfo],
    ) -> List[Attraction]:
        """Select a balanced candidate pool by weather and coarse area clustering."""
        if not candidates:
            return []

        selection_limit = max(6, len(weather_info) * 3)
        reference_locations = [candidate.location for candidate in candidates if candidate.location]
        area_groups: Dict[str, List[Attraction]] = {}
        for attraction in candidates:
            area_tag = self.build_area_tag(attraction.location, reference_locations)
            area_groups.setdefault(area_tag, []).append(attraction)

        sorted_groups = sorted(
            (
                sorted(
                    group,
                    key=lambda item: self.score_candidate_attraction(item, weather_info),
                    reverse=True,
                )
                for group in area_groups.values()
            ),
            key=lambda group: self.score_candidate_attraction(group[0], weather_info),
            reverse=True,
        )

        selected: List[Attraction] = []
        group_offsets = [0 for _ in sorted_groups]
        while len(selected) < selection_limit and sorted_groups:
            made_progress = False
            for group_index, group in enumerate(sorted_groups):
                offset = group_offsets[group_index]
                if offset >= len(group):
                    continue
                selected.append(group[offset])
                group_offsets[group_index] += 1
                made_progress = True
                if len(selected) >= selection_limit:
                    break
            if not made_progress:
                break

        return selected

    @staticmethod
    def build_candidate_suitability(attraction: Attraction) -> List[str]:
        """Derive weather suitability tags for an attraction."""
        indoor = is_indoor_attraction(attraction)
        outdoor = is_outdoor_attraction(attraction)
        if indoor:
            return ["high", "medium", "low"]
        if outdoor:
            return ["low"]
        return ["medium", "low"]

    def build_hotel_nearest_attractions_payload(
        self,
        hotel: Hotel,
        candidate_attractions: List[Attraction],
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Describe nearby attractions for each hotel candidate."""
        if not hotel.location:
            return []
        neighbors = [
            {
                "name": attraction.name,
                "distance_km": round(self.distance_km(hotel.location, attraction.location), 2),
            }
            for attraction in candidate_attractions
            if attraction.location
        ]
        neighbors.sort(key=lambda item: item["distance_km"])
        return neighbors[:limit]

    def build_nearest_candidate_payload(
        self,
        attraction: Attraction,
        candidate_attractions: List[Attraction],
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """Describe nearby attractions to guide same-day grouping."""
        neighbors = []
        for other in candidate_attractions:
            if self.candidate_key(other) == self.candidate_key(attraction):
                continue
            neighbors.append(
                {
                    "name": other.name,
                    "distance_km": round(self.distance_km(attraction.location, other.location), 2),
                }
            )
        neighbors.sort(key=lambda item: item["distance_km"])
        return neighbors[:limit]

    @staticmethod
    def candidate_key(attraction: Attraction) -> str:
        """Build a stable unique key for an attraction candidate."""
        return attraction.poi_id or f"{attraction.name}|{attraction.address}"

    @classmethod
    def hotel_candidate_key(cls, hotel: Hotel) -> str:
        """Build a stable unique key for a hotel candidate."""
        return (
            f"{cls.normalize_place_name(hotel.name, keep_suffix=False)}|"
            f"{cls.normalize_place_name(hotel.address)}"
        )

    @staticmethod
    def estimate_hotel_cost(price_text: str) -> int:
        """Estimate hotel cost from a text price range."""
        values = [int(item) for item in re.findall(r"\d+", price_text or "")]
        if not values:
            return 0
        if len(values) >= 2:
            return int(sum(values[:2]) / 2)
        return values[0]

    @staticmethod
    def normalize_place_name(text: str, keep_suffix: bool = True) -> str:
        """Normalize place names to improve fuzzy matching stability."""
        normalized = re.sub(r"\*\*", "", text or "")
        normalized = normalized.replace("\\n", " ").strip()
        normalized = re.sub(r"^\d+[\.、]\s*", "", normalized)
        normalized = re.sub(r"^[\-•*]+\s*", "", normalized)
        if not keep_suffix:
            normalized = re.sub(r"\s*[（(].*?[）)]\s*", "", normalized)
        normalized = re.sub(r"\s+", "", normalized)
        return normalized.strip("：:，,。；;")

    @staticmethod
    def distance_km(left: Optional[Location], right: Optional[Location]) -> float:
        """Compute spherical distance between two locations."""
        if not left or not right:
            return float("inf")

        left_lat = math.radians(left.latitude)
        right_lat = math.radians(right.latitude)
        lat_delta = right_lat - left_lat
        lon_delta = math.radians(right.longitude - left.longitude)
        haversine = (
            math.sin(lat_delta / 2) ** 2
            + math.cos(left_lat) * math.cos(right_lat) * math.sin(lon_delta / 2) ** 2
        )
        return 6371 * 2 * math.asin(min(1.0, math.sqrt(haversine)))

    @staticmethod
    def build_area_tag(
        location: Optional[Location],
        reference_locations: List[Location],
    ) -> str:
        """Map a location to a coarse area tag relative to all candidates."""
        if not location or not reference_locations:
            return "中心片区"

        longitudes = [item.longitude for item in reference_locations]
        latitudes = [item.latitude for item in reference_locations]
        lon_span = max(longitudes) - min(longitudes)
        lat_span = max(latitudes) - min(latitudes)

        def axis_label(value: float, values: List[float], span: float, low: str, high: str) -> str:
            if span < 0.03:
                return "中"
            normalized = (value - min(values)) / span
            if normalized < 0.33:
                return low
            if normalized > 0.66:
                return high
            return "中"

        lon_label = axis_label(location.longitude, longitudes, lon_span, "西", "东")
        lat_label = axis_label(location.latitude, latitudes, lat_span, "南", "北")

        if lon_label == "中" and lat_label == "中":
            return "中心片区"
        if lon_label == "中":
            return f"{lat_label}部片区"
        if lat_label == "中":
            return f"{lon_label}部片区"
        return f"{lon_label}{lat_label}片区"

    def _check_cancellation(
        self,
        check_cancellation: Optional[CancellationChecker],
        cancellation_token: Optional[object],
        stage: str,
    ) -> None:
        if check_cancellation is not None:
            check_cancellation(cancellation_token, stage)

    def _is_cancellation_exception(self, exc: Exception) -> bool:
        return bool(
            self.cancellation_exception_cls
            and isinstance(exc, self.cancellation_exception_cls)
        )
