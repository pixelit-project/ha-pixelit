"""Host checks for firmware feedback and update entity lifecycle."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_control import Entity, coordinator, module, pkg, stubs

update_stubs = dict(stubs)
update_stubs['pixelit_test'] = pkg
update_stubs['homeassistant.components.update'] = module(
    'update', UpdateEntity=Entity,
    UpdateDeviceClass=SimpleNamespace(FIRMWARE='firmware'),
)
update_stubs['homeassistant.const'] = module(
    'const', CONF_HOST='host', EntityCategory=SimpleNamespace(DIAGNOSTIC='diagnostic'),
)
update_stubs['homeassistant.helpers.entity_platform'] = module(
    'entity_platform', AddEntitiesCallback=object,
)
with patch.dict('sys.modules', update_stubs):
    import pixelit_test.update as update


class UpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = coordinator.PixelItCoordinator(None, 'device', 81, 32, 8)
        self.client._connected = True
        entry = SimpleNamespace(entry_id='entry', data={'host': 'device'},
                                title='device', runtime_data=self.client)
        entities = []
        await update.async_setup_entry(None, entry, entities.extend)
        self.entity = entities[0]

    async def asyncTearDown(self):
        await self.client.player.async_stop()

    def send(self, **info):
        self.client._handle_message(json.dumps({'sysinfo': info}))

    async def test_versions_and_check_completion(self):
        self.send(pixelitVersion='3.0.0', latestReleaseVersion='3.0.0',
                  updateCheckCompleted=False)
        self.assertTrue(self.entity.available)
        self.assertIsNone(self.entity.latest_version)
        self.send(pixelitVersion='3.0.0', latestReleaseVersion='3.1.0',
                  updateCheckCompleted=True)
        self.assertEqual(self.entity.installed_version, '3.0.0')
        self.assertEqual(self.entity.latest_version, '3.1.0')
        self.send(pixelitVersion='3.1.0', latestReleaseVersion='3.1.0')
        self.assertEqual(self.entity.latest_version, self.entity.installed_version)
        self.assertEqual(self.entity._attr_supported_features, 0)
        self.assertTrue(self.entity._attr_entity_registry_enabled_default)
        self.assertEqual(self.entity._attr_unique_id, 'entry_firmware_update')

    async def test_invalid_missing_and_prerelease_versions(self):
        for value in (None, True, 123, '', 'unknown', 'x' * 256):
            self.send(pixelitVersion=value, latestReleaseVersion=value)
            self.assertFalse(self.entity.available)
            self.assertIsNone(self.entity.latest_version)
        self.send(pixelitVersion='v3.0.0-beta.6', latestReleaseVersion='3.0.0')
        self.assertTrue(self.entity.available)
        self.assertEqual(self.entity.installed_version, 'v3.0.0-beta.6')

    async def test_disconnect_reconnect_and_entity_cleanup(self):
        callbacks = []
        calls = []
        self.entity.async_on_remove = callbacks.append
        self.entity.async_write_ha_state = lambda: calls.append(True)
        await self.entity.async_added_to_hass()
        self.send(pixelitVersion='3.0.0', latestReleaseVersion='3.1.0')
        self.assertEqual(len(calls), 1)
        self.client._handle_message(json.dumps({'liveview': 'FF0000'}))
        self.assertEqual(len(calls), 1)
        self.client._connected = False
        self.client._clear_device_data()
        self.assertFalse(self.entity.available)
        self.assertIsNone(self.entity.latest_version)
        self.client._connected = True
        self.assertFalse(self.entity.available)
        self.send(pixelitVersion='3.1.0', latestReleaseVersion='3.1.0')
        self.assertTrue(self.entity.available)
        for remove in callbacks:
            remove()
        count = len(calls)
        self.send(pixelitVersion='3.1.0', latestReleaseVersion='3.2.0')
        self.assertEqual(len(calls), count)
