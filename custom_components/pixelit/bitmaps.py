"""Optional gallery lookup; resolved pixels are persisted with named screens."""

from __future__ import annotations

import asyncio
import json
from collections import OrderedDict
from copy import deepcopy

import aiohttp
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

API_URL = "https://pixelit.bastelbunker.de/API/GetBMPByID/"
MAX_RESPONSE_BYTES = 128 * 1024
MAX_CACHE_BYTES = 256 * 1024
MAX_CACHE_ENTRIES = 32


class BitmapLibrary:
    """Bound downloads and the per-display LRU cache; do not retry implicitly."""

    def __init__(self, session, uuid=""):
        self._session = session
        self._uuid = uuid
        self._cache = OrderedDict()
        self._cache_bytes = 0

    async def async_resolve(self, screen):
        result = deepcopy(screen)
        if not isinstance(result, dict):
            raise ServiceValidationError("Screen must be an object")
        if "icon" in result:
            if "bitmap" in result or "bitmapAnimation" in result:
                raise ServiceValidationError(
                    "Use icon or explicit bitmap content, not both"
                )
            bitmap_id = result.pop("icon")
            if type(bitmap_id) is not int or not 1 <= bitmap_id <= 2**31 - 1:
                raise ServiceValidationError("Icon must be a positive gallery ID")
            delay = result.pop("icon_animation_delay", 100)
            if type(delay) is not int or not 10 <= delay <= 60000:
                raise ServiceValidationError("Icon animation delay must be 10–60000 ms")
            position = result.pop("icon_position", {"x": 0, "y": 0})
            if (
                not isinstance(position, dict)
                or set(position) != {"x", "y"}
                or any(
                    type(value) is not int or abs(value) > 32767
                    for value in position.values()
                )
            ):
                raise ServiceValidationError(
                    "Icon position must contain integer x and y"
                )
            frames = await self._fetch(bitmap_id)
            width = 32 if len(frames[0]) == 256 else 8
            content = {"position": position, "size": {"width": width, "height": 8}}
            if len(frames) == 1:
                content["data"] = frames[0]
                result["bitmap"] = content
            else:
                content.update(data=frames, animationDelay=delay)
                result["bitmapAnimation"] = content
            if isinstance(result.get("text"), dict):
                result["text"].setdefault(
                    "position", {"x": position["x"] + width + 1, "y": 1}
                )
        elif "icon_animation_delay" in result or "icon_position" in result:
            raise ServiceValidationError("Icon options require an icon ID")
        for key in ("bitmap", "bitmapAnimation"):
            content = result.get(key)
            if not isinstance(content, dict):
                continue
            value = content.get("data")
            if isinstance(value, list):
                continue
            if type(value) is not int or not 1 <= value <= 2**31 - 1:
                raise ServiceValidationError(
                    "Bitmap data must be inline pixels or a positive gallery ID"
                )
            frames = await self._fetch(value)
            if key == "bitmap":
                if len(frames) != 1:
                    raise ServiceValidationError(
                        "Use bitmapAnimation for animated gallery entries"
                    )
                content["data"] = frames[0]
            else:
                content["data"] = frames
            if "size" not in content:
                content["size"] = {
                    "width": 32 if len(frames[0]) == 256 else 8,
                    "height": 8,
                }
        return result

    async def _fetch(self, bitmap_id):
        if bitmap_id in self._cache:
            frames, size = self._cache.pop(bitmap_id)
            self._cache[bitmap_id] = (frames, size)
            return deepcopy(frames)
        try:
            async with asyncio.timeout(5):
                async with self._session.get(
                    f"{API_URL}{bitmap_id}",
                    params={"uuid": self._uuid},
                    allow_redirects=False,
                ) as response:
                    if response.status != 200:
                        raise HomeAssistantError(
                            f"PixelIt bitmap API returned HTTP {response.status}"
                        )
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(4096):
                        raw.extend(chunk)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise HomeAssistantError(
                                "PixelIt bitmap API response exceeds size limit"
                            )
            data = json.loads(raw)
            if (
                not isinstance(data, dict)
                or str(data.get("id")) != str(bitmap_id)
                or not isinstance(data.get("rgB565Array"), str)
            ):
                raise ValueError("Invalid bitmap envelope")
            frames = json.loads(f"[{data['rgB565Array']}]")
            if not isinstance(frames, list) or not 1 <= len(frames) <= 28:
                raise ValueError("Invalid frame count")
            size = len(frames[0])
            if size not in (64, 256) or size * len(frames) > 1792:
                raise ValueError("Invalid bitmap size")
            if any(
                not isinstance(frame, list)
                or len(frame) != size
                or any(
                    type(pixel) is not int or not 0 <= pixel <= 65535 for pixel in frame
                )
                for frame in frames
            ):
                raise ValueError("Invalid RGB565 pixels")
        except (
            aiohttp.ClientError,
            OSError,
            TimeoutError,
            ValueError,
            TypeError,
            IndexError,
        ) as err:
            raise HomeAssistantError(
                "Could not load a valid PixelIt gallery bitmap"
            ) from err
        size = len(json.dumps(frames).encode())
        while self._cache and (
            len(self._cache) >= MAX_CACHE_ENTRIES
            or self._cache_bytes + size > MAX_CACHE_BYTES
        ):
            _, (_, removed_size) = self._cache.popitem(last=False)
            self._cache_bytes -= removed_size
        self._cache[bitmap_id] = (frames, size)
        self._cache_bytes += size
        return deepcopy(frames)
