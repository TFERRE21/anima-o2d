"""CPU-only story approval and interrupted-job production regression tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("ANIMA_STORAGE", str(Path(tempfile.gettempdir()) / "anima-story-2d-ci"))
from backend.app import auto_production, main


class AutomaticEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.id = "abc123abc123"
        self.job = {
            "id": self.id, "status": "story_ready", "story_approved": True,
            "auto_production_requested": True, "art_stage": "error",
            "art_error": "Nó 5 (KSampler): CUDA error: out of memory",
            "story_plan": {"planet": "Aurora-7", "palette": "aurora",
                           "scenes": [{"title": "A chegada", "visual_action": "Os amigos exploram."}],
                           "short_scene_indices": [0]},
            "formats": ["9:16"], "title": "A nova aventura",
            "story": "Luna, Tomi e Pipo ajudam o planeta.",
            "planet": "Aurora-7",
        }
        self.started = []
        def update(_id, **kwargs):
            self.job.update(kwargs)
        def start(_id, request):
            self.started.append((_id, request.formats))
            self.job["status"] = "queued"
            return {"job_id": _id, "status": "queued"}
        self.patches = [
            mock.patch.object(main, "STORAGE", Path(self.tmp.name)),
            mock.patch.object(main, "JOBS", {self.id: self.job}),
            mock.patch.object(main, "_get_job", side_effect=lambda _id: self.job),
            mock.patch.object(main, "_update", side_effect=update),
            mock.patch.object(main, "render_story", side_effect=start),
            mock.patch.object(main, "_has", return_value=True),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_old_gpu_oom_story_starts_2d_without_png_or_blender(self):
        auto_production.process_pending()
        self.assertEqual(self.started, [(self.id, ["9:16"])])
        self.assertEqual(self.job["production_engine"], "2d")
        self.assertIsNone(self.job["art_error"])
        self.assertEqual(self.job["status"], "queued")
        auto_production.process_pending()
        self.assertEqual(len(self.started), 1)

    def test_2d_does_not_retry_its_own_render_errors_indefinitely(self):
        self.job.update(status="failed", stage="render_error", production_engine="2d")
        auto_production.process_pending()
        self.assertFalse(self.started)

    def test_ffmpeg_or_speech_unavailable_waits_without_gpu_queue(self):
        with mock.patch.object(main, "_has", return_value=False):
            auto_production.process_pending()
        self.assertFalse(self.started)
        self.assertEqual(self.job["art_stage"], "waiting_video_engine")

    def test_interrupted_old_job_is_resumed_only_once(self):
        self.job.update(status="failed", stage="interrupted", auto_video_recovery_count=0)
        auto_production.process_pending()
        self.assertEqual(self.job["auto_video_recovery_count"], 1)
        self.assertEqual(len(self.started), 1)
        self.job.update(status="failed", stage="interrupted")
        auto_production.process_pending()
        self.assertEqual(len(self.started), 1)


if __name__ == "__main__":
    unittest.main()
