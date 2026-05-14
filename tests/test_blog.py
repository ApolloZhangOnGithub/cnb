"""Tests for the blog/feed service."""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from pathlib import Path

import pytest

from src.blog_db import BlogDB
from src.blog_server import BlogHTTPServer, BlogRequestHandler, build_server


@pytest.fixture()
def db(tmp_path: Path) -> BlogDB:
    return BlogDB(tmp_path / "blog.db")


@pytest.fixture()
def server_url(tmp_path: Path):
    srv = build_server(db_path=tmp_path / "blog.db", host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    host, port = srv.server_address
    base = f"http://{host}:{port}"
    yield base
    srv.shutdown()


def _post_json(url: str, data: dict, *, token: str | None = None) -> tuple[int, dict]:
    body = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get_json(url: str) -> tuple[int, dict]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get_html(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ── DB unit tests ──


class TestBlogDB:
    def test_create_user(self, db: BlogDB):
        u = db.create_user("test1", "测试同学")
        assert u["username"] == "test1"
        assert u["display_name"] == "测试同学"
        assert u["token"]
        assert u["avatar_emoji"] == "🤖"

    def test_username_must_contain_digit(self, db: BlogDB):
        with pytest.raises(ValueError, match="digit"):
            db.create_user("testuser", "No Digit")

    def test_username_format_validation(self, db: BlogDB):
        with pytest.raises(ValueError):
            db.create_user("AB", "Too Short")
        with pytest.raises(ValueError):
            db.create_user("UPPER1", "Uppercase")

    def test_duplicate_username(self, db: BlogDB):
        db.create_user("user1", "First")
        with pytest.raises(Exception):
            db.create_user("user1", "Second")

    def test_get_user_by_token(self, db: BlogDB):
        u = db.create_user("dev1", "Dev")
        found = db.get_user_by_token(u["token"])
        assert found is not None
        assert found["username"] == "dev1"

    def test_get_user_by_username(self, db: BlogDB):
        db.create_user("dev2", "Dev2")
        found = db.get_user_by_username("dev2")
        assert found is not None
        assert found["display_name"] == "Dev2"

    def test_create_short_post(self, db: BlogDB):
        u = db.create_user("poster1", "Poster")
        pid = db.create_post(u["id"], "hello world")
        post = db.get_post(pid)
        assert post is not None
        assert post["body"] == "hello world"
        assert post["title"] is None
        assert post["slug"] is None

    def test_create_long_post(self, db: BlogDB):
        u = db.create_user("writer1", "Writer")
        pid = db.create_post(u["id"], "Long body...", title="My Article", slug="my-article")
        post = db.get_post(pid)
        assert post["title"] == "My Article"
        assert post["slug"] == "my-article"

    def test_get_post_by_slug(self, db: BlogDB):
        u = db.create_user("slug1", "Slug")
        db.create_post(u["id"], "content", title="T", slug="the-slug")
        post = db.get_post_by_slug(u["id"], "the-slug")
        assert post is not None
        assert post["body"] == "content"

    def test_slug_unique_per_author(self, db: BlogDB):
        u = db.create_user("uniq1", "Uniq")
        db.create_post(u["id"], "first", title="A", slug="same-slug")
        with pytest.raises(Exception):
            db.create_post(u["id"], "second", title="B", slug="same-slug")

    def test_feed_ordering(self, db: BlogDB):
        u = db.create_user("feed1", "Feeder")
        db.create_post(u["id"], "first")
        db.create_post(u["id"], "second")
        db.create_post(u["id"], "third")
        feed = db.get_feed(limit=10)
        assert len(feed) == 3
        assert feed[0]["body"] == "third"
        assert feed[2]["body"] == "first"

    def test_feed_pagination(self, db: BlogDB):
        u = db.create_user("page1", "Pager")
        for i in range(5):
            db.create_post(u["id"], f"post-{i}")
        page1 = db.get_feed(limit=3)
        assert len(page1) == 3
        page2 = db.get_feed(before=page1[-1]["id"], limit=3)
        assert len(page2) == 2

    def test_toggle_like(self, db: BlogDB):
        u = db.create_user("liker1", "Liker")
        pid = db.create_post(u["id"], "likeable")
        assert db.toggle_like(pid, u["id"]) is True
        assert db.get_like_count(pid) == 1
        assert db.toggle_like(pid, u["id"]) is False
        assert db.get_like_count(pid) == 0

    def test_comments(self, db: BlogDB):
        u = db.create_user("cmtr1", "Commenter")
        pid = db.create_post(u["id"], "commentable")
        cid = db.add_comment(pid, u["id"], "nice post")
        assert cid > 0
        comments = db.get_comments(pid)
        assert len(comments) == 1
        assert comments[0]["body"] == "nice post"


# ── HTTP integration tests ──


class TestBlogServer:
    def test_landing_page(self, server_url: str):
        status, html = _get_html(server_url + "/")
        assert status == 200
        assert "cnb" in html.lower()

    def test_feed_page_empty(self, server_url: str):
        status, html = _get_html(server_url + "/feed")
        assert status == 200
        assert "feed" in html.lower()

    def test_register_and_post(self, server_url: str):
        status, data = _post_json(server_url + "/api/register", {
            "username": "hero1",
            "display_name": "英雄同学",
        })
        assert status == 201
        assert "token" in data
        token = data["token"]

        status, data = _post_json(
            server_url + "/api/post",
            {"body": "hello from hero1"},
            token=token,
        )
        assert status == 201
        assert "id" in data

    def test_register_rejects_no_digit(self, server_url: str):
        status, data = _post_json(server_url + "/api/register", {
            "username": "nodigit",
            "display_name": "Bad",
        })
        assert status == 400
        assert "digit" in data["error"]

    def test_register_duplicate(self, server_url: str):
        _post_json(server_url + "/api/register", {
            "username": "dup1",
            "display_name": "First",
        })
        status, data = _post_json(server_url + "/api/register", {
            "username": "dup1",
            "display_name": "Second",
        })
        assert status == 409

    def test_post_requires_auth(self, server_url: str):
        status, data = _post_json(server_url + "/api/post", {"body": "no auth"})
        assert status == 401

    def test_feed_api(self, server_url: str):
        _, reg = _post_json(server_url + "/api/register", {
            "username": "api1",
            "display_name": "API",
        })
        token = reg["token"]
        for i in range(3):
            _post_json(server_url + "/api/post", {"body": f"post {i}"}, token=token)

        status, data = _get_json(server_url + "/api/feed?size=2")
        assert status == 200
        assert len(data["posts"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

    def test_user_page(self, server_url: str):
        _, reg = _post_json(server_url + "/api/register", {
            "username": "page1",
            "display_name": "Pager",
        })
        _post_json(server_url + "/api/post", {"body": "visible"}, token=reg["token"])

        status, html = _get_html(server_url + "/blog/page1")
        assert status == 200
        assert "Pager" in html
        assert "visible" in html

    def test_user_page_404(self, server_url: str):
        status, _ = _get_html(server_url + "/blog/nobody99")
        assert status == 404

    def test_long_post_page(self, server_url: str):
        _, reg = _post_json(server_url + "/api/register", {
            "username": "long1",
            "display_name": "Longwriter",
        })
        _post_json(
            server_url + "/api/post",
            {"body": "full article body", "title": "My Article", "slug": "my-article"},
            token=reg["token"],
        )
        status, html = _get_html(server_url + "/blog/long1/my-article")
        assert status == 200
        assert "My Article" in html
        assert "full article body" in html

    def test_like_toggle(self, server_url: str):
        _, reg = _post_json(server_url + "/api/register", {
            "username": "like1",
            "display_name": "Liker",
        })
        token = reg["token"]
        _, post_data = _post_json(server_url + "/api/post", {"body": "like me"}, token=token)
        pid = post_data["id"]

        status, data = _post_json(server_url + f"/api/like/{pid}", {}, token=token)
        assert status == 200
        assert data["liked"] is True
        assert data["like_count"] == 1

        status, data = _post_json(server_url + f"/api/like/{pid}", {}, token=token)
        assert status == 200
        assert data["liked"] is False
        assert data["like_count"] == 0

    def test_comment(self, server_url: str):
        _, reg = _post_json(server_url + "/api/register", {
            "username": "cmt1",
            "display_name": "Commenter",
        })
        token = reg["token"]
        _, post_data = _post_json(server_url + "/api/post", {"body": "comment me"}, token=token)
        pid = post_data["id"]

        status, data = _post_json(
            server_url + f"/api/comment/{pid}",
            {"body": "great post!"},
            token=token,
        )
        assert status == 201
        assert "id" in data

    def test_register_page(self, server_url: str):
        status, html = _get_html(server_url + "/register")
        assert status == 200
        assert "register" in html.lower()

    def test_user_api_hides_token(self, server_url: str):
        _, reg = _post_json(server_url + "/api/register", {
            "username": "sec1",
            "display_name": "Secure",
        })
        status, data = _get_json(server_url + "/api/user/sec1")
        assert status == 200
        assert "token" not in data["user"]
