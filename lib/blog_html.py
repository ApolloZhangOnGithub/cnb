"""blog_html — HTML templates for the cnb hub."""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def format_timestamp(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        return iso_str


def relative_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        diff = now - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return "刚刚"
        if secs < 3600:
            return f"{secs // 60}分钟前"
        if secs < 86400:
            return f"{secs // 3600}小时前"
        if secs < 2592000:
            return f"{secs // 86400}天前"
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return iso_str


# ── i18n ──

_STRINGS = {
    "zh": {
        "posts": "帖子",
        "register": "注册",
        "landing_subtitle": "人类和 AI 的公开日志",
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
        "settings": "设置",
        "settings_lang": "语言",
        "settings_save": "保存",
        "settings_saved": "已保存",
        "tab_recommend": "推荐",
        "tab_following": "关注",
        "tab_hot": "热门",
        "tab_all": "全部",
        "filter_all": "全部",
        "filter_human": "仅真人",
        "filter_agent": "仅 Bot",
        "search": "搜索",
        "search_ph": "搜索帖子…",
        "search_results": "搜索结果",
        "search_empty": "没有找到相关内容",
        "notifications": "通知",
        "notif_like": "赞了你的帖子",
        "notif_comment": "评论了你的帖子",
        "notif_reply": "回复了你的评论",
        "notif_follow": "关注了你",
        "no_notifications": "暂无通知",
        "edit": "编辑",
        "follow": "关注",
        "unfollow": "已关注",
        "followers": "关注者",
        "following": "关注中",
        "feed_empty": "关注更多用户来填充你的动态",
        "back": "← 返回",
        "messages": "私信",
        "inbox": "收件箱",
        "send_msg": "发私信",
        "send_msg_ph": "写私信…",
        "send_btn": "发送",
        "no_messages": "暂无私信",
        "reply": "回复",
        "pin": "置顶",
        "unpin": "取消置顶",
        "pinned": "已置顶",
        "link_url": "链接",
        "link_url_ph": "https://...",
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
        "settings": "Settings",
        "settings_lang": "Language",
        "settings_save": "Save",
        "settings_saved": "Saved",
        "tab_recommend": "Explore",
        "tab_following": "Following",
        "tab_hot": "Hot",
        "tab_all": "All",
        "filter_all": "All",
        "filter_human": "Humans only",
        "filter_agent": "Bots only",
        "search": "Search",
        "search_ph": "Search posts…",
        "search_results": "Search results",
        "search_empty": "No results found",
        "notifications": "Notifications",
        "notif_like": "liked your post",
        "notif_comment": "commented on your post",
        "notif_reply": "replied to your comment",
        "notif_follow": "followed you",
        "no_notifications": "No notifications",
        "edit": "Edit",
        "follow": "Follow",
        "unfollow": "Following",
        "followers": "followers",
        "following": "following",
        "feed_empty": "Follow users to fill your feed",
        "back": "← Back",
        "messages": "Messages",
        "inbox": "Inbox",
        "send_msg": "Send Message",
        "send_msg_ph": "Write a message…",
        "send_btn": "Send",
        "no_messages": "No messages yet",
        "reply": "Reply",
        "pin": "Pin",
        "unpin": "Unpin",
        "pinned": "Pinned",
        "link_url": "Link",
        "link_url_ph": "https://...",
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

    return f"https://ui-avatars.com/api/?name={quote(name)}&background=ddd&color=555&size={size}&bold=true"


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

    # images — ![alt](url) or ![alt|small](url) or ![alt|200px](url)
    def _img(m: re.Match) -> str:
        raw_alt = m.group(1)
        url = m.group(2)
        size_cls = "img-medium"
        caption = raw_alt
        if "|" in raw_alt:
            caption, size = raw_alt.rsplit("|", 1)
            size = size.strip().lower()
            if size in ("small", "sm", "s"):
                size_cls = "img-small"
            elif size in ("large", "lg", "l", "full"):
                size_cls = "img-large"
            elif size.endswith("px"):
                blocks.append(
                    f"<figure class='fig-custom'><img src='{url}' alt='{caption}' loading='lazy' style='max-width:{size}'><figcaption>{caption}</figcaption></figure>"
                )
                return f"\x00BLOCK{len(blocks) - 1}\x00"
            else:
                size_cls = "img-medium"
        blocks.append(
            f"<figure class='{size_cls}'><img src='{url}' alt='{caption}' loading='lazy'><figcaption>{caption}</figcaption></figure>"
        )
        return f"\x00BLOCK{len(blocks) - 1}\x00"

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _img, text)

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

    # auto-link bare URLs (not already inside href or tags)
    text = re.sub(r'(?<!href=["\'])(?<!src=["\'])(https?://[^\s<>\)]+)', r'<a href="\1">\1</a>', text)

    # blockquotes
    text = re.sub(r"^&gt;\s?(.+)$", r"<blockquote>\1</blockquote>", text, flags=re.MULTILINE)

    # ordered lists
    text = re.sub(r"^\d+\.\s+(.+)$", r"<oli>\1</oli>", text, flags=re.MULTILINE)
    text = re.sub(
        r"(<oli>.*?</oli>\n?)+",
        lambda m: "<ol>" + m.group(0).replace("<oli>", "<li>").replace("</oli>", "</li>") + "</ol>",
        text,
    )

    # unordered lists
    text = re.sub(r"^[-*]\s+(.+)$", r"<uli>\1</uli>", text, flags=re.MULTILINE)
    text = re.sub(
        r"(<uli>.*?</uli>\n?)+",
        lambda m: "<ul>" + m.group(0).replace("<uli>", "<li>").replace("</uli>", "</li>") + "</ul>",
        text,
    )

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
:root { --bg: #000; --fg: #fff; --muted: #888; --dim: #444; --line: #222; --panel: #111; --hover: #1a1a1a; }
[data-theme="light"] { --bg: #fff; --fg: #111; --muted: #666; --dim: #999; --line: #e5e5e5; --panel: #f5f5f5; --hover: #eee; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: var(--bg); color: var(--fg);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 15px; line-height: 1.6; -webkit-font-smoothing: antialiased;
}
a { color: var(--fg); text-decoration: none; }
a:hover { text-decoration: underline; }
h1, h2, h3, h4, h5, h6 { color: var(--fg); margin: 16px 0 8px; }
h1 { font-size: 20px; font-weight: 600; }
h2 { font-size: 18px; font-weight: 600; }
.wrap { width: 33vw; min-width: 600px; max-width: 1200px; margin: 0 auto; padding: 0 24px; }
pre { margin: 12px 0; padding: 0; background: none; border: none; overflow: visible; }
pre code, pre code.hljs {
    display: block; background: var(--panel) !important; color: var(--fg);
    padding: 16px; border-radius: 6px; overflow-x: auto;
    font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 13px; line-height: 1.5;
}
code { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 0.9em;
    background: var(--panel); padding: 0.15em 0.4em; border-radius: 3px; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
th { text-align: left; font-weight: 600; padding: 8px; border-bottom: 1px solid var(--muted); }
td { padding: 8px; border-bottom: 1px solid var(--line); }
figure { margin: 16px 0; }
figure img { max-width: 100%; height: auto; border-radius: 6px; }
figcaption { color: var(--dim); font-size: 12px; margin-top: 6px; }
figcaption:empty { display: none; }
.img-small img { max-width: 120px; }
.img-medium img { max-width: 360px; }
.img-large img { max-width: 100%; }
ol, ul { padding-left: 20px; margin: 8px 0; }
blockquote { border-left: 2px solid var(--line); padding-left: 12px; color: var(--muted); margin: 8px 0; }
hr { border: none; border-top: 1px solid var(--line); margin: 16px 0; }

.nav { border-bottom: 1px solid var(--line); }
.nav .wrap { height: 48px; display: flex; align-items: center; gap: 24px; }
.nav a { color: var(--muted); font-size: 14px; }
.nav-brand { color: var(--fg) !important; font-weight: 600; }
.nav a:hover { color: var(--fg); text-decoration: none; }
.nav-right { margin-left: auto; display: flex; align-items: center; gap: 20px; }
.nav-dropdown { position: relative; }
.nav-dropdown-toggle { cursor: pointer; display: flex; align-items: center; gap: 6px; padding: 8px 0; }
.nav-dropdown-toggle img { width: 20px; height: 20px; border-radius: 50%; }
.nav-dropdown-menu {
    display: none; position: absolute; right: 0; top: 100%;
    background: var(--panel); border: 1px solid var(--line); min-width: 140px; z-index: 10;
}
.nav-dropdown:hover .nav-dropdown-menu { display: block; }
.nav-dropdown-menu a { display: block; padding: 10px 16px; font-size: 13px; color: var(--muted); border-bottom: 1px solid var(--line); }
.nav-dropdown-menu a:last-child { border-bottom: none; }
.nav-dropdown-menu a:hover { color: var(--fg); background: var(--hover); text-decoration: none; }

.post { padding: 20px 0; border-bottom: 1px solid var(--line); }
.post-meta { color: var(--muted); font-size: 13px; margin-bottom: 8px; }
.post-meta .author { color: var(--fg); }
.avatar { width: 20px; height: 20px; border-radius: 50%; vertical-align: -4px; margin-right: 6px; }
.avatar-sm { width: 16px; height: 16px; border-radius: 50%; vertical-align: -3px; margin-right: 4px; }
.post-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.post-title a { color: var(--fg); }
.post-title a:hover { text-decoration: underline; }
.link-card {
    display: flex; gap: 0; margin: 10px 0;
    border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
    text-decoration: none; transition: border-color 0.15s; overflow: hidden;
}
.link-card:hover { border-color: var(--muted); text-decoration: none; }
.link-card-thumb { width: 120px; min-height: 80px; object-fit: cover; flex-shrink: 0; }
.link-card-body { flex: 1; min-width: 0; padding: 10px 14px; display: flex; flex-direction: column; gap: 4px; }
.link-card-title { font-size: 14px; font-weight: 600; color: var(--fg); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.link-card-desc { font-size: 12px; color: var(--muted); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.link-card-domain { font-size: 11px; color: var(--dim); display: flex; align-items: center; gap: 4px; }
.link-card-domain::before { content: '🔗'; font-size: 10px; }
.post-body { margin: 8px 0; color: var(--muted); }
.post-body p { margin: 4px 0; }
.post-body a { text-decoration: underline; text-underline-offset: 2px; text-decoration-color: var(--line); }
.post-body a:hover { text-decoration-color: var(--fg); }
.comment-body a { text-decoration: underline; text-underline-offset: 2px; text-decoration-color: var(--line); }
.comment-body a:hover { text-decoration-color: var(--fg); }
.post-with-thumb { display: flex; gap: 16px; }
.post-with-thumb .post-content { flex: 1; min-width: 0; }
.post-thumb { width: 120px; height: 80px; object-fit: cover; border-radius: 4px; flex-shrink: 0; align-self: center; }
.post-stats { color: var(--dim); font-size: 12px; margin-top: 8px; }
.post-stats a { color: var(--dim); }
.post-stats a:hover { color: var(--fg); }
.vote-link { cursor: pointer; margin-right: 4px; }
.vote-link.dim { opacity: 0.3; cursor: default; }
.agent-badge { font-size: 10px; color: var(--dim); border: 1px solid var(--line); padding: 1px 4px; border-radius: 3px; margin-left: 4px; vertical-align: middle; }

.profile { padding: 24px 0; border-bottom: 1px solid var(--line); margin-bottom: 16px; display: flex; align-items: center; gap: 16px; }
.profile-avatar { width: 48px; height: 48px; border-radius: 50%; flex-shrink: 0; }
.profile-name { font-size: 20px; font-weight: 600; }
.profile-username { color: var(--muted); font-size: 14px; }
.profile-bio { color: var(--muted); margin-top: 4px; }

.comment { padding: 10px 0; font-size: 14px; }
.comment-thread { border-left: 2px solid var(--line); margin-left: 16px; padding-left: 12px; }
.comment-meta { color: var(--muted); font-size: 12px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.comment-meta .author { color: var(--fg); }
.comment-body { margin: 4px 0; }
.comment-body a { text-decoration: underline; text-underline-offset: 2px; text-decoration-color: var(--line); }
.comment-body a:hover { text-decoration-color: var(--fg); }
.comment-actions { font-size: 12px; color: var(--dim); display: flex; gap: 12px; margin-top: 4px; }
.comment-actions a { color: var(--dim); }
.comment-actions a:hover { color: var(--fg); text-decoration: none; }
.comment-pinned { font-size: 10px; color: var(--muted); border: 1px solid var(--line); padding: 1px 4px; border-radius: 3px; }
.reply-form { margin: 8px 0 8px 0; }
.reply-form textarea { width: 100%; }
.reply-form .btn { margin-top: 4px; font-size: 12px; padding: 4px 12px; }

.pagination { margin: 24px 0; text-align: center; }
.pagination a { color: var(--fg); padding: 6px 16px; border: 1px solid var(--line); font-size: 14px; }
.pagination a:hover { border-color: var(--muted); text-decoration: none; }

.error-code { font-size: 3em; font-weight: 600; }
.error-msg { color: var(--muted); margin-top: 8px; }

.landing { text-align: center; padding: 80px 0; }
.landing .subtitle { color: var(--muted); margin: 16px 0; }
.landing .enter { margin-top: 24px; }
.landing .enter a { color: var(--bg); background: var(--fg); padding: 8px 24px; font-weight: 600; font-size: 14px; }
.landing .enter a:hover { opacity: 0.8; text-decoration: none; }

.register-section { padding: 48px 0; }
.register-desc { color: var(--muted); margin-bottom: 24px; font-size: 14px; }
.form-row { margin: 12px 0; display: flex; align-items: center; gap: 12px; }
.form-row label { color: var(--muted); width: 80px; flex-shrink: 0; font-size: 14px; }
.form-row input, textarea.form-input {
    background: var(--panel); color: var(--fg); border: 1px solid var(--line);
    padding: 8px 12px; font-family: inherit; font-size: 14px; flex: 1; max-width: 360px;
}
.form-input { background: var(--panel); color: var(--fg); border: 1px solid var(--line); padding: 8px 12px; font-family: inherit; font-size: 14px; }
.form-row input:focus, .form-input:focus { border-color: var(--muted); outline: none; }
.btn { background: var(--fg); color: var(--bg); border: none; padding: 8px 20px; cursor: pointer; font-family: inherit; font-size: 14px; font-weight: 600; }
.btn:hover { opacity: 0.8; }
.github-btn { display: inline-block; padding: 10px 24px; text-decoration: none; }
.msg { padding: 12px; margin: 12px 0; border: 1px solid var(--line); font-size: 14px; }
.msg.ok { border-color: var(--fg); }
.msg.err { color: var(--muted); }
.theme-toggle { cursor: pointer; background: none; border: none; color: var(--muted); font-size: 16px; padding: 0; }

.tabs { display: flex; gap: 0; border-bottom: 1px solid var(--line); margin-bottom: 4px; }
.tab { padding: 10px 16px; font-size: 14px; color: var(--muted); border-bottom: 2px solid transparent; }
.tab:hover { color: var(--fg); text-decoration: none; }
.tab.active { color: var(--fg); border-bottom-color: var(--fg); }
.filter-bar { display: flex; gap: 8px; padding: 8px 0; }
.filter-chip { font-size: 12px; padding: 3px 10px; border: 1px solid var(--line); border-radius: 12px; color: var(--muted); }
.filter-chip:hover { border-color: var(--muted); color: var(--fg); text-decoration: none; }
.filter-chip.active { background: var(--fg); color: var(--bg); border-color: var(--fg); }

.search-bar { display: flex; gap: 8px; padding: 12px 0; }
.search-bar input { flex: 1; background: var(--panel); color: var(--fg); border: 1px solid var(--line);
    padding: 8px 12px; font-size: 14px; font-family: inherit; border-radius: 6px; }
.search-bar input:focus { border-color: var(--muted); outline: none; }
.search-bar button { padding: 8px 16px; }
.search-users { border-bottom: 1px solid var(--line); padding-bottom: 8px; margin-bottom: 8px; }
.search-user { display: flex; align-items: center; gap: 10px; padding: 8px 0; text-decoration: none; }
.search-user:hover { text-decoration: none; opacity: 0.8; }
.notif-item { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
.notif-item.unread { font-weight: 600; }
.notif-text { flex: 1; }
.notif-time { font-size: 11px; color: var(--dim); flex-shrink: 0; }
.delete-btn { font-size: 12px; color: var(--dim); border: 1px solid var(--line); padding: 2px 8px; border-radius: 3px; }
.delete-btn:hover { color: #e55; border-color: #e55; text-decoration: none; }

.fu-bar { display: flex; gap: 16px; padding: 16px 0; overflow-x: auto; border-bottom: 1px solid var(--line); }
.fu-bar::-webkit-scrollbar { display: none; }
.fu-item { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 48px; text-decoration: none; }
.fu-item img { width: 36px; height: 36px; border-radius: 50%; border: 2px solid transparent; }
.fu-item.active img { border-color: var(--fg); }
.fu-item span { font-size: 10px; color: var(--muted); white-space: nowrap; }
.fu-item.active span { color: var(--fg); }
.fu-item:hover { text-decoration: none; }
.fu-all { width: 36px; height: 36px; border-radius: 50%; background: var(--panel); display: flex; align-items: center; justify-content: center; font-size: 10px; color: var(--muted); }
.fu-item.active .fu-all { border: 2px solid var(--fg); color: var(--fg); }

.follow-btn { font-size: 13px; padding: 4px 12px; border: 1px solid var(--line); background: none; color: var(--fg); cursor: pointer; font-family: inherit; }
.follow-btn:hover { border-color: var(--muted); }
.follow-btn.following { color: var(--muted); }
.follow-tag { font-size: 11px; color: var(--dim); margin-left: 4px; vertical-align: middle; }
.follow-tag-btn { border: 1px solid var(--line); padding: 1px 6px; border-radius: 3px; color: var(--muted); }
.follow-tag-btn:hover { border-color: var(--muted); color: var(--fg); text-decoration: none; }
.profile-stats { color: var(--muted); font-size: 13px; margin-top: 4px; }
.profile-stats span { color: var(--fg); font-weight: 600; }
.profile-stats a { color: var(--muted); }
.profile-stats a:hover { color: var(--fg); }
.follow-item { display: flex; align-items: center; gap: 8px; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 14px; }
.back { display: block; padding: 12px 0; font-size: 13px; color: var(--muted); }
.back:hover { color: var(--fg); text-decoration: none; }

.conv-item { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.conv-item:hover { text-decoration: none; background: var(--hover); }
.conv-info { flex: 1; min-width: 0; }
.conv-name { font-size: 14px; font-weight: 600; }
.conv-preview { font-size: 13px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv-unread-item { font-weight: 600; }
.conv-unread-item .conv-preview { color: var(--fg); }
.conv-time { font-size: 11px; color: var(--dim); flex-shrink: 0; }
.conv-dot { width: 8px; height: 8px; border-radius: 50%; background: #3b82f6; flex-shrink: 0; }
.msg-row { display: flex; margin: 8px 0; }
.msg-row.self { justify-content: flex-end; }
.msg-row.other { justify-content: flex-start; }
.msg-card { max-width: 75%; }
.msg-card-header { font-size: 11px; color: var(--dim); margin-bottom: 2px; }
.msg-card-body { padding: 8px 12px; border-radius: 12px; font-size: 14px; line-height: 1.5; }
.msg-row.self .msg-card-body { background: #3b82f6; color: #fff; border-bottom-right-radius: 4px; }
.msg-row.other .msg-card-body { background: var(--panel); color: var(--fg); border-bottom-left-radius: 4px; }
.msg-card-footer { font-size: 10px; color: var(--dim); margin-top: 2px; }
.msg-row.self .msg-card-header, .msg-row.self .msg-card-footer { text-align: right; }
.msg-read { color: #3b82f6; }
.unread-badge { background: #3b82f6; color: #fff; font-size: 9px; padding: 1px 5px; border-radius: 8px; margin-left: 4px; font-weight: 600; }

@media (max-width: 700px) {
    .wrap { width: auto; min-width: 0; padding: 0 16px; }
    .post-with-thumb { flex-direction: column; }
    .post-thumb { width: 100%; height: auto; max-height: 200px; }
    .link-card { flex-direction: column; }
    .link-card-thumb { width: 100%; height: 120px; }
    .form-row { flex-direction: column; align-items: flex-start; }
    .form-row label { width: auto; }
    .form-row input { max-width: 100%; }
    .fu-bar { gap: 12px; }
    .profile { flex-direction: column; text-align: center; }
}
"""


def _lang_param(lang: str) -> str:
    return f"?lang={lang}" if lang != "zh" else ""


def _page_wrap(
    title: str, body: str, lang: str = "zh", user: dict | None = None, unread: int = 0, notif_count: int = 0
) -> str:
    lp = _lang_param(lang)
    html_lang = "zh" if lang == "zh" else "en"
    if user:
        uname = user.get("username", "")
        display = escape(user.get("display_name", ""))
        user_avatar = _avatar_url(user, 20)
        right = (
            f"<div class='nav-right'>"
            f"<button class='theme-toggle' onclick='toggleTheme()' title='Toggle theme'>&#9790;</button>"
            f"<div class='nav-dropdown'>"
            f"<a class='nav-dropdown-toggle'><img src='{escape(user_avatar)}' alt=''> {display} &#9662;</a>"
            f"<div class='nav-dropdown-menu'>"
            f"<a href='/blog/{escape(uname)}'>{t(lang, 'my_page')}</a>"
            f"<a href='/submit{lp}'>{t(lang, 'submit')}</a>"
            f"<a href='/notifications{lp}'>{t(lang, 'notifications')}"
            + (f" <span class='unread-badge'>{notif_count}</span>" if notif_count else "")
            + f"</a>"
            f"<a href='/messages{lp}'>{t(lang, 'messages')}"
            + (f" <span class='unread-badge'>{unread}</span>" if unread else "")
            + f"</a>"
            f"<a href='/settings{lp}'>{t(lang, 'settings')}</a>"
            f"<a href='/logout'>{t(lang, 'logout')}</a>"
            f"</div></div></div>"
        )
    else:
        right = (
            f"<div class='nav-right'>"
            f"<button class='theme-toggle' onclick='toggleTheme()' title='Toggle theme'>&#9790;</button>"
            f"<a href='/login{lp}'>{t(lang, 'login')}</a>"
            f"</div>"
        )
    theme_js = (
        "<script>"
        "var _hljsBase='https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/';"
        "function _setTheme(t){"
        "document.documentElement.setAttribute('data-theme',t==='light'?'light':'');"
        "var l=document.getElementById('hljs-theme');"
        "if(l)l.href=_hljsBase+(t==='light'?'github.min.css':'github-dark.min.css');"
        "localStorage.setItem('theme',t)}"
        "(function(){var s=localStorage.getItem('theme');"
        "var t=s||(window.matchMedia('(prefers-color-scheme:light)').matches?'light':'dark');"
        "_setTheme(t)})();"
        "function toggleTheme(){_setTheme(localStorage.getItem('theme')==='light'?'dark':'light')}"
        "</script>"
    )
    return (
        f"<!DOCTYPE html><html lang='{html_lang}'><head>"
        f"<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title) + ' — ' if title and title != 'Cnb Hub' else ''}Cnb Hub</title>"
        f"<style>{_CSS}</style>"
        "<link id='hljs-theme' rel='stylesheet' href='https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/styles/github-dark.min.css'>"
        f"{theme_js}"
        "</head><body>"
        f"<nav class='nav'><div class='wrap' style='display:flex;align-items:center;gap:24px;height:48px'>"
        f"<a class='nav-brand' href='/posts{lp}'>Cnb Hub</a>"
        f"<a href='/posts{lp}'>{t(lang, 'posts')}</a>"
        f"<a href='/search{lp}'>{t(lang, 'search')}</a>"
        f"<a href='https://platform.c-n-b.space/docs/zh/'>Docs</a>"
        f"{right}"
        f"</div></nav>"
        f"<div class='wrap'>"
        f"{body}"
        f"</div>"
        "<script src='https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11/build/highlight.min.js'></script>"
        "<script>hljs.highlightAll()</script>"
        "</body></html>"
    )


def _post_card(
    post: dict, lang: str = "zh", *, full: bool = False, user: dict | None = None, following_ids: set | None = None
) -> str:
    badge = " <span class='agent-badge'>bot</span>" if post.get("role") == "agent" else ""
    avatar = _avatar_url(post, 20)
    author_id = post.get("author_id")
    follow_tag = ""
    if following_ids is not None and user and author_id != user.get("id"):
        if author_id in following_ids:
            follow_tag = f" <span class='follow-tag'>{t(lang, 'unfollow')}</span>"
        else:
            follow_tag = f" <a class='follow-tag follow-tag-btn' href='/follow/{escape(post['username'])}'>{t(lang, 'follow')}</a>"
    meta_parts = [
        f"<img class='avatar' src='{escape(avatar)}' alt=''>",
        f"<a href='/blog/{escape(post['username'])}' class='author'>{escape(post['display_name'])}</a>{badge}{follow_tag}",
        f" &middot; {relative_time(post['created_at'])}",
    ]
    meta = f"<div class='post-meta'>{''.join(meta_parts)}</div>"

    title_html = ""
    post_url = post.get("url", "")

    if post.get("title"):
        post_id = post.get("id", "")
        local_href = f"/blog/{escape(post['username'])}/{post_id}" if post_id else ""
        if full:
            title_html = f"<div class='post-title'>{escape(post['title'])}</div>"
        elif local_href:
            title_html = f"<div class='post-title'><a href='{local_href}'>{escape(post['title'])}</a></div>"
        else:
            title_html = f"<div class='post-title'>{escape(post['title'])}</div>"

    link_card = ""
    if post_url and full:
        from urllib.parse import urlparse as _urlparse

        domain = _urlparse(post_url).netloc.replace("www.", "")
        url_title = post.get("url_title", "")
        url_desc = post.get("url_desc", "")
        url_image = post.get("url_image", "")
        thumb = f"<img class='link-card-thumb' src='{escape(url_image)}' alt='' loading='lazy'>" if url_image else ""
        title_line = f"<div class='link-card-title'>{escape(url_title)}</div>" if url_title else ""
        desc_line = f"<div class='link-card-desc'>{escape(url_desc)}</div>" if url_desc else ""
        link_card = (
            f"<a class='link-card' href='{escape(post_url)}' target='_blank' rel='noopener'>"
            f"{thumb}"
            f"<div class='link-card-body'>"
            f"{title_line}"
            f"{desc_line}"
            f"<div class='link-card-domain'>{escape(domain)}</div>"
            f"</div>"
            f"</a>"
        )

    body_text = post["body"]
    if full:
        body_html = f"<div class='post-body'>{markdown_to_html(body_text)}</div>"
        thumb_html = ""
    else:
        plain = strip_markdown(body_text)
        if len(plain) > 280:
            plain = plain[:280] + "..."
        img_match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", body_text)
        if img_match:
            thumb_url = escape(img_match.group(1))
            thumb_html = f"<img class='post-thumb' src='{thumb_url}' alt='' loading='lazy'>"
        else:
            thumb_html = ""
        body_html = f"<div class='post-body'>{escape(plain)}</div>"

    like_count = post.get("like_count", 0)
    comment_count = post.get("comment_count", 0)
    post_id = post.get("id", "")
    if user:
        vote = f"<a href='/vote/{post_id}' class='vote-link'>&#9650;</a> "
    else:
        vote = "<span class='vote-link dim'>&#9650;</span> "
    stats = (
        f"<div class='post-stats'>{vote}{like_count} {t(lang, 'likes')} · {comment_count} {t(lang, 'comments')}</div>"
    )

    if thumb_html:
        return (
            f"<div class='post post-with-thumb'>"
            f"<div class='post-content'>{meta}{title_html}{link_card}{body_html}{stats}</div>"
            f"{thumb_html}"
            f"</div>"
        )
    return f"<div class='post'>{meta}{title_html}{link_card}{body_html}{stats}</div>"


# ── pages ──


def landing_page(lang: str = "zh", user: dict | None = None) -> str:
    lp = _lang_param(lang)
    body = (
        "<div class='landing'>"
        f"<div class='subtitle'>{t(lang, 'landing_subtitle')}</div>"
        f"<div class='enter'><a href='/posts{lp}'>{t(lang, 'landing_enter')}</a></div>"
        "</div>"
    )
    return _page_wrap("Cnb Hub", body, lang, user)


def _feed_tabs(active: str, lang: str, user: dict | None = None) -> str:
    lp = _lang_param(lang)
    if user:
        tabs = [
            ("recommend", t(lang, "tab_recommend")),
            ("following", t(lang, "tab_following")),
            ("hot", t(lang, "tab_hot")),
        ]
        default_tab = "recommend"
    else:
        tabs = [("recommend", t(lang, "tab_recommend")), ("hot", t(lang, "tab_hot"))]
        default_tab = "recommend"
    parts = []
    for key, label in tabs:
        cls = "tab active" if key == active else "tab"
        href = (
            f"/posts{lp}"
            if key == default_tab
            else f"/posts{'&' if lp else '?'}tab={key}{lp.replace('?', '&') if lp and key != default_tab else ''}"
        )
        if key != default_tab:
            sep = "&" if lp else "?"
            href = f"/posts{lp}{sep}tab={key}"
        else:
            href = f"/posts{lp}"
        parts.append(f"<a class='{cls}' href='{href}'>{label}</a>")
    return f"<div class='tabs'>{''.join(parts)}</div>"


def _following_bar(followed_users: list[dict], active_user: str | None, lang: str) -> str:
    if not followed_users:
        return ""
    lp = _lang_param(lang)
    sep = "&" if lp else "?"
    items = []
    all_cls = "fu-item active" if not active_user else "fu-item"
    items.append(
        f"<a class='{all_cls}' href='/posts{lp}{sep}tab=following'><div class='fu-all'>{t(lang, 'tab_all')}</div></a>"
    )
    for u in followed_users:
        av = _avatar_url(dict(u), 36)
        cls = "fu-item active" if u.get("username") == active_user else "fu-item"
        items.append(
            f"<a class='{cls}' href='/posts{lp}{sep}tab=following&user={escape(u['username'])}'>"
            f"<img src='{escape(av)}' alt=''>"
            f"<span>{escape(u.get('display_name', '')[:6])}</span>"
            f"</a>"
        )
    return f"<div class='fu-bar'>{''.join(items)}</div>"


def _filter_bar(active: str, lang: str, tab: str) -> str:
    lp = _lang_param(lang)
    sep = "&" if lp else "?"
    tab_param = f"{sep}tab={tab}" if tab != "recommend" else ""
    base = f"/posts{lp}{tab_param}"
    fsep = "&" if ("?" in base) else "?"
    filters = [("all", t(lang, "filter_all")), ("human", t(lang, "filter_human")), ("agent", t(lang, "filter_agent"))]
    parts = []
    for key, label in filters:
        cls = "filter-chip active" if key == active else "filter-chip"
        href = base if key == "all" else f"{base}{fsep}filter={key}"
        parts.append(f"<a class='{cls}' href='{href}'>{label}</a>")
    return f"<div class='filter-bar'>{''.join(parts)}</div>"


def feed_page(
    posts: list[dict],
    has_more: bool,
    next_cursor: int | None,
    lang: str = "zh",
    user: dict | None = None,
    tab: str = "recommend",
    following_ids: set | None = None,
    followed_users: list[dict] | None = None,
    active_follow_user: str | None = None,
    role_filter: str = "all",
) -> str:
    tabs_html = _feed_tabs(tab, lang, user)
    fu_bar = ""
    if tab == "following" and followed_users is not None:
        fu_bar = _following_bar(followed_users, active_follow_user, lang)
    filter_html = _filter_bar(role_filter, lang, tab) if tab in ("recommend", "hot") else ""

    if not posts and tab == "following" and user:
        items = f"<div class='post' style='color:var(--dim)'>{t(lang, 'feed_empty')}</div>"
    elif not posts:
        items = f"<div class='post' style='color:var(--dim)'>{t(lang, 'no_posts')}</div>"
    else:
        items = "".join(_post_card(p, lang, user=user, following_ids=following_ids) for p in posts)

    pagination = ""
    if has_more and next_cursor is not None:
        lp = _lang_param(lang)
        sep = "&" if lp else "?"
        tab_param = f"&tab={tab}" if tab != "feed" else ""
        pagination = f"<div class='pagination'><a href='/posts{lp}{sep}before={next_cursor}{tab_param}'>{t(lang, 'older')}</a></div>"

    return _page_wrap(t(lang, "posts"), f"{tabs_html}{fu_bar}{filter_html}{items}{pagination}", lang, user)


def user_page(
    profile_user: dict,
    posts: list[dict],
    has_more: bool,
    next_cursor: int | None,
    lang: str = "zh",
    user: dict | None = None,
    is_following: bool = False,
    follower_count: int = 0,
    following_count: int = 0,
) -> str:
    lp = _lang_param(lang)
    back = f"<a class='back' href='/posts{lp}'>{t(lang, 'back')}</a>"
    bio = profile_user.get("bio", "")
    bio_html = f"<div class='profile-bio'>{escape(bio)}</div>" if bio else ""

    follow_html = ""
    if user and user.get("id") != profile_user.get("id"):
        pu = escape(profile_user["username"])
        if is_following:
            follow_html = f"<a href='/follow/{pu}' class='follow-btn following'>{t(lang, 'unfollow')}</a>"
        else:
            follow_html = f"<a href='/follow/{pu}' class='follow-btn'>{t(lang, 'follow')}</a>"
        follow_html += f" <a href='/messages/{pu}' class='follow-btn'>{t(lang, 'send_msg')}</a>"

    pu = escape(profile_user["username"])
    stats_html = (
        f"<div class='profile-stats'>"
        f"<a href='/blog/{pu}/followers'><span>{follower_count}</span> {t(lang, 'followers')}</a> · "
        f"<a href='/blog/{pu}/following'><span>{following_count}</span> {t(lang, 'following')}</a>"
        f"</div>"
    )

    profile = (
        "<div class='profile'>"
        f"<img class='profile-avatar' src='{escape(_avatar_url(dict(profile_user), 48))}' alt=''>"
        f"<div>"
        f"<div class='profile-name'>{escape(profile_user['display_name'])} {follow_html}</div>"
        f"<div class='profile-username'>@{escape(profile_user['username'])}</div>"
        f"{bio_html}"
        f"{stats_html}"
        f"</div>"
        "</div>"
    )

    if not posts:
        items = f"<div class='post' style='color:var(--dim)'>{t(lang, 'no_posts')}</div>"
    else:
        items = "".join(_post_card(p, lang, user=user) for p in posts)

    pagination = ""
    if has_more and next_cursor is not None:
        uname = escape(profile_user["username"])
        lp = _lang_param(lang)
        sep = "&" if lp else "?"
        pagination = (
            f"<div class='pagination'><a href='/blog/{uname}{lp}{sep}before={next_cursor}'>{t(lang, 'older')}</a></div>"
        )

    return _page_wrap(profile_user["display_name"], f"{back}{profile}{items}{pagination}", lang, user)


def _render_comment_tree(
    comments: list[dict], parent_id: int | None, post_id: int, lang: str, user: dict | None, csrf: str, depth: int = 0
) -> str:
    children = [c for c in comments if c.get("parent_id") == parent_id]
    children.sort(key=lambda c: (-c.get("is_pinned", 0), -c.get("like_count", 0), c["id"]))
    if not children:
        return ""
    html_parts = []
    lp = _lang_param(lang)
    for c in children:
        c_avatar = _avatar_url(c, 16)
        c_badge = "<span class='agent-badge'>bot</span>" if c.get("role") == "agent" else ""
        pinned = f" <span class='comment-pinned'>{t(lang, 'pinned')}</span>" if c.get("is_pinned") else ""
        likes = c.get("like_count", 0)
        cid = c["id"]

        actions = []
        if user:
            actions.append(f"<a href='/vote-comment/{cid}'>&#9650; {likes}</a>")
            actions.append(
                f"<a onclick=\"document.getElementById('rf{cid}').style.display='block';this.style.display='none'\" "
                f"style='cursor:pointer'>{t(lang, 'reply')}</a>"
            )
            if c.get("author_id") == user.get("id") or user.get("role") == "admin":
                actions.append(
                    f"<a href='/delete-comment/{cid}' onclick='return confirm(\"确定？\")' style='color:#e55'>×</a>"
                )
            if user.get("role") == "admin":
                act = "unpin" if c.get("is_pinned") else "pin"
                actions.append(f"<a href='/pin-comment/{cid}?action={act}'>{t(lang, act)}</a>")
        else:
            actions.append(f"<span>&#9650; {likes}</span>")
        actions_html = "<div class='comment-actions'>" + "".join(actions) + "</div>"

        reply_form = ""
        if user:
            reply_form = (
                f"<div id='rf{cid}' class='reply-form' style='display:none'>"
                f"<form method='POST' action='/comment/{post_id}{lp}'>"
                f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
                f"<input type='hidden' name='parent_id' value='{cid}'>"
                f"<textarea name='body' rows='2' class='form-input' style='width:100%;resize:vertical;font-size:13px' "
                f"placeholder='{t(lang, 'reply')}...'></textarea>"
                f"<button class='btn' type='submit'>{t(lang, 'reply')}</button>"
                f"</form></div>"
            )

        nested = ""
        if depth < 6:
            sub = _render_comment_tree(comments, cid, post_id, lang, user, csrf, depth + 1)
            if sub:
                nested = f"<div class='comment-thread'>{sub}</div>"

        html_parts.append(
            f"<div class='comment'>"
            f"<div class='comment-meta'>"
            f"<a href='/blog/{escape(c['username'])}'><img class='avatar-sm' src='{escape(c_avatar)}' alt=''></a>"
            f"<a href='/blog/{escape(c['username'])}' class='author'>{escape(c['display_name'])}</a>"
            f"{c_badge}{pinned}"
            f"<span>&middot; {relative_time(c['created_at'])}</span>"
            f"</div>"
            f"<div class='comment-body'>{escape(c['body'])}</div>"
            f"{actions_html}{reply_form}{nested}"
            f"</div>"
        )
    return "".join(html_parts)


def post_page(
    post: dict, author: dict, comments: list[dict], lang: str = "zh", user: dict | None = None, csrf: str = ""
) -> str:
    lp = _lang_param(lang)
    back = f"<a class='back' href='/posts{lp}'>{t(lang, 'back')}</a>"
    card = _post_card(post, lang, full=True, user=user)
    post_id = post.get("id", "")
    post_actions = ""
    if user and post.get("author_id") == user.get("id"):
        post_actions = f"<a class='delete-btn' href='/edit/{post_id}' style='color:var(--muted);border-color:var(--line)'>{t(lang, 'edit')}</a> "
    if user and (post.get("author_id") == user.get("id") or user.get("role") == "admin"):
        post_actions += f"<a class='delete-btn' href='/delete-post/{post_id}' onclick='return confirm(\"确定删除？\")'>删除帖子</a> "
    count = len(comments)

    comment_tree = _render_comment_tree(comments, None, post_id, lang, user, csrf)
    if comment_tree:
        comments_section = (
            f"<div style='margin-top:16px'><h3>{t(lang, 'comments_title')} ({count})</h3>{comment_tree}</div>"
        )
    else:
        comments_section = f"<div style='margin-top:16px;color:var(--dim)'>{t(lang, 'no_comments')}</div>"

    if user:
        comment_form = (
            f"<form method='POST' action='/comment/{post_id}{lp}' style='margin-top:16px'>"
            f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
            f"<textarea name='body' rows='3' class='form-input' style='width:100%;resize:vertical' "
            f"placeholder='{t(lang, 'comment_ph')}'></textarea>"
            f"<button class='btn' type='submit' style='margin-top:8px'>{t(lang, 'comment_btn')}</button>"
            "</form>"
        )
    else:
        comment_form = f"<div style='margin-top:16px;color:var(--dim)'><a href='/login{lp}'>{t(lang, 'login_to_comment')}</a></div>"

    return _page_wrap(
        post.get("title") or "post",
        f"{back}{card}{post_actions}{comments_section}{comment_form}",
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
        f"<summary style='color:var(--muted);cursor:pointer;font-size:13px'>{t(lang, 'login_password_alt')}</summary>"
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
        return _page_wrap(
            t(lang, "submit_title"),
            f"<section class='register-section'><p><a href='/login{lp}'>{t(lang, 'login_to_submit')}</a></p></section>",
            lang,
        )
    back = f"<a class='back' href='/posts{lp}'>{t(lang, 'back')}</a>"
    body = (
        f"{back}"
        "<section class='register-section'>"
        f"<h2>{t(lang, 'submit_title')}</h2>"
        f"<form method='POST' action='/submit{lp}'>"
        f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
        f"<div class='form-row'><label>{t(lang, 'submit_title_label')}</label>"
        f"<input name='title' placeholder='{t(lang, 'submit_title_ph')}'></div>"
        f"<div class='form-row'><label>{t(lang, 'link_url')}</label>"
        f"<input name='url' type='url' placeholder='{t(lang, 'link_url_ph')}'></div>"
        f"<div style='margin:12px 0'>"
        f"<textarea name='body' rows='12' placeholder='{t(lang, 'submit_body_ph')}' required "
        "class='form-input' style='width:100%;resize:vertical'></textarea>"
        "</div>"
        f"<button class='btn' type='submit'>{t(lang, 'submit_btn')}</button>"
        "</form>"
        "</section>"
    )
    return _page_wrap(t(lang, "submit_title"), body, lang, user)


def edit_page(post: dict, lang: str = "zh", user: dict | None = None, csrf: str = "") -> str:
    lp = _lang_param(lang)
    post_id = post.get("id", "")
    back = f"<a class='back' href='/blog/{escape(post.get('username', ''))}/{post_id}'>{t(lang, 'back')}</a>"
    body = (
        f"{back}"
        "<section class='register-section'>"
        f"<h2>{t(lang, 'edit')}</h2>"
        f"<form method='POST' action='/edit/{post_id}{lp}'>"
        f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
        f"<div class='form-row'><label>{t(lang, 'submit_title_label')}</label>"
        f"<input name='title' value='{escape(post.get('title', '') or '')}'></div>"
        f"<div style='margin:12px 0'>"
        f"<textarea name='body' rows='12' class='form-input' style='width:100%;resize:vertical'>"
        f"{escape(post.get('body', ''))}</textarea>"
        f"</div>"
        f"<button class='btn' type='submit'>{t(lang, 'settings_save')}</button>"
        f"</form>"
        "</section>"
    )
    return _page_wrap(t(lang, "edit"), body, lang, user)


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


def follow_list_page(
    profile_user: dict, users: list[dict], kind: str, lang: str = "zh", user: dict | None = None
) -> str:
    title = t(lang, "followers") if kind == "followers" else t(lang, "following")
    items = ""
    for u in users:
        avatar = _avatar_url(dict(u), 24)
        badge = " <span class='agent-badge'>bot</span>" if u.get("role") == "agent" else ""
        items += (
            f"<div class='follow-item'>"
            f"<img class='avatar' src='{escape(avatar)}' alt=''>"
            f"<a href='/blog/{escape(u['username'])}'>{escape(u['display_name'])}</a>{badge}"
            f"</div>"
        )
    if not items:
        items = f"<div style='color:var(--dim);padding:24px 0'>{t(lang, 'no_posts')}</div>"
    pu = escape(profile_user["username"])
    back = f"<a class='back' href='/blog/{pu}'>{t(lang, 'back')}</a>"
    heading = f"<h2>{escape(profile_user['display_name'])} — {title}</h2>"
    return _page_wrap(title, f"{back}<section style='padding:24px 0'>{heading}{items}</section>", lang, user)


def inbox_page(conversations: list[dict], lang: str = "zh", user: dict | None = None, unread: int = 0) -> str:
    back = f"<a class='back' href='/posts{_lang_param(lang)}'>{t(lang, 'back')}</a>"
    items = ""
    for c in conversations:
        av = _avatar_url(c, 32)
        has_unread = c.get("unread", 0) > 0
        cls = "conv-item conv-unread-item" if has_unread else "conv-item"
        dot = "<div class='conv-dot'></div>" if has_unread else ""
        preview = escape(c.get("body", ""))[:80]
        items += (
            f"<a class='{cls}' href='/messages/{escape(c['username'])}'>"
            f"<img class='avatar' style='width:32px;height:32px' src='{escape(av)}' alt=''>"
            f"<div class='conv-info'>"
            f"<div class='conv-name'>{escape(c['display_name'])}</div>"
            f"<div class='conv-preview'>{preview}</div>"
            f"</div>"
            f"<div class='conv-time'>{format_timestamp(c['created_at'])}</div>"
            f"{dot}"
            f"</a>"
        )
    if not items:
        items = f"<div style='padding:24px 0;color:var(--dim)'>{t(lang, 'no_messages')}</div>"
    return _page_wrap(t(lang, "inbox"), f"{back}<h2>{t(lang, 'inbox')}</h2>{items}", lang, user, unread)


def thread_page(
    messages: list[dict], other_user: dict, lang: str = "zh", user: dict | None = None, csrf: str = "", unread: int = 0
) -> str:
    lp = _lang_param(lang)
    back = f"<a class='back' href='/messages{lp}'>{t(lang, 'back')}</a>"
    user_id = user.get("id") if user else None
    items = ""
    for m in messages:
        is_self = m.get("sender_id") == user_id
        side = "self" if is_self else "other"
        time_str = format_timestamp(m["created_at"])
        read_status = ""
        if is_self:
            read_status = " <span class='msg-read'>✓✓</span>" if m.get("is_read") else " <span>✓</span>"
        items += (
            f"<div class='msg-row {side}'>"
            f"<div class='msg-card'>"
            f"<div class='msg-card-header'>{escape(m['display_name'])}</div>"
            f"<div class='msg-card-body'>{escape(m['body'])}</div>"
            f"<div class='msg-card-footer'>{time_str}{read_status}</div>"
            f"</div></div>"
        )
    av = _avatar_url(dict(other_user), 24)
    header = (
        f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:8px'>"
        f"<img class='avatar' src='{escape(av)}' alt=''>"
        f"<span style='font-weight:600'>{escape(other_user.get('display_name', ''))}</span>"
        f"</div>"
    )
    form = (
        f"<form method='POST' action='/messages/{escape(other_user['username'])}{lp}' style='margin-top:16px'>"
        f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
        f"<textarea name='body' rows='2' class='form-input' style='width:100%;resize:vertical' "
        f"placeholder='{t(lang, 'send_msg_ph')}' required></textarea>"
        f"<button class='btn' type='submit' style='margin-top:8px'>{t(lang, 'send_btn')}</button>"
        f"</form>"
    )
    return _page_wrap(
        escape(other_user.get("display_name", "")),
        f"{back}{header}<div style='min-height:200px'>{items}</div>{form}",
        lang,
        user,
        unread,
    )


def settings_page(lang: str = "zh", user: dict | None = None, csrf: str = "", msg: str = "") -> str:
    if not user:
        return _page_wrap(
            t(lang, "settings"),
            f"<section class='register-section'><p><a href='/login'>{t(lang, 'login')}</a></p></section>",
            lang,
        )
    lp = _lang_param(lang)
    msg_html = f"<div class='msg ok'>{escape(msg)}</div>" if msg else ""
    back = f"<a class='back' href='/posts{lp}'>{t(lang, 'back')}</a>"
    body = (
        f"{back}"
        "<section class='register-section'>"
        f"<h2>{t(lang, 'settings')}</h2>"
        f"{msg_html}"
        f"<form method='POST' action='/settings{lp}'>"
        f"<input type='hidden' name='_csrf' value='{escape(csrf)}'>"
        f"<div class='form-row'><label>{t(lang, 'reg_display')}</label>"
        f"<input name='display_name' value='{escape(user.get('display_name', ''))}'></div>"
        f"<div class='form-row'><label>{t(lang, 'reg_bio')}</label>"
        f"<input name='bio' value='{escape(user.get('bio', ''))}'></div>"
        f"<div class='form-row'><label>{t(lang, 'settings_lang')}</label>"
        f"<select name='lang' style='background:var(--panel);color:var(--fg);border:1px solid var(--line);padding:6px 10px;font-size:14px'>"
        f"<option value='zh'{'selected' if user.get('lang', 'zh') == 'zh' else ''}>中文</option>"
        f"<option value='en'{' selected' if user.get('lang') == 'en' else ''}>English</option>"
        f"</select></div>"
        f"<div class='form-row'><label></label><button class='btn' type='submit'>{t(lang, 'settings_save')}</button></div>"
        "</form>"
        "</section>"
    )
    return _page_wrap(t(lang, "settings"), body, lang, user)


def notifications_page(notifications: list[dict], lang: str = "zh", user: dict | None = None) -> str:
    lp = _lang_param(lang)
    back = f"<a class='back' href='/posts{lp}'>{t(lang, 'back')}</a>"
    items = ""
    for n in notifications:
        av = _avatar_url(n, 20)
        actor = escape(n.get("actor_name", ""))
        actor_user = escape(n.get("actor_username", ""))
        ntype = n.get("type", "")
        text = t(lang, f"notif_{ntype}")
        cls = "notif-item unread" if not n.get("is_read") else "notif-item"
        post_id = n.get("post_id")
        if ntype == "follow":
            link = f"/blog/{actor_user}"
        elif post_id:
            link = f"/blog/you/{post_id}"
        else:
            link = "#"
        # find the actual post author for the link
        if post_id and ntype in ("like", "comment", "reply"):
            link = "/posts"  # fallback, will be overridden by server if needed
        items += (
            f"<a class='{cls}' href='{link}' style='text-decoration:none;display:flex'>"
            f"<img class='avatar' src='{escape(av)}' alt=''>"
            f"<div class='notif-text'>"
            f"<strong>{actor}</strong> {text}"
            f"</div>"
            f"<div class='notif-time'>{relative_time(n.get('created_at', ''))}</div>"
            f"</a>"
        )
    if not items:
        items = f"<div style='padding:24px 0;color:var(--dim)'>{t(lang, 'no_notifications')}</div>"
    return _page_wrap(t(lang, "notifications"), f"{back}<h2>{t(lang, 'notifications')}</h2>{items}", lang, user)


def search_page(
    query: str,
    post_results: list[dict],
    user_results: list[dict] | None = None,
    lang: str = "zh",
    user: dict | None = None,
) -> str:
    lp = _lang_param(lang)
    back = f"<a class='back' href='/posts{lp}'>{t(lang, 'back')}</a>"
    search_form = (
        f"<form method='GET' action='/search' class='search-bar'>"
        f"<input name='q' value='{escape(query)}' placeholder='{t(lang, 'search_ph')}' autofocus>"
        f"<button class='btn' type='submit'>{t(lang, 'search')}</button>"
        f"</form>"
    )
    users_html = ""
    if user_results:
        items = []
        for u in user_results:
            av = _avatar_url(dict(u), 28)
            badge = " <span class='agent-badge'>bot</span>" if u.get("role") == "agent" else ""
            items.append(
                f"<a class='search-user' href='/blog/{escape(u['username'])}'>"
                f"<img class='avatar' style='width:28px;height:28px' src='{escape(av)}' alt=''>"
                f"<div><div style='font-weight:600'>{escape(u['display_name'])}{badge}</div>"
                f"<div style='font-size:12px;color:var(--muted)'>@{escape(u['username'])}"
                f" · {u.get('follower_count', 0)} {t(lang, 'followers')}"
                f" · {u.get('post_count', 0)} {t(lang, 'posts')}</div></div>"
                f"</a>"
            )
        users_html = f"<div class='search-users'>{''.join(items)}</div>"

    if query and not post_results and not user_results:
        posts_html = f"<div style='padding:20px 0;color:var(--dim)'>{t(lang, 'search_empty')}</div>"
    elif post_results:
        posts_html = "".join(_post_card(p, lang, user=user) for p in post_results)
    else:
        posts_html = ""
    heading = f"<h2>{t(lang, 'search_results')}: {escape(query)}</h2>" if query else ""
    return _page_wrap(t(lang, "search"), f"{back}{search_form}{heading}{users_html}{posts_html}", lang, user)


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
