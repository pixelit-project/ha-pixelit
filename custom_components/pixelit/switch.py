"""Automatic display controls using firmware state feedback."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .control_entity import PixelItControl


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            PixelItAutomaticSwitch(
                entry, "automatic_brightness", "matrixBrightnessAutomatic"
            ),
            PixelItAutomaticSwitch(entry, "automatic_clock", "clockAutoFallbackActive"),
        ]
    )


class PixelItAutomaticSwitch(PixelItControl, SwitchEntity):
    def __init__(self, entry, key, field):
        super().__init__(entry, key)
        self._field = field
        self._attr_icon = (
            "mdi:brightness-auto"
            if key == "automatic_brightness"
            else "mdi:clock-outline"
        )
        if key == "automatic_clock":
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self):
        value = self._coordinator.info.get(self._field)
        return value if type(value) is bool else None

    @property
    def available(self):
        return self._coordinator.connected and self.is_on is not None

    async def _async_set(self, enabled):
        if self._field == "matrixBrightnessAutomatic":
            await self._coordinator.async_send_screens([{"autobrightness": enabled}])
        else:
            await self._coordinator.async_set_clock_config(self._field, enabled)

    async def async_turn_on(self, **kwargs):
        await self._async_set(True)

    async def async_turn_off(self, **kwargs):
        await self._async_set(False)
