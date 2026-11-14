"""Automated image-to-video pipeline regression tests.

Tests use generated TEST shapes as input files; production has no placeholder
image fallback. The server only accepts real image-worker outputs.
"""
from __future__ import annotations

import io
import os
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

os.environ.setdefault("ANIMA_STORAGE", str(Path(tempfile.gettempdir()) / "anima-studio-auto-ci"))
from backend.app import auto_production, comfy_worker, main


def sample_png(width, height, transparent=False):
    canvas = Image.new("RGBA", (width, height),
                       (255, 255, 255, 255) if transparent else (111, 182, 205, 255))
    if transparent:
        ImageDraw.Draw(canvas).ellipse((width//4, height//5, 3*width//4, 4*height//5),
                                      fill=(185, 86, 121, 255))
    stream = io.BytesIO()
    canvas.save(stream, format="PNG")
    return stream.getvalue()


class AutomaticEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Path(self.tmp.name)
        self.id = "abc123abc123"
        self.job = {
            "id": self.id, "status": "story_ready", "story_approved": True,
            "auto_production_requested": True, "art_stage": "queued",
            "story_plan": {
                "planet": "Aurora-7", "biome": "jardim",
                "scenes": [{"title": "Encontro", "visual_action": "Os amigos exploram."}],
                "short_scene_indices": [0],
            },
            "formats": ["9:16"], "title": "Uma aventura", "story": "Uma aventura linda.",
            "planet": "Aurora-7",
        }
        self.renders = []
        def fake_update(_id, **fields):
            self.job.update(fields)
        def fake_render(_id, payload):
            self.renders.append((_id, payload.formats))
            self.job["status"] = "queued"
            return {"job_id": _id, "status": "queued"}
        self.patchers = [
            mock.patch.object(main, "STORAGE", self.storage),
            mock.patch.object(main, "JOBS", {self.id: self.job}),
            mock.patch.object(main, "_get_job", side_effect=lambda id: self.job),
            mock.patch.object(main, "_update", side_effect=fake_update),
            mock.patch.object(main, "render_story", side_effect=fake_render),
            mock.patch.object(main, "_has", return_value=True),
            mock.patch.object(main, "blender_available", return_value=True),
            mock.patch.object(comfy_worker, "_tasks", {}),
            mock.patch.object(comfy_worker, "_queue", queue.Queue()),
            mock.patch.object(comfy_worker, "_workers", {"test": 99999999999}),
            mock.patch.object(comfy_worker, "_store", self.storage/"comfyui"/"task-state.json"),
        ]
        for patch in self.patchers:
            patch.start()
        auto_production._stopping.clear()

    def tearDown(self):
        for patch in reversed(self.patchers):
            patch.stop()
        self.tmp.cleanup()

    def _candidate(self, asset_id, file_bytes, fmt="9:16", status="done"):
        from backend.app.art_director import create_art_plan
        identity = create_art_plan(self.job["story_plan"], fmt)["identity_lock"]
        request = {
            "prompt": "Original cartoon illustration, beautiful landscape",
            "negative_prompt": "plastic toy",
            "width": 576, "height": 1024, "checkpoint": "checkpoint.safetensors",
            "steps": 20, "seed": -1, "cfg": 7,
        }
        item = comfy_worker.queue_art_image(request, self.id, asset_id, fmt, identity)
        task = comfy_worker._tasks[item["task_id"]]
        task["status"] = status
        target = comfy_worker._store.parent/(item["task_id"]+".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
        task["image_file"] = str(target)
        return task

    def test_all_images_are_approved_and_video_starts_without_second_click(self):
        for actor in ("luna", "tomi", "pipo"):
            self._candidate(actor, sample_png(320, 480, transparent=True))
        self._candidate("scene-00-background", sample_png(288, 512))
        auto_production.process_pending()
        self.assertEqual(self.job["status"], "queued")
        self.assertEqual(self.renders, [(self.id, ["9:16"])])
        from backend.app.art_assets import locked_cast_path, readiness
        from backend.app.art_director import create_art_plan
        lock = create_art_plan(self.job["story_plan"])["identity_lock"]
        self.assertTrue(locked_cast_path(self.storage, "luna", lock))
        self.assertTrue(readiness(self.storage, self.id, self.job["story_plan"], "9:16", [0])["ready"])
        auto_production.process_pending()
        self.assertEqual(len(self.renders), 1)

    def test_invalid_art_retries_instead_of_faking_a_frame(self):
        self._candidate("scene-00-background", b"not a PNG")
        auto_production.process_pending()
        tasks = list(comfy_worker._tasks.values())
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["auto_state"], "retry_queued")
        self.assertEqual(tasks[1]["status"], "queued")
        self.assertFalse(self.renders)

    def test_worker_offline_keeps_queue_waiting_with_no_video(self):
        comfy_worker._workers.clear()
        auto_production.process_pending()
        self.assertEqual(self.job["art_stage"], "waiting_image_engine")
        self.assertFalse(self.renders)


if __name__ == "__main__":
    unittest.main()
