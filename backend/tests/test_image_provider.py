"""Image API provider tests: no external requests, no spending or secret leakage."""
from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

os.environ.setdefault("ANIMA_STORAGE", str(Path(tempfile.gettempdir()) / "anima-image-ci"))
from backend.app import image_provider, comfy_worker


class ImageProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(comfy_worker, "_tasks", {}),
            mock.patch.object(comfy_worker, "_store", self.storage / "comfyui"/"task-state.json"),
            mock.patch.object(comfy_worker, "_workers", {}),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    @staticmethod
    def picture(width, height):
        image = Image.new("RGB", (width, height), (90, 155, 211))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        return stream.getvalue()

    def test_cloud_provider_selection_without_exposing_credentials(self):
        with mock.patch.dict(os.environ, {"ANIMA_IMAGE_PROVIDER": "auto",
                                          "RUNWAYML_API_SECRET": "private-runway",
                                          "OPENAI_API_KEY": "private-openai"}):
            self.assertEqual(image_provider.configured_provider(), "runway")
            state = image_provider.engine_state()
            self.assertTrue(state["ready"])
            self.assertNotIn("private", repr(state))
        with mock.patch.dict(os.environ, {"ANIMA_IMAGE_PROVIDER": "openai",
                                          "OPENAI_API_KEY": "private-openai"}, clear=False):
            self.assertEqual(image_provider.configured_provider(), "openai")

    def test_cloud_worker_creates_real_png_and_notifies_orchestrator(self):
        with mock.patch.dict(os.environ, {"ANIMA_IMAGE_PROVIDER": "openai",
                                          "OPENAI_API_KEY": "TEST-KEY"}):
            result = comfy_worker.queue_art_image({
                "prompt": "A children's cartoon forest illustration", "width": 576,
                "height": 1024, "checkpoint": "foo.safetensors",
            }, "abc123abc123", "scene-00-background", "9:16", "identity-lock")
            self.assertEqual(result["provider"], "openai")
            task = comfy_worker._tasks[result["task_id"]]
            self.assertEqual(task["status"], "queued")
            with mock.patch.object(image_provider, "_openai_image",
                                   return_value=self.picture(750, 1000)):
                self.assertTrue(image_provider.process_one())
            self.assertEqual(task["status"], "done")
            with Image.open(task["image_file"]) as img:
                self.assertEqual(img.size, (576, 1024))
            self.assertTrue(comfy_worker._store.exists())
            self.assertFalse(image_provider.process_one())

    def test_previously_queued_unavailable_task_is_recovered(self):
        with mock.patch.dict(os.environ, {"ANIMA_IMAGE_PROVIDER": "openai",
                                          "OPENAI_API_KEY": "TEST-KEY"}):
            comfy_worker._tasks["previous"] = {
                "id": "previous", "job_id": "abc123abc123",
                "asset_id": "scene-00-background", "format": "9:16",
                "status": "queued", "provider": "unavailable",
                "config": {"prompt": "storybook landscape"},
            }
            with mock.patch.object(image_provider, "_openai_image",
                                   return_value=self.picture(800, 1200)):
                self.assertTrue(image_provider.process_one())
            self.assertEqual(comfy_worker._tasks["previous"]["status"], "done")

    def test_opaque_character_not_falsely_accepted_as_transparent(self):
        task = {"asset_id": "luna", "format": "9:16"}
        result = image_provider._normalize_image(self.picture(640, 960), task)
        with Image.open(io.BytesIO(result)) as im:
            self.assertEqual(im.mode, "RGBA")
            self.assertEqual(im.getchannel("A").getextrema(), (255, 255))


if __name__ == "__main__":
    unittest.main()
