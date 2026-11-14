# Publishing releases

Push a version tag on the current default branch tip. The Release workflow
automatically prepares the version and changelog, validates the prepared commit,
and publishes a GitHub release using the changelog notes. No manual version bump
or preparation command is required. Both `v`-prefixed and unprefixed tags work.

| Tag example | Automatic manifest version | Changelog behavior | GitHub release |
| --- | --- | --- | --- |
| `v2.1.0` | `2.1.0` | Move Unreleased into `2.1.0 — YYYY-MM-DD`; create empty Unreleased | Stable |
| `v2.1.0-beta.1` or `v2.1.0b1` | `2.1.0b1` | Keep Unreleased unchanged; use its content as notes | Prerelease |
| `v2.1.0-rc.1` or `v2.1.0rc1` | `2.1.0rc1` | Keep Unreleased unchanged; use its content as notes | Prerelease |

Keep changes in `## Unreleased` while developing. Commit and push your code and
changelog changes, then tag the current default branch tip, for example:

```sh
git switch main
git pull --ff-only origin main
git tag -a v2.1.0-beta.1 -m "PixelIt 2.1.0 beta 1"
git push origin v2.1.0-beta.1
```

## Automatic preparation

The workflow commits the manifest/changelog changes as `github-actions[bot]`,
pushes that commit to the default branch and **moves the triggering tag to the
prepared commit**. This converts an annotated trigger tag to a lightweight tag;
do not use signed release tags with this process. Both references are updated
atomically and guarded against concurrent changes. Tags on older commits are
rejected. Existing GitHub releases are not overwritten.

The tag workflow must already be present in the tagged commit. Repository rules
must allow the workflow's `GITHUB_TOKEN` to write to the default branch and update
release tags. Branch/tag protection or immutable-tag rules may block automatic
preparation; the workflow fails without updating either reference. No extra
secret is required. Only preparation and publication have `contents: write`.

After a release, update your local branch and tag before further development:

```sh
git pull --ff-only origin main
git fetch origin --force --tags
```

Stable release dates use UTC. Beta and RC notes include all current Unreleased
entries, including changes previewed in earlier prereleases. Only the selected
section body is published, without the heading or older versions.

## Validation and publication

HACS, Hassfest and Python/JavaScript host checks run against the exact prepared
commit before publication. The workflow explicitly checks out that commit because
the event's original commit predates preparation. Pushes using `GITHUB_TOKEN` do
not trigger another workflow; validation is invoked directly as a reusable workflow.
If validation fails, the prepared commit/tag remain available for inspection but
no release is published. Fix code with a new commit and use a new version tag.
For transient failures, rerun the workflow while its tag is still at the branch tip.

Missing, empty or duplicate release-note sections fail preparation. Beta and RC
releases are marked as prereleases and never promoted to Latest. Stable releases
use GitHub's default Latest selection. Choose one spelling per version to avoid
duplicate releases. HACS downloads the prepared tagged source, including the
correct manifest version and changelog.

For optional local previews, `python3 scripts/release_changelog.py prepare TAG`
updates metadata without committing or pushing. This is not required for releases.

## First use after updating the workflow

An existing tag pointing to an older workflow keeps using that old workflow when
rerun. Commit and push this workflow update first, then create a new version tag
on that commit. Merely rerunning an earlier failed release does not load the new
automatic preparation logic.
