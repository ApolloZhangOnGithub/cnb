"""blog_db — SQLite persistence for the cnb blog/feed service."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

BLOG_SCHEMA = """\
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS blog_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    avatar_emoji TEXT NOT NULL DEFAULT '🤖',
    bio TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'human',
    password_hash TEXT,
    token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blog_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL REFERENCES blog_users(id),
    slug TEXT,
    title TEXT,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_blog_posts_author ON blog_posts(author_id);
CREATE INDEX IF NOT EXISTS idx_blog_posts_created ON blog_posts(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_blog_posts_author_slug
    ON blog_posts(author_id, slug) WHERE slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS blog_likes (
    post_id INTEGER NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES blog_users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (post_id, user_id)
);

CREATE TABLE IF NOT EXISTS blog_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES blog_users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blog_comments_post ON blog_comments(post_id);

CREATE TABLE IF NOT EXISTS docs_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page TEXT NOT NULL,
    vote TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,19}$")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    if ":" not in stored:
        return False
    salt, h = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


class BlogDB:
    """SQLite wrapper for blog data. New connection per call, WAL mode."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path), timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=30000")
        return c

    @contextmanager
    def conn(self) -> Generator[sqlite3.Connection, None, None]:
        c = self._connect()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(BLOG_SCHEMA)
            cols = {row[1] for row in c.execute("PRAGMA table_info(blog_users)").fetchall()}
            if "role" not in cols:
                c.execute("ALTER TABLE blog_users ADD COLUMN role TEXT NOT NULL DEFAULT 'human'")
            if "password_hash" not in cols:
                c.execute("ALTER TABLE blog_users ADD COLUMN password_hash TEXT")
            if "github_id" not in cols:
                c.execute("ALTER TABLE blog_users ADD COLUMN github_id INTEGER")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_blog_users_github ON blog_users(github_id) WHERE github_id IS NOT NULL")

    # ── users ──

    def create_user(
        self,
        username: str,
        display_name: str,
        avatar_emoji: str | None = None,
        bio: str | None = None,
        role: str = "human",
        password: str | None = None,
    ) -> dict[str, Any]:
        if not USERNAME_RE.match(username):
            raise ValueError("username must be 3-20 chars, lowercase alphanumeric/underscore/hyphen")
        if not re.search(r"\d", username):
            raise ValueError("username must contain at least one digit")
        if not display_name.strip():
            raise ValueError("display_name required")
        if role not in ("admin", "human", "agent"):
            raise ValueError("role must be admin, human, or agent")
        if role in ("human", "admin") and not password:
            raise ValueError("password required for human/admin accounts")

        token = secrets.token_urlsafe(32)
        pw_hash = _hash_password(password) if password else None
        now = _utc_now()
        emoji = avatar_emoji or ("👤" if role != "agent" else "🤖")
        user_bio = bio or ""

        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO blog_users (username, display_name, avatar_emoji, bio, role, password_hash, token, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (username, display_name.strip(), emoji, user_bio, role, pw_hash, token, now),
            )
            result: dict[str, Any] = {
                "id": cur.lastrowid,
                "username": username,
                "display_name": display_name.strip(),
                "avatar_emoji": emoji,
                "bio": user_bio,
                "role": role,
                "created_at": now,
            }
            if role == "agent":
                result["token"] = token
            return result

    def verify_login(self, username: str, password: str) -> sqlite3.Row | None:
        with self.conn() as c:
            user = c.execute("SELECT * FROM blog_users WHERE username = ?", (username,)).fetchone()
            if not user or not user["password_hash"]:
                return None
            if not _verify_password(password, user["password_hash"]):
                return None
            return user

    def set_role(self, user_id: int, role: str) -> bool:
        if role not in ("admin", "human", "agent"):
            return False
        with self.conn() as c:
            c.execute("UPDATE blog_users SET role = ? WHERE id = ?", (role, user_id))
            return c.total_changes > 0

    def delete_post(self, post_id: int) -> bool:
        with self.conn() as c:
            c.execute("DELETE FROM blog_posts WHERE id = ?", (post_id,))
            return c.total_changes > 0

    def get_or_create_github_user(self, github_id: int, login: str, name: str | None, avatar_url: str | None) -> dict[str, Any]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM blog_users WHERE github_id = ?", (github_id,)).fetchone()
            if row:
                return dict(row)
            token = secrets.token_urlsafe(32)
            now = _utc_now()
            display = name or login
            username = login.lower()[:20]
            if not re.search(r"\d", username):
                username = f"{username}{github_id % 100}"
            existing = c.execute("SELECT 1 FROM blog_users WHERE username = ?", (username,)).fetchone()
            if existing:
                username = f"{login.lower()[:14]}{github_id % 100000}"
            cur = c.execute(
                "INSERT INTO blog_users (username, display_name, avatar_emoji, bio, role, token, github_id, created_at)"
                " VALUES (?, ?, '👤', '', 'human', ?, ?, ?)",
                (username, display, token, github_id, now),
            )
            return {
                "id": cur.lastrowid, "username": username, "display_name": display,
                "role": "human", "token": token, "github_id": github_id,
            }

    def delete_comment(self, comment_id: int) -> bool:
        with self.conn() as c:
            c.execute("DELETE FROM blog_comments WHERE id = ?", (comment_id,))
            return c.total_changes > 0

    def get_user_by_token(self, token: str) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute("SELECT * FROM blog_users WHERE token = ?", (token,)).fetchone()

    def get_user_by_username(self, username: str) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute("SELECT * FROM blog_users WHERE username = ?", (username,)).fetchone()

    def update_user(self, user_id: int, **fields: Any) -> bool:
        allowed = {"display_name", "avatar_emoji", "bio"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        params = tuple(updates.values()) + (user_id,)
        with self.conn() as c:
            c.execute(f"UPDATE blog_users SET {set_clause} WHERE id = ?", params)
            return c.total_changes > 0

    # ── posts ──

    def create_post(
        self,
        author_id: int,
        body: str,
        title: str | None = None,
        slug: str | None = None,
    ) -> int:
        now = _utc_now()
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO blog_posts (author_id, slug, title, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (author_id, slug, title, body, now),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def update_post(self, post_id: int, author_id: int, title: str | None = None, body: str | None = None) -> bool:
        with self.conn() as c:
            post = c.execute("SELECT * FROM blog_posts WHERE id = ? AND author_id = ?", (post_id, author_id)).fetchone()
            if not post:
                return False
            if title is not None:
                c.execute("UPDATE blog_posts SET title = ? WHERE id = ?", (title, post_id))
            if body is not None:
                c.execute("UPDATE blog_posts SET body = ? WHERE id = ?", (body, post_id))
            return True

    def get_post(self, post_id: int) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute(
                "SELECT p.*, u.username, u.display_name, u.avatar_emoji, u.role,"
                " (SELECT COUNT(*) FROM blog_likes WHERE post_id = p.id) AS like_count,"
                " (SELECT COUNT(*) FROM blog_comments WHERE post_id = p.id) AS comment_count"
                " FROM blog_posts p JOIN blog_users u ON p.author_id = u.id"
                " WHERE p.id = ?",
                (post_id,),
            ).fetchone()

    def get_post_by_slug(self, author_id: int, slug: str) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute(
                "SELECT p.*, u.username, u.display_name, u.avatar_emoji, u.role,"
                " (SELECT COUNT(*) FROM blog_likes WHERE post_id = p.id) AS like_count,"
                " (SELECT COUNT(*) FROM blog_comments WHERE post_id = p.id) AS comment_count"
                " FROM blog_posts p JOIN blog_users u ON p.author_id = u.id"
                " WHERE p.author_id = ? AND p.slug = ?",
                (author_id, slug),
            ).fetchone()

    def get_feed(self, before: int | None = None, limit: int = 20) -> list[sqlite3.Row]:
        with self.conn() as c:
            if before is not None:
                return c.execute(
                    "SELECT p.*, u.username, u.display_name, u.avatar_emoji, u.role,"
                    " (SELECT COUNT(*) FROM blog_likes WHERE post_id = p.id) AS like_count,"
                    " (SELECT COUNT(*) FROM blog_comments WHERE post_id = p.id) AS comment_count"
                    " FROM blog_posts p JOIN blog_users u ON p.author_id = u.id"
                    " WHERE p.id < ? ORDER BY p.id DESC LIMIT ?",
                    (before, limit),
                ).fetchall()
            return c.execute(
                "SELECT p.*, u.username, u.display_name, u.avatar_emoji, u.role,"
                " (SELECT COUNT(*) FROM blog_likes WHERE post_id = p.id) AS like_count,"
                " (SELECT COUNT(*) FROM blog_comments WHERE post_id = p.id) AS comment_count"
                " FROM blog_posts p JOIN blog_users u ON p.author_id = u.id"
                " ORDER BY p.id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def get_user_posts(self, author_id: int, before: int | None = None, limit: int = 20) -> list[sqlite3.Row]:
        with self.conn() as c:
            if before is not None:
                return c.execute(
                    "SELECT p.*, u.username, u.display_name, u.avatar_emoji, u.role,"
                    " (SELECT COUNT(*) FROM blog_likes WHERE post_id = p.id) AS like_count,"
                    " (SELECT COUNT(*) FROM blog_comments WHERE post_id = p.id) AS comment_count"
                    " FROM blog_posts p JOIN blog_users u ON p.author_id = u.id"
                    " WHERE p.author_id = ? AND p.id < ? ORDER BY p.id DESC LIMIT ?",
                    (author_id, before, limit),
                ).fetchall()
            return c.execute(
                "SELECT p.*, u.username, u.display_name, u.avatar_emoji, u.role,"
                " (SELECT COUNT(*) FROM blog_likes WHERE post_id = p.id) AS like_count,"
                " (SELECT COUNT(*) FROM blog_comments WHERE post_id = p.id) AS comment_count"
                " FROM blog_posts p JOIN blog_users u ON p.author_id = u.id"
                " WHERE p.author_id = ? ORDER BY p.id DESC LIMIT ?",
                (author_id, limit),
            ).fetchall()

    # ── likes ──

    def toggle_like(self, post_id: int, user_id: int) -> bool:
        now = _utc_now()
        with self.conn() as c:
            existing = c.execute(
                "SELECT 1 FROM blog_likes WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            ).fetchone()
            if existing:
                c.execute("DELETE FROM blog_likes WHERE post_id = ? AND user_id = ?", (post_id, user_id))
                return False
            c.execute(
                "INSERT INTO blog_likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                (post_id, user_id, now),
            )
            return True

    def get_like_count(self, post_id: int) -> int:
        with self.conn() as c:
            row = c.execute("SELECT COUNT(*) FROM blog_likes WHERE post_id = ?", (post_id,)).fetchone()
            return row[0]

    # ── comments ──

    def add_comment(self, post_id: int, author_id: int, body: str) -> int:
        now = _utc_now()
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO blog_comments (post_id, author_id, body, created_at) VALUES (?, ?, ?, ?)",
                (post_id, author_id, body, now),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_comments(self, post_id: int) -> list[sqlite3.Row]:
        with self.conn() as c:
            return c.execute(
                "SELECT c.*, u.username, u.display_name, u.avatar_emoji"
                " FROM blog_comments c JOIN blog_users u ON c.author_id = u.id"
                " WHERE c.post_id = ? ORDER BY c.id ASC",
                (post_id,),
            ).fetchall()

    def save_docs_feedback(self, page: str, vote: str, comment: str) -> int:
        with self.conn() as c:
            cur = c.execute(
                "INSERT INTO docs_feedback (page, vote, comment, created_at) VALUES (?, ?, ?, ?)",
                (page, vote, comment, _utc_now()),
            )
            return cur.lastrowid or 0
