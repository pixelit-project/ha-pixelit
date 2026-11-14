"""Changelog preparation preserves prerelease entries and bounds release notes."""

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_release_version import release

spec = importlib.util.spec_from_file_location(
    "release_changelog", Path(__file__).resolve().parents[1] / "scripts/release_changelog.py"
)
changelog = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, release_version=release):
    spec.loader.exec_module(changelog)

TEXT = "# Changelog\n\n## Unreleased\n- New feature\n\n### Fixes\n- Fix\n\n## 2.0.0 — 2026-11-13\n- Old\n"


class ReleaseChangelogTests(unittest.TestCase):
    def test_prereleases_keep_unreleased_byte_for_byte(self):
        for tag in ("v2.1.0-beta.1", "2.1.0b2", "v2.1.0-rc.1", "2.1.0rc2"):
            with self.subTest(tag=tag):
                self.assertEqual(changelog.prepare(TEXT, tag, "2026-11-14"), TEXT)
                self.assertEqual(changelog.notes(TEXT, tag), "- New feature\n\n### Fixes\n- Fix\n")

    def test_stable_rollover_and_repeated_preparation(self):
        updated = changelog.prepare(TEXT, "v2.1.0", "2026-11-14")
        self.assertIn("## Unreleased\n\n## 2.1.0 — 2026-11-14\n", updated)
        self.assertTrue(updated.endswith("## 2.0.0 — 2026-11-13\n- Old\n"))
        self.assertEqual(changelog.notes(updated, "2.1.0"), changelog.notes(TEXT, "2.1.0rc1"))
        self.assertEqual(changelog.prepare(updated, "2.1.0", "2026-11-15"), updated)

    def test_missing_empty_duplicate_sections_fail(self):
        for text, tag in (
            (TEXT, "v2.1.0"),
            ("# Changelog\n\n## Unreleased\n\n", "v2.1.0b1"),
            (TEXT + "\n## Unreleased\n- Duplicate\n", "v2.1.0rc1"),
            ("## 2.1.0\n\n", "v2.1.0"),
        ):
            with self.subTest(text=text, tag=tag), self.assertRaises(ValueError):
                changelog.notes(text, tag)

    def test_next_prerelease_only_contains_new_changes(self):
        stable = changelog.prepare(TEXT, "2.1.0", "2026-11-14")
        next_cycle = stable.replace("## Unreleased\n", "## Unreleased\n- Next cycle\n", 1)
        self.assertEqual(changelog.notes(next_cycle, "2.2.0b1"), "- Next cycle\n")
