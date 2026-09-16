"""消息渲染的测试：段落顺序、缺失降级、HTML 转义。"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import render  # noqa: E402
from calendar_cn import Almanac  # noqa: E402
from weather import Weather  # noqa: E402
from zodiac import ZodiacFortune  # noqa: E402


def make_data(**overrides) -> render.BriefData:
    base = dict(
        date=dt.date(2026, 10, 1),
        city="上海",
        weather=Weather(city="上海", text="多云", temp_min="22", temp_max="29", wind="东南风3级", extras=["紫外线中等"], source="和风天气"),
        almanac=Almanac(lunar_text="八月廿一", jieqi_text="秋分后第8天", yi=["出行", "会友"], ji=["动土"], chong="冲兔"),
        zodiac=ZodiacFortune(sign_cn="天蝎座", summary="适合处理旧事。", stars="★★★★☆"),
        holiday_line="国庆节假期中 · 距元旦还有 92 天",
        warnings=[],
    )
    base.update(overrides)
    return render.BriefData(**base)


class TextRenderTests(unittest.TestCase):
    def test_五段齐全(self):
        text = render.render_text(make_data())
        self.assertEqual(
            text,
            "\n".join(
                [
                    "🌤 10月1日 周四 · 上海",
                    "天气　多云 22~29℃ ｜ 东南风3级 ｜ 紫外线中等",
                    "农历　八月廿一 · 秋分后第8天",
                    "黄历　宜 出行、会友 · 忌 动土 · 冲兔",
                    "星座　天蝎座 ★★★★☆ 适合处理旧事。",
                    "假期　国庆节假期中 · 距元旦还有 92 天",
                ]
            ),
        )

    def test_天气缺失时显示降级文案(self):
        text = render.render_text(make_data(weather=None))
        self.assertIn("天气　数据暂不可用", text)

    def test_星座缺失时整段不出现(self):
        text = render.render_text(make_data(zodiac=None))
        self.assertNotIn("星座", text)

    def test_黄历为空时整段不出现(self):
        text = render.render_text(make_data(almanac=Almanac()))
        self.assertNotIn("农历", text)
        self.assertNotIn("黄历", text)

    def test_提示行出现在末尾(self):
        text = render.render_text(make_data(warnings=["天气来自备用源 wttr.in", "星座运势暂时取不到，已省略"]))
        self.assertTrue(text.endswith("提示　天气来自备用源 wttr.in；星座运势暂时取不到，已省略"))

    def test_标题(self):
        self.assertEqual(render.build_title(make_data()), "10月1日早报 · 上海")

    def test_周三与周日的中文星期(self):
        self.assertIn("9月16日 周三", render.render_text(make_data(date=dt.date(2026, 9, 16))))
        self.assertIn("9月20日 周日", render.render_text(make_data(date=dt.date(2026, 9, 20))))


class HtmlRenderTests(unittest.TestCase):
    def test_包含标题与换行标签(self):
        html = render.render_html(make_data())
        self.assertIn("10月1日 周四 · 上海", html)
        self.assertTrue(html.startswith("<div"))
        self.assertTrue(html.rstrip().endswith("</div>"))
        self.assertIn("天气", html)
        self.assertIn("假期", html)

    def test_特殊字符被转义(self):
        html = render.render_html(make_data(warnings=["接口返回 <script>alert(1)</script>"]))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
