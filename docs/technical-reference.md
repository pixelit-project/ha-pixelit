# Technical reference

## Unified Gallery icons

`show_message`, `show_alert` and `set_screen` accept an optional action-level
`icon` ID and `icon_animation_delay` (10–60000 ms, default 100). Advanced screen
objects can instead include `icon`, `icon_animation_delay` and
`icon_position: {x: 0, y: 0}` directly. Do not specify an icon at both levels or
combine it with explicit `bitmap` / `bitmapAnimation` content.

Gallery frames determine the firmware payload: one frame becomes `bitmap`,
multiple frames become `bitmapAnimation`. Inferred size is 8×8 or 32×8. The
default icon position is (0,0); text without an explicit position starts one
pixel to the right of the icon, at y=1. Explicit text positioning is preserved.
Resolved screen content is validated against display and transport limits and
stored as pixels. Existing explicit bitmap payloads remain supported.

## Screens, playlists and alerts

Actions accept the Display light entity, its device or an area as target. Each
display owns its screens and playlist independently. Screen payloads use the
firmware's `text`, `clock`, `bitmap`, `bitmapAnimation` and optional
`switchAnimation` objects. GPIO, firmware configuration and arbitrary device
commands are intentionally excluded from these display-content actions.

Store named screens first (repeat for each screen):

```yaml
action: pixelit.set_screen
target:
  entity_id: light.your_pixelit_display
data:
  name: clock
  duration: 10
  screen:
    clock:
      show: true
```

```yaml
action: pixelit.set_screen
target:
  entity_id: light.your_pixelit_display
data:
  name: solar
  duration: 5
  screen:
    text:
      textString: "PV {{ states('sensor.pv_power') }} W"
      hexColor: "#FFFF00"
      scrollText: auto
      bigFont: false
      position: {x: 0, y: 1}
```

HA evaluates templates when the action runs. Update the named screen from an
automation triggered by the sensor to keep its value current; stored screens are
snapshots, not templates that are continually reevaluated.

Start rotation:

```yaml
action: pixelit.set_playlist
target:
  entity_id: light.your_pixelit_display
data:
  screens: [clock, solar]
```

Temporarily interrupt it:

```yaml
action: pixelit.show_alert
target:
  entity_id: light.your_pixelit_display
data:
  duration: 10
  screen:
    text:
      textString: "Waschmaschine fertig"
      hexColor: "#00FF00"
      scrollText: auto
      position: {x: 0, y: 1}
```

Here `duration: 10` means **resume managed playback after ten seconds**, measured
from firmware acknowledgement. Unlike `protection_duration`, it is a timer in HA.
The next playlist screen follows an alert; its full configured duration starts
when it is sent. Without a playlist, HA restores its last managed base screen.
Without either, HA switches to the device clock. Content created externally by
MQTT, Node-RED or the WebUI cannot be reconstructed or restored from live pixels.
A newer alert replaces the previous alert and its timer; alerts are not queued.

`pixelit.show_screen` with `name` shows one stored screen persistently and stops
rotation. `pixelit.stop_playlist` (no fields), or an empty `screens` list, stops
rotation and any alert timer, leaving the current display content visible.
Updating a screen with `set_screen` changes its next playlist turn. Unknown names,
invalid durations and invalid payloads are rejected before changing playback.

Saved screens and playlist order survive reloads and HA restarts. Playback starts
at the beginning after reload. Temporary alerts, standalone base content, elapsed
time and playlist position are not persisted. Removing the integration deletes
its stored screens and playlist. Sleep and disconnect pause playback; on wake or
reconnect the next playlist screen resumes, or the managed base is reapplied.
An interrupted alert is discarded. Starting a playlist while asleep does not wake
the display; explicitly showing a message, screen or alert does.

Background transmission failures pause playback and set `playback_error` on the
Display entity. Reconnect or a new playback action can resume it. There is no
continuous retry loop. Entity attributes also expose `current_screen`, `playlist`,
`stored_screens` and `alert_active`, without publishing the full screen payloads.
HA must stay running for rotation and alert expiry. Avoid running a Node-RED
playlist on the same display simultaneously; both controllers can send content.
An existing firmware-protected screen can defer HA content even after an OK
acknowledgement. Avoid firmware protection when using HA playlist/alert timers.

