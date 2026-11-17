# Host control tests

Use Python 3.12 or newer:

```sh
python -m pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
```

These tests exercise command acknowledgement, serialization, error and timeout
handling, cancellation, message payloads, state feedback, and action validation.
Tests also cover playlist rotation, alert replacement/expiry, persistence,
sleep/reconnect, stale callbacks, unload during downloads, and bounded gallery
lookup/cache behavior. Home Assistant interfaces are stubbed. They do not validate HA entity registration
or firmware rendering; those require a running Home Assistant and PixelIt device.

## Dashboard card

Use Node.js 22.22.2+, 24.15.0+ or 26+ (`.nvmrc` selects Node.js 22).
From the repository root:

```sh
npm ci
npm run build
npm run check
```

The readable card and editor source is in `src/pixelit-card.js`. Build instructions
and dependency details are in [Card development](../docs/card-development.md).
`npm test` runs the behavior tests against the source with Lit/DOM test doubles,
and additional runtime contracts against both the source and shipped bundle with
real Lit in jsdom. Runtime tests cover reactive rendering, registration, escaping,
control bindings, pending/error state and editor events. jsdom does not validate
browser layout or Home Assistant's own form components. `npm run check` also checks
formatting and compares a fresh build byte for byte with the shipped bundle.

For a visual check, serve the repository using `python3 -m http.server 8765` and
open `http://127.0.0.1:8765/tests/frontend/card-preview.html`. The fixture renders
the shipped Lit card with test data in narrow/wide, light/dark and error states.
Only the HA card frame is mocked; the editor still needs testing in real HA.
