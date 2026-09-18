"""Tests for ipc.py -- the cross-platform daemon socket fix.

Run: python -m pytest test_ipc.py -q
"""
import socket
import unittest

import ipc


class PortDerivationTests(unittest.TestCase):
    def test_deterministic_across_calls(self):
        # Must match across independent process invocations (daemon vs client),
        # so it cannot depend on Python's salted hash().
        self.assertEqual(ipc.tcp_port("default"), ipc.tcp_port("default"))

    def test_different_names_usually_differ(self):
        ports = {ipc.tcp_port(n) for n in ("default", "work", "remote", "agent1", "agent2")}
        self.assertGreater(len(ports), 1)

    def test_port_in_valid_range(self):
        for name in ("default", "work", "x" * 50, ""):
            port = ipc.tcp_port(name)
            self.assertGreaterEqual(port, ipc._PORT_BASE)
            self.assertLess(port, ipc._PORT_BASE + ipc._PORT_SPAN)
            self.assertLess(port, 65536)


class ListenKwargsTests(unittest.TestCase):
    def test_windows_kwargs_shape(self):
        if ipc.USE_UNIX_SOCKET:
            self.skipTest("this host uses AF_UNIX; the Windows branch isn't exercised here")
        kwargs = ipc.listen_kwargs("default")
        self.assertEqual(set(kwargs), {"host", "port"})
        self.assertEqual(kwargs["host"], "127.0.0.1")

    def test_posix_kwargs_shape(self):
        if not ipc.USE_UNIX_SOCKET:
            self.skipTest("this host has no AF_UNIX; the POSIX branch isn't exercised here")
        kwargs = ipc.listen_kwargs("default")
        self.assertEqual(set(kwargs), {"path"})


class LiveLoopbackTests(unittest.TestCase):
    """Prove connect() actually reaches a real listening socket end to end.

    This is the test that AF_UNIX-only code could never pass on this host:
    it opens a real listener using whichever family this platform gets from
    ipc.py, then calls ipc.connect() and confirms bytes round-trip.
    """

    def test_connect_reaches_a_real_listener(self):
        name = "test-live-loopback"
        if ipc.USE_UNIX_SOCKET:
            import os
            path = ipc.unix_path(name)
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(path)
        else:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(("127.0.0.1", ipc.tcp_port(name)))
        server.listen(1)
        try:
            client = ipc.connect(name, timeout=2)
            try:
                client.sendall(b"ping")
                conn, _ = server.accept()
                try:
                    self.assertEqual(conn.recv(4), b"ping")
                finally:
                    conn.close()
            finally:
                client.close()
        finally:
            server.close()
            if ipc.USE_UNIX_SOCKET:
                import os
                try:
                    os.unlink(ipc.unix_path(name))
                except FileNotFoundError:
                    pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
