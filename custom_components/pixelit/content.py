"""Build display content from user-friendly action fields."""

from __future__ import annotations

from copy import deepcopy

from homeassistant.exceptions import ServiceValidationError


GRADIENT_DIRECTIONS = {
    "left_to_right": "leftToRight",
    "right_to_left": "rightToLeft",
    "top_to_bottom": "topToBottom",
    "bottom_to_top": "bottomToTop",
    "top_left_to_bottom_right": "topLeftToBottomRight",
    "bottom_right_to_top_left": "bottomRightToTopLeft",
    "top_right_to_bottom_left": "topRightToBottomLeft",
    "bottom_left_to_top_right": "bottomLeftToTopRight",
}


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
    gradient_end: str | None = None,
    gradient_direction: str | None = None,
    gradient_cycle_ms: int | None = None,
    rainbow: bool = False,
    character_colors: list[str | None] | None = None,
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
        text = {
            "textString": message,
            "hexColor": color,
            "scrollText": {"auto": "auto", "always": True, "off": False}[scroll],
            "bigFont": bool(large_font),
            "centerText": center,
        }
        if icon is None:
            text["position"] = {"x": 0, "y": 1}
        if gradient_end is not None:
            text["gradientEnd"] = gradient_end
        if gradient_direction is not None:
            text["gradientDirection"] = GRADIENT_DIRECTIONS[gradient_direction]
        if gradient_cycle_ms is not None:
            text["gradientCycleMs"] = gradient_cycle_ms
        if rainbow:
            text["rainbow"] = True
        if character_colors:
            text["characterColors"] = list(character_colors)
        return {"text": text}
    if icon is not None:
        return {}
    raise ServiceValidationError(
        "Enter a message, choose an icon or clock, or provide advanced content"
    )
