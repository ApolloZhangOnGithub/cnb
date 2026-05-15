# Knowledge Surfaces

cnb has several public and project-facing places where information can live. Keep them distinct so users do not have to guess which page is current.

## Canonical Surfaces

| Surface | Use it for | Keep it current by |
|---------|------------|--------------------|
| Public website | First-time visitor overview, install command, demos, and the shortest docs links. | Updating `site/` and the Pages workflow. |
| README | Repository front door, quick start, core terminology, and the shortest command path. | Keeping `README.md` and `README_zh.md` in sync. |
| `docs/` | Durable product docs, operations runbooks, design decisions, and reference material. | Editing Markdown in the repo and reviewing through normal PRs. |
| GitHub Issues | Work queue, bugs, decisions that still need action, and owner-visible project state. | Issue templates, labels, and the issue sync workflow. |
| GitHub Projects | Prioritization and board-style planning over issues. | Automation plus human triage. |

## Retired Surfaces

GitHub Wiki and GitHub Discussions are not canonical cnb surfaces.

Wiki pages are too easy to drift away from the reviewed repo docs. If content is durable, put it under `docs/`. If it is short-lived, put it in an issue or project note.

Discussions are not the right place for current cnb coordination because the project already uses issues, the local board, and Feishu for live operation. If a discussion produces a decision, capture the decision in `docs/` or an issue before treating it as project state.

## Migration Rule

When old Wiki or Discussion content is still useful:

1. Move durable explanations to `docs/`.
2. Move actionable work to GitHub Issues.
3. Link the new location from any remaining historical reference.
4. Disable the old surface once no current navigation depends on it.

This keeps the public path simple: website for discovery, README for quick start, `docs/` for durable knowledge, and issues/projects for work.
