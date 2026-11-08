import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.runtime import find_blender_binary, find_blender_runtime


class BlenderDiscoveryTests(unittest.TestCase):
    def test_finds_configured_absolute_binary_when_path_lookup_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "blender"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o755)
            with patch.dict(os.environ, {"BLENDER_BIN": str(binary)}):
                with patch("backend.app.runtime.shutil.which", return_value=None):
                    self.assertEqual(find_blender_binary(), str(binary.resolve()))

    def test_uses_path_command_when_no_override_is_set(self):
        expected = "/usr/bin/blender"
        with patch.dict(os.environ, {}, clear=True):
            with patch("backend.app.runtime.shutil.which", side_effect=lambda name: expected if name == "blender" else None):
                self.assertEqual(find_blender_binary(), expected)

    def test_returns_none_when_binary_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("backend.app.runtime.shutil.which", return_value=None):
                with patch("backend.app.runtime.os.access", return_value=False):
                    self.assertIsNone(find_blender_binary())

    def test_uses_bpy_python_module_when_cli_binary_is_missing(self):
        with patch("backend.app.runtime.find_blender_binary", return_value=None):
            with patch("backend.app.runtime.has_bpy_module", return_value=True):
                self.assertEqual(
                    find_blender_runtime(),
                    {"backend": "python-module", "executable": None, "module": "bpy"},
                )

    def test_reports_engine_missing_when_neither_binary_nor_module_exists(self):
        with patch("backend.app.runtime.find_blender_binary", return_value=None):
            with patch("backend.app.runtime.has_bpy_module", return_value=False):
                self.assertIsNone(find_blender_runtime())


if __name__ == "__main__":
    unittest.main()
