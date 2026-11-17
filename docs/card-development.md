# Dashboard card development

The maintained, readable source for the card, editor, styles and translations is
[`src/pixelit-card.js`](../src/pixelit-card.js). It was extracted from the previously
shipped bundle; the earlier original source files were not available. The embedded
Lit implementation was replaced with imports from the public `lit` npm package.
The original MIT attribution remains in the source and repository license.

## Install and build

Use a supported Node.js release (22.22.2+, 24.15.0+ or 26+) and npm.
`.nvmrc` selects Node.js 22, also used in CI. With nvm, run `nvm install`
and `nvm use` first. Run these commands from the repository root:

```sh
npm ci
npm run build
npm run check
```

`package.json` declares Lit as the only runtime dependency and esbuild as the
bundler. jsdom is a development-only DOM implementation for runtime tests.
Prettier formats the maintained source and runtime tests (`npm run format:card`).
All packages come from the public npm registry; `package-lock.json` pins the complete dependency
tree and integrity hashes. `npm ci` installs those exact versions.

`scripts/build-card.mjs` bundles the card and Lit into the ES module
`custom_components/pixelit/www/pixelit-card.js`. There are no external runtime
imports or CDN downloads. The generated module is deliberately unminified,
retains dependency license comments and includes a generated-file notice.
The generated file has a Git whitespace exception because Lit regular-expression
strings contain significant spaces and tabs before literal newlines.
Do not edit it directly. The release workflow builds and commits it automatically;
source changes do not require a local build or a generated-file commit.
For a local preview, run `npm run build` first.
Installing or running PixelIt in Home Assistant does not require Node.js or npm.

The card keeps the `pixelit-card` and legacy `pixelit-liveview-card` registrations,
its named export and the existing `/pixelit/pixelit-card.js` resource path.
No firmware, device protocol or user configuration changes are required.

## Validation

`npm run check` runs formatting, build consistency and all card tests. The existing
behavior tests cover configuration, sensor selection, gestures and display controls
with lightweight Lit/DOM doubles. Additional contract tests import the source and
shipped module in isolated processes, each using real Lit and jsdom. They verify
custom-element registration, reactive pixel updates, text escaping, optional DOM,
service event bindings, pending/error state and native editor form bindings.
`--conditions=browser` selects Lit's browser implementation for the source tests.

`npm run build:check` rebuilds in memory and fails if the committed module differs
by even one byte. A regression test verifies that a stale module is rejected
without overwriting it. The reusable validation workflow runs frontend checks in a
separate job alongside Python, HACS and Hassfest checks before release publication.
Branch and pull request CI builds the card before testing. Release validation
checks the exact module committed during automatic release preparation.
jsdom does not implement browser layout or Home Assistant's own components.

For browser preview instructions, see [tests/README.md](../tests/README.md).
Check rendering and the editor in a running Home Assistant before release;
unit tests do not establish compatibility with its actual UI.

## Release and HACS review

Follow [releases.md](releases.md) to publish a new version after committing and
pushing source, dependency and changelog changes. Push a version tag on the current
default branch tip; the release workflow installs dependencies, builds and commits
the card alongside the version metadata, and moves the tag atomically.
No local build is required. The release validation must
pass HACS, Hassfest and host checks. Then request review again on the existing
HACS submission, linking the new release and card sources. Publishing a new
release and requesting review are separate steps from a local build.