### Bitmaps and animations

Supply RGB565 integer arrays as `bitmap.data`, or arrays of frames as
`bitmapAnimation.data`, with optional `size: {width: 8, height: 8}`. An animation
also needs `animationDelay` in milliseconds. Optional `rubberbanding` (Boolean)
plays frames back and forth. Optional `limitLoops` is an integer from 0 to
2,147,483,647: 0 repeats indefinitely, a positive count limits playback. These
firmware options do not change HA screen or alert duration. For Gallery icons,
use action fields `icon_rubberbanding` and `icon_limit_loops` (defaults false and 0),
or the same fields alongside `icon` in an advanced screen object. As in the Node-RED Core node,
`data: 42` resolves gallery bitmap ID 42. Use `bitmapAnimation` for animated gallery
entries. Missing gallery dimensions are inferred as 8×8 or 32×8. Gallery downloads
use the PixelIt API without a configurable UUID, with a five-second
timeout, a 128 KiB response limit, and a per-display LRU cache of at most 32 entries
or 256 KiB. Invalid responses fail the action without changing active playback.
Resolved pixels are stored with named screens, so rotation does not repeatedly
request the gallery. Inline pixels need no internet connection.

The integration conservatively limits each screen to a 12,288-byte WebSocket
message, each bitmap/frame to 256 pixels within the configured matrix dimensions,
and animations to 28 frames / 1,792 total pixels. It does not increase firmware
limits or silently truncate content. At most 100 named screens, 100 playlist
entries and 256 KiB of stored content are allowed. Screen/alert durations are
1–86,400 seconds. Smooth playback and ESP8266 peak memory still require device
validation before release. Transition support depends on device firmware;
bitmap-wipe data must be static RGB565 pixels matching its width and the configured display height.

## How it works

1. The integration opens a WebSocket to `ws://<pixelit-ip>:81`.
2. PixelIt streams its live pixels as `{"liveview":"<hex>"}` (~6 hex chars per pixel, row by row).
3. The integration validates the frame and publishes it as the sensor’s `hex` attribute.
4. The card decodes the frame and renders the pixels as a grid, stretching to fill the card width while keeping pixels square.


## WebSocket port

New entries use the firmware's fixed WebSocket port 81 without asking the user.
Existing entries retain a stored port internally for compatibility, including
when reconfiguring their host or dimensions.

## Card editor and layout

The custom editor uses `ha-form` and native selectors, with language-aware labels
and a collapsible Advanced section. Editor/YAML configuration shares validation
for gap (integer 0–16), booleans, title and sensor entity. Older card tags and
width/height fallbacks remain supported. Theme styling is the default; set
`transparent: true` for the previous frameless appearance. Status is independent
of the title. Sections use automatic content height; masonry uses measured height
with an aspect-ratio estimate before layout. Pixel gaps shrink on narrow cards.

## User-friendly action content

