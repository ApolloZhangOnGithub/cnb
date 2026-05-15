"""Fetch WeChat public-account articles with a local toolbase fallback."""

from __future__ import annotations

import contextlib
import html
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_TOOLBASE = Path.home() / "Desktop" / "Toolbase_Skills" / "fetch_wechat_articles"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
VERIFY_MARKERS = (
    "当前环境异常",
    "完成验证后即可继续访问",
    "环境异常",
    "Weixin Security",
)


@dataclass(frozen=True)
class WechatArticle:
    status: str
    url: str
    title: str = ""
    author: str = ""
    publish_time: str = ""
    text: str = ""
    html: str = ""
    method: str = ""
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def is_wechat_article_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc == "mp.weixin.qq.com" and parsed.path.startswith("/s/")


def fetch_wechat_article(url: str, *, toolbase: Path | None = None, timeout: int = 15) -> WechatArticle:
    if not is_wechat_article_url(url):
        return WechatArticle("invalid_url", url=url, message="只支持 https://mp.weixin.qq.com/s/... 文章链接")

    direct = _fetch_direct(url, timeout=timeout)
    if direct.ok:
        return direct
    if direct.status != "verification_blocked":
        return direct

    fallback = _run_toolbase_fallback(url, toolbase or DEFAULT_TOOLBASE)
    if fallback.ok:
        return fallback
    return WechatArticle(
        "verification_blocked",
        url=url,
        method="direct",
        message=f"微信验证页阻止了直接读取；本机 fetch_wechat_articles fallback 也未成功：{fallback.message}",
    )


def _fetch_direct(url: str, *, timeout: int) -> WechatArticle:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            content_type = response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        return WechatArticle("unavailable", url=url, method="direct", message=f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return WechatArticle("unavailable", url=url, method="direct", message=str(exc.reason))
    except OSError as exc:
        return WechatArticle("unavailable", url=url, method="direct", message=str(exc))

    charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    document = raw.decode(charset, errors="replace")
    if _is_verification_page(document):
        return WechatArticle("verification_blocked", url=url, method="direct", message="微信返回环境验证页")

    article = _parse_article(url, document, method="direct")
    if article.text or article.html:
        return article
    return WechatArticle("unavailable", url=url, method="direct", message="页面可访问，但没有识别到正文")


def _run_toolbase_fallback(url: str, toolbase: Path) -> WechatArticle:
    if not toolbase.is_dir():
        return WechatArticle("fallback_unavailable", url=url, method="toolbase", message=f"找不到工具目录: {toolbase}")

    inserted = False
    try:
        sys.path.insert(0, str(toolbase))
        inserted = True
        from src.core.base_spider import BaseSpider  # type: ignore[import-not-found]

        spider = BaseSpider()
        with open(os.devnull, "w", encoding="utf-8") as devnull, contextlib.redirect_stdout(devnull):
            result = spider.get_an_article(url)
        if not isinstance(result, dict) or result.get("content_flag") != 1:
            return WechatArticle("fallback_unavailable", url=url, method="toolbase", message="工具库未返回文章正文")

        document = str(result.get("content") or "")
        article = _parse_article(url, document, method="toolbase")
        if article.text or article.html:
            return article
        return WechatArticle(
            "fallback_unavailable", url=url, method="toolbase", message="工具库返回 HTML，但未识别到正文"
        )
    except Exception as exc:
        return WechatArticle("fallback_unavailable", url=url, method="toolbase", message=str(exc))
    finally:
        if inserted:
            with contextlib.suppress(ValueError):
                sys.path.remove(str(toolbase))


def _is_verification_page(document: str) -> bool:
    return any(marker in document for marker in VERIFY_MARKERS)


def _parse_article(url: str, document: str, *, method: str) -> WechatArticle:
    title = _meta(document, "property", "og:title") or _tag_text(document, r"<title\b[^>]*>(.*?)</title>")
    author = _meta(document, "name", "author") or _tag_text(document, r'id=["\']js_name["\'][^>]*>(.*?)</')
    publish_time = _first_match(
        document,
        (
            r"var\s+createTime\s*=\s*['\"]([^'\"]+)['\"]",
            r"create_time:\s*JsDecode\(['\"]([^'\"]+)['\"]\)",
        ),
    )
    article_html = _first_match(
        document,
        (
            r'(?is)<div\b[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>\s*<script',
            r'(?is)<div\b[^>]*id=["\']js_content["\'][^>]*>(.*?)</div>',
        ),
    )
    text = _html_to_text(article_html or document)
    return WechatArticle(
        "ok",
        url=url,
        title=title.strip(),
        author=author.strip(),
        publish_time=publish_time.strip(),
        text=text,
        html=document,
        method=method,
    )


def _meta(document: str, attr: str, value: str) -> str:
    pattern = rf'<meta\b(?=[^>]*\b{attr}=["\']{re.escape(value)}["\'])(?=[^>]*\bcontent=["\']([^"\']*)["\'])[^>]*>'
    return html.unescape(_first_match(document, (pattern,)))


def _tag_text(document: str, pattern: str) -> str:
    return _html_to_text(_first_match(document, (pattern,)))


def _first_match(document: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, document)
        if match:
            return html.unescape(match.group(1))
    return ""


def _html_to_text(fragment: str) -> str:
    if not fragment:
        return ""
    text = re.sub(r"(?is)<(script|style|noscript|iframe)\b.*?</\1>", " ", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
