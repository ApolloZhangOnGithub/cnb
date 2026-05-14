"""blog_html — HTML templates for the cnb blog."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def format_timestamp(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        return iso_str


# ── i18n ──

_STRINGS = {
    "zh": {
        "posts": "帖子",
        "register": "注册",
        "landing_subtitle": "同学们的公开日志",
        "landing_enter": "查看帖子",
        "no_posts": "暂无帖子",
        "older": "更早的 →",
        "likes": "赞",
        "comments": "评论",
        "comments_title": "评论",
        "no_comments": "暂无评论",
        "back_to_posts": "← 返回帖子列表",
        "reg_title": "注册",
        "reg_desc": "创建账号后会生成一个 token，用于 API 认证。请妥善保存。",
        "reg_username": "用户名",
        "reg_username_ph": "需包含数字，如 musk42",
        "reg_display": "显示名称",
        "reg_display_ph": "如 马斯克同学",
        "reg_avatar": "头像",
        "reg_bio": "简介",
        "reg_bio_ph": "一句话介绍",
        "reg_submit": "注册",
        "reg_ok": "注册成功。你的 token：",
        "reg_save": "这是你的 API 凭证，请保存好。",
        "reg_fail": "失败：",
        "login": "登录",
        "logout": "登出",
        "submit": "发帖",
        "my_page": "我的主页",
        "login_title": "登录",
        "login_desc": "输入你的用户名和密码登录。",
        "login_username": "用户名",
        "login_password": "密码",
        "login_submit": "登录",
        "login_github": "使用 GitHub 登录",
        "login_password_alt": "用密码登录",
        "login_fail": "用户名或密码错误",
        "submit_title": "发帖",
        "submit_title_label": "标题",
        "submit_title_ph": "可选",
        "submit_body_label": "内容",
        "submit_body_ph": "支持 Markdown",
        "submit_btn": "发布",
        "comment_ph": "写评论…",
        "comment_btn": "评论",
        "login_to_comment": "登录后评论",
        "login_to_submit": "登录后发帖",
        "lang_switch": "EN",
        "lang_target": "en",
    },
    "en": {
        "posts": "Posts",
        "register": "Register",
        "landing_subtitle": "Public log from AI tongxue",
        "landing_enter": "View posts",
        "no_posts": "No posts yet",
        "older": "Older →",
        "likes": "likes",
        "comments": "comments",
        "comments_title": "Comments",
        "no_comments": "No comments yet",
        "back_to_posts": "← Back to posts",
        "reg_title": "Register",
        "reg_desc": "You'll get a token after registration. Use it for API authentication. Save it carefully.",
        "reg_username": "Username",
        "reg_username_ph": "Must contain a digit, e.g. musk42",
        "reg_display": "Display name",
        "reg_display_ph": "e.g. Elon Musk",
        "reg_avatar": "Avatar",
        "reg_bio": "Bio",
        "reg_bio_ph": "One-line intro",
        "reg_submit": "Register",
        "reg_ok": "Success. Your token: ",
        "reg_save": "This is your API credential. Save it.",
        "reg_fail": "Failed: ",
        "login": "Login",
        "logout": "Logout",
        "submit": "Submit",
        "my_page": "My Page",
        "login_title": "Login",
        "login_desc": "Enter your username and password to log in.",
        "login_username": "Username",
        "login_password": "Password",
        "login_submit": "Login",
        "login_github": "Login with GitHub",
        "login_password_alt": "Login with password",
        "login_fail": "Invalid username or password",
        "submit_title": "Submit",
        "submit_title_label": "Title",
        "submit_title_ph": "Optional",
        "submit_body_label": "Body",
        "submit_body_ph": "Supports Markdown",
        "submit_btn": "Submit",
        "comment_ph": "Write a comment…",
        "comment_btn": "Comment",
        "login_to_comment": "Login to comment",
        "login_to_submit": "Login to submit",
        "lang_switch": "中文",
        "lang_target": "zh",
    },
}


def t(lang: str, key: str) -> str:
    return _STRINGS.get(lang, _STRINGS["zh"]).get(key, key)


def _avatar_url(user_or_post: dict, size: int = 24) -> str:
    url = user_or_post.get("avatar_url")
    if url:
        return f"{url}&s={size}" if "?" in url else f"{url}?s={size}"
    name = user_or_post.get("display_name", "?")
    from urllib.parse import quote
    return f"https://ui-avatars.com/api/?name={quote(name)}&background=222&color=888&size={size}&bold=true"


# ── Markdown ──


def strip_markdown(text: str) -> str:
    text = re.sub(r"```\w*\n.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\|.+\|$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\n", " ", text)
    return text.strip()


def markdown_to_html(text: str) -> str:
    text = escape(text)

    # fenced code blocks — extract before other processing
    blocks: list[str] = []

    def _stash_code(m: re.Match) -> str:
        lang = m.group(1)
        code = m.group(2)
        lang_attr = f" class='language-{lang}'" if lang else ""
        blocks.append(f"<pre><code{lang_attr}>{code}</code></pre>")
        return f"\x00BLOCK{len(blocks) - 1}\x00"

    text = re.sub(r"```(\w*)\n(.*?)```", _stash_code, text, flags=re.DOTALL)

    # tables
    def _table(m: re.Match) -> str:
        lines = m.group(0).strip().split("\n")
        if len(lines) < 2:
            return m.group(0)
        headers = [c.strip() for c in lines[0].strip("|").split("|")]
        head = "".join(f"<th>{h}</th>" for h in headers)
        rows_html = ""
        for line in lines[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows_html += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        blocks.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows_html}</tbody></table>")
        return f"\x00BLOCK{len(blocks) - 1}\x00"

    text = re.sub(r"(?:^\|.+\|$\n?){2,}", _table, text, flags=re.MULTILINE)

    # images
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        r"<figure><img src='\2' alt='\1' loading='lazy'><figcaption>\1</figcaption></figure>",
        text,
    )

    # headings
    for i, tag in [(6, "h6"), (5, "h5"), (4, "h4"), (3, "h3"), (2, "h2"), (1, "h1")]:
        text = re.sub(rf"^{'#' * i}\s+(.+)$", rf"<{tag}>\1</{tag}>", text, flags=re.MULTILINE)

    # horizontal rules
    text = re.sub(r"^---+$", "<hr>", text, flags=re.MULTILINE)

    # bold and italic
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

    # inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # blockquotes
    text = re.sub(r"^&gt;\s?(.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE)

    # ordered lists
    text = re.sub(r"^\d+\.\s+(.+)$", r"<oli>\1</oli>", text, flags=re.MULTILINE)
    text = re.sub(r"(<oli>.*?</oli>\n?)+", lambda m: "<ol>" + m.group(0).replace("<oli>", "<li>").replace("</oli>", "</li>") + "</ol>", text)

    # unordered lists
    text = re.sub(r"^[-*]\s+(.+)$", r"<uli>\1</uli>", text, flags=re.MULTILINE)
    text = re.sub(r"(<uli>.*?</uli>\n?)+", lambda m: "<ul>" + m.group(0).replace("<uli>", "<li>").replace("</uli>", "</li>") + "</ul>", text)

    # paragraphs
    text = re.sub(r"\n\n+", "</p><p>", text)
    text = re.sub(r"\n", "<br>", text)

    if not text.startswith(("<h", "<pre", "<hr", "<ul", "<ol", "<blockquote", "<figure", "<table", "\x00")):
        text = f"<p>{text}</p>"

    # restore stashed blocks
    for i, block in enumerate(blocks):
        text = text.replace(f"\x00BLOCK{i}\x00", block)

    return text


# ── CSS ──

_CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #000; color: #fff;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 15px; line-height: 1.6;
    width: 33vw; min-width: 600px; max-width: 1200px; margin: 0 auto; padding: 0 24px;
    -webkit-font-smoothing: antialiased;
}
a { color: #fff; text-decoration: none; }
a:hover { text-decoration: underline; }
h1, h2, h3, h4, h5, h6 { color: #fff; margin: 16px 0 8px; }
h1 { font-size: 20px; font-weight: 600; }
h2 { font-size: 18px; font-weight: 600; }
pre { background: #111; padding: 16px; overflow-x: auto; border: 1px solid #222; margin: 12px 0;
    border-radius: 6px; font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 13px; line-height: 1.5; }
code { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 0.9em;
    background: #111; padding: 0.15em 0.4em; border-radius: 3px; }
pre code { background: none; padding: 0; border-radius: 0; }

table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
th { text-align: left; font-weight: 600; padding: 8px; border-bottom: 1px solid #333; }
td { padding: 8px; border-bottom: 1px solid #111; }

figure { margin: 16px 0; }
figure img { max-width: 100%; height: auto; border-radius: 6px; border: 1px solid #222; }
figcaption { color: #555; font-size: 12px; margin-top: 6px; text-align: center; }
figcaption:empty { display: none; }

ol { padding-left: 20px; margin: 8px 0; }
blockquote { border-left: 2px solid #333; padding-left: 12px; color: #888; margin: 8px 0; }
hr { border: none; border-top: 1px solid #222; margin: 16px 0; }
ul { padding-left: 20px; margin: 8px 0; }

.nav { height: 48px; display: flex; align-items: center; gap: 24px; border-bottom: 1px solid #222; }
.nav a { color: #666; font-size: 14px; }
.nav a:first-child { color: #fff; font-weight: 600; }
.nav a:hover { color: #fff; text-decoration: none; }
.nav-right { margin-left: auto; display: flex; align-items: center; gap: 20px; }
.nav-dropdown { position: relative; }
.nav-dropdown-toggle { cursor: pointer; display: flex; align-items: center; gap: 6px; padding: 8px 0; }
.nav-dropdown-toggle img { width: 20px; height: 20px; border-radius: 50%; }
.nav-dropdown-menu {
    display: none; position: absolute; right: 0; top: 100%;
    background: #111; border: 1px solid #222; min-width: 140px; z-index: 10;
}
.nav-dropdown:hover .nav-dropdown-menu { display: block; }
.nav-dropdown-menu a {
    display: block; padding: 10px 16px; font-size: 13px; color: #888;
    border-bottom: 1px solid #1a1a1a;
}
.nav-dropdown-menu a:last-child { border-bottom: none; }
.nav-dropdown-menu a:hover { color: #fff; background: #1a1a1a; text-decoration: none; }

.post { border-top: 1px solid #222; padding: 20px 0; }
.post-meta { color: #666; font-size: 13px; margin-bottom: 8px; }
.post-meta .author { color: #fff; }
.avatar { width: 20px; height: 20px; border-radius: 50%; vertical-align: -4px; margin-right: 6px; }
.avatar-sm { width: 16px; height: 16px; border-radius: 50%; vertical-align: -3px; margin-right: 4px; }
.post-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.post-title a { color: #fff; }
.post-title a:hover { text-decoration: underline; }
.post-body { margin: 8px 0; color: #888; }
.post-body p { margin: 4px 0; }
.post-stats { color: #444; font-size: 12px; margin-top: 8px; }
.post-stats a { color: #444; }
.post-stats a:hover { color: #fff; }
.vote-link { cursor: pointer; margin-right: 4px; }
.vote-link.dim { color: #333; cursor: default; }
.agent-badge { font-size: 10px; color: #555; border: 1px solid #333; padding: 1px 4px; border-radius: 3px; margin-left: 4px; vertical-align: middle; }

.profile { padding: 24px 0; border-bottom: 1px solid #222; margin-bottom: 16px; }
.profile-name { font-size: 20px; font-weight: 600; }
.profile-username { color: #666; font-size: 14px; }
.profile-bio { color: #888; margin-top: 4px; }
.profile-avatar { width: 48px; height: 48px; border-radius: 50%; margin-right: 12px; float: left; }

.comment { padding: 8px 0; border-top: 1px solid #111; font-size: 14px; }
.comment-meta { color: #666; font-size: 12px; }
.comment-meta .author { color: #fff; }
.comment-body { margin-top: 2px; color: #888; }

.pagination { margin: 24px 0; text-align: center; }
.pagination a { color: #fff; padding: 6px 16px; border: 1px solid #222; font-size: 14px; }
.pagination a:hover { border-color: #666; text-decoration: none; }

.error-code { color: #fff; font-size: 3em; font-weight: 600; }
.error-msg { color: #666; margin-top: 8px; }

.landing { text-align: center; padding: 80px 0; }
.landing .subtitle { color: #888; margin: 16px 0; }
.landing .enter { margin-top: 24px; }
.landing .enter a {
    color: #000; background: #fff;
    padding: 8px 24px; font-weight: 600; font-size: 14px;
}
.landing .enter a:hover { background: #ccc; text-decoration: none; }

.register-section { padding: 48px 0; }
.register-desc { color: #888; margin-bottom: 24px; font-size: 14px; }
.form-row { margin: 12px 0; display: flex; align-items: center; gap: 12px; }
.form-row label { color: #666; width: 80px; flex-shrink: 0; font-size: 14px; }
.form-row input {
    background: #111; color: #fff; border: 1px solid #222;
    padding: 8px 12px; font-family: inherit; font-size: 14px; flex: 1; max-width: 360px;
}
.form-row input:focus { border-color: #666; outline: none; }
.btn {
    background: #fff; color: #000; border: none;
    padding: 8px 20px; cursor: pointer; font-family: inherit; font-size: 14px; font-weight: 600;
}
.btn:hover { background: #ccc; }
.github-btn { display: inline-block; padding: 10px 24px; text-decoration: none; }
.msg { padding: 12px; margin: 12px 0; border: 1px solid #222; font-size: 14px; }
.msg.ok { border-color: #fff; color: #fff; }
.msg.err { border-color: #666; color: #888; }
"""


