"""Validate release tags against the version shipped in the HACS source tree."""

import json
import os
from pathlib import Path
import re


def release_version(tag: str) -> tuple[str, bool]:
    """Accept stable, SemVer beta/rc and HA-style beta/rc version tags."""
    match = re.fullmatch(
        r"v?((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))"
        r"(?:(?:-(beta|rc)\.([1-9][0-9]*))|(?:(b|rc)([1-9][0-9]*)))?",
        tag,
    )
    if match is None:
        raise ValueError(f"Unsupported release tag: {tag!r}")
    base, semver_stage, semver_number, stage, number = match.groups()
    stage = {"beta": "b", "rc": "rc"}.get(semver_stage, stage)
    number = semver_number or number
    return base + (f"{stage}{number}" if stage else ""), stage is not None


def main() -> None:
    """Fail before publishing when the tagged source ships a different version."""
    version, prerelease = release_version(os.environ["GITHUB_REF_NAME"])
    manifest = json.loads(Path("custom_components/pixelit/manifest.json").read_text())
    if manifest["version"] != version:
        raise ValueError(
            f"Set manifest.json version to {version!r} before creating this tag "
            f"(found {manifest['version']!r})."
        )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"prerelease={str(prerelease).lower()}\n")


if __name__ == "__main__":
    main()
