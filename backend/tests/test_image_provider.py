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

    def test_runway_out_of_credits_switches_to_openai_without_extra_runway_calls(self):
        with mock.patch.dict(os.environ, {
            "ANIMA_IMAGE_PROVIDER": "auto",
            "RUNWAYML_API_SECRET": "no-credit-test-key",
            "OPENAI_API_KEY": "working-test-key",
        }):
            image_provider._block_file().unlink(missing_ok=True)
            request = comfy_worker.queue_art_image({
                "prompt": "Original cartoon forest", "width": 576, "height": 1024
            }, "abc123abc123", "scene-00-background", "9:16", "series-lock")
            task = comfy_worker._tasks[request["task_id"]]
            with mock.patch.object(image_provider, "_runway_image",
                                   side_effect=RuntimeError(
                                       'HTTP 400: {"error":"You do not have enough credits to run this task."}'
                                   )) as runway, mock.patch.object(
                                       image_provider, "_openai_image",
                                       return_value=self.picture(720, 1280)) as openai:
                self.assertTrue(image_provider.process_one())
                self.assertEqual(runway.call_count, 1)
                self.assertEqual(openai.call_count, 0)
                self.assertEqual(image_provider.configured_provider(), "openai")
                self.assertEqual(task["status"], "queued")
                self.assertEqual(task["provider"], "openai")
                self.assertTrue(image_provider.process_one())
                self.assertEqual(task["status"], "done")
                self.assertEqual(runway.call_count, 1)
                self.assertEqual(openai.call_count, 1)
                self.assertEqual(image_provider.engine_state()["provider"], "openai")

    def test_no_credits_without_fallback_blocks_tasks_instead_of_rebilling(self):
        with mock.patch.dict(os.environ, {
            "ANIMA_IMAGE_PROVIDER": "auto",
            "RUNWAYML_API_SECRET": "empty-credit-test-key",
            "OPENAI_API_KEY": "",
        }):
            image_provider._block_file().unlink(missing_ok=True)
            request = comfy_worker.queue_art_image({
                "prompt": "Original cartoon forest", "width": 576, "height": 1024
            }, "abc123abc123", "scene-00-background", "9:16", "series-lock")
            task = comfy_worker._tasks[request["task_id"]]
            with mock.patch.object(image_provider, "_runway_image",
                                   side_effect=RuntimeError(
                                       "You do not have enough credits to run this task."
                                   )) as runway:
                self.assertTrue(image_provider.process_one())
                self.assertEqual(task["status"], "blocked")
                self.assertEqual(task["auto_state"], "waiting_provider")
                self.assertEqual(image_provider.configured_provider(), "unavailable")
                self.assertFalse(image_provider.engine_state()["ready"])
                self.assertFalse(image_provider.process_one())
                self.assertEqual(runway.call_count, 1)

    def test_recover_historical_runway_credit_failures(self):
        with mock.patch.dict(os.environ, {
            "ANIMA_IMAGE_PROVIDER": "auto",
            "RUNWAYML_API_SECRET": "",
            "OPENAI_API_KEY": "working-test-key",
        }):
            for index in range(3):
                comfy_worker._tasks[str(index)] = {
                    "id": str(index), "job_id": "abc123abc123",
                    "asset_id": "luna", "format": "9:16",
                    "identity_lock": "fixed-identity",
                    "created_at": "2026-11-14T10:00:0" + str(index) + "Z",
                    "status": "failed", "provider": "runway",
                    "message": 'HTTP 400: {"error":"You do not have enough credits to run this task."}',
                    "auto_state": "failed",
                    "config": {"prompt": "Character Luna full body"},
                }
            self.assertTrue(image_provider.reconcile_credit_tasks())
            current = [t for t in comfy_worker._tasks.values() if t["status"] == "queued"]
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]["provider"], "openai")
            self.assertEqual(current[0]["auto_state"], "resuming")
            self.assertEqual(sum(t["status"] == "cancelled"
                                 for t in comfy_worker._tasks.values()), 2)

    def test_blocked_task_can_move_to_connected_comfyui_worker(self):
        with mock.patch.dict(os.environ, {
            "ANIMA_IMAGE_PROVIDER": "auto",
            "RUNWAYML_API_SECRET": "",
            "OPENAI_API_KEY": "",
        }):
            comfy_worker._workers["gpu"] = image_provider.time.time()
            comfy_worker._tasks["retry"] = {
                "id": "retry", "job_id": "abc123abc123",
                "asset_id": "pipo", "format": "9:16",
                "identity_lock": "fixed", "created_at": "2026-11-14T10:00:00Z",
                "provider": "runway", "provider_error_code": "insufficient_credits",
                "status": "blocked", "auto_state": "waiting_provider",
                "config": {"prompt": "Pipo cartoon"},
            }
            self.assertTrue(image_provider.reconcile_credit_tasks())
            self.assertEqual(comfy_worker._tasks["retry"]["status"], "queued")
            self.assertEqual(comfy_worker._tasks["retry"]["provider"], "comfyui")
            self.assertEqual(comfy_worker._queue.get_nowait(), "retry")

    def test_opaque_character_not_falsely_accepted_as_transparent(self):
        task = {"asset_id": "luna", "format": "9:16"}
        result = image_provider._normalize_image(self.picture(640, 960), task)
        with Image.open(io.BytesIO(result)) as im:
            self.assertEqual(im.mode, "RGBA")
            self.assertEqual(im.getchannel("A").getextrema(), (255, 255))


if __name__ == "__main__":
    unittest.main()