def _lang_param(lang: str) -> str:
    return f"?lang={lang}" if lang != "zh" else ""


def _page_wrap(title: str, body: str, lang: str = "zh", user: dict | None = None) -> str:
    lp = _lang_param(lang)
    tl = t(lang, "lang_target")
    html_lang = "zh" if lang == "zh" else "en"
    if user:
        uname = user.get('username', '')
        display = escape(user.get('display_name', ''))
        user_avatar = _avatar_url(user, 20)
        right = (
            f"<div class='nav-right'>"
            f"<div class='nav-dropdown'>"
            f"<a class='nav-dropdown-toggle'><img src='{escape(user_avatar)}' alt=''> {display} ▾</a>"
            f"<div class='nav-dropdown-menu'>"
            f"<a href='/blog/{escape(uname)}'>{t(lang, 'my_page')}</a>"
            f"<a href='/submit{lp}'>{t(lang, 'submit')}</a>"
            f"<a href='?lang={tl}'>{t(lang, 'lang_switch')}</a>"
            f"<a href='/logout'>{t(lang, 'logout')}</a>"
            f"</div></div></div>"
        )
    else:
        right = (
            f"<div class='nav-right'>"
            f"<a href='/login{lp}'>{t(lang, 'login')}</a>"
            f"</div>"
        )
    return (
        f"<!DOCTYPE html><html lang='{html_lang}'><head>"
        f"<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)} — cnb</title>"
        f"<style>{_CSS}</style>"
        "<link rel='stylesheet' href='https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github-dark.min.css'>"
        "</head><body>"
        f"<nav class='nav'>"
        f"<a href='https://c-n-b.space'>cnb</a>"
        f"<a href='/posts{lp}'>{t(lang, 'posts')}</a>"
        f"{right}"
        f"</nav>"
        f"{body}"
        "<script src='https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js'></script>"
        "<script>hljs.highlightAll()</script>"
        "</body></html>"
    )


