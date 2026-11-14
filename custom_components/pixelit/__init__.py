"""PixelIt integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .bitmaps import BitmapLibrary
from .const import (
    CONF_HEIGHT,
    CONF_WIDTH,
    DEFAULT_HEIGHT,
    DEFAULT_PORT,
    DEFAULT_WIDTH,
    DOMAIN,
)
from .coordinator import PixelItCoordinator
from .frontend import ensure_frontend
from .services import async_setup_services

type PixelItConfigEntry = ConfigEntry[PixelItCoordinator]
PLATFORMS = (Platform.SENSOR, Platform.LIGHT, Platform.UPDATE)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration actions once, including when devices are unloaded."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PixelItConfigEntry) -> bool:
    """Set up PixelIt from a config entry."""
    entry.runtime_data = PixelItCoordinator(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        entry.data.get(CONF_WIDTH, DEFAULT_WIDTH),
        entry.data.get(CONF_HEIGHT, DEFAULT_HEIGHT),
    )
    entry.runtime_data.player.set_bitmap_library(
        BitmapLibrary(entry.runtime_data.session)
    )
    await entry.runtime_data.player.async_load(
        Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.screens")
    )
    await ensure_frontend(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.runtime_data.async_start(hass, entry)

    async def async_shutdown(event) -> None:
        await entry.runtime_data.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PixelItConfigEntry) -> bool:
    """Unload the sensor and stop the WebSocket client."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove only this display's stored playback settings."""
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.screens").async_remove()
