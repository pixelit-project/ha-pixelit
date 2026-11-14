# Publishing releases

Push a version tag to publish a GitHub release using `CHANGELOG.md` as its
release notes. Both `v`-prefixed and unprefixed tags are supported.

| Tag example | Manifest version | Release notes | GitHub release |
| --- | --- | --- | --- |
| `v2.1.0` | `2.1.0` | `2.1.0` section | Stable |
| `v2.1.0-beta.1` or `v2.1.0b1` | `2.1.0b1` | `Unreleased` section | Prerelease |
| `v2.1.0-rc.1` or `v2.1.0rc1` | `2.1.0rc1` | `Unreleased` section | Prerelease |

## Prepare, commit and tag

Keep changes in `## Unreleased` while developing. Before tagging, run the
preparation command from the repository root (Python 3.10 or newer):

```sh
python3 scripts/release_changelog.py prepare v2.1.0-beta.1
```

This updates `custom_components/pixelit/manifest.json` to `2.1.0b1` and leaves
`CHANGELOG.md` unchanged. Beta and RC releases always publish the current
Unreleased content, including changes already previewed in earlier prereleases.

For a stable release, run:

```sh
python3 scripts/release_changelog.py prepare v2.1.0
```

This updates the manifest version and moves the Unreleased content under
`## 2.1.0 — YYYY-MM-DD`, with a new empty `## Unreleased` heading above it.
The date defaults to the local date; use `--date YYYY-MM-DD` to override it.
Preparation does not commit, tag or push. Review and commit the changes before
creating the matching tag, for example for the beta above:

```sh
git add custom_components/pixelit/manifest.json CHANGELOG.md
git commit -m "Prepare 2.1.0 beta 1"
git tag -a v2.1.0-beta.1 -m "PixelIt 2.1.0 beta 1"
git push origin HEAD
git push origin v2.1.0-beta.1
```

The preparation step runs **before tagging** so the tagged source and HACS
installation contain the correct metadata. The tag workflow does not rewrite
commits or move tags. You can also edit the manifest and changelog manually.

## Publication checks

The Release workflow verifies the tag, committed manifest version and nonempty
changelog section, then runs HACS, Hassfest and the Python/JavaScript host checks
before publishing. Missing, empty or duplicate release-note sections fail the
workflow without creating a release. Only the selected section body is published;
older versions and the Unreleased heading are omitted from the release text.

The manifest is never rewritten during the build: HACS downloads the tagged
source tree. Beta and RC releases are marked as prereleases and never promoted
to Latest. Stable releases use GitHub's default Latest selection. Choose one tag
spelling per version to avoid duplicate releases. Existing releases are not
overwritten; rerunning a completed publication fails at the create step.

No release is published until the workflow is committed and a matching tag is
pushed. The workflow uses the built-in `GITHUB_TOKEN` with write access only in
the publication job; no additional secret is needed.