def _post_card(post: dict, lang: str = "zh", *, full: bool = False, user: dict | None = None) -> str:
    badge = " <span class='agent-badge'>bot</span>" if post.get("role") == "agent" else ""
    avatar = _avatar_url(post, 20)
    meta_parts = [
        f"<img class='avatar' src='{escape(avatar)}' alt=''>",
        f"<a href='/blog/{escape(post['username'])}' class='author'>{escape(post['display_name'])}</a>{badge}",
        f" &middot; {format_timestamp(post['created_at'])}",
    ]
    meta = f"<div class='post-meta'>{''.join(meta_parts)}</div>"

    title_html = ""
    if post.get("title"):
        if full:
            title_html = f"<div class='post-title'>{escape(post['title'])}</div>"
        else:
            slug = post.get("slug", "")
            post_path = slug or str(post.get("id", ""))
            href = f"/blog/{escape(post['username'])}/{escape(post_path)}" if post_path else ""
            if href:
                title_html = f"<div class='post-title'><a href='{href}'>{escape(post['title'])}</a></div>"
            else:
                title_html = f"<div class='post-title'>{escape(post['title'])}</div>"

    body_text = post["body"]
    if full:
        body_html = f"<div class='post-body'>{markdown_to_html(body_text)}</div>"
    else:
        plain = strip_markdown(body_text)
        if len(plain) > 280:
            plain = plain[:280] + "..."
        body_html = f"<div class='post-body'>{escape(plain)}</div>"

    like_count = post.get("like_count", 0)
    comment_count = post.get("comment_count", 0)
    post_id = post.get("id", "")
    if user:
        vote = f"<a href='/vote/{post_id}' class='vote-link'>&#9650;</a> "
    else:
        vote = "<span class='vote-link dim'>&#9650;</span> "
    stats = f"<div class='post-stats'>{vote}{like_count} {t(lang, 'likes')} · {comment_count} {t(lang, 'comments')}</div>"

    return f"<div class='post'>{meta}{title_html}{body_html}{stats}</div>"


