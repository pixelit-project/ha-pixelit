# PixelIt Home Assistant integration guidance

## Project intent

Build a full PixelIt integration following current Home Assistant best practices.
The integration domain is `pixelit`; Liveview is one feature of the integration.
Consult the official Home Assistant developer documentation for APIs and lifecycle
conventions before introducing or changing integration architecture.

## Home Assistant conventions

- Register actions in `services.py` from integration `async_setup`. Use the
  platform entity service helper for entity actions so HA resolves entity, device
  and area targets and enforces permissions.
- Use config entries and their `runtime_data`, stable entity unique IDs, a shared
  device identity, translated entity/action names and descriptions, and complete
  `services.yaml` selectors and validated schemas.
- Keep device I/O asynchronous and bounded. Report failed commands as HA errors;
  use actual device feedback for availability and state.
- Own and clean up timers, subscriptions and background tasks on unload/reload
  and HA shutdown. Prevent stale callbacks and superseded operations from sending
  content after stop, sleep, replacement or disconnect.
- Persist user-managed screens and playlists through HA storage helpers. Do not
  persist temporary alerts, timer handles, tasks or live pixel frames.
- Preserve compatibility where practical; document breaking changes and manual
  migration explicitly. Never imply that a domain rename migrates existing HA
  config entries or entity registries automatically.

## Screens, playlists and alerts

Use the local `node-red-contrib-pixelit` implementation as a behavioral reference,
while adapting its architecture to Home Assistant rather than copying Node-RED
lifecycle patterns.

- `duration` on an alert means the time before HA resumes its managed playlist
  or managed base screen. Firmware protection is a separate option named
  `protection_duration`; it does not implement expiry or restore previous content.
- Alerts temporarily interrupt managed playback. Sleep pauses it. Reconnect and
  wake must resume coherently without request floods or stale alert callbacks.
- Only promise restoration of screens owned by this integration. Live pixels do
  not reconstruct arbitrary content set by Node-RED, MQTT or the WebUI.
- Bound stored content, payload sizes, playlists, downloads, caches and retries.
  Validate bitmap and animation content against device capabilities and reject
  invalid or oversized data instead of silently truncating it.

## Sensor coverage

Expose device-provided environmental, battery and diagnostic readings directly
through the integration, without requiring MQTT. Discover optional hardware from
reported values, respect the firmware temperature unit, and keep sensor updates
independent of live pixels. Diagnostics should be disabled initially. Keep card
selection limited to the Liveview sensor as more sensor entities are added.

## Related repositories and device constraints

Firmware and device protocol handlers live in `../PixelIt`; Node-RED behavior in
`../node-red-contrib-pixelit`; external documentation in `../PixelIt.Docs`.
Read applicable companion `AGENTS.md` files before working there.

Smooth animation playback and ESP8266 memory compatibility are requirements.
Consult firmware animation limits and development guidance before changing device
load. Do not increase firmware limits or introduce frequent polling implicitly.
Identify any required firmware or external documentation follow-up explicitly.

## Documentation audience

Keep README focused on end users: installation, setup and simple usage examples.
Put protocol, architecture, memory limits and developer details in `docs/`.

## Validation

Run relevant host tests, Python and JavaScript syntax checks, configuration and
translation validation, and `git diff --check`. Test scheduler behavior including
alert expiry, replacement, sleep/wake, disconnect/reconnect, command failure and
unload. Validate Home Assistant registration/lifecycle in a real HA environment
when available. Clearly distinguish stubbed host tests from actual HA/device
validation; passing tests alone does not prove ESP8266 memory safety or animation
smoothness. Keep README and changelog aligned with user-visible behavior.
