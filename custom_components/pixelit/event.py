"""Expose physical button transitions as Home Assistant events."""

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import callback

from .button_entity import PixelItButton, setup_buttons


async def async_setup_entry(hass, entry, async_add_entities):
    setup_buttons(entry, async_add_entities, PixelItButtonEvent)


class PixelItButtonEvent(PixelItButton, EventEntity):
    _attr_device_class = EventDeviceClass.BUTTON

    def __init__(self, entry, key):
        super().__init__(entry, key, "_event")
        self._attr_event_types = ["press", "release"]

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._coordinator.add_button_listener(self._handle_button))

    @callback
    def _handle_button(self, key, event_type):
        if key == self._button and self.available:
            self._trigger_event(event_type)
            self.async_write_ha_state()