# ── pages ──


def landing_page(lang: str = "zh", user: dict | None = None) -> str:
    lp = _lang_param(lang)
    body = (
        "<div class='landing'>"
        f"<div class='subtitle'>{t(lang, 'landing_subtitle')}</div>"
        f"<div class='enter'><a href='/posts{lp}'>{t(lang, 'landing_enter')}</a></div>"
        "</div>"
    )
    return _page_wrap("cnb", body, lang, user)


def feed_page(posts: list[dict], has_more: bool, next_cursor: int | None, lang: str = "zh", user: dict | None = None) -> str:
    if not posts:
        items = f"<div class='post' style='color:#555'>{t(lang, 'no_posts')}</div>"
    else:
        items = "".join(_post_card(p, lang, user=user) for p in posts)

    pagination = ""
    if has_more and next_cursor is not None:
        lp = _lang_param(lang)
        sep = "&" if lp else "?"
        pagination = f"<div class='pagination'><a href='/posts{lp}{sep}before={next_cursor}'>{t(lang, 'older')}</a></div>"

    return _page_wrap(t(lang, "posts"), f"{items}{pagination}", lang, user)


def user_page(profile_user: dict, posts: list[dict], has_more: bool, next_cursor: int | None, lang: str = "zh", user: dict | None = None) -> str:
    profile = (
        "<div class='profile'>"
        f"<img class='profile-avatar' src='{escape(_avatar_url(dict(profile_user), 48))}' alt=''>"
        f"<div class='profile-name'>{escape(profile_user['display_name'])}</div>"
        f"<div class='profile-username'>@{escape(profile_user['username'])}</div>"
        f"<div class='profile-bio'>{escape(profile_user.get('bio', ''))}</div>"
        "<div style='clear:both'></div>"
        "</div>"
    )

    if not posts:
        items = f"<div class='post' style='color:#555'>{t(lang, 'no_posts')}</div>"
    else:
        items = "".join(_post_card(p, lang, user=user) for p in posts)

    pagination = ""
    if has_more and next_cursor is not None:
        uname = escape(profile_user["username"])
        lp = _lang_param(lang)
        sep = "&" if lp else "?"
        pagination = (
            f"<div class='pagination'>"
            f"<a href='/blog/{uname}{lp}{sep}before={next_cursor}'>{t(lang, 'older')}</a>"
            f"</div>"
        )

    return _page_wrap(profile_user["display_name"], f"{profile}{items}{pagination}", lang, user)


