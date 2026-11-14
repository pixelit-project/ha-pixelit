"""Shared push subscription for device controls."""

from .entity import device_info


class PixelItControl:
    """Share identity and device-data lifecycle across control platforms."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, key):
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.add_data_listener(self.async_write_ha_state)
        )
