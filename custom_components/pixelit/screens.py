"""Bounded screen validation and per-device playback, independent of transport."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from collections.abc import Awaitable, Callable
from copy import deepcopy

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .transitions import TRANSITIONS

_LOGGER = logging.getLogger(__name__)
MAX_SCREENS = 100
MAX_STORAGE_BYTES = 256 * 1024
# Conservative ESP8266 transport budget; firmware remains the final validator.
MAX_PAYLOAD_BYTES = 12_288


def duration_seconds(value, *, allow_zero=False) -> float:
    """Reject non-finite, excessively short and oversized timer intervals."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ServiceValidationError("Duration must be a number of seconds")
    if not math.isfinite(value) or not (
        1 <= value <= 86400 or allow_zero and value == 0
    ):
        raise ServiceValidationError(
            "Duration must be 1–86400 seconds (or 0 when supported)"
        )
    return float(value)


def validate_screen(screen: dict, width: int, height: int) -> dict:
    """Validate display-only payloads before storing or sending them."""
    if (
        not isinstance(screen, dict)
        or not screen
        or set(screen)
        - {
            "text",
            "clock",
            "bitmap",
            "bitmapAnimation",
            "switchAnimation",
        }
        or not any(
            key in screen for key in ("text", "clock", "bitmap", "bitmapAnimation")
        )
    ):
        raise ServiceValidationError(
            "Screen must contain text, clock, bitmap or bitmapAnimation"
        )
    screen = deepcopy(screen)
    if isinstance(screen.get("text"), dict):
        text = screen["text"]
        if "hexColor" not in text and "color" not in text:
            text["hexColor"] = "#FFFFFF"
    try:
        encoded = json.dumps(
            {"setScreen": screen, "forcedDuration": 86400000}, allow_nan=False
        )
    except (TypeError, ValueError, RecursionError) as err:
        raise ServiceValidationError("Screen must contain finite JSON values") from err
    if len(encoded.encode()) > MAX_PAYLOAD_BYTES:
        raise ServiceValidationError(
            "Screen exceeds the ESP8266 WebSocket payload budget"
        )
    for key, content in screen.items():
        if not isinstance(content, dict):
            raise ServiceValidationError(f"{key} must be an object")
        position = content.get("position", {})
        if not isinstance(position, dict) or any(
            type(v) is not int or abs(v) > 32767 for v in position.values()
        ):
            raise ServiceValidationError("Pixel positions must be bounded integers")
    if "text" in screen:
        text = screen["text"]
        if (
            not isinstance(text.get("textString"), str)
            or not 1 <= len(text["textString"]) <= 255
        ):
            raise ServiceValidationError("Text must contain 1–255 characters")
        if "hexColor" in text and (
            not isinstance(text["hexColor"], str)
            or not re.fullmatch(r"#[0-9a-fA-F]{6}", text["hexColor"])
        ):
            raise ServiceValidationError("Text hexColor must use #RRGGBB")
        if "color" in text and (
            not isinstance(text["color"], dict)
            or set(text["color"]) != {"r", "g", "b"}
            or any(
                type(v) is not int or not 0 <= v <= 255 for v in text["color"].values()
            )
        ):
            raise ServiceValidationError(
                "Text RGB channels must be integers from 0 to 255"
            )
        if (
            "scrollText" in text
            and type(text["scrollText"]) is not bool
            and text["scrollText"] != "auto"
        ):
            raise ServiceValidationError("scrollText must be a boolean or auto")
        if "scrollTextDelay" in text and (
            type(text["scrollTextDelay"]) is not int
            or not 10 <= text["scrollTextDelay"] <= 10000
        ):
            raise ServiceValidationError("Scroll delay must be 10–10000 ms")
    for key in ("bitmap", "bitmapAnimation"):
        if key not in screen:
            continue
        content = screen[key]
        size = content.get("size", {"width": 8, "height": 8})
        if not isinstance(size, dict):
            raise ServiceValidationError("Bitmap size must be an object")
        w, h = size.get("width"), size.get("height")
        if (
            type(w) is not int
            or type(h) is not int
            or not (1 <= w <= width and 1 <= h <= height and w * h <= 256)
        ):
            raise ServiceValidationError(
                "Bitmap dimensions exceed the display or conservative 256-pixel limit"
            )
        frames = (
            content.get("data") if key == "bitmapAnimation" else [content.get("data")]
        )
        if (
            not isinstance(frames, list)
            or not 1 <= len(frames) <= 28
            or len(frames) * w * h > 1792
        ):
            raise ServiceValidationError(
                "Animation exceeds conservative ESP8266 frame/pixel limits"
            )
        for frame in frames:
            if (
                not isinstance(frame, list)
                or len(frame) != w * h
                or any(type(p) is not int or not 0 <= p <= 65535 for p in frame)
            ):
                raise ServiceValidationError(
                    "Bitmap data must be RGB565 pixel arrays matching size"
                )
        if key == "bitmapAnimation":
            delay = content.get("animationDelay")
            if type(delay) is not int or not 10 <= delay <= 60000:
                raise ServiceValidationError("Animation delay must be 10–60000 ms")
            if (
                "rubberbanding" in content
                and type(content["rubberbanding"]) is not bool
            ):
                raise ServiceValidationError("rubberbanding must be a boolean")
            if "limitLoops" in content and (
                type(content["limitLoops"]) is not int
                or not 0 <= content["limitLoops"] <= 2**31 - 1
            ):
                raise ServiceValidationError(
                    "limitLoops must be an integer from 0 to 2147483647"
                )
    if "switchAnimation" in screen:
        settings = screen["switchAnimation"]
        if type(settings.get("aktiv", False)) is not bool:
            raise ServiceValidationError("Transition aktiv must be a boolean")
        if settings.get("aktiv"):
            if settings.get("animation") not in TRANSITIONS[1:]:
                raise ServiceValidationError("Unknown PixelIt transition")
            if settings["animation"] == "bitmapWipe":
                data, wipe_width = settings.get("data"), settings.get("width")
                if (
                    type(wipe_width) is not int
                    or not 1 <= wipe_width <= width
                    or wipe_width * height > 256
                ):
                    raise ServiceValidationError(
                        "Bitmap Wipe width exceeds the display"
                    )
                if (
                    not isinstance(data, list)
                    or len(data) != wipe_width * height
                    or any(
                        type(pixel) is not int or not 0 <= pixel <= 65535
                        for pixel in data
                    )
                ):
                    raise ServiceValidationError(
                        "Bitmap Wipe requires RGB565 pixels matching its width and display height"
                    )
            elif "data" in settings:
                raise ServiceValidationError(
                    "Only Bitmap Wipe accepts transition pixels"
                )
    return deepcopy(screen)


