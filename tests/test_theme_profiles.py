"""Tests for lib/theme_profiles.py — profile data integrity.

Verifies: structure consistency, required fields, no duplicate names across themes.
"""

from lib.theme_profiles import PROFILES


class TestProfileStructure:
    def test_profiles_is_dict(self):
        assert isinstance(PROFILES, dict)

    def test_has_themes(self):
        assert len(PROFILES) >= 1

    def test_each_theme_is_dict(self):
        for theme, entries in PROFILES.items():
            assert isinstance(entries, dict), f"theme {theme} is not a dict"

    def test_each_entry_has_full_name(self):
        for theme, entries in PROFILES.items():
            for short, data in entries.items():
                assert "full_name" in data, f"{theme}/{short} missing full_name"
                assert isinstance(data["full_name"], str)
                assert len(data["full_name"]) > 0

    def test_each_entry_has_info(self):
        for theme, entries in PROFILES.items():
            for short, data in entries.items():
                assert "info" in data, f"{theme}/{short} missing info"
                assert isinstance(data["info"], str)
                assert len(data["info"]) > 0

    def test_short_names_are_lowercase_kebab(self):
        import re

        for theme, entries in PROFILES.items():
            for short in entries:
                assert re.match(r"^[a-z][a-z0-9-]*$", short), f"{theme}/{short} is not lowercase kebab-case"

    def test_no_duplicate_short_names_within_theme(self):
        for theme, entries in PROFILES.items():
            names = list(entries.keys())
            assert len(names) == len(set(names)), f"duplicate short names in {theme}"


class TestKnownThemes:
    def test_ai_theme_exists(self):
        assert "ai" in PROFILES
        assert len(PROFILES["ai"]) >= 5

    def test_threebody_theme_exists(self):
        assert "threebody" in PROFILES
        assert len(PROFILES["threebody"]) >= 5

    def test_titan_theme_exists(self):
        assert "titan" in PROFILES
        assert len(PROFILES["titan"]) >= 5


class TestChineseNames:
    def test_zh_field_is_string(self):
        for _theme, entries in PROFILES.items():
            for _short, data in entries.items():
                if "zh" in data:
                    assert isinstance(data["zh"], str)
                    assert len(data["zh"]) > 0

    def test_some_entries_have_zh(self):
        all_entries = [data for entries in PROFILES.values() for data in entries.values()]
        zh_count = sum(1 for d in all_entries if "zh" in d)
        assert zh_count >= 3
