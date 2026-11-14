"""Host checks for direct controls and physical button discovery/lifecycle."""

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_control import Entity, HAError, Socket, coordinator, module, pkg, stubs


class HostEntity(Entity):
    async def async_added_to_hass(self):
        self.parent_added = True


interfaces = dict(stubs)
interfaces["pixelit_test"] = pkg
interfaces["homeassistant.const"] = module(
    "const",
    CONF_HOST="host",
    EntityCategory=SimpleNamespace(CONFIG="config"),
    UnitOfTime=SimpleNamespace(SECONDS="s"),
)
interfaces["homeassistant.components.switch"] = module(
    "switch", SwitchEntity=HostEntity
)
interfaces["homeassistant.components.number"] = module(
    "number",
    NumberEntity=HostEntity,
    NumberMode=SimpleNamespace(BOX="box"),
)
interfaces["homeassistant.components.binary_sensor"] = module(
    "binary_sensor", BinarySensorEntity=HostEntity
)
interfaces["homeassistant.components.event"] = module(
    "event",
    EventEntity=HostEntity,
    EventDeviceClass=SimpleNamespace(BUTTON="button"),
)
with patch.dict("sys.modules", interfaces):
    from pixelit_test import binary_sensor, event, number, switch


class Response:
    def __init__(self, raw=b'{"response":"OK"}', error=None):
        self.raw = raw
        self.error = error
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        if self.error:
            raise self.error

    async def read(self, limit):
        limit = min(limit, 2)
        chunk, self.raw = self.raw[:limit], self.raw[limit:]
        return chunk


class DeviceControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = coordinator.PixelItCoordinator(None, "device", 81, 32, 8)
        self.client._connected = True
        self.client._ws = Socket(self.client)
        self.cleanup = []
        self.entry = SimpleNamespace(
            entry_id="entry",
            title="device",
            data={"host": "device"},
            runtime_data=self.client,
            async_on_unload=self.cleanup.append,
        )
        self.sent = []
        self.response = Response()
        self.client._session = SimpleNamespace(post=self.post)

    def post(self, url, **kwargs):
        self.sent.append((str(url), kwargs))
        return Response(self.response.raw, self.response.error)

    async def asyncTearDown(self):
        for cleanup in self.cleanup:
            cleanup()
        await self.client.player.async_stop()

    def send(self, **payload):
        self.client._handle_message(json.dumps(payload))

    async def test_switches_use_device_feedback_and_separate_commands(self):
        entities = []
        await switch.async_setup_entry(None, self.entry, entities.extend)
        brightness, clock = entities
        self.assertFalse(brightness.available)
        self.send(
            sysinfo={
                "matrixBrightnessAutomatic": False,
                "clockAutoFallbackActive": False,
            }
        )
        await brightness.async_turn_on()
        self.assertEqual(
            self.client._ws.sent[-1]["setScreen"], {"autobrightness": True}
        )
        self.assertFalse(brightness.is_on)
        await clock.async_turn_on()
        self.assertEqual(
            self.sent[-1],
            ("http://device/api/config", {"json": {"clockAutoFallbackActive": True}}),
        )
        self.assertFalse(clock.is_on)
        self.send(
            sysinfo={"matrixBrightnessAutomatic": True, "clockAutoFallbackActive": True}
        )
        self.assertTrue(brightness.is_on)
        self.assertTrue(clock.is_on)
        await brightness.async_turn_off()
        await clock.async_turn_off()
        self.assertEqual(self.sent[-1][1]["json"], {"clockAutoFallbackActive": False})
        self.client._connected = False
        self.assertFalse(clock.available)
        with self.assertRaises(HAError):
            await clock.async_turn_on()

    async def test_number_bounds_feedback_and_config_failures(self):
        entity = number.PixelItClockDelay(self.entry)
        for invalid in (True, None, "2", 0, -1, 86401, 1.5, float("nan"), float("inf")):
            with self.assertRaises(HAError):
                await entity.async_set_native_value(invalid)
        self.assertEqual(self.sent, [])
        self.send(sysinfo={"clockAutoFallbackTime": 10})
        for value in (1, 86400, 30.0):
            await entity.async_set_native_value(value)
            self.assertEqual(
                self.sent[-1][1]["json"], {"clockAutoFallbackTime": int(value)}
            )
        self.assertEqual(entity.native_value, 10)
        for raw in (b"{}", b"[]", b"invalid", b'{"response":"failed"}', b"x" * 1025):
            self.response = Response(raw)
            with self.assertRaises(HAError):
                await entity.async_set_native_value(20)
        self.response = Response(error=OSError("failed"))
        with self.assertRaises(HAError):
            await entity.async_set_native_value(20)
        self.client._stopping = True
        with self.assertRaises(HAError):
            await entity.async_set_native_value(20)

    async def test_buttons_discovery_snapshot_transitions_and_cleanup(self):
        states, events = [], []
        await binary_sensor.async_setup_entry(None, self.entry, states.extend)
        await event.async_setup_entry(None, self.entry, events.extend)
        self.send(buttons={"leftButton": "false", "middleButton": "true"})
        self.assertEqual(states, [])
        self.send(
            config={"btn0Enabled": True, "btn1Enabled": False, "btn2Enabled": False}
        )
        self.assertEqual(len(states), 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(states[0]._attr_unique_id, "entry_left_button")
        observed = []
        for entity in states + events:
            entity.async_on_remove = self.cleanup.append
            entity.async_write_ha_state = lambda: None
            entity._trigger_event = observed.append
            await entity.async_added_to_hass()
            self.assertTrue(entity.parent_added)
        self.send(buttons={"leftButton": False})
        self.assertEqual(observed, [])
        self.send(buttons={"leftButton": True})
        self.assertTrue(states[0].is_on)
        self.send(buttons={"leftButton": True})
        self.send(buttons={"leftButton": False})
        self.assertEqual(observed, ["press", "release"])
        for invalid in (None, 1, "invalid", {}, []):
            self.send(buttons={"leftButton": invalid})
        self.assertEqual(observed, ["press", "release"])
        self.send(config={"temperatureUnit": 0})
        self.assertTrue(states[0].available)
        self.send(config={"btn0Enabled": False})
        self.assertFalse(states[0].available)
        self.send(buttons={"leftButton": True})
        self.assertEqual(observed, ["press", "release"])
        self.client._connected = False
        self.client._clear_device_data()
        self.assertFalse(events[0].available)
        self.client._connected = True
        self.send(config={"btn0Enabled": True, "btn2Enabled": True})
        self.send(buttons={"leftButton": "true", "rightButton": "false"})
        self.assertEqual(observed, ["press", "release"])
        self.assertEqual(len(states), 2)
        self.send(liveview="FF0000")
        self.assertEqual(observed, ["press", "release"])
        for remove in self.cleanup:
            remove()
        self.send(buttons={"leftButton": False})
        self.assertEqual(observed, ["press", "release"])
        self.assertEqual(self.client._button_listeners, set())

    async def test_clock_setting_validation(self):
        for field, value in [
            ("bad", 10),
            ("clockAutoFallbackActive", 1),
            ("clockAutoFallbackTime", True),
            ("clockAutoFallbackTime", 0),
        ]:
            with self.assertRaises(HAError):
                await self.client.async_set_clock_config(field, value)
        self.assertEqual(self.sent, [])

    async def test_clock_request_timeout_is_reported(self):
        class SlowResponse(Response):
            async def read(self, limit):
                await asyncio.Event().wait()

        self.client._session = SimpleNamespace(
            post=lambda *args, **kwargs: SlowResponse()
        )
        with (
            patch.object(coordinator, "COMMAND_TIMEOUT", 0.001),
            self.assertRaises(HAError),
        ):
            await self.client.async_set_clock_config("clockAutoFallbackTime", 20)
        self.assertFalse(self.client._command_lock.locked())

    async def test_control_translations_match_entity_keys(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "custom_components/pixelit"
        expected = {
            "switch": {"automatic_brightness", "automatic_clock"},
            "number": {"clock_fallback_delay"},
            "binary_sensor": {side + "_button" for side in ("left", "middle", "right")},
            "event": {side + "_button_event" for side in ("left", "middle", "right")},
        }
        for file in ("strings.json", "translations/en.json", "translations/de.json"):
            data = json.loads((root / file).read_text())
            for platform, keys in expected.items():
                self.assertEqual(set(data["entity"][platform]), keys)
            for description in data["entity"]["event"].values():
                self.assertEqual(
                    set(description["state_attributes"]["event_type"]["state"]),
                    {"press", "release"},
                )
