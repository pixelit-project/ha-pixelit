"""Transition payload and prerelease compatibility regression tests."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import voluptuous as vol
from test_bitmaps import Session
from test_control import HAError, Socket, coordinator, light, services, stubs

with patch.dict("sys.modules", stubs):
    import pixelit_test.bitmaps as bitmaps
    import pixelit_test.screens as screens
    import pixelit_test.transitions as transitions


class TransitionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = coordinator.PixelItCoordinator(None, "device", 81, 32, 8)
        self.client._connected = True
        self.client.info = {"pixelitVersion": "3.0.0-rc.1"}
        self.ws = Socket(self.client)
        self.client._ws = self.ws
        self.entry = SimpleNamespace(
            entry_id="test",
            title="device",
            data={"host": "device"},
            runtime_data=self.client,
        )
        self.light = light.PixelItLight(self.entry)

    async def asyncTearDown(self):
        await self.client.player.async_stop()

    async def test_message_alert_and_saved_screen_carry_effect(self):
        schema = vol.Schema(services.ACTION_SCHEMAS["show_message"])
        await self.light.async_show_message(
            **schema({"message": "Hello", "transition": "fade"})
        )
        self.assertEqual(
            self.ws.sent[-1]["setScreen"]["switchAnimation"],
            {"aktiv": True, "animation": "fade"},
        )
        schema = vol.Schema(services.ACTION_SCHEMAS["show_alert"])
        await self.light.async_show_alert(
            **schema({"message": "Alert", "transition": "verticalSlide"})
        )
        self.assertEqual(
            self.ws.sent[-1]["setScreen"]["switchAnimation"]["animation"],
            "verticalSlide",
        )
        schema = vol.Schema(services.ACTION_SCHEMAS["set_screen"])
        await self.light.async_set_screen(
            **schema({"name": "hello", "message": "Hello", "transition": "curtain"})
        )
        stored = self.client.player.screens["hello"]["screen"]
        self.assertEqual(stored["switchAnimation"]["animation"], "curtain")
        await self.light.async_show_screen("hello")
        self.assertEqual(
            self.ws.sent[-1]["setScreen"]["switchAnimation"]["animation"], "curtain"
        )

    async def test_incompatible_effect_does_not_wake_or_send(self):
        self.client.info = {"pixelitVersion": "3.0.0-beta.5"}
        schema = vol.Schema(services.ACTION_SCHEMAS["show_alert"])
        with self.assertRaisesRegex(HAError, "beta.6"):
            await self.light.async_show_alert(
                **schema({"message": "Hello", "transition": "verticalSlide"})
            )
        self.assertEqual(self.ws.sent, [])

    async def test_saved_effect_is_rechecked_after_firmware_downgrade(self):
        schema = vol.Schema(services.ACTION_SCHEMAS["set_screen"])
        await self.light.async_set_screen(
            **schema({"name": "hello", "message": "Hello", "transition": "curtain"})
        )
        self.client.info = {"pixelitVersion": "3.0.0-beta.0"}
        with self.assertRaisesRegex(HAError, "beta.1"):
            await self.light.async_show_screen("hello")
        self.assertEqual(self.ws.sent, [])

    def test_firmware_boundaries(self):
        cases = [
            ("3.0.0-beta", False, False),
            ("3.0.0-beta.0", False, False),
            ("3.0.0-beta.1", True, False),
            ("3.0.0-beta.5", True, False),
            ("3.0.0-beta.6", True, True),
            ("3.0.0-beta.7", True, True),
            ("3.0.0-rc.1", True, True),
            ("3.0.0", True, True),
            ("v3.0.0-beta.6+build", True, True),
            ("2.7.0", False, False),
            (None, False, False),
        ]
        for version, expanded, vertical in cases:
            for effect, supported in [
                ("curtain", expanded),
                ("verticalSlide", vertical),
            ]:
                payload = {"switchAnimation": {"aktiv": True, "animation": effect}}
                if supported:
                    transitions.validate_firmware_transition(payload, version)
                else:
                    with self.assertRaises(HAError):
                        transitions.validate_firmware_transition(payload, version)
        transitions.validate_firmware_transition(
            {"switchAnimation": {"aktiv": True, "animation": "random"}}, "3.0.0-beta"
        )

    def test_default_preserves_advanced_effect_and_none_overrides_it(self):
        payload = {
            "text": {"textString": "Hello"},
            "switchAnimation": {"aktiv": True, "animation": "slide"},
        }
        copied = transitions.with_transition(payload, None, None, "#FFFFFF")
        self.assertEqual(copied, payload)
        self.assertIsNot(copied, payload)
        disabled = transitions.with_transition(payload, "none", None, "#FFFFFF")
        self.assertEqual(disabled["switchAnimation"], {"aktiv": False})
        self.assertTrue(payload["switchAnimation"]["aktiv"])

    def test_invalid_transition_inputs_are_rejected(self):
        schema = vol.Schema(services.ACTION_SCHEMAS["show_alert"])
        with self.assertRaises(vol.Invalid):
            schema({"message": "Hello", "transition": "invalid"})
        for effect, bitmap in [
            ("bitmapWipe", None),
            ("bitmapWipe", True),
            ("fade", 42),
            (None, 42),
        ]:
            with self.assertRaises(HAError):
                transitions.with_transition(
                    {"text": {"textString": "Hi"}}, effect, bitmap, "#FFFFFF"
                )
        wipe = transitions.with_transition(
            {"text": {"textString": "Hi"}}, "zigzagWipe", None, "#123456"
        )
        self.assertEqual(wipe["switchAnimation"]["hexColor"], "#123456")

    async def test_bitmap_wipe_is_resolved_validated_and_persisted(self):
        self.client.player.set_bitmap_library(bitmaps.BitmapLibrary(Session()))
        schema = vol.Schema(services.ACTION_SCHEMAS["set_screen"])
        await self.light.async_set_screen(
            **schema(
                {
                    "name": "wipe",
                    "message": "Hello",
                    "transition": "bitmapWipe",
                    "transition_bitmap": 42,
                }
            )
        )
        payload = self.client.player.screens["wipe"]["screen"]
        self.assertEqual(payload["switchAnimation"]["width"], 8)
        self.assertEqual(len(payload["switchAnimation"]["data"]), 64)
        screens.validate_screen(payload, 32, 8)
        await self.light.async_show_screen("wipe")
        self.assertEqual(
            self.ws.sent[-1]["setScreen"]["switchAnimation"]["data"], [0] * 64
        )
        bad = {
            **payload,
            "switchAnimation": {**payload["switchAnimation"], "width": 32},
        }
        with self.assertRaises(HAError):
            screens.validate_screen(bad, 32, 8)

    async def test_animated_bitmap_wipe_is_rejected_before_send(self):
        import json

        session = Session()
        session.raw = json.dumps(
            {"id": 42, "rgB565Array": ",".join([json.dumps([0] * 64)] * 2)}
        ).encode()
        self.client.player.set_bitmap_library(bitmaps.BitmapLibrary(session))
        schema = vol.Schema(services.ACTION_SCHEMAS["show_alert"])
        with self.assertRaisesRegex(HAError, "static bitmap"):
            await self.light.async_show_alert(
                **schema(
                    {
                        "message": "Hello",
                        "transition": "bitmapWipe",
                        "transition_bitmap": 42,
                    }
                )
            )
        self.assertEqual(self.ws.sent, [])

    async def test_ha_selector_keys_and_legacy_names_use_same_wire_payload(self):
        for schema_name in ("show_message", "show_alert", "set_screen"):
            schema = vol.Schema(services.ACTION_SCHEMAS[schema_name])
            for public, wire in transitions.TRANSITION_OPTIONS.items():
                base = {"message": "Hello", "transition": public}
                if schema_name == "set_screen":
                    base["name"] = "hello"
                if public == "bitmap_wipe":
                    base["transition_bitmap"] = 42
                data = schema(base)
                actual = transitions.with_transition(
                    {"text": {"textString": "Hello"}},
                    data["transition"],
                    data.get("transition_bitmap"),
                    "#FFFFFF",
                )
                legacy = transitions.with_transition(
                    {"text": {"textString": "Hello"}},
                    wire,
                    data.get("transition_bitmap"),
                    "#FFFFFF",
                )
                self.assertEqual(actual, legacy)
                if public != "none":
                    self.assertEqual(actual["switchAnimation"]["animation"], wire)
