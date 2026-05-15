from pathlib import Path

from lib.worktree_checkpoint import (
    WorktreeCheckpoint,
    classify_path,
    parse_status,
    render_checkpoint,
)


def test_parse_status_buckets_secret_generated_board_and_code():
    changes = parse_status(
        "\n".join(
            [
                " M lib/foo.py",
                "?? .env.local",
                "?? dist/app.js",
                " M board/state.db",
                "?? notes.txt",
            ]
        )
    )

    assert [(change.path, change.bucket) for change in changes] == [
        ("lib/foo.py", "code/docs change"),
        (".env.local", "secret/config risk"),
        ("dist/app.js", "generated artifact"),
        ("board/state.db", "board/runtime churn"),
        ("notes.txt", "untracked local file"),
    ]


def test_renamed_status_uses_new_path_for_classification():
    changes = parse_status("R  old.txt -> lib/new.py")

    assert changes[0].path == "lib/new.py"
    assert changes[0].bucket == "code/docs change"


def test_secret_like_config_is_never_plain_code_change():
    bucket, reason = classify_path("tools/local/config.toml", "M")

    assert bucket == "secret/config risk"
    assert "Do not".lower()[:6] in reason.lower()


def test_render_clean_checkpoint_mentions_github_only_planning():
    checkpoint = WorktreeCheckpoint(
        root=Path("/repo"),
        branch="main",
        head="abc123 commit",
        upstream="origin/main",
        ahead=0,
        behind=0,
        changes=(),
    )

    rendered = render_checkpoint(checkpoint)

    assert "Working tree clean" in rendered
    assert "GitHub-only planning" in rendered


def test_render_guard_warns_about_secret_and_shift_report_followups():
    checkpoint = WorktreeCheckpoint(
        root=Path("/repo"),
        branch="topic",
        head="abc123 commit",
        upstream="origin/topic",
        ahead=1,
        behind=0,
        changes=tuple(parse_status("?? .env\n M lib/foo.py\n")),
    )

    rendered = render_checkpoint(checkpoint, guard=True)

    assert "secret/config risk" in rendered
    assert "Guard mode" in rendered
    assert "#74" in rendered
    assert "#41" in rendered
