"""Trip planning post-processing and fallback services."""

import re
from typing import List, Optional, Set, Tuple

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
from .trip_planning_parsing_service import TripPlanningParsingService
from .weather_planning_service import (
    build_trip_dates,
    is_indoor_attraction,
    is_outdoor_attraction,
    parse_weather_response,
)


class TripPlanningPostProcessService:
    """Handle trip validation, spatial alignment, and fallback generation."""

    def post_validate_trip_plan(
        self,
        trip_plan: TripPlan,
        request: TripRequest,
        weather_info: List[WeatherInfo],
        candidate_attractions: Optional[List[Attraction]] = None,
        candidate_hotels: Optional[List[Hotel]] = None,
    ) -> TripPlan:
        """Validate and normalize the generated trip plan."""
        warnings: List[str] = []
        expected_dates = build_trip_dates(request.start_date, request.travel_days)
        candidate_attractions = candidate_attractions or []
        candidate_hotels = candidate_hotels or []

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
            day.meals = self._ensure_daily_meals(day.meals, index)

            if not day.attractions:
                warnings.append(f"{expected_date} 未生成景点安排,保留空景点列表供前端提示")

            normalized_days.append(day)

        for index, day in enumerate(normalized_days):
            previous_day = normalized_days[index - 1] if index > 0 else None
            next_day = normalized_days[index + 1] if index + 1 < len(normalized_days) else None
            warnings.extend(
                self._align_day_attractions_with_candidates(day, candidate_attractions)
            )
            start_reference = self._get_day_end_location(previous_day) if previous_day else None
            reordered_attractions, route_improved = self._reorder_attractions_for_flow(
                day.attractions,
                start_reference=start_reference,
            )
            day.attractions = reordered_attractions
            if route_improved:
                warnings.append(f"{day.date} 已按更顺路的空间动线重排景点顺序")

            day.hotel, hotel_warnings = self._ensure_hotel_alignment(
                request,
                day,
                index,
                next_day=next_day,
                candidate_hotels=candidate_hotels,
            )
            warnings.extend(hotel_warnings)
            day.description = self._align_day_description(
                day,
                weather_info[index],
                next_day=next_day,
            )
            warnings.extend(
                self._validate_generated_weather_alignment(
                    day,
                    weather_info[index],
                    candidate_attractions,
                )
            )
            warnings.extend(
                self._validate_spatial_day_plan(
                    day,
                    next_day=next_day,
                    previous_day=previous_day,
                )
            )

        if len(trip_plan.days) > request.travel_days:
            warnings.append("原始计划天数多于请求天数,已按请求天数截断")

        trip_plan.city = request.city
        trip_plan.start_date = request.start_date
        trip_plan.end_date = request.end_date
        trip_plan.days = normalized_days
        trip_plan.weather_info = weather_info
        trip_plan.warnings = warnings

        warnings.extend(self._validate_cross_day_spatial_flow(trip_plan.days))
        trip_plan.budget = self._merge_budget_with_fallback(
            trip_plan.budget,
            trip_plan.days,
        )
        trip_plan.overall_suggestions = self._merge_weather_suggestions(
            trip_plan.overall_suggestions,
            weather_info,
            trip_plan.days,
        )
        trip_plan.validation_status = "warning" if warnings else "validated"
        trip_plan.fallback_used = False
        trip_plan.warnings = warnings
        return trip_plan

    def create_fallback_plan(
        self,
        request: TripRequest,
        weather_info: Optional[List[WeatherInfo]] = None,
        reason: str = "",
    ) -> TripPlan:
        """Create a weather-aware fallback trip plan."""
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
                days,
            ),
            budget=self._recalculate_budget(days),
            validation_status="fallback",
            fallback_used=True,
            warnings=warnings,
        )

    def _create_structural_placeholder_day(
        self,
        request: TripRequest,
        date: str,
        day_index: int,
    ) -> DayPlan:
        return DayPlan(
            date=date,
            day_index=day_index,
            description=f"第{day_index + 1}天行程待确认",
            transportation=request.transportation,
            accommodation=request.accommodation,
            hotel=None,
            attractions=[],
            meals=self._ensure_daily_meals([], day_index),
        )

    def _validate_generated_weather_alignment(
        self,
        day: DayPlan,
        weather: WeatherInfo,
        candidate_attractions: Optional[List[Attraction]] = None,
    ) -> List[str]:
        warnings: List[str] = []
        outdoor_count = sum(1 for attraction in day.attractions if is_outdoor_attraction(attraction))
        indoor_count = sum(1 for attraction in day.attractions if is_indoor_attraction(attraction))
        attraction_count = len(day.attractions)
        candidate_keys = {
            TripPlanningParsingService.candidate_key(attraction)
            for attraction in (candidate_attractions or [])
        }

        if candidate_keys:
            unmatched = [
                attraction.name
                for attraction in day.attractions
                if TripPlanningParsingService.candidate_key(attraction) not in candidate_keys
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

    def _create_weather_safe_day(
        self,
        request: TripRequest,
        date: str,
        day_index: int,
        weather: WeatherInfo,
        base_day: Optional[DayPlan] = None,
    ) -> DayPlan:
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
        hotel = base_day.hotel if base_day and base_day.hotel else None
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

    def _align_day_description(
        self,
        day: DayPlan,
        weather: WeatherInfo,
        next_day: Optional[DayPlan] = None,
    ) -> str:
        attraction_names = [attraction.name for attraction in day.attractions[:3] if attraction.name]
        hotel_name = day.hotel.name if day.hotel and day.hotel.name else "住宿待确认"
        weather_hint = {
            "high": "受天气影响,以稳妥出行为主",
            "medium": "结合天气情况灵活安排行程",
            "low": "天气较稳定,可正常游览",
        }.get(weather.risk_level, "根据当日天气安排行程")

        if not attraction_names:
            return (
                f"第{day.day_index + 1}天{weather_hint}，建议以{hotel_name}周边休整和就近活动为主，"
                f"减少额外跨区移动。"
            )

        route_logic = "同片区顺路串联" if len(attraction_names) > 1 else "围绕核心片区轻量游览"
        joined_names = "、".join(attraction_names)
        hotel_logic = f"住宿安排在{hotel_name}，方便结束最后一个景点后就近入住"
        if not day.hotel:
            hotel_logic = "当晚住宿待确认，建议优先选择当天收尾景点附近且便于次日上午衔接的真实酒店"
        elif next_day and next_day.attractions:
            hotel_logic = (
                f"住宿安排在{hotel_name}，既便于当天收尾后休息，"
                f"也方便次日上午顺接{next_day.attractions[0].name}"
            )
        return (
            f"第{day.day_index + 1}天{weather_hint}，按{route_logic}游览{joined_names}；"
            f"{hotel_logic}。"
        )

    def _match_candidate_attraction(
        self,
        attraction: Attraction,
        candidate_attractions: List[Attraction],
    ) -> Optional[Attraction]:
        direct_key = TripPlanningParsingService.candidate_key(attraction)
        normalized_name = TripPlanningParsingService.normalize_place_name(attraction.name, keep_suffix=False)
        normalized_address = TripPlanningParsingService.normalize_place_name(attraction.address)

        exact_name_matches: List[Attraction] = []
        loose_matches: List[Attraction] = []
        for candidate in candidate_attractions:
            if TripPlanningParsingService.candidate_key(candidate) == direct_key:
                return candidate

            candidate_name = TripPlanningParsingService.normalize_place_name(candidate.name, keep_suffix=False)
            if normalized_name and candidate_name == normalized_name:
                exact_name_matches.append(candidate)
                continue

            if normalized_name and (
                normalized_name in candidate_name or candidate_name in normalized_name
            ):
                loose_matches.append(candidate)

        for matched_group in (exact_name_matches, loose_matches):
            if len(matched_group) == 1:
                return matched_group[0]
            if len(matched_group) > 1 and normalized_address:
                for candidate in matched_group:
                    candidate_address = TripPlanningParsingService.normalize_place_name(candidate.address)
                    if candidate_address and (
                        candidate_address in normalized_address
                        or normalized_address in candidate_address
                    ):
                        return candidate

        if exact_name_matches:
            return exact_name_matches[0]
        if loose_matches:
            return loose_matches[0]
        return None

    def _match_candidate_hotel(
        self,
        hotel: Hotel,
        candidate_hotels: List[Hotel],
    ) -> Optional[Hotel]:
        if not candidate_hotels:
            return None

        direct_key = TripPlanningParsingService.hotel_candidate_key(hotel)
        normalized_name = TripPlanningParsingService.normalize_place_name(hotel.name, keep_suffix=False)
        normalized_address = TripPlanningParsingService.normalize_place_name(hotel.address)
        exact_name_matches: List[Hotel] = []
        loose_matches: List[Hotel] = []

        for candidate in candidate_hotels:
            if TripPlanningParsingService.hotel_candidate_key(candidate) == direct_key:
                return candidate

            candidate_name = TripPlanningParsingService.normalize_place_name(candidate.name, keep_suffix=False)
            if normalized_name and candidate_name == normalized_name:
                exact_name_matches.append(candidate)
                continue

            if normalized_name and (
                normalized_name in candidate_name or candidate_name in normalized_name
            ):
                loose_matches.append(candidate)

        for matched_group in (exact_name_matches, loose_matches):
            if len(matched_group) == 1:
                return matched_group[0]
            if len(matched_group) > 1 and normalized_address:
                for candidate in matched_group:
                    candidate_address = TripPlanningParsingService.normalize_place_name(candidate.address)
                    if candidate_address and (
                        candidate_address in normalized_address
                        or normalized_address in candidate_address
                    ):
                        return candidate

        if exact_name_matches:
            return exact_name_matches[0]
        if loose_matches:
            return loose_matches[0]
        return None

    def _select_best_candidate_hotel(
        self,
        request: TripRequest,
        day_attractions: List[Attraction],
        next_day_attractions: Optional[List[Attraction]],
        candidate_hotels: List[Hotel],
    ) -> Optional[Hotel]:
        if not candidate_hotels:
            return None

        anchor = self._build_hotel_anchor(
            day_attractions,
            next_day_attractions or [],
            0,
        )
        preferred_text = TripPlanningParsingService.normalize_place_name(request.accommodation)
        ranked = sorted(
            candidate_hotels,
            key=lambda hotel: (
                0 if preferred_text and preferred_text in TripPlanningParsingService.normalize_place_name(hotel.type) else 1,
                TripPlanningParsingService.distance_km(hotel.location, anchor) if hotel.location else float("inf"),
                -(TripPlanningParsingService.safe_float(hotel.rating) or 0.0),
                hotel.estimated_cost or float("inf"),
            ),
        )
        return ranked[0] if ranked else None

    def _align_day_attractions_with_candidates(
        self,
        day: DayPlan,
        candidate_attractions: List[Attraction],
    ) -> List[str]:
        if not candidate_attractions or not day.attractions:
            return []

        warnings: List[str] = []
        aligned: List[Attraction] = []
        seen_keys: Set[str] = set()
        for attraction in day.attractions:
            original_key = TripPlanningParsingService.candidate_key(attraction)
            matched = self._match_candidate_attraction(attraction, candidate_attractions)
            if matched:
                attraction = matched.model_copy(
                    update={
                        "visit_duration": attraction.visit_duration or matched.visit_duration,
                        "ticket_price": attraction.ticket_price or matched.ticket_price,
                    }
                )
            aligned_key = TripPlanningParsingService.candidate_key(attraction)
            if aligned_key in seen_keys:
                continue
            seen_keys.add(aligned_key)
            aligned.append(attraction)
            if matched and original_key != TripPlanningParsingService.candidate_key(matched):
                warnings.append(f"{day.date} 已将景点对齐到真实候选 POI: {matched.name}")

        day.attractions = aligned
        return warnings

    def _ensure_daily_meals(self, meals: List[Meal], day_index: int) -> List[Meal]:
        meal_map = {meal.type: meal for meal in meals if meal.type}
        defaults = {
            "breakfast": Meal(type="breakfast", name=f"第{day_index + 1}天早餐", description="酒店附近早餐", estimated_cost=25),
            "lunch": Meal(type="lunch", name=f"第{day_index + 1}天午餐", description="景点周边简餐", estimated_cost=45),
            "dinner": Meal(type="dinner", name=f"第{day_index + 1}天晚餐", description="当地特色晚餐", estimated_cost=70),
        }
        return [meal_map.get(meal_type, default_meal) for meal_type, default_meal in defaults.items()]

    @staticmethod
    def _safe_transportation(preferred: str, risk_level: str) -> str:
        if risk_level == "high":
            return "公共交通/打车优先,减少步行和跨区换乘"
        if risk_level == "medium":
            return f"{preferred}为主,尽量选择地铁或短距离接驳"
        return preferred

    def _recalculate_budget(self, days: List[DayPlan]) -> Budget:
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
        days: Optional[List[DayPlan]] = None,
    ) -> str:
        base_text = re.sub(r"\*\*", "", (original_text or "").replace("\\n", "\n")).strip()
        lines: List[str] = []

        if base_text:
            for segment in re.split(r"\n+|(?<=[。；！？])", base_text):
                cleaned = segment.strip(" \n\t-•")
                if cleaned:
                    lines.append(cleaned)

        if weather_info:
            high_risk_days = [item.date for item in weather_info if item.risk_level == "high"]
            medium_risk_days = [item.date for item in weather_info if item.risk_level == "medium"]
            if high_risk_days:
                lines.append(f"高风险天气日: {', '.join(high_risk_days)}，优先室内与就近动线。")
            elif medium_risk_days:
                lines.append(f"中风险天气日: {', '.join(medium_risk_days)}，注意预留机动并减少跨区移动。")

        spatial_lines = self._build_spatial_summary(days or [])
        for line in spatial_lines:
            if line not in lines:
                lines.append(line)

        return "\n".join(lines).strip()

    @staticmethod
    def _distance_km(
        left: Optional[Location],
        right: Optional[Location],
    ) -> float:
        return TripPlanningParsingService.distance_km(left, right)

    @staticmethod
    def _centroid_location(attractions: List[Attraction]) -> Optional[Location]:
        locations = [attraction.location for attraction in attractions if attraction.location]
        if not locations:
            return None
        return Location(
            longitude=sum(item.longitude for item in locations) / len(locations),
            latitude=sum(item.latitude for item in locations) / len(locations),
        )

    def _build_hotel_anchor(
        self,
        day_attractions: List[Attraction],
        next_day_attractions: List[Attraction],
        day_index: int = 0,
    ) -> Location:
        current_end = day_attractions[-1].location if day_attractions else None
        next_start = next_day_attractions[0].location if next_day_attractions else None
        if current_end and next_start:
            return Location(
                longitude=current_end.longitude * 0.55 + next_start.longitude * 0.45,
                latitude=current_end.latitude * 0.55 + next_start.latitude * 0.45,
            )
        if current_end:
            return current_end
        if next_start:
            return next_start
        return Location(longitude=116.35 + day_index * 0.01, latitude=39.90 + day_index * 0.01)

    def _build_hotel_distance_text(
        self,
        day_attractions: List[Attraction],
        next_day_attractions: List[Attraction],
        hotel_location: Location,
    ) -> str:
        current_end = day_attractions[-1].location if day_attractions else None
        next_start = next_day_attractions[0].location if next_day_attractions else None
        current_distance = self._distance_km(hotel_location, current_end)
        next_distance = self._distance_km(hotel_location, next_start)

        if current_end and next_start:
            return (
                f"距当日晚间景点约{current_distance:.1f}公里,"
                f"距次日上午景点约{next_distance:.1f}公里"
            )
        if current_end:
            return f"距当日晚间景点约{current_distance:.1f}公里"
        if next_start:
            return f"距次日上午景点约{next_distance:.1f}公里"
        return "围绕行程动线中段选址"

    @staticmethod
    def _get_day_start_location(day: Optional[DayPlan]) -> Optional[Location]:
        if not day:
            return None
        if day.attractions:
            return day.attractions[0].location
        if day.hotel and day.hotel.location:
            return day.hotel.location
        return None

    @staticmethod
    def _get_day_end_location(day: Optional[DayPlan]) -> Optional[Location]:
        if not day:
            return None
        if day.attractions:
            return day.attractions[-1].location
        if day.hotel and day.hotel.location:
            return day.hotel.location
        return None

    def _path_distance_km(
        self,
        attractions: List[Attraction],
        start_reference: Optional[Location] = None,
    ) -> float:
        if not attractions:
            return 0.0

        total = 0.0
        previous = start_reference
        for attraction in attractions:
            if previous:
                total += self._distance_km(previous, attraction.location)
            previous = attraction.location
        return total

    def _reorder_attractions_for_flow(
        self,
        attractions: List[Attraction],
        start_reference: Optional[Location] = None,
    ) -> Tuple[List[Attraction], bool]:
        if len(attractions) <= 2:
            return attractions, False

        current_distance = self._path_distance_km(attractions, start_reference)
        best_order = attractions
        best_distance = current_distance

        for candidate_start in attractions:
            remaining = [
                attraction
                for attraction in attractions
                if TripPlanningParsingService.candidate_key(attraction)
                != TripPlanningParsingService.candidate_key(candidate_start)
            ]
            path = [candidate_start]
            while remaining:
                last_location = path[-1].location
                next_attraction = min(
                    remaining,
                    key=lambda item: self._distance_km(last_location, item.location),
                )
                path.append(next_attraction)
                remaining = [
                    attraction
                    for attraction in remaining
                    if TripPlanningParsingService.candidate_key(attraction)
                    != TripPlanningParsingService.candidate_key(next_attraction)
                ]

            distance = self._path_distance_km(path, start_reference)
            if distance < best_distance:
                best_order = path
                best_distance = distance

        improved = current_distance > 0 and best_distance <= current_distance * 0.85
        return (best_order if improved else attractions), improved

    def _ensure_hotel_alignment(
        self,
        request: TripRequest,
        day: DayPlan,
        _day_index: int,
        next_day: Optional[DayPlan] = None,
        candidate_hotels: Optional[List[Hotel]] = None,
    ) -> Tuple[Optional[Hotel], List[str]]:
        del _day_index
        warnings: List[str] = []
        candidate_hotels = candidate_hotels or []
        selected_candidate = self._select_best_candidate_hotel(
            request,
            day.attractions,
            next_day.attractions if next_day else None,
            candidate_hotels,
        )

        if not day.hotel:
            if selected_candidate:
                selected_candidate.distance = self._build_hotel_distance_text(
                    day.attractions,
                    next_day.attractions if next_day else [],
                    selected_candidate.location,
                )
                warnings.append(f"{day.date} 未生成酒店,已回填为真实候选酒店 {selected_candidate.name}")
                return selected_candidate, warnings
            warnings.append(f"{day.date} 未生成可核验的真实酒店,保留为空避免展示虚构酒店")
            return None, warnings

        hotel = day.hotel
        matched_hotel = self._match_candidate_hotel(hotel, candidate_hotels) if candidate_hotels else None
        if matched_hotel:
            hotel = matched_hotel.model_copy(
                update={
                    "estimated_cost": hotel.estimated_cost or matched_hotel.estimated_cost,
                    "price_range": hotel.price_range or matched_hotel.price_range,
                    "rating": hotel.rating or matched_hotel.rating,
                    "type": hotel.type or matched_hotel.type,
                    "distance": hotel.distance or matched_hotel.distance,
                }
            )
        elif candidate_hotels:
            if selected_candidate:
                warnings.append(f"{day.date} 原酒店不在真实候选中,已替换为真实候选酒店 {selected_candidate.name}")
                hotel = selected_candidate
            else:
                warnings.append(f"{day.date} 原酒店不在真实候选中,且无可用真实酒店候选")
                return None, warnings

        if not hotel.location:
            hotel.type = hotel.type or request.accommodation
            hotel.estimated_cost = hotel.estimated_cost or self._estimate_hotel_cost_with_request(
                hotel,
                request,
            )
            if candidate_hotels:
                warnings.append(f"{day.date} 酒店缺少有效坐标且无法与真实候选对齐")
            return hotel, warnings

        current_end = self._get_day_end_location(day)
        next_start = self._get_day_start_location(next_day)
        current_distance = self._distance_km(hotel.location, current_end)
        next_distance = self._distance_km(hotel.location, next_start)
        if current_end and next_start and current_distance > 8 and next_distance > 8:
            if selected_candidate and (
                TripPlanningParsingService.hotel_candidate_key(selected_candidate)
                != TripPlanningParsingService.hotel_candidate_key(hotel)
            ):
                selected_candidate.distance = self._build_hotel_distance_text(
                    day.attractions,
                    next_day.attractions if next_day else [],
                    selected_candidate.location,
                )
                warnings.append(f"{day.date} 酒店与今明两天主要景点脱节,已替换为真实候选酒店 {selected_candidate.name}")
                return selected_candidate, warnings
            warnings.append(f"{day.date} 酒店与今明两天主要景点脱节,但未改写为虚构酒店")
            return hotel, warnings
        if current_end and not next_start and current_distance > 8:
            if selected_candidate and (
                TripPlanningParsingService.hotel_candidate_key(selected_candidate)
                != TripPlanningParsingService.hotel_candidate_key(hotel)
            ):
                selected_candidate.distance = self._build_hotel_distance_text(
                    day.attractions,
                    next_day.attractions if next_day else [],
                    selected_candidate.location,
                )
                warnings.append(f"{day.date} 酒店距离当日收尾景点过远,已替换为真实候选酒店 {selected_candidate.name}")
                return selected_candidate, warnings
            warnings.append(f"{day.date} 酒店距离当日收尾景点过远,但未改写为虚构酒店")
            return hotel, warnings

        hotel.distance = self._build_hotel_distance_text(
            day.attractions,
            next_day.attractions if next_day else [],
            hotel.location,
        )
        hotel.estimated_cost = hotel.estimated_cost or self._estimate_hotel_cost_with_request(
            hotel,
            request,
        )
        return hotel, warnings

    def _merge_budget_with_fallback(
        self,
        existing_budget: Optional[Budget],
        days: List[DayPlan],
    ) -> Budget:
        recalculated = self._recalculate_budget(days)
        if not existing_budget:
            return recalculated

        total_attractions = existing_budget.total_attractions or recalculated.total_attractions
        total_hotels = existing_budget.total_hotels or recalculated.total_hotels
        total_meals = existing_budget.total_meals or recalculated.total_meals
        total_transportation = (
            existing_budget.total_transportation or recalculated.total_transportation
        )
        total = existing_budget.total or (
            total_attractions + total_hotels + total_meals + total_transportation
        )
        return Budget(
            total_attractions=total_attractions,
            total_hotels=total_hotels,
            total_meals=total_meals,
            total_transportation=total_transportation,
            total=total,
        )

    def _estimate_hotel_cost_with_request(
        self,
        hotel: Hotel,
        request: TripRequest,
    ) -> int:
        hotel_type = hotel.type or request.accommodation
        rating = TripPlanningParsingService.safe_float(hotel.rating)
        return TripPlanningParsingService.estimate_hotel_cost_with_fallback(
            price_text=hotel.price_range,
            hotel_type=hotel_type,
            rating=rating,
        )

    def _validate_spatial_day_plan(
        self,
        day: DayPlan,
        next_day: Optional[DayPlan] = None,
        previous_day: Optional[DayPlan] = None,
    ) -> List[str]:
        warnings: List[str] = []
        if len(day.attractions) >= 3:
            direct_distance = self._distance_km(day.attractions[0].location, day.attractions[-1].location)
            path_distance = self._path_distance_km(day.attractions)
            if direct_distance < 4 and path_distance > direct_distance * 2.2:
                warnings.append(f"{day.date} 单日路线存在明显折返风险")

        if previous_day and previous_day.attractions and day.attractions:
            handoff_distance = self._distance_km(
                previous_day.attractions[-1].location,
                day.attractions[0].location,
            )
            if handoff_distance > 12:
                warnings.append(f"{day.date} 与前一日首尾衔接较弱,存在跨区跳转风险")

        if day.hotel and day.hotel.location:
            today_end = self._get_day_end_location(day)
            tomorrow_start = self._get_day_start_location(next_day)
            hotel_to_today = self._distance_km(day.hotel.location, today_end)
            hotel_to_tomorrow = self._distance_km(day.hotel.location, tomorrow_start)
            if today_end and tomorrow_start and hotel_to_today > 8 and hotel_to_tomorrow > 8:
                warnings.append(f"{day.date} 酒店未与今明两天景点形成有效衔接")

        return warnings

    def _validate_cross_day_spatial_flow(self, days: List[DayPlan]) -> List[str]:
        warnings: List[str] = []
        day_focus_locations = [self._centroid_location(day.attractions) for day in days]
        for index in range(len(day_focus_locations) - 2):
            first = day_focus_locations[index]
            middle = day_focus_locations[index + 1]
            last = day_focus_locations[index + 2]
            if not first or not middle or not last:
                continue
            first_to_middle = self._distance_km(first, middle)
            middle_to_last = self._distance_km(middle, last)
            first_to_last = self._distance_km(first, last)
            if first_to_middle > 10 and middle_to_last > 10 and first_to_last < 6:
                warnings.append(
                    f"{days[index].date} 至 {days[index + 2].date} 存在类似北边-南边-北边的跨日往返"
                )
        return warnings

    def _build_spatial_summary(self, days: List[DayPlan]) -> List[str]:
        summaries: List[str] = []
        all_locations = [
            attraction.location
            for day in days
            for attraction in day.attractions
            if attraction.location
        ]
        for index, day in enumerate(days):
            if not day.attractions:
                continue
            focus = self._centroid_location(day.attractions)
            area_tag = TripPlanningParsingService.build_area_tag(focus, all_locations)
            attraction_names = "、".join(attraction.name for attraction in day.attractions[:3])
            summaries.append(
                f"第{index + 1}天以{area_tag}为主,按顺路动线串联{attraction_names}。"
            )
            if day.hotel and index + 1 < len(days) and days[index + 1].attractions:
                summaries.append(
                    f"第{index + 1}晚住宿兼顾{day.attractions[-1].name}与次日上午{days[index + 1].attractions[0].name}。"
                )
                break
        return summaries[:2]
