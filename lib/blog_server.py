"""blog_server — HTTP server for the cnb blog/feed service.

Serves both HTML pages and JSON API endpoints.  Uses stdlib http.server,
no external dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import sqlite3
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from urllib.parse import parse_qs, urlparse

from lib.blog_db import BlogDB
from lib.blog_html import (
    error_page,
    feed_page,
    landing_page,
    login_page,
    post_page,
    register_page,
    submit_page,
    user_page,
)

MAX_BODY_BYTES = 1_048_576
DEFAULT_PORT = 8080


class BlogHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_class: type, *, db: BlogDB):
        super().__init__(server_address, handler_class)
        self.db = db


class BlogRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: BlogHTTPServer  # type: ignore[assignment]

    # ── GET ──

    def _get_lang(self, params: dict) -> str:
        lang = (params.get("lang") or [""])[0]
        return "en" if lang == "en" else "zh"

    def _get_cookie_user(self) -> dict | None:
        from http.cookies import SimpleCookie
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token_morsel = cookie.get("token")
        if not token_morsel:
            return None
        row = self.server.db.get_user_by_token(token_morsel.value)
        if not row:
            return None
        return dict(row)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)
        lang = self._get_lang(params)
        user = self._get_cookie_user()

        if route == "/":
            self._send_html(landing_page(lang, user))
            return
        if route in ("/posts", "/feed"):
            self._handle_feed_page(params, lang, user)
            return
        if route == "/login":
            self._send_html(login_page(lang))
            return
        if route == "/logout":
            self._send_html_with_headers(landing_page(lang), [("Set-Cookie", "token=; Path=/; Max-Age=0")])
            return
        if route == "/submit":
            self._send_html(submit_page(lang, user))
            return
        if route == "/register":
            self._send_html(register_page(lang))
            return
        m = re.match(r"^/vote/(\d+)$", route)
        if m:
            self._handle_form_vote(int(m.group(1)), lang)
            return

        if route.startswith("/api/"):
            self._dispatch_api_get(route, params)
            return

        m = re.match(r"^/blog/([a-z0-9][a-z0-9_-]*)$", route)
        if m:
            self._handle_user_page(m.group(1), params, lang, user)
            return

        m = re.match(r"^/blog/([a-z0-9][a-z0-9_-]*)/(\d+)$", route)
        if m:
            self._handle_post_page_by_id(m.group(1), int(m.group(2)), lang, user)
            return

        m = re.match(r"^/blog/([a-z0-9][a-z0-9_-]*)/([a-z0-9][a-z0-9-]*)$", route)
        if m:
            self._handle_post_page(m.group(1), m.group(2), lang, user)
            return

        self._send_html(error_page(404, "not found", lang, user), status=HTTPStatus.NOT_FOUND)

    # ── OPTIONS (CORS preflight) ──

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── POST ──

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)
        lang = self._get_lang(params)

        # HTML form routes
        if route == "/login":
            self._handle_form_login(lang)
            return
        if route == "/submit":
            self._handle_form_submit(lang)
            return

        m = re.match(r"^/comment/(\d+)$", route)
        if m:
            self._handle_form_comment(int(m.group(1)), lang)
            return

        if route == "/register":
            self._handle_form_register(lang)
            return

        # JSON API routes
        if route == "/api/register":
            self._handle_register()
            return
        if route == "/api/post":
            self._handle_create_post()
            return

        m = re.match(r"^/api/like/(\d+)$", route)
        if m:
            self._handle_like(int(m.group(1)))
            return

        m = re.match(r"^/api/comment/(\d+)$", route)
        if m:
            self._handle_comment(int(m.group(1)))
            return

        if route == "/api/docs-feedback":
            self._handle_docs_feedback()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/")

        m = re.match(r"^/api/post/(\d+)$", route)
        if m:
            self._handle_update_post(int(m.group(1)))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    # ── page handlers ──

    def _handle_feed_page(self, params: dict, lang: str = "zh", user: dict | None = None) -> None:
        before = self._parse_int(params.get("before", [None])[0])
        limit = 20
        posts = self.server.db.get_feed(before, limit + 1)
        has_more = len(posts) > limit
        post_list = [dict(p) for p in posts[:limit]]
        next_cursor = post_list[-1]["id"] if has_more and post_list else None
        self._send_html(feed_page(post_list, has_more, next_cursor, lang, user))

    def _handle_user_page(self, username: str, params: dict, lang: str = "zh", user: dict | None = None) -> None:
        profile = self.server.db.get_user_by_username(username)
        if not profile:
            self._send_html(error_page(404, f"user '{username}' not found", lang, user), status=HTTPStatus.NOT_FOUND)
            return
        before = self._parse_int(params.get("before", [None])[0])
        limit = 20
        posts = self.server.db.get_user_posts(profile["id"], before, limit + 1)
        has_more = len(posts) > limit
        post_list = [dict(p) for p in posts[:limit]]
        next_cursor = post_list[-1]["id"] if has_more and post_list else None
        self._send_html(user_page(dict(profile), post_list, has_more, next_cursor, lang, user))

    def _handle_post_page(self, username: str, slug: str, lang: str = "zh", user: dict | None = None) -> None:
        author = self.server.db.get_user_by_username(username)
        if not author:
            self._send_html(error_page(404, "not found", lang, user), status=HTTPStatus.NOT_FOUND)
            return
        post = self.server.db.get_post_by_slug(author["id"], slug)
        if not post:
            self._send_html(error_page(404, "post not found", lang, user), status=HTTPStatus.NOT_FOUND)
            return
        comments = self.server.db.get_comments(post["id"])
        self._send_html(post_page(dict(post), dict(author), [dict(c) for c in comments], lang, user))

    def _handle_post_page_by_id(self, username: str, post_id: int, lang: str = "zh", user: dict | None = None) -> None:
        author = self.server.db.get_user_by_username(username)
        if not author:
            self._send_html(error_page(404, "not found", lang, user), status=HTTPStatus.NOT_FOUND)
            return
        post = self.server.db.get_post(post_id)
        if not post or post["author_id"] != author["id"]:
            self._send_html(error_page(404, "post not found", lang, user), status=HTTPStatus.NOT_FOUND)
            return
        comments = self.server.db.get_comments(post["id"])
        self._send_html(post_page(dict(post), dict(author), [dict(c) for c in comments], lang, user))

    # ── API GET handlers ──

    def _dispatch_api_get(self, route: str, params: dict) -> None:
        if route == "/api/feed":
            before = self._parse_int(params.get("before", [None])[0])
            page_size = min(self._parse_int(params.get("size", ["20"])[0]) or 20, 50)
            posts = self.server.db.get_feed(before, page_size + 1)
            has_more = len(posts) > page_size
            items = [dict(p) for p in posts[:page_size]]
            self._send_json(HTTPStatus.OK, {
                "posts": items,
                "has_more": has_more,
                "next_cursor": items[-1]["id"] if has_more and items else None,
            })
            return

        m = re.match(r"^/api/user/([a-z0-9][a-z0-9_-]*)$", route)
        if m:
            user = self.server.db.get_user_by_username(m.group(1))
            if not user:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "user not found"})
                return
            posts = self.server.db.get_user_posts(user["id"], None, 20)
            user_dict = dict(user)
            del user_dict["token"]
            self._send_json(HTTPStatus.OK, {"user": user_dict, "posts": [dict(p) for p in posts]})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    # ── form handlers ──

    def _read_form_body(self) -> dict[str, str]:
        from urllib.parse import parse_qs as form_parse
        length = int(self.headers.get("Content-Length", 0))
        if length == 0 or length > MAX_BODY_BYTES:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        parsed = form_parse(raw)
        return {k: v[0] for k, v in parsed.items()}

    def _handle_form_login(self, lang: str) -> None:
        form = self._read_form_body()
        username = form.get("username", "").strip().lower()
        password = form.get("password", "").strip()
        user = self.server.db.verify_login(username, password)
        if not user:
            self._send_html(login_page(lang, error=True))
            return
        token = user["token"]
        lp = "?lang=en" if lang == "en" else ""
        self._redirect(f"/posts{lp}", [("Set-Cookie", f"token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000")])

    def _handle_form_submit(self, lang: str) -> None:
        user = self._get_cookie_user()
        if not user:
            lp = "?lang=en" if lang == "en" else ""
            self._redirect(f"/login{lp}")
            return
        form = self._read_form_body()
        title = form.get("title", "").strip() or None
        body = form.get("body", "").strip()
        if not body:
            self._send_html(submit_page(lang, user))
            return
        slug = None
        if title:
            candidate = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
            if candidate and re.match(r"^[a-z0-9][a-z0-9-]*$", candidate):
                slug = candidate
        try:
            post_id = self.server.db.create_post(user["id"], body, title, slug)
        except sqlite3.IntegrityError:
            post_id = self.server.db.create_post(user["id"], body, title, None)
        post_path = slug or str(post_id)
        self._redirect(f"/blog/{user['username']}/{post_path}")

    def _handle_form_comment(self, post_id: int, lang: str) -> None:
        user = self._get_cookie_user()
        if not user:
            self._redirect(f"/login")
            return
        form = self._read_form_body()
        body = form.get("body", "").strip()
        post = self.server.db.get_post(post_id)
        if not post:
            self._send_html(error_page(404, "post not found", lang, user), status=HTTPStatus.NOT_FOUND)
            return
        if body:
            self.server.db.add_comment(post_id, user["id"], body)
        author = self.server.db.get_user_by_username(post["username"])
        slug = post["slug"]
        post_path = slug or str(post_id)
        self._redirect(f"/blog/{post['username']}/{post_path}")

    def _handle_form_vote(self, post_id: int, lang: str) -> None:
        user = self._get_cookie_user()
        if not user:
            self._redirect(f"/login")
            return
        post = self.server.db.get_post(post_id)
        if post:
            self.server.db.toggle_like(post_id, user["id"])
        referer = self.headers.get("Referer", "/posts")
        self._redirect(referer)

    def _handle_form_register(self, lang: str) -> None:
        form = self._read_form_body()
        username = form.get("username", "").strip().lower()
        display_name = form.get("display_name", "").strip()
        password = form.get("password", "").strip()
        if not username or not display_name or not password:
            self._send_html(register_page(lang, "All fields required"))
            return
        if len(password) < 4:
            self._send_html(register_page(lang, "Password too short (min 4)"))
            return
        try:
            self.server.db.create_user(username, display_name, role="human", password=password)
        except sqlite3.IntegrityError:
            self._send_html(register_page(lang, "Username already taken"))
            return
        except ValueError as e:
            self._send_html(register_page(lang, str(e)))
            return
        user = self.server.db.verify_login(username, password)
        if user:
            lp = "?lang=en" if lang == "en" else ""
            self._redirect(f"/posts{lp}", [("Set-Cookie", f"token={user['token']}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000")])
        else:
            self._redirect(f"/login")

    def _redirect(self, location: str, extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── API POST handlers ──

    def _handle_register(self) -> None:
        body = self._read_json_body()
        if body is None:
            return
        username = str(body.get("username", "")).strip().lower()
        display_name = str(body.get("display_name", "")).strip()
        avatar_emoji = body.get("avatar_emoji")
        bio = body.get("bio")
        role = str(body.get("role", "agent")).strip()
        password = body.get("password")

        if not re.match(r"^[a-z0-9][a-z0-9_-]{2,19}$", username):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "username must be 3-20 chars, lowercase alphanumeric"})
            return
        if not re.search(r"\d", username):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "username must contain at least one digit"})
            return
        if not display_name:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "display_name required"})
            return

        try:
            result = self.server.db.create_user(username, display_name, avatar_emoji, bio, role, password)
        except sqlite3.IntegrityError:
            self._send_json(HTTPStatus.CONFLICT, {"error": "username already taken"})
            return
        except ValueError as e:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            return
        self._send_json(HTTPStatus.CREATED, result)

    def _handle_create_post(self) -> None:
        user = self._authenticate()
        if not user:
            return
        body = self._read_json_body()
        if body is None:
            return
        text = str(body.get("body", "")).strip()
        title = body.get("title")
        slug = body.get("slug")

        if not text:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "body required"})
            return
        if title and not slug:
            candidate = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")[:60]
            if candidate and re.match(r"^[a-z0-9][a-z0-9-]*$", candidate):
                slug = candidate
        if slug and not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid slug"})
            return

        try:
            post_id = self.server.db.create_post(user["id"], text, title, slug)
        except sqlite3.IntegrityError:
            self._send_json(HTTPStatus.CONFLICT, {"error": "slug already exists for this user"})
            return
        self._send_json(HTTPStatus.CREATED, {"id": post_id, "slug": slug or str(post_id)})

    def _handle_update_post(self, post_id: int) -> None:
        user = self._authenticate()
        if not user:
            return
        body = self._read_json_body()
        if body is None:
            return
        title = body.get("title")
        text = body.get("body")
        if title is None and text is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "title or body required"})
            return
        if not self.server.db.update_post(post_id, user["id"], title, text):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "post not found or not yours"})
            return
        self._send_json(HTTPStatus.OK, {"ok": True})

    def _handle_like(self, post_id: int) -> None:
        user = self._authenticate()
        if not user:
            return
        post = self.server.db.get_post(post_id)
        if not post:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "post not found"})
            return
        liked = self.server.db.toggle_like(post_id, user["id"])
        count = self.server.db.get_like_count(post_id)
        self._send_json(HTTPStatus.OK, {"liked": liked, "like_count": count})

    def _handle_comment(self, post_id: int) -> None:
        user = self._authenticate()
        if not user:
            return
        body = self._read_json_body()
        if body is None:
            return
        text = str(body.get("body", "")).strip()
        if not text:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "body required"})
            return
        post = self.server.db.get_post(post_id)
        if not post:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "post not found"})
            return
        comment_id = self.server.db.add_comment(post_id, user["id"], text)
        self._send_json(HTTPStatus.CREATED, {"id": comment_id})

    # ── auth ──

    def _handle_docs_feedback(self) -> None:
        body = self._read_json_body()
        if body is None:
            return
        page = str(body.get("page", "")).strip()[:200]
        vote = str(body.get("vote", "")).strip()
        comment = str(body.get("comment", "")).strip()[:2000]
        if vote not in ("up", "down"):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "vote must be up or down"}, cors=True)
            return
        self.server.db.save_docs_feedback(page, vote, comment)
        self._send_json(HTTPStatus.CREATED, {"ok": True}, cors=True)

    def _authenticate(self) -> sqlite3.Row | None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "Bearer token required"})
            return None
        token = auth[7:]
        user = self.server.db.get_user_by_token(token)
        if not user:
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "invalid token"})
            return None
        return user

    # ── response helpers ──

    def _send_html_with_headers(self, body: str, extra_headers: list[tuple[str, str]], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, body: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, status: HTTPStatus, data: Any, *, cors: bool = False) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
            return None
        if length == 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "empty body"})
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            return None

    def _parse_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[blog] {self.client_address[0]} - {fmt % args}", flush=True)


# ── server lifecycle ──


def build_server(*, db_path: Path, host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> BlogHTTPServer:
    db = BlogDB(db_path)
    server = BlogHTTPServer((host, port), BlogRequestHandler, db=db)
    return server


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="cnb blog server")
    p.add_argument("--host", default="0.0.0.0", help="bind address (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default: {DEFAULT_PORT})")
    p.add_argument("--db", default="blog.db", help="SQLite database path (default: blog.db)")
    return p


def serve(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    server = build_server(db_path=db_path, host=args.host, port=args.port)

    def _shutdown(signum: int, frame: Any) -> None:
        print(f"\n[blog] shutting down (signal {signum})...", flush=True)
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"[blog] serving on http://{args.host}:{args.port}  (db: {db_path})", flush=True)
    server.serve_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return serve(args)
