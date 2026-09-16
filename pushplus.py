"""PushPlus 发送：发送失败必须抛错，让 GitHub Actions 任务变红并给你发提醒。"""

from __future__ import annotations

import net

PUSHPLUS_URL = "https://www.pushplus.plus/send"


class PushError(RuntimeError):
    """推送失败。"""


def send(
    token: str,
    title: str,
    content: str,
    *,
    topic: str = "",
    template: str = "html",
    timeout: float = 10.0,
    url: str = PUSHPLUS_URL,
    poster=None,
) -> dict:
    if not token:
        raise PushError("缺少 PUSHPLUS_TOKEN")
    payload = {"token": token, "title": title, "content": content, "template": template}
    if topic:
        payload["topic"] = topic
    try:
        response = (poster or net.http_post_json)(url, payload, timeout=timeout, retries=1)
    except net.HttpError as error:
        raise PushError(str(error)) from error
    except Exception as error:  # noqa: BLE001 - 统一成 PushError
        raise PushError(f"请求 PushPlus 失败：{error}") from error
    if not isinstance(response, dict):
        raise PushError(f"PushPlus 返回格式异常：{response!r}")
    code = response.get("code")
    if str(code) != "200":
        raise PushError(f"PushPlus 返回异常 code={code} msg={response.get('msg')}")
    return response
