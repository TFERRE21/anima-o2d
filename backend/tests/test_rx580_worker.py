"""Pure offline tests for RX580 ZLUDA memory profile; never run GPU in CI."""
from __future__ import annotations

import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

_SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "windows-gpu-agent" / "comfyui-agent.py"


class RX580MemoryProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with mock.patch.dict(os.environ, {
            "ANIMA_STUDIO_URL": "https://example.invalid",
            "ANIMA_COMFY_TOKEN": "TEST-ONLY-DO-NOT-USE",
            "ANIMA_COMFY_OUTPUT": self.tmp.name,
        }):
            spec = importlib.util.spec_from_file_location("anima_windows_gpu_agent_tests", str(_SCRIPT))
            self.agent = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.agent)
        self.agent._RX580_MODE = True

    def tearDown(self):
        self.tmp.cleanup()

    def test_rx580_8gb_fp32_fallback_resolutions(self):
        portrait = self.agent._sizes_for({"width": 576, "height": 1024})
        landscape = self.agent._sizes_for({"width": 1024, "height": 576})
        cast = self.agent._sizes_for({"width": 768, "height": 1024})
        self.assertEqual(portrait, [(384, 704), (320, 576)])
        self.assertEqual(landscape, [(704, 384), (576, 320)])
        self.assertEqual(cast, [(448, 640), (384, 512)])
        for sizes in [portrait, landscape, cast]:
            self.assertGreater(sizes[0][0] * sizes[0][1],
                               sizes[1][0] * sizes[1][1])

    def test_default_gpu_does_not_force_small_diffusion(self):
        self.agent._RX580_MODE = False
        self.assertEqual(
            self.agent._sizes_for({"width": 576, "height": 1024}),
            [(576, 1024)],
        )

    def test_upscale_on_cpu_keeps_scene_dimensions(self):
        image = Image.new("RGB", (384, 704), "white")
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        enlarged = self.agent._image_for_upload(
            raw.getvalue(), {"width": 576, "height": 1024, "_asset_id": "scene-00-background"}
        )
        with Image.open(io.BytesIO(enlarged)) as result:
            self.assertEqual(result.size, (576, 1024))
            self.assertEqual(result.format, "PNG")

    def test_character_upscale_preserves_white_corners(self):
        image = Image.new("RGB", (448, 640), "white")
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        enlarged = self.agent._image_for_upload(
            raw.getvalue(), {"width": 768, "height": 1024, "_asset_id": "luna"}
        )
        with Image.open(io.BytesIO(enlarged)) as result:
            self.assertEqual(result.size, (768, 1024))
            self.assertEqual(result.getpixel((0, 0))[:3], (255, 255, 255))

    def test_windows_agent_starts_comfy_once_when_offline(self):
        launcher = Path(self.tmp.name) / "comfyui.bat"
        launcher.write_text("@echo off\n", encoding="utf-8")
        self.agent._COMFY_AUTOSTART = True
        self.agent._COMFY_LAUNCHER = launcher
        self.agent._COMFY_ROOT = Path(self.tmp.name)
        self.agent._COMFY_START_ATTEMPTS[:] = []
        self.agent._LAST_COMFY_START = float("-inf")
        with mock.patch.object(self.agent, "_comfy_port_in_use", return_value=False), (
            mock.patch.object(self.agent.subprocess, "Popen")
        ) as started:
            self.assertTrue(self.agent._autostart_comfyui())
            self.assertFalse(self.agent._autostart_comfyui())
            self.assertEqual(started.call_count, 1)

    def test_windows_agent_does_not_duplicate_existing_listener(self):
        launcher = Path(self.tmp.name) / "comfyui.bat"
        launcher.write_text("@echo off\n", encoding="utf-8")
        self.agent._COMFY_AUTOSTART = True
        self.agent._COMFY_LAUNCHER = launcher
        self.agent._COMFY_ROOT = Path(self.tmp.name)
        self.agent._COMFY_START_ATTEMPTS[:] = []
        self.agent._LAST_COMFY_START = float("-inf")
        with mock.patch.object(self.agent, "_comfy_port_in_use", return_value=True), (
            mock.patch.object(self.agent.subprocess, "Popen")
        ) as started:
            self.assertFalse(self.agent._autostart_comfyui())
            started.assert_not_called()

    def test_disconnected_comfy_clears_ready_signal(self):
        self.agent._LOCAL_READY.set()
        self.agent._COMFY_AUTOSTART = False
        with mock.patch.object(self.agent.requests, "get",
                               side_effect=self.agent.requests.ConnectionError("port refused")):
            self.assertFalse(self.agent.check_local_comfy())
        self.assertFalse(self.agent._LOCAL_READY.is_set())

    def test_fp16_profile_requires_noncomment_launcher_flag(self):
        launcher = Path(self.tmp.name) / "comfyui.bat"
        self.agent._COMFY_LAUNCHER = launcher
        launcher.write_text("@echo off\nREM --fp16-unet\nset \"commandline_args=--novram --force-fp32\"\n", encoding="utf-8")
        self.assertEqual(self.agent._profile_version(), "rx580-memory-safe-v1")
        launcher.write_text("@echo off\nset \"commandline_args=--novram --fp16-unet --cpu-vae\"\n", encoding="utf-8")
        self.assertEqual(self.agent._profile_version(), "rx580-unet-fp16-v2")
        self.agent._RX580_MODE = False
        self.assertEqual(self.agent._profile_version(), "")

    def test_directml_backend_is_recognized_without_cuda(self):
        self.agent._DIRECTML_MODE = False
        self.agent._RX580_MODE = False
        status = {
            "devices": [{
                "name": "privateuseone",
                "type": "privateuseone",
                "index": 0,
            }]
        }
        response = mock.Mock()
        response.json.return_value = status
        response.raise_for_status.return_value = None
        with mock.patch.dict(os.environ, {"ANIMA_GPU_BACKEND": "directml"}), (
            mock.patch.object(self.agent.requests, "get", return_value=response)
        ):
            self.assertTrue(self.agent.check_local_comfy())
        self.assertTrue(self.agent._DIRECTML_MODE)
        self.assertEqual(self.agent._profile_version(), "rx580-directml-v3")
        self.agent._LOCAL_READY.clear()

    def test_does_not_falsely_claim_directml_when_zluda_listens(self):
        self.agent._DIRECTML_MODE = False
        self.agent._RX580_MODE = False
        response = mock.Mock()
        response.json.return_value = {
            "devices": [{"name": "cuda:0 AMD Radeon RX 580 [ZLUDA]", "type": "cuda"}]
        }
        response.raise_for_status.return_value = None
        self.agent._COMFY_AUTOSTART = False
        with mock.patch.dict(os.environ, {"ANIMA_GPU_BACKEND": "directml"}), (
            mock.patch.object(self.agent.requests, "get", return_value=response)
        ):
            self.assertFalse(self.agent.check_local_comfy())
        self.assertFalse(self.agent._LOCAL_READY.is_set())

    def test_oom_recognized_without_other_errors_becoming_oom(self):
        self.assertTrue(self.agent._is_oom("CUDA error: out of memory"))
        self.assertTrue(self.agent._is_oom("HIP error: out of memory"))
        self.assertFalse(self.agent._is_oom("missing checkpoint"))
        self.assertFalse(self.agent._is_oom("ConnectionError: timed out"))


if __name__ == "__main__":
    unittest.main()
