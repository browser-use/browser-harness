import importlib
import sys
import unittest
from unittest import mock


class StreamWithoutReconfigure:
    encoding = "cp1252"


class RunImportTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("run", None)

    def test_import_tolerates_streams_without_reconfigure(self):
        sys.modules.pop("run", None)

        with (
            mock.patch.object(sys, "stdout", StreamWithoutReconfigure()),
            mock.patch.object(sys, "stderr", StreamWithoutReconfigure()),
        ):
            importlib.import_module("run")

    def test_import_tolerates_missing_standard_streams(self):
        sys.modules.pop("run", None)

        with (
            mock.patch.object(sys, "stdout", None),
            mock.patch.object(sys, "stderr", None),
        ):
            importlib.import_module("run")


if __name__ == "__main__":
    unittest.main()
