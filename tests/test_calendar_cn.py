"""节假日判定、下个假期倒数、缓存回退与黄历本地计算的测试。"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import calendar_cn  # noqa: E402

SAMPLE_PAYLOAD = {
    "year": 2026,
    "days": [
        {"name": "中秋节", "date": "2026-09-25", "isOffDay": True},
        {"name": "国庆节", "date": "2026-10-01", "isOffDay": True},
        {"name": "国庆节", "date": "2026-10-02", "isOffDay": True},
        {"name": "国庆节", "date": "2026-10-10", "isOffDay": False},
        {"name": "元旦", "date": "2027-01-01", "isOffDay": True},
    ],
}


class DayStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.days = calendar_cn.parse_holiday_payload(SAMPLE_PAYLOAD)

    def test_普通工作日(self):
        status = calendar_cn.describe_day(dt.date(2026, 9, 16), self.days)
        self.assertEqual(status.kind, calendar_cn.WORKDAY)
        self.assertEqual(status.label, "工作日")

    def test_普通周末(self):
        status = calendar_cn.describe_day(dt.date(2026, 9, 19), self.days)
        self.assertEqual(status.kind, calendar_cn.WEEKEND)
        self.assertEqual(status.label, "周末")

    def test_法定节日(self):
        status = calendar_cn.describe_day(dt.date(2026, 10, 1), self.days)
        self.assertEqual(status.kind, calendar_cn.HOLIDAY)
        self.assertEqual(status.holiday_name, "国庆节")

    def test_调休上班的周六(self):
        status = calendar_cn.describe_day(dt.date(2026, 10, 10), self.days)
        self.assertEqual(status.kind, calendar_cn.MAKEUP)
        self.assertEqual(status.label, "调休上班（国庆节）")


class NextHolidayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.days = calendar_cn.parse_holiday_payload(SAMPLE_PAYLOAD)

    def test_倒数到最近假期(self):
        self.assertEqual(calendar_cn.next_holiday(dt.date(2026, 9, 16), self.days), ("中秋节", 9))

    def test_假期当天跳过当前假期(self):
        # 10 月 1 日当天应跳过国庆节整段，指向下一个假期
        self.assertEqual(calendar_cn.next_holiday(dt.date(2026, 10, 1), self.days, skip_name="国庆节"), ("元旦", 92))

    def test_没有后续假期时返回空(self):
        self.assertIsNone(calendar_cn.next_holiday(dt.date(2027, 1, 2), self.days))


class HolidayLineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.days = calendar_cn.parse_holiday_payload(SAMPLE_PAYLOAD)

    def test_工作日带倒数(self):
        line = calendar_cn.describe_holiday_line(dt.date(2026, 9, 16), self.days)
        self.assertEqual(line, "工作日 · 距中秋节还有 9 天")

    def test_假期中指向下一个假期(self):
        line = calendar_cn.describe_holiday_line(dt.date(2026, 10, 1), self.days)
        self.assertEqual(line, "国庆节假期中 · 距元旦还有 92 天")


class CacheTests(unittest.TestCase):
    def test_联网失败时回退本地缓存(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = pathlib.Path(tmp)
            (cache_dir / "2026.json").write_text(json.dumps(SAMPLE_PAYLOAD), encoding="utf-8")

            def boom(year, timeout):
                raise RuntimeError("网络断了")

            days = calendar_cn.load_holiday_days(2026, cache_dir=cache_dir, fetcher=boom)
            self.assertIn("2026-10-01", days)

    def test_联网成功时写入缓存(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = pathlib.Path(tmp)
            days = calendar_cn.load_holiday_days(2026, cache_dir=cache_dir, fetcher=lambda year, timeout: SAMPLE_PAYLOAD)
            self.assertEqual(days["2026-09-25"]["name"], "中秋节")
            self.assertTrue((cache_dir / "2026.json").exists())

    def test_无网络无缓存时返回空字典(self):
        with tempfile.TemporaryDirectory() as tmp:
            days = calendar_cn.load_holiday_days(
                2026,
                cache_dir=pathlib.Path(tmp),
                fetcher=lambda year, timeout: (_ for _ in ()).throw(RuntimeError("boom")),
            )
            self.assertEqual(days, {})

    def test_离线模式不联网(self):
        calls = []

        def fetcher(year, timeout):
            calls.append(year)
            return SAMPLE_PAYLOAD

        with tempfile.TemporaryDirectory() as tmp:
            days = calendar_cn.load_holiday_days(2026, use_network=False, cache_dir=pathlib.Path(tmp), fetcher=fetcher)
            self.assertEqual(days, {})
            self.assertEqual(calls, [])


class AlmanacTests(unittest.TestCase):
    def test_缺依赖时返回空结果(self):
        try:
            import lunar_python  # noqa: F401
        except ImportError:
            self.assertEqual(calendar_cn.get_almanac(dt.date(2026, 9, 16)), calendar_cn.Almanac())

    def test_农历与节气(self):
        try:
            import lunar_python  # noqa: F401
        except ImportError:
            self.skipTest("未安装 lunar_python")
        almanac = calendar_cn.get_almanac(dt.date(2026, 9, 16))
        self.assertTrue(almanac.lunar_text)
        self.assertIn("月", almanac.lunar_text)
        self.assertTrue(almanac.almanac_line())

    def test_国庆当天黄历可生成(self):
        try:
            import lunar_python  # noqa: F401
        except ImportError:
            self.skipTest("未安装 lunar_python")
        almanac = calendar_cn.get_almanac(dt.date(2026, 10, 1))
        self.assertTrue(almanac.lunar_text)
        self.assertTrue(almanac.chong.startswith("冲"))


if __name__ == "__main__":
    unittest.main()
