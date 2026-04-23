import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import transport


class TransportTests(unittest.TestCase):
    def test_endpoint_label_reports_unknown_tcp_port_without_invalid_host_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(transport, "TMP_DIR", Path(tmp)),
                mock.patch("transport.supports_unix_sockets", return_value=False),
            ):
                label = transport.endpoint_label("missing-port")

        self.assertIn("<unknown port>", label)
        self.assertIn("port file:", label)
        self.assertNotIn("127.0.0.1:" + tmp, label)


class AsyncTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_unix_server_start_failure_falls_back_to_authenticated_tcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = "fallback"
            with (
                mock.patch.object(transport, "TMP_DIR", Path(tmp)),
                mock.patch("transport.supports_unix_sockets", return_value=True),
                mock.patch("asyncio.start_unix_server", side_effect=NotImplementedError, create=True),
            ):

                async def handler(reader, writer):
                    line = await reader.readline()
                    writer.write(line)
                    await writer.drain()
                    writer.close()

                server = await transport.start_server(handler, name)
                paths = transport.runtime_paths(name)
                port = int(paths.port.read_text().strip())

                async with server:
                    self.assertTrue(paths.port.exists())
                    self.assertTrue((Path(tmp) / f"bu-{name}.token").exists())
                    self.assertEqual(transport.endpoint_label(name), f"127.0.0.1:{port}")

                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.write(b"ping\n")
                    await writer.drain()
                    self.assertEqual(await asyncio.wait_for(reader.read(1024), timeout=1), b"")
                    writer.close()
                    await writer.wait_closed()

                    def roundtrip():
                        client = transport.connect_client(name, timeout=1)
                        client.sendall(b"ping\n")
                        data = client.recv(1024)
                        client.close()
                        return data

                    self.assertEqual(await asyncio.to_thread(roundtrip), b"ping\n")


if __name__ == "__main__":
    unittest.main()
