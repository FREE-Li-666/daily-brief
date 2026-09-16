"""星座运势解析、降级与生日换算的测试。"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import net  # noqa: E402
import zodiac  # noqa: E402

GOOD_PAYLOAD = {
    "success": True,
    "data": {
        "title": "天蝎座",
        "short": "适合处理旧事，别急着表态。",
        "luckynumber": "7",
        "luckycolor": "深蓝",
        "index": {"love": "3", "work": "4", "money": "4"},
    },
}

TIANAPI_PAYLOAD = {
    "code": 200,
    "msg": "success",
    "result": {
        "list": [
            {
                "astro": "天蝎座",
                "content": "今天适合整理旧资料，别急着做决定。",
                "luckynumber": "9",
                "luckycolor": "酒红",
            }
        ]
    },
}


class NormalizeTests(unittest.TestCase):
    def test_中文星座(self):
        self.assertEqual(zodiac.normalize_sign("天蝎座"), ("天蝎座", "scorpio"))

    def test_英文键(self):
        self.assertEqual(zodiac.normalize_sign("scorpio"), ("天蝎座", "scorpio"))

    def test_省略座字(self):
        self.assertEqual(zodiac.normalize_sign("天蝎"), ("天蝎座", "scorpio"))

    def test_无法识别(self):
        self.assertEqual(zodiac.normalize_sign("随便写的"), (None, None))
        self.assertEqual(zodiac.normalize_sign(""), (None, None))


class BirthdayTests(unittest.TestCase):
    def test_边界与跨年(self):
        self.assertEqual(zodiac.sign_from_birthday(10, 23), "天秤座")
        self.assertEqual(zodiac.sign_from_birthday(10, 24), "天蝎座")
        self.assertEqual(zodiac.sign_from_birthday(1, 19), "摩羯座")
        self.assertEqual(zodiac.sign_from_birthday(1, 20), "水瓶座")
        self.assertEqual(zodiac.sign_from_birthday(12, 25), "摩羯座")
        self.assertIsNone(zodiac.sign_from_birthday(13, 1))


class FetchTests(unittest.TestCase):
    def test_解析成功(self):
        with mock.patch.object(net, "http_get_json", return_value=GOOD_PAYLOAD):
            fortune = zodiac.fetch_fortune("天蝎座")
        self.assertIsNotNone(fortune)
        self.assertEqual(fortune.sign_cn, "天蝎座")
        self.assertTrue(fortune.summary.startswith("适合处理旧事"))
        self.assertIn("幸运数字7", fortune.lucky)
        self.assertEqual(fortune.stars, "★★★★☆")
        self.assertEqual(fortune.line(), "天蝎座 ★★★★☆ 适合处理旧事，别急着表态。（幸运色深蓝 · 幸运数字7）")

    def test_接口异常时返回空(self):
        with mock.patch.object(net, "http_get_json", side_effect=net.HttpError("超时")):
            self.assertIsNone(zodiac.fetch_fortune("天蝎座"))

    def test_接口报失败时返回空(self):
        with mock.patch.object(net, "http_get_json", return_value={"success": False, "msg": "次数超限"}):
            self.assertIsNone(zodiac.fetch_fortune("天蝎座"))

    def test_响应里没有文案时返回空(self):
        with mock.patch.object(net, "http_get_json", return_value={"success": True, "data": {"title": "天蝎座"}}):
            self.assertIsNone(zodiac.fetch_fortune("天蝎座"))

    def test_星座无法识别时不发请求(self):
        calls = []

        def fetcher(*args, **kwargs):
            calls.append(args)
            return GOOD_PAYLOAD

        self.assertIsNone(zodiac.fetch_fortune("不是星座", fetcher=fetcher))
        self.assertEqual(calls, [])

    def test_超长文案被截断(self):
        payload = {"success": True, "data": {"short": "今" * 200}}
        fortune = zodiac.parse_fortune(payload, "天蝎座")
        self.assertLessEqual(len(fortune.summary), 61)
        self.assertTrue(fortune.summary.endswith("…"))

    def test_天行数据格式可解析(self):
        fortune = zodiac.parse_fortune(TIANAPI_PAYLOAD, "天蝎座", source="天行数据")
        self.assertEqual(fortune.summary, "今天适合整理旧资料，别急着做决定。")
        self.assertIn("幸运数字9", fortune.lucky)
        self.assertEqual(fortune.source, "天行数据")

    def test_天行数据无效key时返回空(self):
        self.assertIsNone(zodiac.parse_fortune({"code": 230, "msg": "API密钥无效"}, "天蝎座"))

    def test_候选顺序为自定义到天行到免key(self):
        urls = zodiac.candidate_urls("scorpio", "天蝎座", url_template="https://x/{key}", api_key="k")
        self.assertEqual([name for name, _ in urls], ["自定义接口", "天行数据", "vvhan"])
        self.assertEqual(urls[0][1], "https://x/scorpio")
        self.assertIn("astro=%E5%A4%A9%E8%9D%8E%E5%BA%A7", urls[1][1])
        self.assertEqual(len(zodiac.candidate_urls("scorpio", "天蝎座")), 1)

    def test_配置了key时优先用天行数据(self):
        calls = []

        def fetcher(url, **kwargs):
            calls.append(url)
            return TIANAPI_PAYLOAD

        fortune = zodiac.fetch_fortune("天蝎座", api_key="abc", fetcher=fetcher)
        self.assertEqual(fortune.source, "天行数据")
        self.assertTrue(calls[0].startswith("https://apis.tianapi.com/star/index"))

    def test_天行数据失败时降级到免key接口(self):
        calls = []

        def fetcher(url, **kwargs):
            calls.append(url)
            if "tianapi" in url:
                raise net.HttpError("密钥无效")
            return GOOD_PAYLOAD

        fortune = zodiac.fetch_fortune("天蝎座", api_key="abc", fetcher=fetcher)
        self.assertEqual(fortune.source, "vvhan")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
