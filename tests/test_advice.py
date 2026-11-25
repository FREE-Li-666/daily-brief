"""AI 建议的解析、长度限制与异常降级的测试（全部离线）。"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import advice  # noqa: E402
import net  # noqa: E402

SAMPLE_FACTS = "天气：多云 22~29℃ ｜ 东南风3级\n假期：工作日 · 距中秋节还有 9 天"
GOOD_TEXT = "今天多云，22~29℃，早晚偏凉，出门带件外套，白天注意防晒。"

GOOD_PAYLOAD = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": GOOD_TEXT}, "finish_reason": "stop"}
    ],
}


class FactsTests(unittest.TestCase):
    def test_事实清单跳过空段(self):
        rows = [("天气", "多云 22~29℃"), ("星座", ""), ("假期", "工作日")]
        self.assertEqual(advice.build_facts(rows), "天气：多云 22~29℃\n假期：工作日")


class ParseTests(unittest.TestCase):
    def test_解析正文(self):
        self.assertEqual(advice.parse_advice(GOOD_PAYLOAD), GOOD_TEXT)

    def test_去掉markdown标记与换行(self):
        payload = {"choices": [{"message": {"content": "## 今天多云，记得带伞。\n\n**早晚偏凉**"}}]}
        self.assertEqual(advice.parse_advice(payload), "今天多云，记得带伞。 早晚偏凉")

    def test_结构不对时返回空串(self):
        self.assertEqual(advice.parse_advice(None), "")
        self.assertEqual(advice.parse_advice({"error": {"message": "invalid api key"}}), "")
        self.assertEqual(advice.parse_advice({"choices": []}), "")
        self.assertEqual(advice.parse_advice({"choices": [{"message": {"content": None}}]}), "")


class FetchTests(unittest.TestCase):
    def test_正常返回(self):
        calls = []

        def poster(url, payload, **kwargs):
            calls.append((url, payload, kwargs))
            return GOOD_PAYLOAD

        result = advice.fetch_advice(SAMPLE_FACTS, api_key="sk-test", poster=poster)

        self.assertIsNotNone(result.advice)
        self.assertEqual(result.advice.text, GOOD_TEXT)
        self.assertEqual(result.advice.source, "DeepSeek")
        self.assertEqual(result.errors, [])
        url, payload, kwargs = calls[0]
        self.assertEqual(url, advice.DEEPSEEK_URL)
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["content"], SAMPLE_FACTS)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-test")

    def test_请求超时(self):
        with mock.patch.object(net, "http_post_json", side_effect=net.HttpError("请求超时")):
            result = advice.fetch_advice(SAMPLE_FACTS, api_key="sk-test")
        self.assertIsNone(result.advice)
        self.assertTrue(result.errors)
        self.assertIn("请求超时", result.errors[0])

    def test_接口返回非200(self):
        with mock.patch.object(net, "http_post_json", side_effect=net.HttpError("HTTP Error 401: Unauthorized")):
            result = advice.fetch_advice(SAMPLE_FACTS, api_key="sk-test")
        self.assertIsNone(result.advice)
        self.assertIn("401", result.errors[0])

    def test_返回错误体时省略(self):
        with mock.patch.object(net, "http_post_json", return_value={"error": {"message": "Insufficient Balance"}}):
            result = advice.fetch_advice(SAMPLE_FACTS, api_key="sk-test")
        self.assertIsNone(result.advice)
        self.assertTrue(result.errors)

    def test_返回内容为空(self):
        payload = {"choices": [{"message": {"content": "   "}}]}
        with mock.patch.object(net, "http_post_json", return_value=payload):
            result = advice.fetch_advice(SAMPLE_FACTS, api_key="sk-test")
        self.assertIsNone(result.advice)
        self.assertTrue(result.errors)

    def test_输出超长被省略(self):
        payload = {"choices": [{"message": {"content": "今" * 200}}]}
        with mock.patch.object(net, "http_post_json", return_value=payload):
            result = advice.fetch_advice(SAMPLE_FACTS, api_key="sk-test")
        self.assertIsNone(result.advice)
        self.assertIn("80", result.errors[0])

    def test_没有配置key时不发请求(self):
        def poster(*args, **kwargs):
            raise AssertionError("没有 key 时不应该发请求")

        result = advice.fetch_advice(SAMPLE_FACTS, api_key="", poster=poster)
        self.assertIsNone(result.advice)
        self.assertIn("DEEPSEEK_API_KEY", result.errors[0])

    def test_事实为空时不发请求(self):
        def poster(*args, **kwargs):
            raise AssertionError("没有事实时不应该发请求")

        result = advice.fetch_advice("   ", api_key="sk-test", poster=poster)
        self.assertIsNone(result.advice)
        self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main()
