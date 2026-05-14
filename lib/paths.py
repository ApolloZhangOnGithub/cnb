"""paths — central path definitions for the cnb project.

All directory references should go through this module.
When directories move, update only this file.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ROLES_DIR = PROJECT_ROOT / "config" / "roles"
MIGRATIONS_DIR = PROJECT_ROOT / "config" / "migrations"
REGISTRY_DIR = PROJECT_ROOT / "config" / "registry"
COMMANDS_DIR = PROJECT_ROOT / "config" / "commands"
DOCS_DIR = PROJECT_ROOT / "docs"
