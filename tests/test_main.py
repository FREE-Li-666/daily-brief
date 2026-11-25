"""端到端的离线冒烟测试：不联网也能渲染出完整消息。"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import main  # noqa: E402


class RunTests(unittest.TestCase):
    def test_离线dry_run返回0并打印标题(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main.run(["--offline", "--dry-run", "--date", "2026-10-01", "--city", "上海"])
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn("10月1日 周四 · 上海", output)
        self.assertIn("天气　数据暂不可用", output)
        self.assertIn("假期　", output)

    def test_缺少token时返回2(self):
        buffer = io.StringIO()
        with mock.patch.dict("os.environ", {"PUSHPLUS_TOKEN": ""}, clear=False):
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                code = main.run(["--offline", "--date", "2026-10-01"])
        self.assertEqual(code, 2)
        self.assertIn("PUSHPLUS_TOKEN", buffer.getvalue())

    def test_推送失败时返回1(self):
        with mock.patch.dict("os.environ", {"PUSHPLUS_TOKEN": "token"}, clear=False):
            with mock.patch.object(main.pushplus, "send", side_effect=main.pushplus.PushError("boom")):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = main.run(["--offline", "--date", "2026-10-01"])
        self.assertEqual(code, 1)

    def test_推送成功时返回0(self):
        calls = []
        with mock.patch.dict("os.environ", {"PUSHPLUS_TOKEN": "token"}, clear=False):
            with mock.patch.object(main.pushplus, "send", side_effect=lambda *a, **k: calls.append(a) or {"code": 200}):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main.run(["--offline", "--date", "2026-10-01"])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertIn("<div", calls[0][2])

    def test_指定星座与城市生效(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main.run(["--offline", "--dry-run", "--date", "2026-10-01", "--city", "杭州"])
        self.assertIn("杭州", buffer.getvalue())

    def test_建议段接入dry_run输出(self):
        buffer = io.StringIO()
        with mock.patch.object(main.weather, "get_weather", return_value=main.weather.WeatherResult()):
            with mock.patch.object(main.calendar_cn, "load_holiday_days", return_value={}):
                with mock.patch.object(
                    main.advice,
                    "fetch_advice",
                    return_value=main.advice.AdviceResult(advice=main.advice.Advice(text="今天多云，出门带件外套。")),
                ):
                    with contextlib.redirect_stdout(buffer):
                        code = main.run(["--dry-run", "--no-zodiac", "--date", "2026-10-01"])
        self.assertEqual(code, 0)
        self.assertIn("建议　今天多云，出门带件外套。", buffer.getvalue())

    def test_加no_advice时不请求大模型(self):
        buffer = io.StringIO()
        with mock.patch.object(main.weather, "get_weather", return_value=main.weather.WeatherResult()):
            with mock.patch.object(main.calendar_cn, "load_holiday_days", return_value={}):
                with mock.patch.object(main.advice, "fetch_advice") as fetcher:
                    with contextlib.redirect_stdout(buffer):
                        code = main.run(["--dry-run", "--no-zodiac", "--no-advice", "--date", "2026-10-01"])
        self.assertEqual(code, 0)
        fetcher.assert_not_called()
        self.assertNotIn("建议", buffer.getvalue())

    def test_非法日期参数被拒绝(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                main.build_parser().parse_args(["--date", "2026/10/01"])


if __name__ == "__main__":
    unittest.main()
