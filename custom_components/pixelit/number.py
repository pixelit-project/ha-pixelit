"""Configure the firmware's automatic clock delay."""

import math

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.exceptions import ServiceValidationError

from .control_entity import PixelItControl


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PixelItClockDelay(entry)])


class PixelItClockDelay(PixelItControl, NumberEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 86400
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry):
        super().__init__(entry, "clock_fallback_delay")

    @property
    def native_value(self):
        value = self._coordinator.info.get("clockAutoFallbackTime")
        return value if type(value) is int and 1 <= value <= 86400 else None

    @property
    def available(self):
        return self._coordinator.connected and self.native_value is not None

    async def async_set_native_value(self, value):
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 1 <= value <= 86400
            or int(value) != value
        ):
            raise ServiceValidationError(
                "Clock delay must be a whole number from 1 to 86400 seconds"
            )
        await self._coordinator.async_set_clock_config(
            "clockAutoFallbackTime", int(value)
        )