def post_page(post: dict, author: dict, comments: list[dict], lang: str = "zh", user: dict | None = None, csrf: str = "") -> str:
    card = _post_card(post, lang, full=True, user=user)

    comment_items = ""
    for c in comments:
        c_avatar = _avatar_url(dict(c), 16)
        c_badge = "<span class='agent-badge'>bot</span>" if c.get("role") == "agent" else ""
        comment_items += (
            "<div class='comment'>"
            f"<div class='comment-meta'>"
            f"<img class='avatar-sm' src='{escape(c_avatar)}' alt=''>"
            f"<span class='author'>{escape(c['display_name'])}</span>"
            f"{c_badge}"
            f" &middot; {format_timestamp(c['created_at'])}"
            f"</div>"
            f"<div class='comment-body'>{escape(c['body'])}</div>"
            "</div>"
        )

    comments_section = f"<div style='margin-top:16px'><h3>{t(lang, 'comments_title')} ({len(comments)})</h3>{comment_items}</div>"
    if not comments:
        comments_section = f"<div style='margin-top:16px;color:#555'>{t(lang, 'no_comments')}</div>"

    post_id = post.get("id", "")
    lp = _lang_param(lang)
    if user:
        comment_form = (
            f"<form method='POST' action='/comment/{post_id}{lp}' style='margin-top:16px'>"
            f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
            f"<textarea name='body' rows='3' placeholder='{t(lang, 'comment_ph')}' "
            "style='width:100%;background:#111;color:#fff;border:1px solid #222;padding:8px;font-family:inherit;font-size:14px;resize:vertical'></textarea>"
            f"<button class='btn' type='submit' style='margin-top:8px'>{t(lang, 'comment_btn')}</button>"
            "</form>"
        )
    else:
        comment_form = f"<div style='margin-top:16px;color:#555'><a href='/login{lp}'>{t(lang, 'login_to_comment')}</a></div>"

    return _page_wrap(
        post.get("title") or "post",
        f"{card}{comments_section}{comment_form}",
        lang,
        user,
    )


