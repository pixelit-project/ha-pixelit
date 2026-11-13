"""Screen transitions and capability boundaries verified against firmware 3.0 tags."""

from __future__ import annotations

import re
from copy import deepcopy

from homeassistant.exceptions import ServiceValidationError

TRANSITIONS = (
    "none",
    "random",
    "fade",
    "coloredBarWipe",
    "zigzagWipe",
    "bitmapWipe",
    "curtain",
    "pixelDissolve",
    "slide",
    "blinds",
    "crt",
    "glitch",
    "verticalSlide",
)
EXPANDED_TRANSITIONS = {"curtain", "pixelDissolve", "slide", "blinds", "crt", "glitch"}
VERSION = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)(?:\.(\d+))?)?(?:\+[^\s]+)?")


def with_transition(
    screen: dict, transition: str | None, bitmap: int | None, color: str
) -> dict:
    """A supplied selection overrides only the transition, never content."""
    result = deepcopy(screen)
    if transition is None:
        if bitmap is not None:
            raise ServiceValidationError("A transition bitmap requires Bitmap Wipe")
        return result
    if transition not in TRANSITIONS:
        raise ServiceValidationError("Unknown PixelIt transition")
    if bitmap is not None and transition != "bitmapWipe":
        raise ServiceValidationError(
            "A transition bitmap can only be used with Bitmap Wipe"
        )
    if transition == "none":
        result["switchAnimation"] = {"aktiv": False}
    else:
        settings = {"aktiv": True, "animation": transition}
        if transition == "zigzagWipe":
            settings["hexColor"] = color
        if transition == "bitmapWipe":
            if type(bitmap) is not int or not 1 <= bitmap <= 2**31 - 1:
                raise ServiceValidationError(
                    "Bitmap Wipe needs a static Gallery bitmap ID"
                )
            settings["data"] = bitmap
        result["switchAnimation"] = settings
    return result


def validate_firmware_transition(screen: dict, version: str | None) -> None:
    """Do not silently send effects missing from the connected firmware."""
    settings = screen.get("switchAnimation", {})
    if not settings.get("aktiv"):
        return
    effect = settings.get("animation")
    minimum = (
        6
        if effect == "verticalSlide"
        else 1
        if effect in EXPANDED_TRANSITIONS
        else None
    )
    if minimum is None:
        return
    match = VERSION.fullmatch(version) if isinstance(version, str) else None
    supported = False
    if match:
        major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
        prerelease, number = match.group(4), int(match.group(5) or 0)
        supported = (major, minor, patch) > (3, 0, 0) or (
            (major, minor, patch) == (3, 0, 0)
            and (
                prerelease in (None, "rc") or prerelease == "beta" and number >= minimum
            )
        )
    if not supported:
        raise ServiceValidationError(
            f"Transition {effect} requires PixelIt firmware 3.0.0-beta.{minimum} or newer; "
            f"device reports {version or 'an unknown version'}"
        )
