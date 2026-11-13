"""Playback regression tests with a deterministic clock and fake transport."""

import asyncio
import unittest
from copy import deepcopy
from unittest.mock import patch

from test_control import HAError, coordinator

Player = coordinator.ScreenPlayer


def text(value):
    return {"text": {"textString": value, "hexColor": "#FFFFFF"}}


class Timer:
    def __init__(self, seconds, callback):
        self.seconds, self.callback, self.cancelled = seconds, callback, False

    def cancel(self):
        self.cancelled = True

    def fire(self, even_if_cancelled=False):
        if not self.cancelled or even_if_cancelled:
            self.callback()


class Store:
    def __init__(self):
        self.data = None
        self.send_fails = False

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, data):
        if self.send_fails:
            raise OSError("disk error")
        self.data = deepcopy(data)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.ready = True
        self.sent, self.timers = [], []
        self.send_fails = False
        self.store = Store()

        async def send(screens, duration=0):
            if self.send_fails:
                raise HAError("disconnected")
            self.sent.extend(deepcopy(screens))

        self.send = send
        self.player = Player(
            send, lambda: self.ready, 32, 8, self.store, call_later=self.schedule
        )
        self.player._was_ready = True
        await self.player.async_set_screen("one", text("ONE"), 3)
        await self.player.async_set_screen("two", text("TWO"), 5)

    def schedule(self, seconds, callback):
        timer = Timer(seconds, callback)
        self.timers.append(timer)
        return timer

    async def settle(self):
        for _ in range(5):
            await asyncio.sleep(0)

    async def asyncTearDown(self):
        await self.player.async_stop()

    async def test_playlist_rotates_with_per_screen_duration(self):
        await self.player.async_set_playlist(["one", "two"])
        self.assertEqual(self.sent, [text("ONE")])
        self.assertEqual(self.timers[-1].seconds, 3)
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], text("TWO"))
        self.assertEqual(self.timers[-1].seconds, 5)
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], text("ONE"))

    async def test_alert_interrupts_and_resumes_next_screen(self):
        await self.player.async_set_playlist(["one", "two"])
        previous = self.timers[-1]
        await self.player.async_show_alert(text("ALERT"), 10)
        self.assertTrue(previous.cancelled)
        self.assertTrue(self.player.alert_active)
        self.assertEqual(self.timers[-1].seconds, 10)
        self.assertEqual(self.sent[-1], text("ALERT"))
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], text("TWO"))
        self.assertFalse(self.player.alert_active)

    async def test_latest_alert_wins_and_stale_timer_is_ignored(self):
        await self.player.async_set_playlist(["one", "two"])
        await self.player.async_show_alert(text("OLD"), 10)
        old = self.timers[-1]
        await self.player.async_show_alert(text("NEW"), 20)
        old.fire(even_if_cancelled=True)
        await self.settle()
        self.assertEqual(self.sent[-1], text("NEW"))
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], text("TWO"))

    async def test_alert_returns_to_managed_base_or_clock(self):
        await self.player.async_show_screen("one")
        await self.player.async_show_alert(text("TEMP"), 10)
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], text("ONE"))
        self.player._base = None
        await self.player.async_show_alert(text("TEMP"), 10)
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], {"clock": {"show": True}})

    async def test_sleep_or_disconnect_pauses_then_resumes_once(self):
        await self.player.async_set_playlist(["one", "two"])
        old = self.timers[-1]
        self.ready = False
        self.player.state_changed()
        old.fire(even_if_cancelled=True)
        await self.settle()
        self.assertEqual(self.sent[-1], text("ONE"))
        self.ready = True
        self.player.state_changed()
        self.player.state_changed()
        await self.settle()
        self.assertEqual(self.sent, [text("ONE"), text("TWO")])

    async def test_alert_disconnected_without_base_returns_to_clock(self):
        await self.player.async_show_alert(text("TEMP"), 10)
        self.ready = False
        self.player.state_changed()
        self.ready = True
        self.player.state_changed()
        await self.settle()
        self.assertEqual(self.sent[-1], {"clock": {"show": True}})

    async def test_playlist_can_be_set_while_asleep(self):
        self.ready = False
        self.player.state_changed()
        await self.player.async_set_playlist(["two"])
        self.assertEqual(self.sent, [])
        self.ready = True
        self.player.state_changed()
        await self.settle()
        self.assertEqual(self.sent, [text("TWO")])

    async def test_stop_invalidates_pending_callbacks(self):
        await self.player.async_set_playlist(["one", "two"])
        old = self.timers[-1]
        await self.player.async_stop_playlist()
        old.fire(even_if_cancelled=True)
        await self.settle()
        self.assertEqual(self.sent, [text("ONE")])
        self.assertEqual(self.store.data["playlist"], [])

    async def test_unload_prevents_all_late_sends(self):
        await self.player.async_show_alert(text("TEMP"), 10)
        old = self.timers[-1]
        await self.player.async_stop()
        old.fire(even_if_cancelled=True)
        await self.settle()
        self.assertEqual(self.sent[-1], text("TEMP"))
        with self.assertRaises(HAError):
            await self.player.async_set_playlist(["one"])

    async def test_failed_tick_pauses_without_retry_flood(self):
        await self.player.async_set_playlist(["one", "two"])
        self.send_fails = True
        count = len(self.timers)
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(len(self.timers), count)
        self.assertEqual(self.player.last_error, "disconnected")

    async def test_invalid_playlist_does_not_replace_working_playlist(self):
        await self.player.async_set_playlist(["one"])
        for playlist in (["missing"], "one", [1], ["one"] * 101):
            with self.assertRaises(HAError):
                await self.player.async_set_playlist(playlist)
        self.assertEqual(self.player.playlist, ["one"])
        self.assertFalse(self.timers[-1].cancelled)

    async def test_persistence_does_not_store_alerts(self):
        await self.player.async_set_playlist(["one", "two"])
        await self.player.async_show_alert(text("TEMP"), 10)
        restored = Player(self.send, lambda: False, 32, 8, self.store)
        await restored.async_load()
        self.assertEqual(restored.playlist, ["one", "two"])
        self.assertEqual(restored.screens["one"]["screen"], text("ONE"))
        self.assertFalse(restored.alert_active)
        await restored.async_stop()

    async def test_storage_failure_keeps_running_playlist(self):
        await self.player.async_set_playlist(["one"])
        self.store.send_fails = True
        with self.assertRaisesRegex(HAError, "Could not save"):
            await self.player.async_set_playlist(["two"])
        self.assertEqual(self.player.playlist, ["one"])
        self.assertFalse(self.timers[-1].cancelled)

    async def test_screen_validation_and_storage_limits(self):
        invalid = [
            {"sleepMode": True},
            {},
            {"text": {"textString": ""}},
            {"bitmap": {"data": [0] * 63}},
            {"bitmap": {"data": [True] * 64}},
            {"bitmapAnimation": {"data": [[0] * 64] * 29, "animationDelay": 50}},
            {
                "bitmapAnimation": {
                    "data": [[0] * 256] * 8,
                    "size": {"width": 32, "height": 8},
                    "animationDelay": 50,
                }
            },
            {"text": {"textString": "x", "position": {"x": float("inf")}}},
        ]
        for screen in invalid:
            with self.assertRaises(HAError):
                await self.player.async_set_screen("bad", screen)
        for duration in (0, -1, float("nan"), float("inf"), True, 86401, 0.01):
            with self.assertRaises(HAError):
                await self.player.async_show_alert(text("bad"), duration)
        await self.player.async_set_screen("icon", {"bitmap": {"data": [0] * 64}})
        await self.player.async_set_screen(
            "animation",
            {"bitmapAnimation": {"data": [[0] * 64] * 2, "animationDelay": 50}},
        )
        with self.assertRaises(HAError):
            await self.player.async_set_screen("x" * 65, text("bad"))

    async def test_updating_screen_changes_next_playlist_turn(self):
        await self.player.async_set_playlist(["one"])
        await self.player.async_set_screen("one", text("UPDATED"), 7)
        self.assertEqual(self.sent[-1], text("ONE"))
        self.timers[-1].fire()
        await self.settle()
        self.assertEqual(self.sent[-1], text("UPDATED"))
        self.assertEqual(self.timers[-1].seconds, 7)

    async def test_unload_during_gallery_resolution_never_sends(self):
        started, release = asyncio.Event(), asyncio.Event()

        class Library:
            async def async_resolve(self, screen):
                started.set()
                await release.wait()
                return text("LOADED")

        self.player.set_bitmap_library(Library())
        alert = asyncio.create_task(
            self.player.async_show_alert({"bitmap": {"data": 1}}, 10)
        )
        await started.wait()
        stop = asyncio.create_task(self.player.async_stop())
        await asyncio.sleep(0)
        release.set()
        with self.assertRaises(HAError):
            await alert
        await stop
        self.assertEqual(self.sent, [])

    async def test_waking_for_explicit_content_does_not_send_duplicate(self):
        self.ready = False
        self.player.state_changed()
        original = self.player._send

        async def send(screens, duration=0):
            self.ready = True
            self.player.state_changed()
            await original(screens, duration)

        self.player._send = send
        await self.player.async_show_screen("one")
        await self.settle()
        self.assertEqual(self.sent, [{"sleepMode": False}, text("ONE")])

    async def test_stored_content_is_copied_and_bounds_are_enforced(self):
        screen = text("ORIGINAL")
        await self.player.async_set_screen("copy", screen)
        screen["text"]["textString"] = "CHANGED"
        self.assertEqual(self.player.screens["copy"]["screen"], text("ORIGINAL"))
        with patch.dict(Player.async_set_screen.__globals__, MAX_SCREENS=3):
            with self.assertRaises(HAError):
                await self.player.async_set_screen("over", text("OVER"))

    async def test_invalid_stored_configuration_is_reported(self):
        self.store.data = {
            "screens": {"broken": {"screen": {}, "duration": 5}},
            "playlist": ["broken"],
        }
        other = Player(self.send, lambda: False, 32, 8, self.store)
        with self.assertRaisesRegex(HAError, "Invalid stored"):
            await other.async_load()
        await other.async_stop()
