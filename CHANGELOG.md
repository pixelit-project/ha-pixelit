# Changelog

## Unreleased

## 2.1.0 — 2026-11-14
- (o0shojo0o) Automatically prepare manifest versions and changelog notes from release tags, preserving Unreleased for beta and RC prereleases and finalizing it for stable releases.
- (o0shojo0o) Add automatic brightness and clock switches, clock delay (clock changes restart the display), and physical button states and press/release events without MQTT.
- (o0shojo0o) Report available firmware updates through an enabled native HA update entity without MQTT Discovery.
- (o0shojo0o) Fix reconnect handling for static and sleeping displays using WebSocket heartbeats and bounded connection attempts.
- (o0shojo0o) Add back-and-forth animation and loop limits to Gallery icon actions, with validation for advanced animation payloads.

## 2.0.1 — 2026-11-13
- (o0shojo0o) Refresh README screenshots from Home Assistant, setup instructions, stable firmware compatibility, card examples and troubleshooting.
- (o0shojo0o) Fix Hassfest translation validation by using lowercase transition selector keys while preserving firmware names and existing action calls.
- (o0shojo0o) Remove the optional Gallery API UUID setting from setup and reconfiguration.
- (o0shojo0o) Add transition selectors, static Gallery bitmap wipes and firmware 3.0.0 prerelease compatibility checks for messages, alerts and saved displays.
- (o0shojo0o) Add push-based environment, battery and diagnostic sensors without MQTT, with automatic hardware detection and Liveview-only card selection.
- (o0shojo0o) Add simple text, color and clock controls for saved displays and alerts, with collapsible advanced options and an easy playlist list editor.

## 2.0.0 — 2026-11-13
- (o0shojo0o) Use native HA card editor fields, theme styling, optional transparency and responsive sizing; keep status visible independently of the title.
- (o0shojo0o) Use the fixed WebSocket port automatically instead of asking during setup.
- (o0shojo0o) Automatically detect static and animated Gallery icons through a shared `icon` field.
- (o0shojo0o) Add persistent screens and playlists, temporary alerts with managed playback restoration, and bounded gallery bitmap loading.
- (o0shojo0o) Separate alert duration from firmware protection and register targeted actions during integration setup (requires HA 2025.10+).
- (o0shojo0o) Rename the integration and action domain to PixelIt (`pixelit`); existing installations require manual reconfiguration.
- (o0shojo0o) Add direct WebSocket power and brightness control, a shared device, and a message action without requiring MQTT.

## 1.2.0
- (Pissbirne) Continue development under the PixelIt project, with credits to Pissbirne for the idea and initial implementation.
- (Pissbirne) Add per-display sensor selection, compact live frames, and display reconfiguration.
- (Pissbirne) Automatically register and update the Lovelace card resource.
- (Pissbirne) Add HACS and hassfest validation and PixelIt project brand icons.
