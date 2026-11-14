"""Discover enabled physical buttons from firmware configuration."""

from homeassistant.core import callback

from .control_entity import PixelItControl
from .coordinator import BUTTON_KEYS


def setup_buttons(entry, async_add_entities, entity_type):
    discovered = set()

    @callback
    def discover():
        entities = []
        for key in BUTTON_KEYS:
            if key in entry.runtime_data.enabled_buttons and key not in discovered:
                discovered.add(key)
                entities.append(entity_type(entry, key))
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(entry.runtime_data.add_data_listener(discover))
    discover()


class PixelItButton(PixelItControl):
    _attr_icon = "mdi:gesture-tap-button"

    def __init__(self, entry, key, suffix=""):
        super().__init__(entry, key.removesuffix("Button") + "_button" + suffix)
        self._button = key

    @property
    def available(self):
        return (
            self._coordinator.connected
            and self._button in self._coordinator.enabled_buttons
            and self._button in self._coordinator.buttons
        )
