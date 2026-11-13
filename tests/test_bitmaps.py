"""Exercise bounded gallery downloads and LRU behavior without network access."""

import json
import unittest
from unittest.mock import patch

from test_control import HAError, stubs

with patch.dict("sys.modules", stubs):
    import pixelit_test.bitmaps as bitmaps


class Content:
    def __init__(self, raw):
        self.raw = raw

    async def iter_chunked(self, size):
        for offset in range(0, len(self.raw), size):
            yield self.raw[offset : offset + size]


class Response:
    status = 200

    def __init__(self, raw):
        self.content = Content(raw)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class Session:
    def __init__(self):
        self.calls = 0
        self.raw = None
        self.status = 200

    def get(self, url, **kwargs):
        self.calls += 1
        bitmap_id = int(url.rsplit("/", 1)[1])
        raw = (
            self.raw
            if self.raw is not None
            else json.dumps(
                {"id": bitmap_id, "rgB565Array": json.dumps([0] * 64)}
            ).encode()
        )
        response = Response(raw)
        response.status = self.status
        return response


class BitmapTests(unittest.IsolatedAsyncioTestCase):
    async def test_download_resolve_cache_and_copy_isolation(self):
        session = Session()
        library = bitmaps.BitmapLibrary(session)
        first = await library.async_resolve({"bitmap": {"data": 42}})
        self.assertEqual(first["bitmap"]["size"], {"width": 8, "height": 8})
        first["bitmap"]["data"][0] = 99
        second = await library.async_resolve({"bitmap": {"data": 42}})
        self.assertEqual(second["bitmap"]["data"][0], 0)
        self.assertEqual(session.calls, 1)

    async def test_inline_pixels_do_not_access_network(self):
        session = Session()
        screen = {"bitmap": {"data": [0] * 64}}
        self.assertEqual(
            await bitmaps.BitmapLibrary(session).async_resolve(screen), screen
        )
        self.assertEqual(session.calls, 0)

    async def test_invalid_and_oversized_responses_are_rejected(self):
        session = Session()
        library = bitmaps.BitmapLibrary(session)
        for raw in (
            b"bad",
            b"{}",
            b"x" * (bitmaps.MAX_RESPONSE_BYTES + 1),
            json.dumps({"id": 42, "rgB565Array": "[true]"}).encode(),
        ):
            session.raw = raw
            with self.assertRaises(HAError):
                await library.async_resolve({"bitmap": {"data": 42}})
        self.assertEqual(len(library._cache), 0)
        session.status = 429
        with self.assertRaisesRegex(HAError, "429"):
            await library.async_resolve({"bitmap": {"data": 42}})

    async def test_lru_eviction_and_animation(self):
        session = Session()
        library = bitmaps.BitmapLibrary(session)
        with patch.object(bitmaps, "MAX_CACHE_ENTRIES", 2):
            for bitmap_id in (1, 2, 1, 3, 2):
                await library.async_resolve({"bitmap": {"data": bitmap_id}})
        self.assertEqual(session.calls, 4)
        session.raw = json.dumps(
            {"id": 42, "rgB565Array": ",".join([json.dumps([0] * 64)] * 2)}
        ).encode()
        animation = await library.async_resolve(
            {"bitmapAnimation": {"data": 42, "animationDelay": 50}}
        )
        self.assertEqual(len(animation["bitmapAnimation"]["data"]), 2)
        with self.assertRaises(HAError):
            await library.async_resolve({"bitmap": {"data": 42}})

    async def test_shared_icon_detects_static_and_animated_and_places_text(self):
        session = Session()
        library = bitmaps.BitmapLibrary(session)
        source = {"icon": 42, "text": {"textString": "Hello"}}
        static = await library.async_resolve(source)
        self.assertNotIn("icon", static)
        self.assertIn("bitmap", static)
        self.assertEqual(static["text"]["position"], {"x": 9, "y": 1})
        self.assertEqual(source, {"icon": 42, "text": {"textString": "Hello"}})
        session.raw = json.dumps(
            {"id": 43, "rgB565Array": ",".join([json.dumps([0] * 64)] * 2)}
        ).encode()
        animated = await library.async_resolve(
            {"icon": 43, "icon_animation_delay": 80, "icon_position": {"x": 1, "y": 0}}
        )
        self.assertNotIn("bitmap", animated)
        self.assertEqual(animated["bitmapAnimation"]["animationDelay"], 80)
        self.assertEqual(animated["bitmapAnimation"]["position"], {"x": 1, "y": 0})
        cached = await library.async_resolve({"icon": 43})
        self.assertEqual(cached["bitmapAnimation"]["animationDelay"], 100)
        self.assertEqual(session.calls, 2)

    async def test_shared_icon_rejects_conflicts_and_invalid_options(self):
        session = Session()
        library = bitmaps.BitmapLibrary(session)
        for screen in (
            {"icon": True},
            {"icon": 0},
            {"icon": "42"},
            {"icon": 42, "bitmap": {"data": [0] * 64}},
            {"icon": 42, "icon_animation_delay": 0},
            {"icon": 42, "icon_position": {"x": 0}},
            {"icon_animation_delay": 100},
        ):
            with self.assertRaises(HAError):
                await library.async_resolve(screen)
        self.assertEqual(session.calls, 0)

    async def test_named_icon_is_stored_as_resolved_pixels(self):
        from test_control import coordinator
        from test_playback import Store

        store = Store()
        player = coordinator.ScreenPlayer(None, lambda: False, 32, 8, store)
        player.set_bitmap_library(bitmaps.BitmapLibrary(Session()))
        await player.async_set_screen(
            "hello", {"icon": 42, "text": {"textString": "Hello"}}
        )
        saved = store.data["screens"]["hello"]["screen"]
        self.assertNotIn("icon", saved)
        self.assertEqual(len(saved["bitmap"]["data"]), 64)
        self.assertEqual(saved["text"]["position"]["x"], 9)
        await player.async_stop()
