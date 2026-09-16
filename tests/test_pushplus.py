"""PushPlus 发送链的测试：成功、业务码异常、缺少 token。"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import net  # noqa: E402
import pushplus  # noqa: E402


class SendTests(unittest.TestCase):
    def test_发送成功(self):
        captured = {}

        def poster(url, payload, **kwargs):
            captured["url"] = url
            captured["payload"] = payload
            return {"code": 200, "msg": "请求成功", "data": "12345"}

        response = pushplus.send("token-abc", "标题", "<div>正文</div>", topic="话题", poster=poster)
        self.assertEqual(response["code"], 200)
        self.assertEqual(captured["payload"]["token"], "token-abc")
        self.assertEqual(captured["payload"]["template"], "html")
        self.assertEqual(captured["payload"]["topic"], "话题")

    def test_业务码异常时抛错(self):
        def poster(url, payload, **kwargs):
            return {"code": 500, "msg": "用户不存在"}

        with self.assertRaises(pushplus.PushError) as ctx:
            pushplus.send("token-abc", "标题", "正文", poster=poster)
        self.assertIn("500", str(ctx.exception))

    def test_网络异常时抛错(self):
        def poster(url, payload, **kwargs):
            raise net.HttpError("连接超时")

        with self.assertRaises(pushplus.PushError):
            pushplus.send("token-abc", "标题", "正文", poster=poster)

    def test_缺少token时抛错(self):
        with self.assertRaises(pushplus.PushError):
            pushplus.send("", "标题", "正文", poster=lambda *a, **k: {"code": 200})

    def test_不传话题时不带topic字段(self):
        captured = {}

        def poster(url, payload, **kwargs):
            captured.update(payload)
            return {"code": "200"}

        pushplus.send("token-abc", "标题", "正文", poster=poster)
        self.assertNotIn("topic", captured)


if __name__ == "__main__":
    unittest.main()
