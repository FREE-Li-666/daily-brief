"""把各段数据拼成一条手机上好读的中文早报（纯文本 + HTML 两版）。"""

from __future__ import annotations

import datetime as dt
import html
from dataclasses import dataclass, field

from advice import Advice
from calendar_cn import WEEKDAY_CN, Almanac
from weather import Weather
from zodiac import ZodiacFortune

SEPARATOR = "　"


@dataclass
class BriefData:
    date: dt.date
    city: str
    weather: Weather | None = None
    almanac: Almanac | None = None
    zodiac: ZodiacFortune | None = None
    holiday_line: str = ""
    advice: Advice | None = None
    warnings: list[str] = field(default_factory=list)

    def heading(self) -> str:
        weekday = WEEKDAY_CN[self.date.weekday()]
        return f"🌤 {self.date.month}月{self.date.day}日 {weekday} · {self.city}"

    def lines(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        if self.weather is not None:
            rows.append(("天气", self.weather.line() or "数据暂不可用"))
        else:
            rows.append(("天气", "数据暂不可用"))
        if self.almanac is not None:
            lunar_line = self.almanac.lunar_line()
            if lunar_line:
                rows.append(("农历", lunar_line))
            almanac_line = self.almanac.almanac_line()
            if almanac_line:
                rows.append(("黄历", almanac_line))
        if self.zodiac is not None:
            rows.append(("星座", self.zodiac.line()))
        if self.holiday_line:
            rows.append(("假期", self.holiday_line))
        if self.advice is not None and self.advice.line():
            rows.append(("建议", self.advice.line()))
        return rows


def build_title(data: BriefData) -> str:
    return f"{data.date.month}月{data.date.day}日早报 · {data.city}"


def render_text(data: BriefData) -> str:
    lines = [data.heading()]
    lines.extend(f"{label}{SEPARATOR}{content}" for label, content in data.lines())
    if data.warnings:
        lines.append("提示　" + "；".join(data.warnings))
    return "\n".join(lines)


def render_html(data: BriefData) -> str:
    rows = []
    for label, content in data.lines():
        rows.append(
            '<div style="margin:2px 0">'
            f'<span style="color:#888">{html.escape(label)}{SEPARATOR}</span>'
            f"{html.escape(content)}</div>"
        )
    if data.warnings:
        rows.append(
            '<div style="margin-top:8px;color:#999;font-size:13px">'
            f"⚠ {html.escape('；'.join(data.warnings))}</div>"
        )
    return (
        '<div style="font-size:15px;line-height:1.7">'
        f'<div style="font-size:16px;font-weight:600;margin-bottom:6px">{html.escape(data.heading())}</div>'
        + "".join(rows)
        + "</div>"
    )
