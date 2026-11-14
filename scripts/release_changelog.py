"""Prepare release metadata before tagging and extract curated release notes."""

import argparse
from datetime import date
import json
from pathlib import Path
import re

from release_version import release_version


def section(text: str, title: str) -> tuple[int, int, str]:
    """Find one exact level-two heading, keeping nested headings in its body."""
    headings = list(re.finditer(r"^## ([^\n]+)\n", text, re.MULTILINE))
    matches = [
        (index, heading) for index, heading in enumerate(headings)
        if heading[1].strip() == title
        or heading[1].strip().startswith(title + " — ")
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one changelog section for {title!r}")
    index, heading = matches[0]
    end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
    body = text[heading.end():end].strip()
    if not body:
        raise ValueError(f"Changelog section {title!r} is empty")
    return heading.start(), end, body


def notes(text: str, tag: str) -> str:
    """Prereleases preview Unreleased; stable releases use their own section."""
    version, prerelease = release_version(tag)
    return section(text, "Unreleased" if prerelease else version)[2] + "\n"


def prepare(text: str, tag: str, released_on: str) -> str:
    """Leave Unreleased untouched for beta/RC; finalize it for stable versions."""
    version, prerelease = release_version(tag)
    if prerelease:
        notes(text, tag)
        return text
    date.fromisoformat(released_on)
    if re.search(rf"^## {re.escape(version)}(?: — [^\n]+)?$", text, re.MULTILINE):
        notes(text, tag)
        return text
    start, end, body = section(text, "Unreleased")
    return (
        text[:start] + f"## Unreleased\n\n## {version} — {released_on}\n"
        + body + "\n\n" + text[end:]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "notes"))
    parser.add_argument("tag")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    changelog = Path("CHANGELOG.md")
    text = changelog.read_text(encoding="utf-8")
    if args.command == "notes":
        if args.output is None:
            parser.error("notes requires --output")
        args.output.write_text(notes(text, args.tag), encoding="utf-8")
        return
    version, _ = release_version(args.tag)
    updated = prepare(text, args.tag, args.date)
    manifest_path = Path("custom_components/pixelit/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    changelog.write_text(updated, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
