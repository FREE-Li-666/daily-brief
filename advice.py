"""AI 建议：调用 DeepSeek 生成当天的穿衣与出行提醒，取不到就整段省略。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import net

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT = 20.0
MAX_LENGTH = 80
SOURCE = "DeepSeek"

SYSTEM_PROMPT = (
    "你是早报助手。只根据用户给出的当天信息，写一条不超过 80 字的穿衣与出行提醒。"
    "直接给出提醒正文，不要标题、不要编号、不要 markdown 标记。"
    "信息里没有提到的内容不要编造。"
)

_LEADING = re.compile(r"^(?:[>\-*#•]+\s*|\d+[.、)）]\s*)+")


@dataclass
class Advice:
    text: str = ""
    source: str = SOURCE

    def line(self) -> str:
        return self.text


@dataclass
class AdviceResult:
    advice: Advice | None = None
    errors: list[str] = field(default_factory=list)


def build_facts(rows: list[tuple[str, str]]) -> str:
    """把已经渲染好的早报各段拼成给模型的事实清单。"""
    return "\n".join(f"{label}：{content}" for label, content in rows if content)


def clean_text(text: str) -> str:
    """压掉换行、markdown 标记和开头的编号，只留一行纯文本。"""
    cleaned = " ".join(str(text or "").replace("**", "").replace("`", "").split())
    return _LEADING.sub("", cleaned).strip()


def parse_advice(payload) -> str:
    """从 Chat Completions 响应里取出建议正文，取不到返回空串。"""
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, str):
        return ""
    return clean_text(content)


def fetch_advice(
    facts: str,
    *,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT,
    url: str = DEEPSEEK_URL,
    poster=None,
) -> AdviceResult:
    """调用 DeepSeek 生成建议；任何异常都收敛成空结果，不影响其余内容。"""
    result = AdviceResult()
    if not api_key:
        result.errors.append("未配置 DEEPSEEK_API_KEY")
        return result
    if not str(facts or "").strip():
        result.errors.append("没有可用于生成建议的当天信息")
        return result

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": facts},
        ],
        "max_tokens": 300,
        "temperature": 0.7,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = (poster or net.http_post_json)(url, payload, headers=headers, timeout=timeout, retries=0)
    except Exception as error:  # noqa: BLE001 - 建议段失败不能拖垮整条推送
        result.errors.append(f"请求 DeepSeek 失败：{error}")
        return result

    text = parse_advice(response)
    if not text:
        result.errors.append("DeepSeek 没有返回可用的建议内容")
        return result
    if len(text) > MAX_LENGTH:
        result.errors.append(f"DeepSeek 返回的建议超过 {MAX_LENGTH} 字，已省略")
        return result
    result.advice = Advice(text=text)
    return result
