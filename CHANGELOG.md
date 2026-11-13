# Changelog

## Unreleased

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
