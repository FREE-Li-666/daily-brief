"""星座运势：外部免费接口，取不到就整段省略，不影响其余内容。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import net

# 免 key 的公共接口，海外节点不一定连通，所以只当兜底
VVHAN_URL = "https://api.vvhan.com/api/horoscope?type={key}&time=today"
# 天行数据星座运势，注册后有免费额度，需要 key
TIANAPI_URL = "https://apis.tianapi.com/star/index?key={api_key}&astro={sign}"

# (中文名, 接口键, 起始月, 起始日)
SIGNS = [
    ("白羊座", "aries", 3, 21),
    ("金牛座", "taurus", 4, 20),
    ("双子座", "gemini", 5, 21),
    ("巨蟹座", "cancer", 6, 22),
    ("狮子座", "leo", 7, 23),
    ("处女座", "virgo", 8, 23),
    ("天秤座", "libra", 9, 23),
    ("天蝎座", "scorpio", 10, 24),
    ("射手座", "sagittarius", 11, 23),
    ("摩羯座", "capricorn", 12, 22),
    ("水瓶座", "aquarius", 1, 20),
    ("双鱼座", "pisces", 2, 19),
]

CN_TO_KEY = {cn: key for cn, key, _, _ in SIGNS}
KEY_TO_CN = {key: cn for cn, key, _, _ in SIGNS}
SUMMARY_FIELDS = ("short", "fortune", "content", "summary", "text", "desc", "today", "all")
MAX_SUMMARY = 60


@dataclass
class ZodiacFortune:
    sign_cn: str
    summary: str = ""
    lucky: str = ""
    stars: str = ""
    source: str = ""

    def line(self) -> str:
        parts = [self.sign_cn]
        if self.stars:
            parts.append(self.stars)
        head = " ".join(parts)
        tail = self.summary
        if self.lucky:
            tail = f"{tail}（{self.lucky}）" if tail else f"（{self.lucky}）"
        return f"{head} {tail}".strip()


def normalize_sign(value: str) -> tuple[str | None, str | None]:
    """把「天蝎座」或「scorpio」统一成 (中文名, 接口键)。"""
    text = str(value or "").strip()
    if not text:
        return None, None
    lowered = text.lower()
    if text in CN_TO_KEY:
        return text, CN_TO_KEY[text]
    if lowered in KEY_TO_CN:
        return KEY_TO_CN[lowered], lowered
    if not text.endswith("座") and f"{text}座" in CN_TO_KEY:
        return f"{text}座", CN_TO_KEY[f"{text}座"]
    return None, None


def sign_from_birthday(month: int, day: int) -> str | None:
    """按公历生日判断星座，返回中文名。"""
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        return None
    # 按公历顺序排列的星座起始日；摩羯座跨年，单独兜底
    ordered = [
        ("水瓶座", 1, 20),
        ("双鱼座", 2, 19),
        ("白羊座", 3, 21),
        ("金牛座", 4, 20),
        ("双子座", 5, 21),
        ("巨蟹座", 6, 22),
        ("狮子座", 7, 23),
        ("处女座", 8, 23),
        ("天秤座", 9, 23),
        ("天蝎座", 10, 24),
        ("射手座", 11, 23),
        ("摩羯座", 12, 22),
    ]
    matched = None
    for cn, start_month, start_day in ordered:
        if (month, day) >= (start_month, start_day):
            matched = cn
    return matched or "摩羯座"


def _first_text(data: dict) -> str:
    for field in SUMMARY_FIELDS:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return ""


def _tidy(text: str) -> str:
    cleaned = " ".join(text.replace("\r", "\n").split())
    if len(cleaned) <= MAX_SUMMARY:
        return cleaned
    return f"{cleaned[:MAX_SUMMARY].rstrip('，。,.')}…"


def _lucky(data: dict) -> str:
    color = str(data.get("luckycolor") or data.get("lucky_color") or "").strip()
    number = str(data.get("luckynumber") or data.get("lucky_number") or "").strip()
    parts = []
    if color:
        parts.append(f"幸运色{color}")
    if number:
        parts.append(f"幸运数字{number}")
    return " · ".join(parts)


def _stars(data: dict) -> str:
    index = data.get("index")
    if not isinstance(index, dict) or not index:
        return ""
    values = []
    for value in index.values():
        try:
            values.append(float(str(value).replace("%", "")))
        except ValueError:
            continue
    if not values:
        return ""
    average = sum(values) / len(values)
    if average > 10:
        average = average / 10
    score = max(1, min(5, int(round(average / 2)) if average > 5 else int(round(average))))
    return "★" * score + "☆" * (5 - score)


def parse_fortune(payload, sign_cn: str, source: str = "") -> ZodiacFortune | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("success") is False:
        return None
    code = payload.get("code")
    if code is not None and str(code) not in ("200", "0"):
        return None
    data = payload.get("data") or payload.get("result") or payload
    if isinstance(data, dict) and isinstance(data.get("list"), list) and data["list"]:
        first = data["list"][0]
        if isinstance(first, dict):
            data = first
    if not isinstance(data, dict):
        return None
    summary = _tidy(_first_text(data))
    if not summary:
        return None
    return ZodiacFortune(
        sign_cn=sign_cn,
        summary=summary,
        lucky=_lucky(data),
        stars=_stars(data),
        source=source or "外部接口",
    )


def candidate_urls(key: str, sign_cn: str, *, url_template: str = "", api_key: str = "") -> list[tuple[str, str]]:
    """按优先级给出候选地址：自定义模板 → 天行数据 → 免 key 公共接口。"""
    candidates = []
    if url_template:
        candidates.append(
            ("自定义接口", url_template.format(key=key, sign=quote(sign_cn), api_key=quote(api_key)))
        )
    if api_key:
        candidates.append(("天行数据", TIANAPI_URL.format(api_key=quote(api_key), sign=quote(sign_cn))))
    candidates.append(("vvhan", VVHAN_URL.format(key=key)))
    return candidates


def fetch_fortune(
    sign: str,
    *,
    timeout: float = 3.0,
    url_template: str = "",
    api_key: str = "",
    fetcher=None,
) -> ZodiacFortune | None:
    sign_cn, key = normalize_sign(sign)
    if not sign_cn or not key:
        return None
    for name, url in candidate_urls(key, sign_cn, url_template=url_template, api_key=api_key):
        try:
            payload = (fetcher or net.http_get_json)(url, timeout=timeout, retries=0)
        except Exception:
            continue
        fortune = parse_fortune(payload, sign_cn, source=name)
        if fortune is not None:
            return fortune
    return None
