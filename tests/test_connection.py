"""Transport regression tests using a local WebSocket server and HA stubs."""

import asyncio
import unittest
from unittest.mock import patch

import aiohttp
from aiohttp import web

from test_control import coordinator


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_after_receiver_failure_allows_cleanup(self):
        client = coordinator.PixelItCoordinator(None, 'localhost', 81, 32, 8)

        async def failed_receiver():
            raise TypeError('entity state write failed')

        client._task = asyncio.create_task(failed_receiver())
        await asyncio.sleep(0)
        with self.assertLogs(coordinator._LOGGER, level='ERROR') as logs:
            await client.async_stop()
        self.assertIn('entity state write failed', '\n'.join(logs.output))
        self.assertIsNone(client._task)
        self.assertTrue(client.player._closed)
        await client.async_stop()

    async def run_server(self, handler):
        app = web.Application()
        app.router.add_get('/', handler)
        runner = web.AppRunner(app)
        await runner.setup()
        self.addAsyncCleanup(runner.cleanup)
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        client = coordinator.PixelItCoordinator(None, '127.0.0.1', port, 32, 8)
        session = aiohttp.ClientSession()
        self.addAsyncCleanup(session.close)
        client._session = session
        return client

    async def test_static_display_stays_connected_with_pongs(self):
        pings = 0

        async def handler(request):
            nonlocal pings
            ws = web.WebSocketResponse(autoping=False)
            await ws.prepare(request)
            await ws.send_json({'liveview': '000000'})
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.PING:
                    pings += 1
                    await ws.pong(msg.data)
                    if pings == 3:
                        await ws.close()
            return ws

        client = await self.run_server(handler)
        with patch.object(coordinator, 'HEARTBEAT_INTERVAL', 0.04):
            await asyncio.wait_for(client._run_connection(), 2)
        self.assertEqual(pings, 3)
        self.assertEqual(client.attributes['hex'], '000000')

    async def test_dead_connection_without_first_frame_is_closed(self):
        async def handler(request):
            ws = web.WebSocketResponse(autoping=False)
            await ws.prepare(request)
            async for _ in ws:
                pass  # Simulate a peer that never answers heartbeat pings.
            return ws

        client = await self.run_server(handler)
        with patch.object(coordinator, 'HEARTBEAT_INTERVAL', 0.04):
            await asyncio.wait_for(client._run_connection(), 2)
        self.assertTrue(client._ws.closed)

    async def test_connection_attempt_is_bounded(self):
        class Session:
            async def ws_connect(self, *args, **kwargs):
                await asyncio.Event().wait()

        client = coordinator.PixelItCoordinator(None, 'localhost', 81, 32, 8)
        client._session = Session()
        with patch.object(coordinator, 'CONNECT_TIMEOUT', 0.01):
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(client._run_connection(), 1)
        self.assertFalse(client.connected)
