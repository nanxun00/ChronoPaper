"""天气查询原生 Tool（Open-Meteo，无需 API Key）。"""
from __future__ import annotations

import requests

from src.utils.logging_config import setup_logger

logger = setup_logger("weather-tool")

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → 简短中文描述
_WMO_ZH = {
    0: "晴",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "小阵雨",
    81: "阵雨",
    82: "大阵雨",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


def _weather_text(code: int | None) -> str:
    if code is None:
        return "未知"
    return _WMO_ZH.get(int(code), f"天气代码 {code}")


def get_weather(city: str) -> dict:
    name = (city or "").strip()
    if not name:
        return {"ok": False, "error": "城市名称不能为空"}

    try:
        geo_resp = requests.get(
            _GEO_URL,
            params={"name": name, "count": 1, "language": "zh"},
            timeout=12,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except Exception as exc:
        logger.warning("geocoding failed city=%s err=%s", name, exc)
        return {"ok": False, "error": f"城市定位失败: {exc}"}

    results = geo_data.get("results") or []
    if not results:
        return {"ok": False, "error": f"未找到城市: {name}"}

    place = results[0]
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        return {"ok": False, "error": f"城市坐标无效: {name}"}

    try:
        forecast_resp = requests.get(
            _FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=12,
        )
        forecast_resp.raise_for_status()
        forecast = forecast_resp.json()
    except Exception as exc:
        logger.warning("forecast failed city=%s err=%s", name, exc)
        return {"ok": False, "error": f"天气查询失败: {exc}"}

    current = forecast.get("current") or {}
    code = current.get("weather_code")
    return {
        "ok": True,
        "city": place.get("name") or name,
        "country": place.get("country") or "",
        "admin1": place.get("admin1") or "",
        "latitude": lat,
        "longitude": lon,
        "temperature_c": current.get("temperature_2m"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "weather": _weather_text(code),
        "observed_at": current.get("time"),
        "timezone": forecast.get("timezone") or "",
    }
