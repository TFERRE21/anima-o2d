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

    def test_oom_recognized_without_other_errors_becoming_oom(self):
        self.assertTrue(self.agent._is_oom("CUDA error: out of memory"))
        self.assertTrue(self.agent._is_oom("HIP error: out of memory"))
        self.assertFalse(self.agent._is_oom("missing checkpoint"))
        self.assertFalse(self.agent._is_oom("ConnectionError: timed out"))


if __name__ == "__main__":
    unittest.main()
