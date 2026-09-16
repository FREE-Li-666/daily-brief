#!/usr/bin/env python3
"""每日早报：抓数据 → 拼消息 → 推送到微信。

用法：
    python3 main.py                 # 正式发送
    python3 main.py --dry-run       # 只打印，不推送（数据照常抓取）
    python3 main.py --dry-run --offline --date 2026-10-01   # 完全离线，用于测试
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import calendar_cn
import pushplus
import render
import weather
import zodiac

TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_CITY = "合肥"
DEFAULT_SIGN = "白羊座"
DEFAULT_TIMEOUT = 8.0


@dataclass
class Config:
    city: str
    sign: str
    pushplus_token: str
    pushplus_topic: str
    qweather_key: str
    qweather_host: str
    tianapi_key: str
    horoscope_url: str
    timeout: float


def parse_iso_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"日期格式应为 YYYY-MM-DD，收到：{value}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="每日早报：天气 + 黄历星座 + 节假日，推送到微信")
    parser.add_argument("--dry-run", action="store_true", help="只打印消息，不推送到微信（数据仍然实时抓取）")
    parser.add_argument("--offline", action="store_true", help="完全不联网：不抓天气、不抓星座、节假日只用本地缓存")
    parser.add_argument("--date", type=parse_iso_date, help="指定日期，格式 YYYY-MM-DD，默认今天（北京时间）")
    parser.add_argument("--city", help=f"城市名，默认取环境变量 CITY，再默认 {DEFAULT_CITY}")
    parser.add_argument("--sign", help=f"星座，默认取环境变量 ZODIAC，再默认 {DEFAULT_SIGN}")
    parser.add_argument("--no-zodiac", action="store_true", help="不发送星座那一段")
    parser.add_argument("--verbose", action="store_true", help="打印各数据源的失败原因")
    return parser


def load_config(args: argparse.Namespace) -> Config:
    timeout_raw = os.environ.get("HTTP_TIMEOUT", "")
    try:
        timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return Config(
        city=(args.city or os.environ.get("CITY") or DEFAULT_CITY).strip(),
        sign=(args.sign or os.environ.get("ZODIAC") or DEFAULT_SIGN).strip(),
        pushplus_token=(os.environ.get("PUSHPLUS_TOKEN") or "").strip(),
        pushplus_topic=(os.environ.get("PUSHPLUS_TOPIC") or "").strip(),
        qweather_key=(os.environ.get("QWEATHER_KEY") or "").strip(),
        qweather_host=(os.environ.get("QWEATHER_HOST") or weather.QWEATHER_DEFAULT_HOST).strip(),
        tianapi_key=(os.environ.get("TIANAPI_KEY") or "").strip(),
        horoscope_url=(os.environ.get("HOROSCOPE_URL") or "").strip(),
        timeout=timeout,
    )


def collect(args: argparse.Namespace, config: Config, target: dt.date) -> render.BriefData:
    warnings: list[str] = []

    holidays = calendar_cn.load_holiday_days(target.year, use_network=not args.offline, timeout=config.timeout)
    if not holidays:
        warnings.append("节假日数据不可用，今天的假期状态按周末粗略判断")

    weather_result = weather.get_weather(
        config.city,
        target,
        api_key=config.qweather_key,
        api_host=config.qweather_host,
        timeout=config.timeout,
        use_network=not args.offline,
    )
    if weather_result.weather is None:
        warnings.append("天气暂时取不到")
    elif weather_result.weather.source and weather_result.weather.source != weather.PRIMARY_SOURCE:
        warnings.append(f"天气来自备用源 {weather_result.weather.source}")
    if args.verbose:
        for error in weather_result.errors:
            print(f"[天气] {error}", file=sys.stderr)

    fortune = None
    if not args.no_zodiac and not args.offline:
        fortune = zodiac.fetch_fortune(
            config.sign,
            timeout=min(5.0, config.timeout),
            url_template=config.horoscope_url,
            api_key=config.tianapi_key,
        )
        if fortune is None:
            warnings.append("星座运势暂时取不到，已省略")

    return render.BriefData(
        date=target,
        city=config.city,
        weather=weather_result.weather,
        almanac=calendar_cn.get_almanac(target),
        zodiac=fortune,
        holiday_line=calendar_cn.describe_holiday_line(target, holidays),
        warnings=warnings,
    )


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args)
    target = args.date or dt.datetime.now(TZ).date()
    data = collect(args, config, target)

    if args.dry_run:
        print(render.render_text(data))
        return 0

    if not config.pushplus_token:
        print("缺少 PUSHPLUS_TOKEN，无法发送；加 --dry-run 可以只看内容。", file=sys.stderr)
        return 2

    try:
        pushplus.send(
            config.pushplus_token,
            render.build_title(data),
            render.render_html(data),
            topic=config.pushplus_topic,
            timeout=config.timeout,
        )
    except pushplus.PushError as error:
        print(f"发送失败：{error}", file=sys.stderr)
        return 1

    print(f"已发送：{render.build_title(data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
