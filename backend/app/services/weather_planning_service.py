"""天气规划辅助服务."""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..models.schemas import Attraction, WeatherInfo

INDOOR_KEYWORDS = (
    "博物馆", "美术馆", "科技馆", "纪念馆", "展览馆", "艺术馆", "图书馆",
    "书店", "商场", "剧院", "故居", "宫", "馆", "中心", "海洋馆", "水族馆",
    "天文馆", "温泉", "影院", "室内", "非遗馆"
)

OUTDOOR_KEYWORDS = (
    "公园", "广场", "步行街", "长城", "山", "湖", "海", "乐园", "动物园",
    "植物园", "湿地", "沙滩", "古镇", "街区", "森林", "漂流", "峡谷", "草原",
    "岛", "栈道", "露营", "夜市"
)

HIGH_RISK_WEATHER_KEYWORDS = (
    "暴雨", "大暴雨", "特大暴雨", "雷暴", "雷阵雨", "暴雪", "大雪",
    "冰雹", "台风", "龙卷风", "冻雨", "沙尘暴", "强对流"
)

MEDIUM_RISK_WEATHER_KEYWORDS = (
    "中雨", "小雨", "阵雨", "雨夹雪", "中雪", "雾", "霾", "扬沙",
    "浮尘", "大风", "阴"
)

LOW_RISK_WEATHER_KEYWORDS = ("晴", "少云", "多云")
ALL_WEATHER_KEYWORDS = tuple(
    dict.fromkeys(
        HIGH_RISK_WEATHER_KEYWORDS + MEDIUM_RISK_WEATHER_KEYWORDS + LOW_RISK_WEATHER_KEYWORDS
    )
)


