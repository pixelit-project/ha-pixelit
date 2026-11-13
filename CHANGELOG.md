# Changelog

## 2.0.1 — 2026-11-13
- Refresh README screenshots from Home Assistant, setup instructions, stable firmware compatibility, card examples and troubleshooting.
- Fix Hassfest translation validation by using lowercase transition selector keys while preserving firmware names and existing action calls.
- Remove the optional Gallery API UUID setting from setup and reconfiguration.
- Add transition selectors, static Gallery bitmap wipes and firmware 3.0.0 prerelease compatibility checks for messages, alerts and saved displays.
- Add push-based environment, battery and diagnostic sensors without MQTT, with automatic hardware detection and Liveview-only card selection.
- Add simple text, color and clock controls for saved displays and alerts, with collapsible advanced options and an easy playlist list editor.
- 
## 2.0.0 — 2026-11-13
- Use native HA card editor fields, theme styling, optional transparency and responsive sizing; keep status visible independently of the title.
- Use the fixed WebSocket port automatically instead of asking during setup.
- Automatically detect static and animated Gallery icons through a shared `icon` field.
- Add persistent screens and playlists, temporary alerts with managed playback restoration, and bounded gallery bitmap loading.
- Separate alert duration from firmware protection and register targeted actions during integration setup (requires HA 2025.10+).
- Rename the integration and action domain to PixelIt (`pixelit`); existing installations require manual reconfiguration.
- Add direct WebSocket power and brightness control, a shared device, and a message action without requiring MQTT.

## 1.2.0
- Continue development under the PixelIt project, with credits to Pissbirne for the idea and initial implementation.
- Add per-display sensor selection, compact live frames, and display reconfiguration.
- Automatically register and update the Lovelace card resource.
- Add HACS and hassfest validation and PixelIt project brand icons.
