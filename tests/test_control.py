"""Host protocol tests. HA interfaces are stubbed; no running HA is required."""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import aiohttp  # Keep transport modules loaded outside the temporary HA stubs.
import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]


def module(name, **attrs):
    obj = ModuleType(name)
    obj.__dict__.update(attrs)
    return obj


class HAError(Exception):
    pass


class Entity:
    pass


platform = SimpleNamespace(async_register_entity_service=lambda *args: None)
stubs = {
    "homeassistant": module("homeassistant"),
    "homeassistant.config_entries": module("config_entries", ConfigEntry=object),
    "homeassistant.core": module(
        "core", HomeAssistant=object, callback=lambda func: func
    ),
    "homeassistant.const": module("const", CONF_HOST="host"),
    "homeassistant.exceptions": module(
        "exceptions", HomeAssistantError=HAError, ServiceValidationError=HAError
    ),
    "homeassistant.components": module("components"),
    "homeassistant.components.light": module(
        "light",
        ATTR_BRIGHTNESS="brightness",
        ColorMode=SimpleNamespace(BRIGHTNESS="brightness"),
        LightEntity=Entity,
    ),
    "homeassistant.helpers": module("helpers"),
    "homeassistant.helpers.aiohttp_client": module(
        "aiohttp_client", async_get_clientsession=lambda hass: None
    ),
    "homeassistant.helpers.config_validation": module("cv", string=str, boolean=bool),
    "homeassistant.helpers.device_registry": module("device_registry", DeviceInfo=dict),
    "homeassistant.helpers.entity_platform": module(
        "entity_platform", async_get_current_platform=lambda: platform
    ),
}
stubs["homeassistant.helpers.service"] = module(
    "service", async_register_platform_entity_service=lambda *args, **kwargs: None
)
stubs["homeassistant.helpers"].service = stubs["homeassistant.helpers.service"]
stubs["homeassistant.helpers"].config_validation = stubs[
    "homeassistant.helpers.config_validation"
]
stubs["homeassistant.helpers"].entity_platform = stubs[
    "homeassistant.helpers.entity_platform"
]
pkg = module("pixelit_test")
pkg.__path__ = [str(ROOT / "custom_components/pixelit")]
stubs["pixelit_test"] = pkg
with patch.dict(sys.modules, stubs):
    import pixelit_test.coordinator as coordinator
    import pixelit_test.light as light
    import pixelit_test.services as services


class Socket:
    closed = False

    def __init__(self, client, response="OK"):
        self.client = client
        self.response = response
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)
        await asyncio.sleep(0)
        if self.response is not None:
            self.client._handle_message(json.dumps({"response": self.response}))

    async def close(self):
        self.closed = True


class ControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = coordinator.PixelItCoordinator(None, "::1", 81, 32, 8)
        self.ws = Socket(self.client)
        self.client._ws = self.ws
        self.client._connected = True
        self.entry = SimpleNamespace(
            entry_id="test",
            title="Matrix",
            data={"host": "::1"},
            runtime_data=self.client,
        )
        self.light = light.PixelItLight(self.entry)

    async def test_power_brightness_and_device_feedback(self):
        self.assertFalse(self.light.available)
        self.client._handle_message(
            json.dumps(
                {"sysinfo": {"sleepMode": False, "currentMatrixBrightness": 123}}
            )
        )
        self.assertTrue(self.light.available)
        self.assertTrue(self.light.is_on)
        self.assertEqual(self.light.brightness, 123)
        await self.light.async_turn_on(brightness=80)
        await self.light.async_turn_off()
        self.assertEqual(
            self.ws.sent[0]["setScreen"], {"sleepMode": False, "brightness": 80}
        )
        self.assertEqual(self.ws.sent[1]["setScreen"], {"sleepMode": True})
        # No optimistic state: external state remains authoritative.
        self.assertTrue(self.light.is_on)

    async def test_message_wake_and_content_are_atomic(self):
        await asyncio.gather(
            self.light.async_show_message("Fertig", "#00FF00", "off", True, True, 10),
            self.light.async_turn_off(),
        )
        self.assertEqual(self.ws.sent[0]["setScreen"], {"sleepMode": False})
        content = self.ws.sent[1]
        self.assertNotIn("sleepMode", content["setScreen"])
        self.assertEqual(content["forcedDuration"], 10000)
        text = content["setScreen"]["text"]
        self.assertEqual(text["textString"], "Fertig")
        self.assertEqual(text["hexColor"], "#00FF00")
        self.assertIs(text["scrollText"], False)
        self.assertEqual(text["bigFont"], 1)
        self.assertEqual(self.ws.sent[2]["setScreen"], {"sleepMode": True})

    async def test_errors_and_timeout(self):
        self.ws.response = "Invalid animation"
        with self.assertRaisesRegex(HAError, "rejected"):
            await self.light.async_turn_off()
        self.ws.response = None
        with patch.object(coordinator, "COMMAND_TIMEOUT", 0.01):
            with self.assertRaisesRegex(HAError, "timed out"):
                await self.light.async_turn_off()
        self.assertTrue(self.ws.closed)
        with self.assertRaisesRegex(HAError, "disconnected"):
            await self.light.async_turn_off()

    async def test_cancellation_closes_socket(self):
        self.ws.response = None
        task = asyncio.create_task(self.light.async_turn_off())
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(self.ws.closed)
        self.assertIsNone(self.client._response)

    async def test_liveview_does_not_trigger_control_updates(self):
        frames, controls = [], []
        self.client.on_update = lambda: frames.append(True)
        remove = self.client.add_control_listener(lambda: controls.append(True))
        self.client._handle_message('{"liveview":"FF0000"}')
        self.assertEqual(self.client.attributes["hex"], "FF0000")
        self.assertEqual(len(frames), 1)
        self.assertEqual(len(controls), 0)
        self.client._handle_message('{"sysinfo":{"sleepMode":true}}')
        self.assertEqual(len(controls), 1)
        remove()
        self.client._handle_message('{"sysinfo":{"sleepMode":false}}')
        self.assertEqual(len(controls), 1)
        for value in ("bad", "[]", '{"sysinfo":null}', '{"response":"OK"}'):
            self.client._handle_message(value)

    async def test_action_validation(self):
        captured = []
        with patch.object(
            services.service,
            "async_register_platform_entity_service",
            lambda *args, **kwargs: captured.append((args, kwargs)),
        ):
            services.async_setup_services(None)
        self.assertEqual(len(captured), 6)
        self.assertTrue(
            all(
                args[1] == "pixelit" and kwargs["entity_domain"] == "light"
                for args, kwargs in captured
            )
        )
        schema = vol.Schema(captured[0][1]["schema"])
        self.assertEqual(schema({"message": "Test"})["scroll"], "auto")
        for data in (
            {"message": ""},
            {"message": "x" * 256},
            {"message": "x", "color": "red"},
            {"message": "x", "protection_duration": -1},
            {"message": "x", "scroll": "invalid"},
        ):
            with self.assertRaises(vol.Invalid):
                schema(data)

    async def test_friendly_alert_fields_become_screen_content(self):
        data = vol.Schema(services.ACTION_SCHEMAS["show_alert"])(
            {
                "message": "Fertig",
                "color": "#123456",
                "scroll": "off",
                "large_font": True,
                "center": False,
                "duration": 10,
            }
        )
        await self.light.async_show_alert(**data)
        text = self.ws.sent[-1]["setScreen"]["text"]
        self.assertEqual(text["textString"], "Fertig")
        self.assertEqual(text["hexColor"], "#123456")
        self.assertIs(text["scrollText"], False)
        self.assertIs(text["bigFont"], True)
        self.assertIs(text["centerText"], False)
        await self.client.player.async_stop()

    async def test_friendly_saved_text_and_clock(self):
        schema = vol.Schema(services.ACTION_SCHEMAS["set_screen"])
        await self.light.async_set_screen(
            **schema({"name": "welcome", "message": "Hallo"})
        )
        self.assertEqual(
            self.client.player.screens["welcome"]["screen"]["text"]["hexColor"],
            "#FFFFFF",
        )
        await self.light.async_set_screen(
            **schema({"name": "clock", "clock": True, "color": "#00FF00"})
        )
        self.assertEqual(
            self.client.player.screens["clock"]["screen"],
            {"clock": {"show": True, "hexColor": "#00FF00"}},
        )

    async def test_advanced_content_remains_compatible(self):
        screen = {
            "text": {
                "textString": "Legacy",
                "hexColor": "#CC0000",
                "position": {"x": 3, "y": 1},
            }
        }
        data = vol.Schema(services.ACTION_SCHEMAS["show_alert"])({"screen": screen})
        await self.light.async_show_alert(**data)
        self.assertEqual(self.ws.sent[-1]["setScreen"], screen)
        await self.client.player.async_stop()

    async def test_gallery_animation_options_reach_device_for_all_actions(self):
        from test_bitmaps import Session, bitmaps

        session = Session()
        session.raw = json.dumps(
            {"id": 42, "rgB565Array": ",".join([json.dumps([0] * 64)] * 2)}
        ).encode()
        self.client.player.set_bitmap_library(bitmaps.BitmapLibrary(session))
        for action in ("show_message", "show_alert", "set_screen"):
            with self.subTest(action=action):
                data = {
                    "message": "Hello",
                    "icon": 42,
                    "icon_rubberbanding": True,
                    "icon_limit_loops": 3,
                }
                if action == "set_screen":
                    data["name"] = "animated"
                schema = vol.Schema(services.ACTION_SCHEMAS[action])
                await getattr(self.light, "async_" + action)(**schema(data))
                if action == "set_screen":
                    await self.light.async_show_screen("animated")
                animation = self.ws.sent[-1]["setScreen"]["bitmapAnimation"]
                self.assertIs(animation["rubberbanding"], True)
                self.assertEqual(animation["limitLoops"], 3)
                await self.light.async_stop_playlist()
                for field, value in (
                    ("icon_rubberbanding", "true"),
                    ("icon_limit_loops", True),
                    ("icon_limit_loops", -1),
                    ("icon_limit_loops", 1.5),
                    ("icon_limit_loops", 2**31),
                ):
                    with self.assertRaises(vol.Invalid):
                        schema({**data, field: value})
        await self.client.player.async_stop()

    async def test_ambiguous_or_empty_content_does_not_send(self):
        for action in ("show_alert", "set_screen"):
            schema = vol.Schema(services.ACTION_SCHEMAS[action])
            base = {"name": "test"} if action == "set_screen" else {}
            with self.assertRaises(vol.Invalid):
                schema(
                    {**base, "message": "hello", "screen": {"clock": {"show": True}}}
                )
            for values in ({}, {"message": "hello", "clock": True}):
                with self.assertRaises(HAError):
                    await getattr(self.light, "async_" + action)(
                        **schema({**base, **values})
                    )
        self.assertEqual(self.ws.sent, [])


if __name__ == "__main__":
    unittest.main()
