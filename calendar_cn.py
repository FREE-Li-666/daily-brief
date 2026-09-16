"""中国节假日与黄历：节假日走公开数据集并落盘缓存，黄历用 lunar_python 本地计算。"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
from dataclasses import dataclass, field

import net

HOLIDAY_URL_TEMPLATE = "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json"
CACHE_DIR = pathlib.Path(__file__).resolve().parent / "data" / "holidays"
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

WORKDAY = "workday"
WEEKEND = "weekend"
HOLIDAY = "holiday"
MAKEUP = "makeup"


@dataclass
class DayStatus:
    kind: str
    label: str
    holiday_name: str = ""


@dataclass
class Almanac:
    lunar_text: str = ""
    jieqi_text: str = ""
    yi: list[str] = field(default_factory=list)
    ji: list[str] = field(default_factory=list)
    chong: str = ""

    def lunar_line(self) -> str:
        return " · ".join(part for part in (self.lunar_text, self.jieqi_text) if part)

    def almanac_line(self) -> str:
        parts = []
        if self.yi:
            parts.append(f"宜 {'、'.join(self.yi)}")
        if self.ji:
            parts.append(f"忌 {'、'.join(self.ji)}")
        if self.chong:
            parts.append(self.chong)
        return " · ".join(parts)


def parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_holiday_payload(payload) -> dict:
    """把 holiday-cn 的 JSON 转成 {日期: {name, isOffDay}}，格式不对则返回空字典。"""
    if not isinstance(payload, dict):
        return {}
    days = payload.get("days")
    if not isinstance(days, list):
        return {}
    parsed = {}
    for item in days:
        if not isinstance(item, dict):
            continue
        date_str = str(item.get("date") or "")
        if not parse_date(date_str):
            continue
        parsed[date_str] = {
            "name": str(item.get("name") or "假期"),
            "isOffDay": bool(item.get("isOffDay")),
        }
    return parsed


def _fetch_remote(year: int, timeout: float):
    return net.http_get_json(HOLIDAY_URL_TEMPLATE.format(year=year), timeout=timeout)


def _read_cache(cache_file: pathlib.Path) -> dict:
    try:
        with cache_file.open("r", encoding="utf-8") as handle:
            return parse_holiday_payload(json.load(handle))
    except Exception:
        return {}


def _write_cache(cache_file: pathlib.Path, payload) -> None:
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with cache_file.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except Exception:
        pass


def load_holiday_days(
    year: int,
    *,
    use_network: bool = True,
    cache_dir: pathlib.Path = CACHE_DIR,
    timeout: float = 8.0,
    fetcher=None,
) -> dict:
    """取全年节假日与调休安排：优先联网更新并写缓存，失败时退回本地缓存。"""
    cache_file = pathlib.Path(cache_dir) / f"{year}.json"
    cached = _read_cache(cache_file)
    if use_network:
        try:
            payload = (fetcher or _fetch_remote)(year, timeout)
            days = parse_holiday_payload(payload)
            if days:
                _write_cache(cache_file, payload)
                return days
        except Exception:
            pass
    return cached


def describe_day(target: dt.date, days: dict) -> DayStatus:
    info = days.get(target.isoformat())
    if info:
        name = info.get("name") or "假期"
        if info.get("isOffDay"):
            return DayStatus(HOLIDAY, name, name)
        return DayStatus(MAKEUP, f"调休上班（{name}）")
    if target.weekday() >= 5:
        return DayStatus(WEEKEND, "周末")
    return DayStatus(WORKDAY, "工作日")


def next_holiday(target: dt.date, days: dict, *, skip_name: str = "") -> tuple[str, int] | None:
    """返回下一个假期的（名称，天数）；skip_name 用于跳过当前正在放的假。"""
    upcoming = []
    for date_str, info in days.items():
        if not info.get("isOffDay"):
            continue
        day = parse_date(date_str)
        if day is None or day <= target:
            continue
        name = info.get("name") or "假期"
        if skip_name and name == skip_name:
            continue
        upcoming.append((day, name))
    if not upcoming:
        return None
    upcoming.sort(key=lambda item: item[0])
    day, name = upcoming[0]
    return name, (day - target).days


def describe_holiday_line(target: dt.date, days: dict) -> str:
    status = describe_day(target, days)
    if status.kind == HOLIDAY:
        line = f"{status.holiday_name}假期中"
        upcoming = next_holiday(target, days, skip_name=status.holiday_name)
    else:
        line = status.label
        upcoming = next_holiday(target, days)
    if upcoming:
        line = f"{line} · 距{upcoming[0]}还有 {upcoming[1]} 天"
    return line


def _call(obj, name: str, default=None):
    method = getattr(obj, name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:
        return default


def _lunar_text(lunar) -> str:
    month = str(_call(lunar, "getMonthInChinese", "") or "")
    day = str(_call(lunar, "getDayInChinese", "") or "")
    if not month or not day:
        return ""
    if not month.endswith("月"):
        month = f"{month}月"
    return f"{month}{day}"


def _jieqi_text(lunar, target: dt.date) -> str:
    today = str(_call(lunar, "getJieQi", "") or "").strip()
    if today:
        return f"今日{today}"
    previous = _call(lunar, "getPrevJieQi")
    if previous is None:
        return ""
    name = str(_call(previous, "getName", "") or "").strip()
    ymd = str(_call(_call(previous, "getSolar"), "toYmd", "") or "").strip()
    start = parse_date(ymd)
    if not name or start is None:
        return ""
    offset = (target - start).days
    if offset <= 0:
        return ""
    return f"{name}后第{offset}天"


def _chong_text(lunar) -> str:
    """拼成老黄历常见写法，例如「冲猪（丁亥）煞东」。"""
    desc = str(_call(lunar, "getDayChongDesc", "") or "").strip()
    sha = str(_call(lunar, "getDaySha", "") or "").strip()
    animal = ""
    ganzhi = ""
    matched = re.match(r"^\((?P<ganzhi>[^)]*)\)(?P<animal>.+)$", desc)
    if matched:
        ganzhi = matched.group("ganzhi").strip()
        animal = matched.group("animal").strip()
    elif desc:
        animal = desc
    if not animal:
        animal = str(_call(lunar, "getDayChong", "") or "").strip()
    if not animal:
        return ""
    text = f"冲{animal}" + (f"（{ganzhi}）" if ganzhi else "")
    if sha:
        text += f"煞{sha}"
    return text


def get_almanac(target: dt.date) -> Almanac:
    """农历、节气、宜忌、冲煞，全部本地计算；lunar_python 缺失时返回空结果。"""
    try:
        from lunar_python import Solar

        lunar = Solar.fromYmd(target.year, target.month, target.day).getLunar()
    except Exception:
        return Almanac()

    almanac = Almanac()
    almanac.lunar_text = _lunar_text(lunar)
    almanac.jieqi_text = _jieqi_text(lunar, target)
    almanac.yi = [str(item) for item in (_call(lunar, "getDayYi", []) or [])][:4]
    almanac.ji = [str(item) for item in (_call(lunar, "getDayJi", []) or [])][:3]
    almanac.chong = _chong_text(lunar)
    return almanac
