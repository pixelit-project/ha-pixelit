"""Sensor exposing the latest PixelIt frame."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfInformation,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

if TYPE_CHECKING:
    from . import PixelItConfigEntry
from .const import SENSOR_NAME
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PixelItConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Liveview and discover only readings supported by this device."""
    async_add_entities([PixelItLiveviewSensor(entry)])
    discovered: set[str] = set()

    def async_discover() -> None:
        entities = []
        for description in DEVICE_SENSORS:
            if description.key in discovered:
                continue
            source = (
                entry.runtime_data.sensor_data
                if description.source == "sensor"
                else entry.runtime_data.info
            )
            if (
                description.field not in source
                or source[description.field] == "Not installed"
            ):
                continue
            discovered.add(description.key)
            entities.append(PixelItDeviceSensor(entry, description))
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(entry.runtime_data.add_data_listener(async_discover))
    async_discover()


class PixelItLiveviewSensor(SensorEntity):
    """Expose live pixels and connection status."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:led-strip-variant"
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({"hex"})

    def __init__(self, entry: PixelItConfigEntry) -> None:
        """Initialize the sensor with a stable registry ID."""
        self._attr_device_info = device_info(entry)
        self._attr_unique_id = entry.entry_id
        self._attr_name = f"{SENSOR_NAME} ({entry.title})"
        self._coordinator = entry.runtime_data

    async def async_added_to_hass(self) -> None:
        """Subscribe to WebSocket updates while the entity is loaded."""
        self._coordinator.on_update = self.async_write_ha_state
        self.async_on_remove(self._coordinator.clear_listener)

    @property
    def native_value(self) -> str:
        """Return the connection status used by existing cards."""
        return "connected" if self._coordinator.connected else "disconnected"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the live frame and its dimensions."""
        return self._coordinator.attributes


@dataclass(frozen=True, kw_only=True)
class PixelItSensorDescription(SensorEntityDescription):
    """Map a firmware field to a typed Home Assistant sensor."""

    field: str
    source: str = "info"
    numeric: bool = True
    minimum: float | None = 0
    maximum: float | None = None


def _measurement(key, field, unit, device_class=None, **kwargs):
    return PixelItSensorDescription(
        key=key,
        field=field,
        translation_key=key,
        native_unit_of_measurement=unit,
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT,
        **kwargs,
    )


def _diagnostic(key, field, unit=None, device_class=None, **kwargs):
    return PixelItSensorDescription(
        key=key,
        field=field,
        translation_key=key,
        native_unit_of_measurement=unit,
        device_class=device_class,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        **kwargs,
    )


DEVICE_SENSORS = (
    _measurement(
        "temperature",
        "temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
        source="sensor",
        minimum=None,
    ),
    _measurement(
        "humidity",
        "humidity",
        PERCENTAGE,
        SensorDeviceClass.HUMIDITY,
        source="sensor",
        maximum=100,
    ),
    _measurement(
        "pressure",
        "pressure",
        UnitOfPressure.HPA,
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        source="sensor",
    ),
    _measurement("gas_resistance", "gas", "kΩ", source="sensor", icon="mdi:resistor"),
    _measurement(
        "illuminance", "lux", "lx", SensorDeviceClass.ILLUMINANCE, source="sensor"
    ),
    _measurement(
        "battery",
        "battery",
        PERCENTAGE,
        SensorDeviceClass.BATTERY,
        source="sensor",
        maximum=100,
    ),
    _diagnostic(
        "wifi_signal",
        "wifiRSSI",
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        SensorDeviceClass.SIGNAL_STRENGTH,
        minimum=-127,
        maximum=0,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _diagnostic(
        "wifi_quality",
        "wifiQuality",
        PERCENTAGE,
        maximum=100,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:wifi",
    ),
    _diagnostic("cpu_frequency", "cpuFreqMHz", "MHz", SensorDeviceClass.FREQUENCY),
    _diagnostic("wifi_ssid", "wifiSSID", numeric=False, icon="mdi:wifi"),
    _diagnostic("wifi_bssid", "wifiBSSID", numeric=False, icon="mdi:access-point"),
    _diagnostic("chip_id", "chipID", numeric=False, icon="mdi:chip"),
    _diagnostic(
        "uptime",
        "uptime",
        UnitOfTime.SECONDS,
        SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _diagnostic(
        "free_heap",
        "freeHeap",
        UnitOfInformation.BYTES,
        SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _diagnostic("restart_reason", "resetReason", numeric=False, icon="mdi:restart"),
    _diagnostic("ip_address", "ipAddress", numeric=False, icon="mdi:ip-network"),
    _diagnostic("firmware_version", "pixelitVersion", numeric=False, icon="mdi:chip"),
    _diagnostic(
        "latest_firmware_version",
        "latestReleaseVersion",
        numeric=False,
        icon="mdi:update",
    ),
    _diagnostic(
        "free_flash",
        "freeSketchSpace",
        UnitOfInformation.BYTES,
        SensorDeviceClass.DATA_SIZE,
    ),
    _diagnostic(
        "firmware_size",
        "sketchSize",
        UnitOfInformation.BYTES,
        SensorDeviceClass.DATA_SIZE,
    ),
    _diagnostic(
        "largest_free_block",
        "maxFreeBlock",
        UnitOfInformation.BYTES,
        SensorDeviceClass.DATA_SIZE,
    ),
    _diagnostic(
        "minimum_free_heap",
        "minFreeHeap",
        UnitOfInformation.BYTES,
        SensorDeviceClass.DATA_SIZE,
    ),
    _diagnostic("heap_fragmentation", "heapFragmentation", PERCENTAGE, maximum=100),
    _diagnostic(
        "animation_frames", "animationFrames", icon="mdi:animation-play-outline"
    ),
)


class PixelItDeviceSensor(SensorEntity):
    """Expose device readings without subscribing to high-frequency live pixels."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entry: PixelItConfigEntry, description: PixelItSensorDescription
    ):
        self.entity_description = description
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.add_data_listener(self.async_write_ha_state)
        )

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.key == "temperature":
            if self._coordinator.temperature_unit is None:
                return None
            return (
                UnitOfTemperature.FAHRENHEIT
                if self._coordinator.temperature_unit == 1
                else UnitOfTemperature.CELSIUS
            )
        return self.entity_description.native_unit_of_measurement

    @property
    def native_value(self) -> str | int | float | None:
        description = self.entity_description
        source = (
            self._coordinator.sensor_data
            if description.source == "sensor"
            else self._coordinator.info
        )
        value = source.get(description.field)
        if value is None or value == "Not installed" or isinstance(value, bool):
            return None
        if not description.numeric:
            if isinstance(value, (str, int)) and len(str(value)) <= 255:
                return str(value)
            return None
        if type(value) not in (int, float) or not math.isfinite(value):
            return None
        if description.minimum is not None and value < description.minimum:
            return None
        if description.maximum is not None and value > description.maximum:
            return None
        if (
            description.key == "temperature"
            and self._coordinator.temperature_unit is None
        ):
            return None
        return value

    @property
    def available(self) -> bool:
        return self._coordinator.connected and self.native_value is not None
