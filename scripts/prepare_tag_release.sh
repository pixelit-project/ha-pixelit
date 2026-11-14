#!/usr/bin/env bash
# Run in the authenticated Actions checkout. Never overwrite concurrent changes.
set -euo pipefail

: "${RELEASE_TAG:?}"
: "${DEFAULT_BRANCH:?}"
: "${GITHUB_OUTPUT:?}"

git check-ref-format "refs/tags/$RELEASE_TAG"
git check-ref-format "refs/heads/$DEFAULT_BRANCH"
git fetch --no-tags origin \
  "+refs/heads/$DEFAULT_BRANCH:refs/remotes/origin/$DEFAULT_BRANCH" \
  "+refs/tags/$RELEASE_TAG:refs/tags/$RELEASE_TAG"
old_tag=$(git rev-parse "refs/tags/$RELEASE_TAG")
tag_commit=$(git rev-parse "refs/tags/$RELEASE_TAG^{commit}")
branch_commit=$(git rev-parse "refs/remotes/origin/$DEFAULT_BRANCH")
if [[ "$tag_commit" != "$branch_commit" ]]; then
  echo "::error::Release tags must point to the current default branch tip. Pull the default branch and create a new version tag."
  exit 1
fi
git checkout --detach "$tag_commit"
python scripts/release_changelog.py prepare "$RELEASE_TAG" --date "$(date -u +%F)"
python scripts/release_changelog.py notes "$RELEASE_TAG" --output "$RUNNER_TEMP/release-notes.md"
GITHUB_REF_NAME="$RELEASE_TAG" python scripts/release_version.py

if ! git diff --quiet -- CHANGELOG.md custom_components/pixelit/manifest.json; then
  git config user.name 'github-actions[bot]'
  git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  git add CHANGELOG.md custom_components/pixelit/manifest.json
  git commit -m "Prepare release $RELEASE_TAG"
  # Push both references together, or neither. Leases guard both against races.
  git push --atomic \
    "--force-with-lease=refs/heads/$DEFAULT_BRANCH:$branch_commit" \
    "--force-with-lease=refs/tags/$RELEASE_TAG:$old_tag" \
    origin "HEAD:refs/heads/$DEFAULT_BRANCH" "HEAD:refs/tags/$RELEASE_TAG"
fi
echo "commit=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"
