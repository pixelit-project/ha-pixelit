"""Expose physical pressed/released button states."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .button_entity import PixelItButton, setup_buttons


async def async_setup_entry(hass, entry, async_add_entities):
    setup_buttons(entry, async_add_entities, PixelItButtonState)


class PixelItButtonState(PixelItButton, BinarySensorEntity):
    @property
    def is_on(self):
        return self._coordinator.buttons.get(self._button)
