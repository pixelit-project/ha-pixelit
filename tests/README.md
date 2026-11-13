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

Run `node --test tests/frontend/card.test.cjs` for editor/card behavior tests.
These use Lit/DOM test doubles and do not verify actual HA form rendering.

For a visual check, serve the repository using `python3 -m http.server 8765` and
open `http://127.0.0.1:8765/tests/frontend/card-preview.html`. The fixture renders
the shipped Lit card with test data in narrow/wide, light/dark and error states.
Only the HA card frame is mocked; the editor still needs testing in real HA.