class ScreenPlayer:
    """Serialize user operations and playback; never queue alerts indefinitely."""

    def __init__(
        self,
        send: Callable[..., Awaitable],
        ready: Callable[[], bool],
        width: int,
        height: int,
        store=None,
        create_task=None,
        changed=None,
        call_later=None,
    ):
        self._call_later = call_later or (
            lambda seconds, callback: asyncio.get_running_loop().call_later(
                seconds, callback
            )
        )
        self._send = send
        self._ready = ready
        self._width, self._height = width, height
        self._store = store
        self._bitmaps = None
        self._create_task = create_task or asyncio.create_task
        self._changed = changed or (lambda: None)
        self.screens: dict[str, dict] = {}
        self.playlist: list[str] = []
        self.current: str | None = None
        self.alert_active = False
        self.last_error: str | None = None
        self._base: dict | None = None
        self._next = 0
        self._timer = None
        self._generation = 0
        self._tasks: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._closed = False
        self._was_ready = False
        self._restore_clock = False
        self._resume_requested = False
        self._resume_active = False
        self._sending_content = False

    def _spawn(self, coro):
        if self._closed:
            coro.close()
            return
        task = self._create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _cancel_timer(self):
        self._generation += 1
        self._resume_requested = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _schedule(self, seconds):
        if not self._ready() or self._closed:
            return
        generation = self._generation
        self._timer = self._call_later(
            seconds, lambda: self._spawn(self._advance(generation))
        )

    def state_changed(self):
        """Pause immediately on disconnect/sleep; resume once when ready."""
        ready = self._ready()
        if not ready:
            self._cancel_timer()
            self.alert_active = False
        elif not self._was_ready and not self._closed and not self._sending_content:
            self._resume_requested = True
            if not self._resume_active:
                self._resume_active = True
                self._spawn(self._resume())
        self._was_ready = ready

    async def _resume(self):
        """Coalesce readiness changes into one owned task."""
        try:
            while self._resume_requested and not self._closed:
                self._resume_requested = False
                await self._advance(self._generation, resume=True)
        finally:
            self._resume_active = False

    def set_bitmap_library(self, library):
        """Enable optional gallery resolution before validation and storage."""
        self._bitmaps = library

    async def _resolve(self, screen):
        if self._bitmaps is not None:
            screen = await self._bitmaps.async_resolve(screen)
        return validate_screen(screen, self._width, self._height)

    def set_task_factory(self, create_task):
        """Bind timer jobs to the config entry lifecycle."""
        self._create_task = create_task

    async def async_load(self, store=None):
        """Load and validate persistent user content before connecting."""
        if store is not None:
            self._store = store
        if self._store is None:
            return
        data = await self._store.async_load()
        if data is None:
            return
        try:
            screens = data["screens"]
            if not isinstance(screens, dict) or len(screens) > MAX_SCREENS:
                raise ValueError("Invalid stored screens")
            for name, value in screens.items():
                self._validate_name(name)
                validate_screen(value["screen"], self._width, self._height)
                duration_seconds(value["duration"])
            playlist = self._validate_playlist(data["playlist"], screens)
            self._check_storage(screens, playlist)
        except (KeyError, TypeError, ValueError, HomeAssistantError) as err:
            raise HomeAssistantError(
                "Invalid stored PixelIt playback configuration"
            ) from err
        self.screens, self.playlist = deepcopy(screens), playlist

    def _validate_name(self, name):
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise ServiceValidationError("Screen name must contain 1–64 characters")

    def _validate_playlist(self, playlist, screens):
        if not isinstance(playlist, list) or len(playlist) > MAX_SCREENS:
            raise ServiceValidationError(
                "Playlist must be a list of at most 100 screen names"
            )
        if any(not isinstance(name, str) or name not in screens for name in playlist):
            raise ServiceValidationError("Every playlist screen must be stored first")
        return list(playlist)

    def _check_storage(self, screens, playlist):
        data = {"screens": screens, "playlist": playlist}
        if (
            len(screens) > MAX_SCREENS
            or len(json.dumps(data).encode()) > MAX_STORAGE_BYTES
        ):
            raise ServiceValidationError(
                "Stored screens exceed the playback storage budget"
            )
        return data

    async def _save(self, screens, playlist):
        data = self._check_storage(screens, playlist)
        if self._store is not None:
            try:
                await self._store.async_save(data)
            except OSError as err:
                raise HomeAssistantError(
                    "Could not save PixelIt screens and playlist"
                ) from err

    def _ensure_open(self):
        if self._closed:
            raise HomeAssistantError("PixelIt playback is unloaded")

    async def async_set_screen(self, name, screen, duration=5):
        self._validate_name(name)
        seconds = duration_seconds(duration)
        async with self._lock:
            self._ensure_open()
            content = await self._resolve(screen)
            self._ensure_open()
            screens = {**self.screens, name: {"screen": content, "duration": seconds}}
            await self._save(screens, self.playlist)
            self._ensure_open()
            self.screens = screens
            self._changed()

    async def async_set_playlist(self, screens):
        async with self._lock:
            self._ensure_open()
            playlist = self._validate_playlist(screens, self.screens)
            await self._save(self.screens, playlist)
            self._ensure_open()
            self._cancel_timer()
            self.playlist = playlist
            self._next = 0
            self.alert_active = False
            if playlist and self._ready():
                await self._play_next()
            self._changed()

    async def async_stop_playlist(self):
        await self.async_set_playlist([])

    async def async_show_screen(self, name):
        async with self._lock:
            self._ensure_open()
            if name not in self.screens:
                raise ServiceValidationError("Unknown screen name")
            await self._show_base(self.screens[name]["screen"], name)

    async def _send_awake(self, content, protection_duration=0):
        self._sending_content = True
        try:
            await self._send(
                [{"sleepMode": False}, content], int(protection_duration * 1000)
            )
        finally:
            self._sending_content = False

    async def _show_base(self, content, name=None, protection_duration=0):
        await self._save(self.screens, [])
        self._ensure_open()
        self._cancel_timer()
        self.playlist = []
        self.alert_active = False
        await self._send_awake(content, protection_duration)
        self._base = deepcopy(content)
        self.current = name
        self.last_error = None
        self._changed()

    async def async_show_message(self, content, protection_duration=0):
        duration_seconds(protection_duration, allow_zero=True)
        async with self._lock:
            self._ensure_open()
            content = await self._resolve(content)
            self._ensure_open()
            await self._show_base(content, protection_duration=protection_duration)

    async def async_show_alert(self, screen, duration=10):
        seconds = duration_seconds(duration)
        async with self._lock:
            self._ensure_open()
            content = await self._resolve(screen)
            self._ensure_open()
            self._cancel_timer()
            self.alert_active = True
            self._restore_clock = self._base is None and not self.playlist
            try:
                await self._send_awake(content)
            except HomeAssistantError:
                self.alert_active = False
                raise
            self.alert_active = True
            self.last_error = None
            self._schedule(seconds)
            self._changed()

    async def _play_next(self):
        name = self.playlist[self._next % len(self.playlist)]
        data = self.screens[name]
        await self._send([data["screen"]])
        self.current = name
        self._next = (self._next + 1) % len(self.playlist)
        self._base = deepcopy(data["screen"])
        self.last_error = None
        self._schedule(data["duration"])

    async def _advance(self, generation, resume=False):
        async with self._lock:
            if self._closed or generation != self._generation or not self._ready():
                return
            if resume and self._timer is not None:
                return
            self._timer = None
            self.alert_active = False
            try:
                if self.playlist:
                    await self._play_next()
                elif self._base is not None:
                    await self._send([self._base])
                elif not resume or self._restore_clock:
                    # An alert without managed content returns to the device clock.
                    await self._send([{"clock": {"show": True}}])
                    self._restore_clock = False
            except HomeAssistantError as err:
                self.last_error = str(err)
                _LOGGER.warning(
                    "PixelIt playback paused after command failure: %s", err
                )
            self._changed()

    async def async_power(self, screen):
        async with self._lock:
            self._ensure_open()
            if screen.get("sleepMode") is True:
                self._cancel_timer()
                self.alert_active = False
            await self._send([screen])

    async def async_stop(self):
        """Invalidate queued callbacks and await owned work on unload."""
        self._closed = True
        self._cancel_timer()
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        async with self._lock:
            pass
