"""Shared device identity for PixelIt entities."""

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from yarl import URL

from .const import DOMAIN


def device_info(entry) -> DeviceInfo:
    """Keep a stable device across host reconfiguration."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"PixelIt {entry.title}",
        manufacturer="PixelIt",
        model="PixelIt",
        configuration_url=str(URL.build(scheme="http", host=entry.data[CONF_HOST])),
    )
