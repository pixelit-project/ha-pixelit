"""Release tag classification and committed manifest consistency checks."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "release_version", Path(__file__).resolve().parents[1] / "scripts/release_version.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseVersionTests(unittest.TestCase):
    def test_supported_versions(self):
        for prefix in ("", "v"):
            for tag, version, prerelease in (
                ("2.1.0", "2.1.0", False),
                ("2.1.0-beta.1", "2.1.0b1", True),
                ("2.1.0b12", "2.1.0b12", True),
                ("2.1.0-rc.2", "2.1.0rc2", True),
                ("2.1.0rc12", "2.1.0rc12", True),
            ):
                with self.subTest(tag=prefix + tag):
                    self.assertEqual(release.release_version(prefix + tag), (version, prerelease))

    def test_invalid_versions(self):
        for tag in ("latest", "v2.1", "v02.1.0", "v2.1.0-alpha.1", "v2.1.0-beta",
                    "v2.1.0-rc.0", "v2.1.0b01", "v2.1.0+build", "v2.1.0\n"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.release_version(tag)

    def test_manifest_must_match_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with patch.dict(os.environ, GITHUB_REF_NAME="v2.1.0-beta.1", GITHUB_OUTPUT=str(output)):
                with patch.object(release.Path, "read_text", return_value=json.dumps({"version": "2.1.0"})):
                    with self.assertRaisesRegex(ValueError, "Set manifest.json"):
                        release.main()
                self.assertFalse(output.exists())
                with patch.object(release.Path, "read_text", return_value=json.dumps({"version": "2.1.0b1"})):
                    release.main()
                self.assertEqual(output.read_text(), "prerelease=true\n")
