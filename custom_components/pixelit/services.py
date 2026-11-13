"""Register targeted PixelIt actions once during integration setup."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN
from .screens import duration_seconds
from .transitions import TRANSITION_OPTIONS, TRANSITIONS


def seconds(value, *, allow_zero=False):
    """Adapt playback validation to HA action schema errors."""
    try:
        return duration_seconds(value, allow_zero=allow_zero)
    except ServiceValidationError as err:
        raise vol.Invalid(str(err)) from err


NAME = vol.All(cv.string, vol.Length(min=1, max=64))
ICON_FIELDS = {
    vol.Optional("icon"): vol.All(int, vol.Range(min=1, max=2**31 - 1)),
    vol.Optional("icon_animation_delay", default=100): vol.All(
        int, vol.Range(min=10, max=60000)
    ),
}
TRANSITION_FIELDS = {
    vol.Optional("transition"): vol.In((*TRANSITION_OPTIONS, *TRANSITIONS)),
    vol.Optional("transition_bitmap"): vol.All(int, vol.Range(min=1, max=2**31 - 1)),
}
TEXT_FIELDS = {
    vol.Optional("color", default="#FFFFFF"): vol.Match(r"^#[0-9A-Fa-f]{6}$"),
    vol.Optional("scroll", default="auto"): vol.In(["auto", "always", "off"]),
    vol.Optional("large_font", default=False): cv.boolean,
    vol.Optional("center", default=True): cv.boolean,
}
CONTENT_FIELDS = {
    **TRANSITION_FIELDS,
    **ICON_FIELDS,
    **TEXT_FIELDS,
    vol.Exclusive("message", "content"): vol.All(cv.string, vol.Length(min=1, max=255)),
    vol.Exclusive("screen", "content"): dict,
    vol.Optional("clock", default=False): cv.boolean,
}
MESSAGE_FIELDS = {
    **TRANSITION_FIELDS,
    **ICON_FIELDS,
    **TEXT_FIELDS,
    vol.Required("message"): vol.All(cv.string, vol.Length(min=1, max=255)),
    vol.Optional("protection_duration", default=0): lambda value: seconds(
        value, allow_zero=True
    ),
}
ACTION_SCHEMAS = {
    "show_message": MESSAGE_FIELDS,
    "set_screen": {
        **CONTENT_FIELDS,
        vol.Required("name"): NAME,
        vol.Optional("duration", default=5): seconds,
    },
    "show_screen": {vol.Required("name"): NAME},
    "set_playlist": {
        vol.Required("screens"): vol.All(list, vol.Length(max=100), [NAME])
    },
    "stop_playlist": {},
    "show_alert": {
        **CONTENT_FIELDS,
        vol.Optional("duration", default=10): seconds,
    },
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Use HA's permission-aware entity/device/area target resolution."""
    for name, schema in ACTION_SCHEMAS.items():
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            name,
            entity_domain="light",
            schema=schema,
            func=f"async_{name}",
        )
