"""Regression tests for iContainer Blender installation on container creation."""
import unittest
from types import SimpleNamespace
from unittest import mock

from backend.app import blender_bootstrap as bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        bootstrap._started = False
        bootstrap._status.update(state="not_started", detail="", error=None)

    def tearDown(self):
        bootstrap._started = False

    def test_existing_blender_skips_install(self):
        with mock.patch.object(bootstrap, "blender_available", return_value=True), \
             mock.patch.object(bootstrap.threading, "Thread") as thread:
            bootstrap.start_blender_bootstrap()
        self.assertEqual(bootstrap.blender_bootstrap_status()["state"], "ready" if bootstrap.blender_available() else bootstrap._status["state"])
        thread.assert_not_called()

    def test_missing_blender_starts_one_background_install(self):
        with mock.patch.object(bootstrap, "blender_available", return_value=False), \
             mock.patch.object(bootstrap.os.path, "exists", return_value=True), \
             mock.patch.object(bootstrap.os, "geteuid", return_value=0, create=True), \
             mock.patch.object(bootstrap.shutil, "which", return_value="/usr/bin/apt-get"), \
             mock.patch.object(bootstrap.threading, "Thread") as thread, \
             mock.patch.dict(bootstrap.os.environ, {"ANIMA_AUTO_INSTALL_BLENDER": "1"}):
            bootstrap.start_blender_bootstrap()
            bootstrap.start_blender_bootstrap()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_apt_failure_reports_error(self):
        fake = SimpleNamespace(returncode=100, stdout="Repository temporarily unavailable")
        with mock.patch.object(bootstrap, "blender_available", return_value=False), \
             mock.patch.object(bootstrap.subprocess, "run", return_value=fake):
            bootstrap._install_blender()
        self.assertEqual(bootstrap._status["state"], "failed")
        self.assertIn("Repository", bootstrap._status["error"])


if __name__ == "__main__":
    unittest.main()