`set_screen` and `show_alert` accept the same simple text options as
`show_message`: `message`, `color` (#RRGGBB, default white), `scroll`,
`large_font`, `center`, and optional `icon`. They can also use `clock: true`
instead of a message. Advanced `screen` payloads remain supported; the screen,
message and clock choices are mutually exclusive. Icon-only content is allowed.
Explicit advanced payloads retain their own text styling and positioning.

Action forms use native text inputs and a text selector with `type: color` for
color picking, preserving the existing hexadecimal `color` field. Text appearance
and advanced payloads live in collapsed sections. Sections do not change the
flat action data structure. The playlist selector now edits a list of names via
`text.multiple`; the existing `screens: [clock, weather]` format stays valid.

## Device sensors

Sensor readings use the existing `sensor` WebSocket envelopes; illuminance and
physical sensor messages are merged by field. Diagnostic readings use `sysinfo`.
Only `temperatureUnit` is read from `config`; configuration secrets are not retained.
Celsius/Fahrenheit comes from enum values 0/1. Temperature stays unavailable until
its unit is known. Reconnect clears readings and unit metadata before fresh state.

Entities are discovered lazily for firmware fields that are actually reported,
excluding `Not installed`. Environment sensors use measurement state classes,
correct native units and device classes. The BME680 gas reading is resistance in
kΩ, not a VOC concentration. Diagnostics are disabled by default. Diagnostic
coverage includes MQTT-discovered fields plus IP address, firmware versions,
board-specific flash/heap values and animation frame count. Board-specific values
are only created when present. Each entity has a stable per-entry unique ID.
Invalid values (including booleans, non-finite numbers, impossible percentages and
overlong text) are unavailable. Updates are push-only; no extra polling or device
requests are introduced. Sensor subscribers do not receive live pixel updates.

The card's entity selection and suggestions now check for Liveview attributes,
so additional environmental or diagnostic sensors cannot displace Liveview.

## Transition controls for firmware 3.0.0 prereleases

`transition` is optional on `show_message`, `show_alert` and `set_screen`. Omitting
it preserves an existing advanced `screen.switchAnimation`. Explicit `none`
sets `aktiv: false`; other values set `aktiv: true` and the firmware effect name.
An explicit selection replaces the advanced transition. `zigzagWipe` uses the
flat `color` value as `hexColor`.

`bitmapWipe` requires `transition_bitmap`, a static Gallery ID. HA resolves it
through the bounded Gallery cache, infers width (8/32), and stores pixels for
playlist reuse. Inline advanced wipe pixels remain accepted. Validation requires
width within the configured matrix, one row per display row, RGB565 pixels and
at most 256 wipe pixels, with the existing combined payload limit still applied.
Animated wipe images are rejected. This adds no firmware buffer allocations or
polling; the firmware performs the transition.

Compatibility was checked locally at firmware tags `3.0.0-beta`, `.beta.0` through
`.beta.7` and `3.0.0-rc.1` (the shorthand `.beta.N` means `3.0.0-beta.N`). The
expanded effects begin at beta.1, verticalSlide at beta.6. Before every actual
transmission, the coordinator checks `sysinfo.pixelitVersion`; this also protects
stored playlists after a firmware downgrade. Saved configuration may contain an
effect for a newer firmware, but attempting playback on an older device raises an
error or pauses background playback. `random` is selected by the firmware, not HA.
No arbitrary delays are added; alert/playlist duration still starts after command
acknowledgement and includes the transition's runtime.

No companion firmware change is required. Real-device frame timing and ESP8266
peak-memory validation remain necessary before release.

The former `bitmap_api_uuid` setting is no longer exposed or used. Existing
config entries can retain that obsolete key without needing reconfiguration.

HA transition selector values use snake_case, for example `vertical_slide` and
`bitmap_wipe`. They map to firmware `verticalSlide` and `bitmapWipe` internally.
Legacy CamelCase action values remain accepted; advanced firmware payloads and
stored screens retain their original wire names.


## Native controls and physical buttons

Automatic brightness uses `setScreen` with `autobrightness` over the existing
serialized WebSocket command channel. Its state comes from
`sysinfo.matrixBrightnessAutomatic`; a successful acknowledgement alone does not
change the entity state.

Clock controls send a single whitelisted setting (`clockAutoFallbackActive` or
`clockAutoFallbackTime`, 1–86400 integer seconds) to HTTP `POST /api/config` on
port 80. Firmware 3.0.1 saves configuration and restarts after responding with
`{"response":"OK"}`. The WebSocket configuration command also restarts and has
no acknowledgement, so it is unsuitable for acknowledged control here. HTTP
requests share the device command lock, have a five-second deadline and a
1024-byte response limit, and are never automatically retried. Clock
configuration writes restart the device even when reapplying a value. States remain device-reported;
normal disconnect/reconnect handling pauses and resumes managed playback.

Button discovery uses `config.btn0Enabled` through `btn2Enabled`. WebSocket
`buttons.leftButton`, `middleButton`, and `rightButton` accept JSON booleans and
the firmware snapshot strings `"true"` and `"false"`. Only changes after a known
initial state produce `press`/`release` events. Reconnect clears baselines and
hardware availability; disabled buttons are unavailable. All entity discovery
and event listeners are removed on unload. There is no button polling, gesture
timer, or retained/replayed event. Firmware 3.0.1 sends resolved single/double/long
press gestures only through MQTT; adding native gestures requires a bounded,
non-retained WebSocket firmware event channel. No firmware changes or increased
animation/network limits are introduced by these platforms.
