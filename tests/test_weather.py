"""天气解析与降级链的测试。"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import net  # noqa: E402
import weather  # noqa: E402

TARGET = dt.date(2026, 9, 16)

QWEATHER_GEO = {"code": "200", "location": [{"id": "101020100", "name": "上海"}]}
QWEATHER_FORECAST = {
    "code": "200",
    "daily": [
        {
            "fxDate": "2026-09-16",
            "tempMin": "22",
            "tempMax": "29",
            "textDay": "多云",
            "windDirDay": "东南风",
            "windScaleDay": "3",
        }
    ],
}
QWEATHER_INDICES = {
    "code": "200",
    "daily": [
        {"date": "2026-09-16", "type": "3", "name": "穿衣指数", "category": "炎热"},
        {"date": "2026-09-16", "type": "5", "name": "紫外线指数", "category": "中等"},
    ],
}
WTTR_PAYLOAD = {
    "current_condition": [
        {
            "lang_zh": [{"value": "Cloudy "}],
            "lang_zh-cn": [{"value": "多云"}],
            "weatherDesc": [{"value": "Cloudy"}],
            "winddir16Point": "SE",
            "windspeedKmph": "12",
        }
    ],
    "weather": [{"mintempC": "22", "maxtempC": "29", "hourly": [{}] * 4 + [{"uvIndex": "7"}]}],
}
WTTR_ENGLISH_ONLY = {
    "current_condition": [{"lang_zh": [{"value": "Smoky haze"}], "weatherDesc": [{"value": "Smoky haze"}]}],
    "weather": [{"mintempC": "1", "maxtempC": "2", "hourly": [{}] * 4 + [{"uvIndex": "1"}]}],
}


class ParseTests(unittest.TestCase):
    def test_和风天气解析(self):
        with mock.patch.object(net, "http_get_json", side_effect=[QWEATHER_GEO, QWEATHER_FORECAST, QWEATHER_INDICES]):
            result = weather.fetch_qweather("上海", TARGET, "key", "example.re.qweatherapi.com")
        self.assertEqual(result.source, weather.PRIMARY_SOURCE)
        self.assertEqual(result.text, "多云")
        self.assertEqual(result.wind, "东南风3级")
        self.assertEqual(result.extras, ["炎热", "紫外线中等"])
        self.assertEqual(result.line(), "多云 22~29℃ ｜ 东南风3级 ｜ 炎热 ｜ 紫外线中等")

    def test_和风天气返回错误码时抛错(self):
        with mock.patch.object(net, "http_get_json", return_value={"code": "401"}):
            with self.assertRaises(net.HttpError):
                weather.fetch_qweather("上海", TARGET, "bad-key", "example.re.qweatherapi.com")

    def test_wttr解析出中文描述与风力(self):
        with mock.patch.object(net, "http_get_json", return_value=WTTR_PAYLOAD):
            result = weather.fetch_wttr("上海", TARGET)
        self.assertEqual(result.text, "多云")
        self.assertEqual(result.wind, "东南风12km/h")
        self.assertEqual(result.extras, ["紫外线强"])

    def test_wttr只有英文时翻译成中文(self):
        with mock.patch.object(net, "http_get_json", return_value=WTTR_ENGLISH_ONLY):
            result = weather.fetch_wttr("上海", TARGET)
        self.assertEqual(result.text, "烟霾")
        self.assertEqual(result.extras, ["紫外线弱"])

    def test_生活指数失败不影响主体天气(self):
        with mock.patch.object(net, "http_get_json", side_effect=[QWEATHER_GEO, QWEATHER_FORECAST, RuntimeError("指数接口挂了")]):
            result = weather.fetch_qweather("上海", TARGET, "key", "host")
        self.assertEqual(result.text, "多云")
        self.assertEqual(result.extras, [])


class ChainTests(unittest.TestCase):
    def test_和风天气可用时用它(self):
        calls = []

        def qweather(city, target, api_key, host, timeout):
            calls.append("qweather")
            return weather.Weather(city=city, text="多云", source=weather.PRIMARY_SOURCE)

        def wttr(city, target, timeout):
            calls.append("wttr")
            return weather.Weather(city=city, text="备用", source="wttr.in")

        result = weather.get_weather("上海", TARGET, api_key="key", qweather_fetcher=qweather, wttr_fetcher=wttr)
        self.assertEqual(calls, ["qweather"])
        self.assertIsNotNone(result.weather)
        self.assertEqual(result.weather.source, weather.PRIMARY_SOURCE)

    def test_和风天气挂掉时降级到wttr(self):
        def qweather(city, target, api_key, host, timeout):
            raise net.HttpError("和风 500")

        def wttr(city, target, timeout):
            return weather.Weather(city=city, text="多云", source="wttr.in")

        result = weather.get_weather("上海", TARGET, api_key="key", qweather_fetcher=qweather, wttr_fetcher=wttr)
        self.assertEqual(result.weather.source, "wttr.in")
        self.assertTrue(result.errors)

    def test_全部失败时返回空结果并记录原因(self):
        def boom(*args, **kwargs):
            raise net.HttpError("挂了")

        result = weather.get_weather(
            "上海",
            TARGET,
            api_key="key",
            qweather_fetcher=boom,
            wttr_fetcher=boom,
            openmeteo_fetcher=boom,
        )
        self.assertIsNone(result.weather)
        self.assertEqual(len(result.errors), 3)

    def test_没有key时跳过和风天气(self):
        calls = []

        def wttr(city, target, timeout):
            calls.append("wttr")
            return weather.Weather(city=city, text="多云", source="wttr.in")

        weather.get_weather("上海", TARGET, wttr_fetcher=wttr)
        self.assertEqual(calls, ["wttr"])

    def test_离线模式不抓取(self):
        calls = []

        def wttr(city, target, timeout):
            calls.append("wttr")
            return weather.Weather(city=city)

        result = weather.get_weather("上海", TARGET, use_network=False, wttr_fetcher=wttr)
        self.assertIsNone(result.weather)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
