import json
import sqlite3
from pathlib import Path

import pytest

from lib.capture_ingest import cmd_capture
from lib.wechat_article import WechatArticle, fetch_wechat_article


class FakeResponse:
    def __init__(self, body: str, content_type: str = "text/html; charset=utf-8"):
        self._body = body.encode("utf-8")
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self) -> bytes:
        return self._body


ARTICLE_HTML = """
<html>
  <head>
    <meta property="og:title" content="测试文章">
    <meta property="og:url" content="https://mp.weixin.qq.com/s/abc">
    <meta name="author" content="测试作者">
    <script>var createTime = '2026-05-01 12:00';</script>
  </head>
  <body>
    <div id="js_content"><p>第一段</p><p>第二段</p></div><script>window.__END__=1</script>
  </body>
</html>
"""


def test_fetch_wechat_article_direct_success(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda _request, timeout: FakeResponse(ARTICLE_HTML))

    article = fetch_wechat_article("https://mp.weixin.qq.com/s/abc")

    assert article.ok
    assert article.method == "direct"
    assert article.title == "测试文章"
    assert article.author == "测试作者"
    assert article.publish_time == "2026-05-01 12:00"
    assert "第一段" in article.text
    assert "第二段" in article.text


def test_fetch_wechat_article_verification_uses_toolbase_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda _request, timeout: FakeResponse("当前环境异常, 完成验证后即可继续访问")
    )

    def fake_fallback(url: str, toolbase: Path) -> WechatArticle:
        assert toolbase == tmp_path
        return WechatArticle("ok", url=url, title="fallback", text="from toolbase", html="<html />", method="toolbase")

    monkeypatch.setattr("lib.wechat_article._run_toolbase_fallback", fake_fallback)

    article = fetch_wechat_article("https://mp.weixin.qq.com/s/abc", toolbase=tmp_path)

    assert article.ok
    assert article.method == "toolbase"
    assert article.text == "from toolbase"


def test_fetch_wechat_article_reports_verification_when_fallback_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda _request, timeout: FakeResponse("当前环境异常, 完成验证后即可继续访问")
    )
    monkeypatch.setattr(
        "lib.wechat_article._run_toolbase_fallback",
        lambda url, toolbase: WechatArticle("fallback_unavailable", url=url, method="toolbase", message="missing deps"),
    )

    article = fetch_wechat_article("https://mp.weixin.qq.com/s/abc", toolbase=tmp_path)

    assert article.status == "verification_blocked"
    assert "验证页" in article.message
    assert "missing deps" in article.message


def test_capture_wechat_ingests_article(monkeypatch, tmp_path, capsys):
    (tmp_path / ".cnb").mkdir()
    monkeypatch.setattr(
        "lib.capture_ingest.fetch_wechat_article",
        lambda url, toolbase=None: WechatArticle(
            "ok",
            url=url,
            title="已读文章",
            author="公众号",
            publish_time="2026-05-01",
            text="正文内容",
            html="<html>正文内容</html>",
            method="direct",
        ),
    )

    cmd_capture(["wechat", "https://mp.weixin.qq.com/s/abc", "--project", str(tmp_path), "--no-notify"])

    out = capsys.readouterr().out
    assert "OK WeChat article 已保存" in out
    capture_dir = next((tmp_path / ".cnb" / "captures").iterdir())
    content = (capture_dir / "content.md").read_text()
    payload = json.loads((capture_dir / "payload.redacted.json").read_text())
    assert "已读文章" in content
    assert "正文内容" in content
    assert payload["metadata"]["fetch_method"] == "direct"


def test_capture_wechat_reports_blocked(monkeypatch, tmp_path, capsys):
    (tmp_path / ".cnb").mkdir()
    monkeypatch.setattr(
        "lib.capture_ingest.fetch_wechat_article",
        lambda url, toolbase=None: WechatArticle("verification_blocked", url=url, message="微信验证页阻止了直接读取"),
    )

    with pytest.raises(SystemExit) as exc:
        cmd_capture(["wechat", "https://mp.weixin.qq.com/s/abc", "--project", str(tmp_path), "--no-notify"])

    assert exc.value.code == 1
    assert "微信验证页" in capsys.readouterr().err


def test_capture_wechat_can_notify_board(monkeypatch, tmp_path):
    cnb = tmp_path / ".cnb"
    cnb.mkdir()
    schema = (Path(__file__).parent.parent / "schema.sql").read_text()
    conn = sqlite3.connect(str(cnb / "board.db"))
    conn.executescript(schema)
    conn.execute("INSERT INTO sessions(name) VALUES ('lead')")
    conn.execute("INSERT INTO sessions(name) VALUES ('dispatcher')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(
        "lib.capture_ingest.fetch_wechat_article",
        lambda url, toolbase=None: WechatArticle("ok", url=url, title="通知文章", text="正文", method="direct"),
    )

    cmd_capture(["wechat", "https://mp.weixin.qq.com/s/abc", "--project", str(tmp_path)])

    conn = sqlite3.connect(str(cnb / "board.db"))
    message = conn.execute("SELECT body FROM messages").fetchone()[0]
    conn.close()
    assert "通知文章" in message
