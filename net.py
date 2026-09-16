"""HTTP 小工具：只用 Python 标准库，便于在无依赖环境下运行和测试。"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request

USER_AGENT = "daily-brief/1.0"
DEFAULT_TIMEOUT = 8.0

# macOS 上用 python.org 安装包的解释器默认没有 CA 证书，按序找可用的证书文件
CA_FILE_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
    "/etc/pki/tls/certs/ca-bundle.crt",
)

_SSL_CONTEXT = None


class HttpError(RuntimeError):
    """网络请求失败。"""


def ssl_context() -> ssl.SSLContext:
    """返回带可用证书的 SSL 上下文，并缓存复用。"""
    global _SSL_CONTEXT
    if _SSL_CONTEXT is not None:
        return _SSL_CONTEXT
    context = ssl.create_default_context()
    if _has_ca(context):
        _SSL_CONTEXT = context
        return context
    try:
        import certifi  # 装了就用它的证书包

        context = ssl.create_default_context(cafile=certifi.where())
        if _has_ca(context):
            _SSL_CONTEXT = context
            return context
    except Exception:
        pass
    for path in CA_FILE_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            candidate = ssl.create_default_context(cafile=path)
        except Exception:
            continue
        if _has_ca(candidate):
            _SSL_CONTEXT = candidate
            return candidate
    _SSL_CONTEXT = context
    return context


def _has_ca(context: ssl.SSLContext) -> bool:
    try:
        return bool(context.cert_store_stats().get("x509_ca"))
    except Exception:
        return False


def url_with_params(base: str, params: dict) -> str:
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    return f"{base}?{urllib.parse.urlencode(clean, doseq=True)}"


def _fetch(url: str, data: bytes | None, headers: dict, timeout: float) -> str:
    request = urllib.request.Request(url, data=data, headers=headers)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Accept", "application/json, text/plain, */*")
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context()) as response:
        return response.read().decode("utf-8", errors="replace")


def _with_retry(label: str, call, retries: int) -> object:
    last_error = None
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - 统一收敛成 HttpError
            last_error = error
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
    raise HttpError(f"{label} 失败：{last_error}") from last_error


def http_get_text(url: str, headers: dict | None = None, timeout: float = DEFAULT_TIMEOUT, retries: int = 2) -> str:
    request_headers = dict(headers or {})
    return _with_retry(f"GET {url}", lambda: _fetch(url, None, request_headers, timeout), retries)


def http_get_json(url: str, headers: dict | None = None, timeout: float = DEFAULT_TIMEOUT, retries: int = 2):
    text = http_get_text(url, headers=headers, timeout=timeout, retries=retries)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise HttpError(f"GET {url} 返回的不是合法 JSON：{text[:120]!r}") from error


def http_post_json(url: str, payload: dict, headers: dict | None = None, timeout: float = DEFAULT_TIMEOUT, retries: int = 1):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json; charset=utf-8", **dict(headers or {})}
    return _with_retry(f"POST {url}", lambda: json.loads(_fetch(url, body, request_headers, timeout)), retries)
