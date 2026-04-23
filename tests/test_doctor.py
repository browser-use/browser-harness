import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DoctorCommandTests(unittest.TestCase):
    def test_doctor_does_not_crash_when_unix_sockets_are_unavailable(self):
        script = """
import runpy
import socket
import sys

if hasattr(socket, "AF_UNIX"):
    delattr(socket, "AF_UNIX")
sys.argv = ["run.py", "--doctor"]
runpy.run_path("run.py", run_name="__main__")
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        combined = f"{proc.stdout}\n{proc.stderr}"

        self.assertIn("browser-harness doctor", combined)
        self.assertNotIn("AttributeError", combined)
        self.assertNotIn("AF_UNIX", combined)


if __name__ == "__main__":
    unittest.main()
