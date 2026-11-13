"""Persistent WebSocket client for PixelIt."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from contextlib import suppress

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .screens import ScreenPlayer
from .transitions import validate_firmware_transition

_LOGGER = logging.getLogger(__name__)

# If we previously received liveview data on the current connection but then
# nothing arrives within this window, treat the connection as stale and reconnect.
RECEIVE_TIMEOUT = 15.0
COMMAND_TIMEOUT = 5.0
HEX_FRAME = re.compile(r"[0-9a-fA-F]+")


class PixelItCoordinator:
    """Fetch liveview data from a PixelIt display over WebSocket."""

    def __init__(
        self, hass: HomeAssistant, host: str, port: int, width: int, height: int
    ):
        """Initialize."""
        self._session = async_get_clientsession(hass)
        self.on_update: Callable[[], None] | None = None
        self._host = host
        self._port = port
        self._width = width
        self._height = height
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._connected = False
        self._ws = None
        self._command_lock = asyncio.Lock()
        self._response = None
        self.info: dict = {}
        self.sensor_data: dict = {}
        self.temperature_unit: int | None = None
        self._data_listeners: set[Callable[[], None]] = set()
        self._control_listeners: set[Callable[[], None]] = set()
        self._hex = ""
        self._had_data = False
        self.player = ScreenPlayer(
            self.async_send_screens,
            lambda: self.connected and self.info.get("sleepMode") is False,
            width,
            height,
            changed=self._publish_controls,
        )

    @property
    def session(self) -> aiohttp.ClientSession:
        """Reuse Home Assistant's managed HTTP session for gallery requests."""
        return self._session

    @property
    def ws_url(self) -> URL:
        """Build the WebSocket URL, including IPv6 support."""
        return URL.build(scheme="ws", host=self._host, port=self._port)

    def async_start(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Start an entry-owned task without delaying HA startup."""
        self.player.set_task_factory(
            lambda coro: entry.async_create_background_task(
                hass, coro, "pixelit_playback"
            )
        )
        self._task = entry.async_create_background_task(
            hass, self._ws_loop(), "pixelit_websocket"
        )

    async def async_stop(self) -> None:
        """Wait for the WebSocket context to close."""
        self._stopping = True
        await self.player.async_stop()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def clear_listener(self) -> None:
        """Detach the sensor callback."""
        self.on_update = None

    @property
    def connected(self) -> bool:
        """Return the current connection status."""
        return self._connected

    @property
    def attributes(self) -> dict:
        """Return the latest frame."""
        return {
            "connected": self._connected,
            "width": self._width,
            "height": self._height,
            "hex": self._hex,
        }

    def add_data_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to device information and readings, never pixel frames."""
        self._data_listeners.add(listener)
        return lambda: self._data_listeners.discard(listener)

    def _publish_data(self) -> None:
        for listener in tuple(self._data_listeners):
            listener()

    def _clear_device_data(self) -> None:
        self.info = {}
        self.sensor_data = {}
        self.temperature_unit = None
        self._publish_data()

    def add_control_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state changes without publishing every pixel frame."""
        self._control_listeners.add(listener)
        return lambda: self._control_listeners.discard(listener)

    def _publish_controls(self) -> None:
        self.player.state_changed()
        for listener in tuple(self._control_listeners):
            listener()

    async def async_send_screens(self, screens: list[dict], duration: int = 0) -> None:
        """Send serialized commands and wait for firmware acknowledgement."""
        async with self._command_lock:
            ws = self._ws
            if self._stopping or ws is None or ws.closed:
                raise HomeAssistantError("PixelIt is disconnected")
            for screen in screens:
                validate_firmware_transition(screen, self.info.get("pixelitVersion"))
            try:
                for screen in screens:
                    if self._stopping:
                        raise HomeAssistantError("PixelIt is unloading")
                    self._response = asyncio.get_running_loop().create_future()
                    await ws.send_json(
                        {"setScreen": screen, "forcedDuration": duration}
                    )
                    response = await asyncio.wait_for(self._response, COMMAND_TIMEOUT)
                    if response != "OK":
                        raise HomeAssistantError(
                            f"PixelIt rejected command: {response}"
                        )
            except asyncio.CancelledError:
                await ws.close()
                raise
            except (aiohttp.ClientError, OSError, TimeoutError) as err:
                # A late acknowledgement must not be assigned to the next command.
                await ws.close()
                raise HomeAssistantError("PixelIt command failed or timed out") from err
            finally:
                self._response = None

    def _publish(self) -> None:
        if self.on_update is not None:
            self.on_update()

    async def _ws_loop(self) -> None:
        """Keep the WebSocket connected and read liveview messages."""
        while True:
            try:
                await self._run_connection()
            except (aiohttp.ClientError, OSError, TimeoutError) as err:
                _LOGGER.debug("PixelIt WebSocket error for %s: %s", self._host, err)
            finally:
                if self._connected:
                    self._connected = False
                    self._ws = None
                    self._clear_device_data()
                    if self._response is not None and not self._response.done():
                        self._response.set_exception(
                            HomeAssistantError("PixelIt disconnected")
                        )
                    self._publish_controls()
                    self._publish()
            await asyncio.sleep(5)

    async def _run_connection(self) -> None:
        """Run a single WebSocket connection until it is stale, closed, or errors."""
        async with self._session.ws_connect(self.ws_url) as ws:
            self._ws = ws
            self._clear_device_data()
            self._connected = True
            self._publish_controls()
            self._had_data = False
            self._publish()
            _LOGGER.debug("Connected to %s", self.ws_url)
            while True:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=RECEIVE_TIMEOUT)
                except asyncio.TimeoutError:
                    if self._had_data:
                        _LOGGER.debug(
                            "PixelIt sent no frames for %.0fs, reconnecting",
                            RECEIVE_TIMEOUT,
                        )
                        raise
                    # No data has ever arrived on this connection — PixelIt may
                    # legitimately be idle. Keep waiting instead of hammering it.
                    continue
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._handle_message(msg.data)
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                    aiohttp.WSMsgType.CLOSE,
                ):
                    break

    def _handle_message(self, message) -> None:
        if not isinstance(message, str):
            return
        try:
            obj = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(obj, dict):
            return
        if (
            "response" in obj
            and self._response is not None
            and not self._response.done()
        ):
            self._response.set_result(obj["response"])
        if isinstance(obj.get("sysinfo"), dict):
            self.info = obj["sysinfo"]
            self._publish_controls()
            self._publish_data()
        if isinstance(obj.get("sensor"), dict):
            readings = {
                key: value
                for key, value in obj["sensor"].items()
                if key
                in {"temperature", "humidity", "pressure", "gas", "lux", "battery"}
            }
            if readings:
                self.sensor_data.update(readings)
                self._publish_data()
        if isinstance(obj.get("config"), dict) and "temperatureUnit" in obj["config"]:
            unit = obj["config"]["temperatureUnit"]
            self.temperature_unit = (
                unit if type(unit) is int and unit in (0, 1) else None
            )
            self._publish_data()
        if not isinstance(obj.get("liveview"), str):
            return
        frame = obj["liveview"][: self._width * self._height * 6]
        frame = frame[: len(frame) - len(frame) % 6]
        if not HEX_FRAME.fullmatch(frame):
            return

        self._had_data = True
        if frame != self._hex:
            self._hex = frame
            self._publish()
