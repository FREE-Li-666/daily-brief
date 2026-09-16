"""天气数据：和风天气为主，wttr.in 与 Open-Meteo 依次兜底。"""

from __future__ import annotations

import datetime as dt
import urllib.parse
from dataclasses import dataclass, field

import net

QWEATHER_DEFAULT_HOST = "devapi.qweather.com"
PRIMARY_SOURCE = "和风天气"

WIND_16_TO_CN = {
    "N": "北风",
    "NNE": "北东北风",
    "NE": "东北风",
    "ENE": "东东北风",
    "E": "东风",
    "ESE": "东东南风",
    "SE": "东南风",
    "SSE": "南东南风",
    "S": "南风",
    "SSW": "南西南风",
    "SW": "西南风",
    "WSW": "西西南风",
    "W": "西风",
    "WNW": "西西北风",
    "NW": "西北风",
    "NNW": "北西北风",
}

WMO_TEXT = {
    0: "晴",
    1: "晴间多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "冻雾",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "米雪",
    80: "阵雨",
    81: "强阵雨",
    82: "暴雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷阵雨",
    96: "雷阵雨伴冰雹",
    99: "强雷阵雨伴冰雹",
}

WTTR_EN_CN = {
    "sunny": "晴",
    "clear": "晴",
    "partly cloudy": "多云",
    "cloudy": "多云",
    "overcast": "阴",
    "mist": "薄雾",
    "fog": "雾",
    "freezing fog": "冻雾",
    "haze": "霾",
    "smoky haze": "烟霾",
    "light drizzle": "小毛毛雨",
    "drizzle": "毛毛雨",
    "patchy rain possible": "局部阵雨",
    "light rain": "小雨",
    "moderate rain": "中雨",
    "heavy rain": "大雨",
    "patchy light rain with thunder": "局部雷阵雨",
    "thundery outbreaks possible": "可能雷阵雨",
    "light rain shower": "小阵雨",
    "moderate or heavy rain shower": "强阵雨",
    "light snow": "小雪",
    "moderate snow": "中雪",
    "heavy snow": "大雪",
    "patchy snow possible": "局部降雪",
    "light snow showers": "阵雪",
    "blizzard": "暴风雪",
    "ice pellets": "冰粒",
}


@dataclass
class Weather:
    city: str
    text: str = ""
    temp_min: str = ""
    temp_max: str = ""
    wind: str = ""
    extras: list[str] = field(default_factory=list)
    source: str = ""

    def line(self) -> str:
        parts = []
        head = self.text
        if self.temp_min or self.temp_max:
            head = f"{head} {self.temp_min}~{self.temp_max}℃".strip()
        if head:
            parts.append(head)
        if self.wind:
            parts.append(self.wind)
        parts.extend(extra for extra in self.extras if extra)
        return " ｜ ".join(parts)


@dataclass
class WeatherResult:
    weather: Weather | None = None
    errors: list[str] = field(default_factory=list)


def _at(values, index: int, default=None):
    if isinstance(values, list) and 0 <= index < len(values):
        return values[index]
    return default


def _uv_text(index: int) -> str:
    if index <= 2:
        return "弱"
    if index <= 5:
        return "中等"
    if index <= 7:
        return "强"
    if index <= 10:
        return "很强"
    return "极强"


def _qweather_headers(api_key: str) -> dict:
    return {"X-QW-Api-Key": api_key}


def _qweather_lookup(city: str, api_key: str, host: str, timeout: float) -> tuple[str, str]:
    url = net.url_with_params(
        f"https://{host}/geo/v2/city/lookup",
        {"location": city, "number": 1, "lang": "zh"},
    )
    payload = net.http_get_json(url, headers=_qweather_headers(api_key), timeout=timeout)
    if str(payload.get("code")) != "200":
        raise net.HttpError(f"和风天气城市查询失败 code={payload.get('code')}")
    locations = payload.get("location") or []
    if not locations:
        raise net.HttpError(f"和风天气查不到城市：{city}")
    return str(locations[0].get("id", "")), str(locations[0].get("name") or city)


def _qweather_wind(daily: dict) -> str:
    direction = str(daily.get("windDirDay") or "").strip()
    scale = str(daily.get("windScaleDay") or "").strip()
    if direction and scale:
        return f"{direction}{scale}级"
    return direction


def _qweather_extras(location_id: str, api_key: str, host: str, target: dt.date, timeout: float) -> list[str]:
    url = net.url_with_params(
        f"https://{host}/v7/indices/1d",
        {"location": location_id, "type": "3,5", "lang": "zh"},
    )
    try:
        payload = net.http_get_json(url, headers=_qweather_headers(api_key), timeout=timeout, retries=0)
    except Exception:  # 生活指数拿不到不影响主体天气
        return []
    if str(payload.get("code")) != "200":
        return []
    prefix = {"3": "", "5": "紫外线"}
    extras = []
    for item in payload.get("daily") or []:
        item_date = str(item.get("date") or "")
        if item_date and item_date != target.isoformat():
            continue
        category = str(item.get("category") or "").strip()
        if not category:
            continue
        label = f"{prefix.get(str(item.get('type')), '')}{category}"
        if label not in extras:
            extras.append(label)
    return extras[:3]


