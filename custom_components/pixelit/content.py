"""Build display content from user-friendly action fields."""

from __future__ import annotations

from copy import deepcopy

from homeassistant.exceptions import ServiceValidationError


def build_screen(
    *,
    screen: dict | None = None,
    message: str | None = None,
    clock: bool = False,
    color: str = "#FFFFFF",
    scroll: str = "auto",
    large_font: bool = False,
    center: bool = True,
    icon: int | None = None,
) -> dict:
    """Keep advanced screen payloads compatible without silently merging content."""
    if sum((screen is not None, message is not None, clock)) > 1:
        raise ServiceValidationError(
            "Choose a message, clock or advanced screen content"
        )
    if screen is not None:
        return deepcopy(screen)
    if clock:
        return {"clock": {"show": True, "hexColor": color}}
    if message is not None:
        return {
            "text": {
                "textString": message,
                "hexColor": color,
                "scrollText": {"auto": "auto", "always": True, "off": False}[scroll],
                "bigFont": bool(large_font),
                "centerText": center,
                **({"position": {"x": 0, "y": 1}} if icon is None else {}),
            }
        }
    if icon is not None:
        return {}
    raise ServiceValidationError(
        "Enter a message, choose an icon or clock, or provide advanced content"
    )
