"""Test push discovery, typed values, availability and temperature units."""

import json
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_control import Entity, coordinator, module, pkg, stubs


@dataclass(frozen=True, kw_only=True)
class Description:
    key: str
    translation_key: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    entity_category: str | None = None
    entity_registry_enabled_default: bool = True
    icon: str | None = None


# Use the actual sensor module while replacing only the HA host interfaces.
sensor_stubs = dict(stubs)
sensor_stubs["pixelit_test"] = pkg
sensor_stubs["homeassistant.components.sensor"] = module(
    "sensor",
    SensorEntity=Entity,
    SensorEntityDescription=Description,
    SensorDeviceClass=SimpleNamespace(
        **{
            key: key
            for key in (
                "TEMPERATURE",
                "HUMIDITY",
                "ATMOSPHERIC_PRESSURE",
                "ILLUMINANCE",
                "BATTERY",
                "SIGNAL_STRENGTH",
                "FREQUENCY",
                "DURATION",
                "DATA_SIZE",
            )
        }
    ),
    SensorStateClass=SimpleNamespace(MEASUREMENT="measurement"),
)
sensor_stubs["homeassistant.const"] = module(
    "const",
    CONF_HOST="host",
    PERCENTAGE="%",
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT="dBm",
    EntityCategory=SimpleNamespace(DIAGNOSTIC="diagnostic"),
    UnitOfInformation=SimpleNamespace(BYTES="B"),
    UnitOfPressure=SimpleNamespace(HPA="hPa"),
    UnitOfTemperature=SimpleNamespace(CELSIUS="°C", FAHRENHEIT="°F"),
    UnitOfTime=SimpleNamespace(SECONDS="s"),
)
sensor_stubs["homeassistant.helpers.entity_platform"] = module(
    "entity_platform", AddEntitiesCallback=object
)
with patch.dict("sys.modules", sensor_stubs):
    import pixelit_test.sensor as sensor


class SensorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = coordinator.PixelItCoordinator(None, "device", 81, 32, 8)
        self.client._connected = True
        self.cleanup = []
        self.entry = SimpleNamespace(
            entry_id="entry",
            title="device",
            data={"host": "device"},
            runtime_data=self.client,
            async_on_unload=self.cleanup.append,
        )
        self.entities = []
        await sensor.async_setup_entry(None, self.entry, self.entities.extend)

    async def asyncTearDown(self):
        for cleanup in self.cleanup:
            cleanup()
        await self.client.player.async_stop()

    def send(self, **payload):
        self.client._handle_message(json.dumps(payload))

    def values(self):
        return {
            entity.entity_description.key: entity
            for entity in self.entities
            if hasattr(entity, "entity_description")
        }

    async def test_discovers_installed_hardware_and_merges_sensor_frames(self):
        self.assertEqual(len(self.entities), 1)
        self.send(sensor={"lux": 12, "hostname": "device"})
        self.send(
            sensor={
                "temperature": 23.5,
                "humidity": 51,
                "pressure": "Not installed",
                "gas": "Not installed",
                "battery": "Not installed",
            }
        )
        self.send(config={"temperatureUnit": 0, "mqttPassword": "not-stored"})
        values = self.values()
        self.assertEqual(set(values), {"illuminance", "temperature", "humidity"})
        self.assertEqual(values["illuminance"].native_value, 12)
        self.assertEqual(values["temperature"].native_value, 23.5)
        self.assertTrue(values["temperature"].available)
        self.assertFalse(hasattr(self.client, "config"))
        self.send(sensor={"lux": 0})
        self.assertEqual(len(self.values()), 3)
        self.assertEqual(values["illuminance"].native_value, 0)
        self.assertEqual(values["humidity"].native_value, 51)

    async def test_temperature_waits_for_unit_and_supports_fahrenheit(self):
        self.send(sensor={"temperature": 77})
        temp = self.values()["temperature"]
        self.assertFalse(temp.available)
        self.send(config={"temperatureUnit": 1})
        self.assertEqual(temp.native_value, 77)
        self.assertEqual(temp.native_unit_of_measurement, "°F")
        self.send(config={"temperatureUnit": 0})
        self.assertEqual(temp.native_unit_of_measurement, "°C")
        self.send(config={"temperatureUnit": True})
        self.assertFalse(temp.available)

    async def test_zeroes_are_valid_and_invalid_values_unavailable(self):
        self.send(sensor={"humidity": 0, "battery": 100, "lux": 0, "temperature": -5})
        self.send(config={"temperatureUnit": 0})
        values = self.values()
        self.assertEqual(values["temperature"].native_value, -5)
        self.assertEqual(values["humidity"].native_value, 0)
        for invalid in (None, True, "NaN", float("nan"), float("inf"), -1, 101):
            self.send(sensor={"humidity": invalid})
            self.assertIsNone(values["humidity"].native_value)
            self.assertFalse(values["humidity"].available)
        self.send(sensor={"humidity": "Not installed"})
        self.assertFalse(values["humidity"].available)

    async def test_diagnostics_have_stable_ids_and_correct_metadata(self):
        self.send(
            sysinfo={
                "wifiRSSI": -65,
                "cpuFreqMHz": 160,
                "freeHeap": 12345,
                "chipID": 1234,
                "uptime": 20,
                "resetReason": "Power on",
            }
        )
        values = self.values()
        self.assertEqual(values["wifi_signal"].native_value, -65)
        self.assertEqual(values["chip_id"].native_value, "1234")
        for entity in values.values():
            self.assertEqual(entity.entity_description.entity_category, "diagnostic")
            self.assertFalse(entity.entity_description.entity_registry_enabled_default)
            self.assertTrue(entity._attr_unique_id.startswith("entry_"))
            self.assertEqual(
                entity._attr_device_info["identifiers"], {("pixelit", "entry")}
            )
        self.assertEqual(
            values["free_heap"].entity_description.native_unit_of_measurement, "B"
        )

    async def test_disconnect_clears_stale_values_and_requires_new_unit(self):
        self.send(sensor={"temperature": 20, "lux": 10}, config={"temperatureUnit": 0})
        values = self.values()
        self.client._connected = False
        self.client._clear_device_data()
        self.assertFalse(values["temperature"].available)
        self.client._connected = True
        self.send(sensor={"temperature": 86, "lux": 11})
        self.assertFalse(values["temperature"].available)
        self.assertEqual(values["illuminance"].native_value, 11)
        self.send(config={"temperatureUnit": 1})
        self.assertTrue(values["temperature"].available)
        self.assertEqual(values["temperature"].native_unit_of_measurement, "°F")

    async def test_data_listeners_ignore_live_pixels_and_unsubscribe(self):
        calls = []
        remove = self.client.add_data_listener(lambda: calls.append(True))
        self.send(liveview="FF0000")
        self.assertEqual(calls, [])
        self.send(sensor={"lux": 5})
        self.assertEqual(len(calls), 1)
        remove()
        self.send(sensor={"lux": 6})
        self.assertEqual(len(calls), 1)

    async def test_optional_board_fields_are_discovered_later(self):
        self.send(sysinfo={"wifiRSSI": -50})
        self.assertNotIn("minimum_free_heap", self.values())
        self.send(sysinfo={"wifiRSSI": -50, "minFreeHeap": 10000})
        self.assertEqual(self.values()["minimum_free_heap"].native_value, 10000)
        self.send(sensor={"battery": 80})
        self.assertEqual(self.values()["battery"].native_value, 80)

    async def test_every_sensor_name_is_translated(self):
        root = Path(__file__).resolve().parents[1] / "custom_components/pixelit"
        for lang in ("en", "de"):
            data = json.loads((root / f"translations/{lang}.json").read_text())
            self.assertEqual(
                {description.key for description in sensor.DEVICE_SENSORS},
                set(data["entity"]["sensor"]),
            )