def fetch_qweather(city: str, target: dt.date, api_key: str, host: str, timeout: float = 8.0) -> Weather:
    location_id, location_name = _qweather_lookup(city, api_key, host, timeout)
    url = net.url_with_params(f"https://{host}/v7/weather/3d", {"location": location_id, "lang": "zh"})
    payload = net.http_get_json(url, headers=_qweather_headers(api_key), timeout=timeout)
    if str(payload.get("code")) != "200":
        raise net.HttpError(f"和风天气预报失败 code={payload.get('code')}")
    daily_list = payload.get("daily") or []
    if not daily_list:
        raise net.HttpError("和风天气没有返回预报数据")
    picked = next((item for item in daily_list if item.get("fxDate") == target.isoformat()), daily_list[0])
    weather = Weather(
        city=location_name,
        text=str(picked.get("textDay") or picked.get("textNight") or ""),
        temp_min=str(picked.get("tempMin") or ""),
        temp_max=str(picked.get("tempMax") or ""),
        wind=_qweather_wind(picked),
        source=PRIMARY_SOURCE,
    )
    weather.extras = _qweather_extras(location_id, api_key, host, target, timeout)
    return weather


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _wttr_text(current: dict) -> str:
    """wttr.in 的 lang=zh 有时仍返回英文，所以优先挑含中文的那一条。"""
    candidates = []
    for key in ("lang_zh-cn", "lang_zh", "lang_xx"):
        for item in current.get(key) or []:
            value = str(item.get("value") or "").strip()
            if value:
                candidates.append(value)
    for desc in current.get("weatherDesc") or []:
        value = str(desc.get("value") or "").strip()
        if value:
            candidates.append(value)
    for value in candidates:
        if _has_cjk(value):
            return value
    for value in candidates:
        translated = WTTR_EN_CN.get(" ".join(value.lower().split()))
        if translated:
            return translated
    return candidates[0] if candidates else ""


def _wttr_wind(current: dict) -> str:
    direction = WIND_16_TO_CN.get(str(current.get("winddir16Point") or "").upper(), "")
    speed = str(current.get("windspeedKmph") or "").strip()
    if direction and speed:
        return f"{direction}{speed}km/h"
    return direction


def fetch_wttr(city: str, target: dt.date, timeout: float = 8.0) -> Weather:
    url = net.url_with_params(f"https://wttr.in/{urllib.parse.quote(city)}", {"format": "j1", "lang": "zh-cn"})
    payload = net.http_get_json(url, headers={"Accept-Language": "zh-CN,zh"}, timeout=timeout)
    conditions = payload.get("current_condition") or []
    if not conditions:
        raise net.HttpError("wttr.in 没有返回当前天气")
    current = conditions[0]
    days = payload.get("weather") or []
    today = days[0] if days else {}
    weather = Weather(
        city=city,
        text=_wttr_text(current),
        temp_min=str(today.get("mintempC") or ""),
        temp_max=str(today.get("maxtempC") or ""),
        wind=_wttr_wind(current),
        source="wttr.in",
    )
    hourly = today.get("hourly") or []
    raw_uv = str(_at(hourly, 4, {}).get("uvIndex", "") or "")
    if raw_uv.isdigit():
        weather.extras.append(f"紫外线{_uv_text(int(raw_uv))}")
    return weather


def fetch_openmeteo(city: str, target: dt.date, timeout: float = 8.0) -> Weather:
    geo_url = net.url_with_params(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": city, "count": 1, "language": "zh", "format": "json"},
    )
    geo = net.http_get_json(geo_url, timeout=timeout)
    results = geo.get("results") or []
    if not results:
        raise net.HttpError(f"Open-Meteo 查不到城市：{city}")
    place = results[0]
    forecast_url = net.url_with_params(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,uv_index_max,wind_speed_10m_max",
            "timezone": "Asia/Shanghai",
            "forecast_days": 3,
        },
    )
    payload = net.http_get_json(forecast_url, timeout=timeout)
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        raise net.HttpError("Open-Meteo 没有返回预报数据")
    index = dates.index(target.isoformat()) if target.isoformat() in dates else 0
    code = _at(daily.get("weather_code"), index)
    weather = Weather(
        city=str(place.get("name") or city),
        text=WMO_TEXT.get(code, ""),
        temp_min=str(_at(daily.get("temperature_2m_min"), index, "")).split(".")[0],
        temp_max=str(_at(daily.get("temperature_2m_max"), index, "")).split(".")[0],
        wind=_openmeteo_wind(_at(daily.get("wind_speed_10m_max"), index)),
        source="Open-Meteo",
    )
    uv = _at(daily.get("uv_index_max"), index)
    if isinstance(uv, (int, float)):
        weather.extras.append(f"紫外线{_uv_text(int(round(uv)))}")
    return weather


def _openmeteo_wind(speed) -> str:
    if not isinstance(speed, (int, float)):
        return ""
    return f"风速{int(round(speed))}km/h"


def get_weather(
    city: str,
    target: dt.date,
    *,
    api_key: str = "",
    api_host: str = QWEATHER_DEFAULT_HOST,
    timeout: float = 8.0,
    use_network: bool = True,
    qweather_fetcher=fetch_qweather,
    wttr_fetcher=fetch_wttr,
    openmeteo_fetcher=fetch_openmeteo,
) -> WeatherResult:
    """按 和风 → wttr.in → Open-Meteo 的顺序取天气，全部失败则返回空结果。"""
    result = WeatherResult()
    if not use_network:
        result.errors.append("离线模式：未抓取天气")
        return result

    chain = []
    if api_key:
        chain.append((PRIMARY_SOURCE, lambda: qweather_fetcher(city, target, api_key, api_host, timeout)))
    chain.append(("wttr.in", lambda: wttr_fetcher(city, target, timeout)))
    chain.append(("Open-Meteo", lambda: openmeteo_fetcher(city, target, timeout)))

    for name, call in chain:
        try:
            result.weather = call()
            return result
        except Exception as error:  # noqa: BLE001 - 任何异常都往下一档降级
            result.errors.append(f"{name}：{error}")
    return result