def build_trip_dates(start_date: str, travel_days: int) -> List[str]:
    """根据开始日期和天数生成旅行日期序列."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        (start + timedelta(days=index)).strftime("%Y-%m-%d")
        for index in range(travel_days)
    ]


def parse_weather_response(raw_weather: str, start_date: str, travel_days: int) -> List[WeatherInfo]:
    """从天气工具原始输出中提取并归一化逐日天气."""
    parsed_entries = _parse_weather_entries(raw_weather)
    trip_dates = build_trip_dates(start_date, travel_days)
    normalized_entries: List[WeatherInfo] = []

    for index, trip_date in enumerate(trip_dates):
        source = parsed_entries[index] if index < len(parsed_entries) else parsed_entries[-1] if parsed_entries else {}
        normalized = WeatherInfo(
            date=trip_date,
            day_weather=str(source.get("day_weather", "")).strip(),
            night_weather=str(source.get("night_weather", "")).strip(),
            day_temp=_safe_temperature(source.get("day_temp")),
            night_temp=_safe_temperature(source.get("night_temp")),
            wind_direction=str(source.get("wind_direction", "")).strip(),
            wind_power=str(source.get("wind_power", "")).strip(),
        )
        normalized_entries.append(apply_weather_risk(normalized))

    return normalized_entries


def apply_weather_risk(weather: WeatherInfo) -> WeatherInfo:
    """根据天气文本和温度风力补充风险等级."""
    score = 0
    reasons: List[str] = []
    weather_text = f"{weather.day_weather} {weather.night_weather}".strip()

    if any(keyword in weather_text for keyword in HIGH_RISK_WEATHER_KEYWORDS):
        score += 85
        reasons.append("存在强降水或强对流天气")
    elif any(keyword in weather_text for keyword in MEDIUM_RISK_WEATHER_KEYWORDS):
        score += 45
        reasons.append("存在降水、低能见度或风沙风险")
    elif any(keyword in weather_text for keyword in LOW_RISK_WEATHER_KEYWORDS):
        score += 10

    high_temp = max(_safe_temperature(weather.day_temp), _safe_temperature(weather.night_temp))
    low_temp = min(_safe_temperature(weather.day_temp), _safe_temperature(weather.night_temp))
    if high_temp >= 35:
        score += 30
        reasons.append("白天气温偏高")
    if low_temp <= 0:
        score += 30
        reasons.append("夜间气温偏低")

    wind_level = _parse_wind_power(weather.wind_power)
    if wind_level >= 6:
        score += 35
        reasons.append("风力较强")
    elif wind_level >= 4:
        score += 20
        reasons.append("存在明显风力")

    if score >= 80:
        risk_level = "high"
        advice = "高风险天气,优先安排室内景点和就近餐饮,减少跨区移动与长时间步行。"
    elif score >= 40:
        risk_level = "medium"
        advice = "中风险天气,优先安排可快速避雨或避风景点,控制单日跨区数量。"
    else:
        risk_level = "low"
        advice = "低风险天气,可正常规划行程,关注早晚温差并预留机动时间。"

    if reasons:
        advice = f"{advice} 风险原因: {'; '.join(reasons)}。"

    weather.risk_level = risk_level
    weather.risk_score = min(score, 100)
    weather.planning_advice = advice
    return weather


def build_weather_constraint_text(weather_list: List[WeatherInfo]) -> str:
    """把天气风险转为给规划模型使用的约束文本."""
    constraint_lines = [
        "- 高风险天气日: 仅安排1-2个室内或半室内景点,避免公园、步行街、远距离换乘和长时间户外停留。",
        "- 中风险天气日: 优先安排室内景点或同一区域景点,减少跨区移动,预留机动时间。",
        "- 低风险天气日: 可正常安排,但仍需保证酒店、景点和餐饮动线紧凑。",
    ]

    for item in weather_list:
        label = {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(item.risk_level, "未知")
        weather_desc = item.day_weather or item.night_weather or "未知天气"
        temps = f"{_safe_temperature(item.day_temp)}/{_safe_temperature(item.night_temp)}"
        constraint_lines.append(
            f"- {item.date}: {label}, 天气={weather_desc}, 温度={temps}, 约束={item.planning_advice}"
        )

    return "\n".join(constraint_lines)


def is_outdoor_attraction(attraction: Attraction) -> bool:
    """判断景点是否更偏向户外."""
    text = " ".join(
        part for part in [
            attraction.name,
            attraction.category or "",
            attraction.description or "",
            attraction.address or "",
        ] if part
    )
    return any(keyword in text for keyword in OUTDOOR_KEYWORDS)


def is_indoor_attraction(attraction: Attraction) -> bool:
    """判断景点是否更偏向室内."""
    text = " ".join(
        part for part in [
            attraction.name,
            attraction.category or "",
            attraction.description or "",
            attraction.address or "",
        ] if part
    )
    return any(keyword in text for keyword in INDOOR_KEYWORDS)


def _parse_weather_entries(raw_weather: str) -> List[Dict[str, Any]]:
    """优先从 JSON 提取天气,失败时退回文本解析."""
    json_entries = _parse_weather_entries_from_json(raw_weather)
    if json_entries:
        return json_entries
    return _parse_weather_entries_from_text(raw_weather)


def _parse_weather_entries_from_json(raw_weather: str) -> List[Dict[str, Any]]:
    """尝试从 JSON 或 JSON 代码块中提取天气预报."""
    candidates = _collect_json_candidates(raw_weather)
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        extracted = _extract_weather_entries_from_structure(data)
        if extracted:
            return extracted
    return []


def _collect_json_candidates(text: str) -> List[str]:
    """收集文本里的 JSON 候选片段."""
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


def _extract_weather_entries_from_structure(data: Any) -> List[Dict[str, Any]]:
    """从常见天气接口结构中抽取天气列表."""
    if isinstance(data, list):
        entries = [_normalize_weather_entry(item) for item in data]
        return [entry for entry in entries if entry]

    if not isinstance(data, dict):
        return []

    if isinstance(data.get("casts"), list):
        entries = [_normalize_weather_entry(item) for item in data["casts"]]
        return [entry for entry in entries if entry]

    if isinstance(data.get("weather_info"), list):
        entries = [_normalize_weather_entry(item) for item in data["weather_info"]]
        return [entry for entry in entries if entry]

    if isinstance(data.get("forecasts"), list):
        for forecast in data["forecasts"]:
            extracted = _extract_weather_entries_from_structure(forecast)
            if extracted:
                return extracted

    for value in data.values():
        extracted = _extract_weather_entries_from_structure(value)
        if extracted:
            return extracted

    return []


def _normalize_weather_entry(item: Any) -> Dict[str, Any]:
    """把单个天气条目转为统一字段."""
    if not isinstance(item, dict):
        return {}

    day_weather = (
        item.get("dayweather")
        or item.get("day_weather")
        or item.get("weather")
        or item.get("textDay")
        or ""
    )
    night_weather = (
        item.get("nightweather")
        or item.get("night_weather")
        or item.get("textNight")
        or day_weather
    )
    day_temp = item.get("daytemp") or item.get("day_temp") or item.get("temp") or item.get("temp_max") or 0
    night_temp = item.get("nighttemp") or item.get("night_temp") or item.get("temp_min") or day_temp
    wind_direction = item.get("daywind") or item.get("wind_direction") or item.get("winddirection") or ""
    wind_power = item.get("daypower") or item.get("wind_power") or item.get("windpower") or ""
    date = item.get("date") or item.get("fxDate") or item.get("day") or ""

    if not any([day_weather, night_weather, day_temp, night_temp, wind_direction, wind_power]):
        return {}

    return {
        "date": str(date).strip(),
        "day_weather": str(day_weather).strip(),
        "night_weather": str(night_weather).strip(),
        "day_temp": day_temp,
        "night_temp": night_temp,
        "wind_direction": str(wind_direction).strip(),
        "wind_power": str(wind_power).strip(),
    }


def _parse_weather_entries_from_text(raw_weather: str) -> List[Dict[str, Any]]:
    """从非结构化文本中尽量提取逐日天气."""
    segmented_entries = _parse_weather_entries_from_segments(raw_weather)
    if segmented_entries:
        return segmented_entries

    entries: List[Dict[str, Any]] = []
    for line in raw_weather.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        date_match = re.search(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}", stripped)
        weather_keywords = _extract_weather_keywords(stripped)
        if not date_match and not weather_keywords:
            continue

        day_temp, night_temp = _extract_temperature_pair(stripped)
        wind_direction_match = re.search(r"(东北风|东南风|西北风|西南风|东风|西风|南风|北风)", stripped)
        wind_power_match = re.search(r"(\d+\s*-\s*\d+级|\d+级)", stripped)

        entries.append({
            "date": date_match.group(0) if date_match else "",
            "day_weather": weather_keywords[0] if weather_keywords else "",
            "night_weather": weather_keywords[1] if len(weather_keywords) > 1 else weather_keywords[0] if weather_keywords else "",
            "day_temp": day_temp,
            "night_temp": night_temp,
            "wind_direction": wind_direction_match.group(0) if wind_direction_match else "",
            "wind_power": wind_power_match.group(0) if wind_power_match else "",
        })

    return entries


def _parse_weather_entries_from_segments(raw_weather: str) -> List[Dict[str, Any]]:
    """按日期片段切分天气文本,避免整段文本被错误复用到多天."""
    normalized_text = raw_weather.replace("\\n", "\n")
    lines = [line.rstrip() for line in normalized_text.splitlines()]
    raw_segments: List[str] = []
    current_segment: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if _is_weather_segment_header(line):
            if current_segment:
                raw_segments.append("\n".join(current_segment))
            current_segment = [line]
            continue

        if current_segment:
            current_segment.append(line)

    if current_segment:
        raw_segments.append("\n".join(current_segment))

    if not raw_segments:
        return []

    segments: List[Dict[str, Any]] = []
    for raw_segment in raw_segments:
        segment = raw_segment.strip(" \n-•*")
        if not segment:
            continue

        date_match = re.search(
            r"\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日(?:（[^）]+）)?|\d{2}-\d{2}",
            segment,
        )
        weather_keywords = _extract_weather_keywords(segment)
        if not date_match and not weather_keywords:
            continue

        day_temp, night_temp = _extract_temperature_pair(segment)
        wind_direction_match = re.search(r"(东北风|东南风|西北风|西南风|东风|西风|南风|北风)", segment)
        wind_power_match = re.search(r"(\d+\s*-\s*\d+级|\d+级)", segment)

        day_weather, night_weather = _extract_day_night_weather(segment, weather_keywords)
        segments.append({
            "date": date_match.group(0) if date_match else "",
            "day_weather": day_weather,
            "night_weather": night_weather,
            "day_temp": day_temp,
            "night_temp": night_temp,
            "wind_direction": wind_direction_match.group(0) if wind_direction_match else "",
            "wind_power": wind_power_match.group(0) if wind_power_match else "",
        })

    return segments


def _is_weather_segment_header(text: str) -> bool:
    """判断一行是否为逐日天气条目的起始标题."""
    normalized = text.strip()
    if not normalized:
        return False

    if re.search(r"(今天|明天|后天).{0,12}\d{1,2}月\d{1,2}日", normalized):
        return True

    return bool(
        re.match(
            r"^(?:\d+\.\s*)?(?:\*{1,2})?\s*(?:\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日(?:（[^）]+）)?|\d{2}-\d{2})",
            normalized,
        )
    )


def _extract_weather_keywords(text: str) -> List[str]:
    """按文本出现顺序提取天气关键词."""
    pattern = "|".join(sorted((re.escape(keyword) for keyword in ALL_WEATHER_KEYWORDS), key=len, reverse=True))
    if not pattern:
        return []

    matched: List[str] = []
    for match in re.finditer(pattern, text):
        keyword = match.group(0)
        if keyword not in matched:
            matched.append(keyword)
    return matched[:2]


def _extract_day_night_weather(text: str, weather_keywords: List[str]) -> List[str]:
    """优先提取白天/夜间天气,没有显式标注时退回关键词顺序."""
    day_match = re.search(r"白天(?:天气)?[:：]?\s*([^\n\r，,；;。 ]+)", text)
    night_match = re.search(r"夜间(?:天气)?[:：]?\s*([^\n\r，,；;。 ]+)", text)

    day_weather = day_match.group(1).strip() if day_match else ""
    night_weather = night_match.group(1).strip() if night_match else ""

    if not day_weather and weather_keywords:
        day_weather = weather_keywords[0]
    if not night_weather:
        if len(weather_keywords) > 1:
            night_weather = weather_keywords[1]
        else:
            night_weather = day_weather

    return [day_weather, night_weather]


def _extract_temperature_pair(text: str) -> List[int]:
    """从文本中提取白天/夜间温度."""
    temp_range_match = re.search(
        r"(?:气温|温度)?\s*(-?\d+)\s*(?:°C|℃|°)?\s*(?:~|～|至|到)\s*(-?\d+)\s*(?:°C|℃|°)?",
        text,
        flags=re.IGNORECASE,
    )
    if temp_range_match:
        first_temp = _safe_temperature(temp_range_match.group(1))
        second_temp = _safe_temperature(temp_range_match.group(2))
        return [max(first_temp, second_temp), min(first_temp, second_temp)]

    explicit_day = re.search(r"(?:白天|最高|日间|day)\D*(-?\d+)", text, flags=re.IGNORECASE)
    explicit_night = re.search(r"(?:夜间|最低|晚间|night)\D*(-?\d+)", text, flags=re.IGNORECASE)
    if explicit_day or explicit_night:
        return [
            _safe_temperature(explicit_day.group(1) if explicit_day else 0),
            _safe_temperature(explicit_night.group(1) if explicit_night else 0),
        ]

    numbers = [
        int(match)
        for match in re.findall(r"(?<![\d-])(\d+)\s*(?:°C|℃|°)", text)
        if -50 <= int(match) <= 60
    ]
    if len(numbers) >= 2:
        return [max(numbers), min(numbers)]
    if len(numbers) == 1:
        return [numbers[0], numbers[0]]
    return [0, 0]


def _safe_temperature(value: Any) -> int:
    """把温度统一转为整数."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9-]", "", value)
        if cleaned and cleaned not in {"-", "--"}:
            try:
                return int(cleaned)
            except ValueError:
                return 0
    return 0


def _parse_wind_power(wind_power: str) -> int:
    """解析风力级别."""
    values = [int(item) for item in re.findall(r"\d+", wind_power or "")]
    if not values:
        return 0
    return max(values)
