"""paths — central path definitions for the cnb project.

All directory references should go through this module.
When directories move, update only this file.
"""

from pathlib import Path

# __file__ is src/cnb/paths.py → .parent.parent.parent = project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

ROLES_DIR = PROJECT_ROOT / "config" / "roles"
MIGRATIONS_DIR = PROJECT_ROOT / "config" / "migrations"
REGISTRY_DIR = PROJECT_ROOT / "config" / "registry"
COMMANDS_DIR = PROJECT_ROOT / "config" / "commands"
DOCS_DIR = PROJECT_ROOT / "docs"

# URLs
REPO_URL = "https://github.com/ApolloZhangOnGithub/cnb"
SITE_URL = "https://c-n-b.space"
DOCS_URL = "https://platform.c-n-b.space/docs"
BLOG_URL = "https://blog.c-n-b.space"
NPM_URL = "https://www.npmjs.com/package/claude-nb"