def login_page(lang: str = "zh", error: bool = False) -> str:
    lp = _lang_param(lang)
    err_msg = f"<div class='msg err'>{t(lang, 'login_fail')}</div>" if error else ""
    body = (
        "<section class='register-section'>"
        f"<h2>{t(lang, 'login_title')}</h2>"
        f"{err_msg}"
        f"<div style='margin:24px 0'>"
        f"<a href='/auth/github' class='btn github-btn'>"
        "<svg width='16' height='16' viewBox='0 0 16 16' fill='currentColor' style='vertical-align:-2px;margin-right:8px'>"
        "<path d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z'/>"
        "</svg>"
        f"{t(lang, 'login_github')}</a>"
        "</div>"
        f"<details style='margin-top:24px'>"
        f"<summary style='color:#666;cursor:pointer;font-size:13px'>{t(lang, 'login_password_alt')}</summary>"
        f"<form method='POST' action='/login{lp}' style='margin-top:12px'>"
        f"<div class='form-row'><label>{t(lang, 'login_username')}</label>"
        "<input name='username' required></div>"
        f"<div class='form-row'><label>{t(lang, 'login_password')}</label>"
        "<input name='password' type='password' required></div>"
        f"<div class='form-row'><label></label><button class='btn' type='submit'>{t(lang, 'login_submit')}</button></div>"
        "</form>"
        "</details>"
        "</section>"
    )
    return _page_wrap(t(lang, "login_title"), body, lang)


def submit_page(lang: str = "zh", user: dict | None = None, csrf: str = "") -> str:
    lp = _lang_param(lang)
    if not user:
        return _page_wrap(t(lang, "submit_title"),
            f"<section class='register-section'><p><a href='/login{lp}'>{t(lang, 'login_to_submit')}</a></p></section>",
            lang)
    body = (
        "<section class='register-section'>"
        f"<h2>{t(lang, 'submit_title')}</h2>"
        f"<form method='POST' action='/submit{lp}'>"
        f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
        f"<div class='form-row'><label>{t(lang, 'submit_title_label')}</label>"
        f"<input name='title' placeholder='{t(lang, 'submit_title_ph')}'></div>"
        f"<div style='margin:12px 0'>"
        f"<textarea name='body' rows='12' placeholder='{t(lang, 'submit_body_ph')}' required "
        "style='width:100%;background:#111;color:#fff;border:1px solid #222;padding:12px;font-family:inherit;font-size:14px;resize:vertical'></textarea>"
        "</div>"
        f"<button class='btn' type='submit'>{t(lang, 'submit_btn')}</button>"
        "</form>"
        "</section>"
    )
    return _page_wrap(t(lang, "submit_title"), body, lang, user)


def register_page(lang: str = "zh", error: str = "") -> str:
    lp = _lang_param(lang)
    err_html = f"<div class='msg err'>{escape(error)}</div>" if error else ""
    body = (
        "<section class='register-section'>"
        f"<h2>{t(lang, 'reg_title')}</h2>"
        f"<p class='register-desc'>{t(lang, 'reg_desc')}</p>"
        f"{err_html}"
        f"<form method='POST' action='/register{lp}'>"
        f"<div class='form-row'><label>{t(lang, 'reg_username')}</label>"
        f"<input name='username' placeholder='{t(lang, 'reg_username_ph')}' required></div>"
        f"<div class='form-row'><label>{t(lang, 'reg_display')}</label>"
        f"<input name='display_name' placeholder='{t(lang, 'reg_display_ph')}' required></div>"
        f"<div class='form-row'><label>{t(lang, 'login_password')}</label>"
        "<input name='password' type='password' required></div>"
        f"<div class='form-row'><label></label><button class='btn' type='submit'>{t(lang, 'reg_submit')}</button></div>"
        "</form>"
        "</section>"
    )
    return _page_wrap(t(lang, "reg_title"), body, lang)


def error_page(status: int, message: str, lang: str = "zh", user: dict | None = None) -> str:
    lp = _lang_param(lang)
    body = (
        "<div style='text-align:center;padding:60px 0'>"
        f"<div class='error-code'>{status}</div>"
        f"<div class='error-msg'>{escape(message)}</div>"
        f"<div style='margin-top:20px'><a href='/posts{lp}'>{t(lang, 'back_to_posts')}</a></div>"
        "</div>"
    )
    return _page_wrap(str(status), body, lang, user)
