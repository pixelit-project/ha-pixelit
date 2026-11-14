"""Report firmware updates directly from PixelIt without MQTT."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import device_info

if TYPE_CHECKING:
    from . import PixelItConfigEntry

VERSION = re.compile(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PixelItConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an enabled, read-only firmware update entity."""
    async_add_entities([PixelItFirmwareUpdate(entry)])


class PixelItFirmwareUpdate(UpdateEntity):
    """Use the device's release check without extra polling or downloads."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True
    _attr_translation_key = "firmware"
    _attr_title = "PixelIt firmware"
    _attr_supported_features = UpdateEntityFeature(0)
    _attr_release_url = "https://github.com/pixelit-project/PixelIt/releases"

    def __init__(self, entry: PixelItConfigEntry) -> None:
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_firmware_update"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Subscribe only to device data, with entity-owned cleanup."""
        self.async_on_remove(
            self._coordinator.add_data_listener(self.async_write_ha_state)
        )

    def _version(self, field: str) -> str | None:
        value = self._coordinator.info.get(field)
        if isinstance(value, str) and len(value) <= 128 and VERSION.fullmatch(value):
            return value
        return None

    @property
    def installed_version(self) -> str | None:
        return self._version("pixelitVersion")

    @property
    def latest_version(self) -> str | None:
        # Older firmware has no completion flag; retain its reported versions.
        # New firmware initially echoes the installed version before checking.
        if self._coordinator.info.get("updateCheckCompleted", True) is not True:
            return None
        return self._version("latestReleaseVersion")

    @property
    def available(self) -> bool:
        return self._coordinator.connected and self.installed_version is not None
