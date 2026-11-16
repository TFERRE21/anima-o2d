"""One-click story approval and status tests for the new narrated 2D engine."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("ANIMA_STORAGE", str(Path(tempfile.gettempdir()) / "anima-studio-2d-ci-jobs"))
from backend.app import main


class UnifiedStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.job_id = "c0ffeec0ffee"
        self.job = {
            "id": self.job_id, "status": "story_ready",
            "story_approved": False,
            "story_plan": {
                "planet": "Aurora-7", "palette": "aurora",
                "scenes": [
                    {"title": "Chegada", "visual_action": "Amigos chegam ao planeta."},
                    {"title": "Trilha", "visual_action": "Pipo encontra uma pista."},
                ],
                "short_scene_indices": [0],
            },
            "formats": ["16:9", "9:16"],
        }
        self.calls = []
        def update(_id, **kwargs):
            self.job.update(kwargs)
        def start(_id, payload):
            self.calls.append((_id, payload.formats))
            self.job["status"] = "queued"
            return {"status": "queued", "job_id": _id}
        self.patchers = [
            mock.patch.object(main, "STORAGE", Path(self.tmp.name)),
            mock.patch.object(main, "_get_job", return_value=self.job),
            mock.patch.object(main, "_update", side_effect=update),
            mock.patch.object(main, "render_story", side_effect=start),
        ]
        for item in self.patchers:
            item.start()

    def tearDown(self):
        for patch in reversed(self.patchers):
            patch.stop()
        self.tmp.cleanup()

    def test_approval_starts_narrated_2d_without_images_or_gpu(self):
        result = main.approve_story_generate_images(self.job_id)
        self.assertEqual(result["production_engine"], "2d")
        self.assertFalse(result["gpu_required"])
        self.assertEqual(result["status"], "queued")
        self.assertEqual(self.calls, [(self.job_id, ["16:9", "9:16"])])
        self.assertTrue(self.job["story_approved"])
        self.assertEqual(self.job["art_stage"], "drawing")

    def test_board_returns_cpu_progress_instead_of_image_queue(self):
        self.job.update(story_approved=True, auto_production_requested=True,
                        status="processing", art_stage="drawing", progress=47,
                        drawing_scenes_finished=7)
        board = main.get_episode_art_board(self.job_id)
        self.assertEqual(board["production_engine"], "2d")
        self.assertEqual(board["video_progress"], 47)
        self.assertEqual(board["approved_artworks"], 7)
        self.assertEqual(board["total_artworks"], 2)
        self.assertEqual(board["tasks"], [])
        self.assertEqual(board["image_engine"]["provider"], "cpu-2d")

    def test_old_gpu_error_story_is_reusable(self):
        self.job.update(status="story_ready", story_approved=True,
                        art_stage="error", art_error="CUDA error: out of memory")
        result = main.approve_story_generate_images(self.job_id)
        self.assertEqual(result["status"], "queued")
        self.assertIsNone(self.job["art_error"])
        self.assertEqual(len(self.calls), 1)

    def test_no_second_approval_during_render(self):
        self.job["status"] = "processing"
        with self.assertRaises(main.HTTPException) as ex:
            main.approve_story_generate_images(self.job_id)
        self.assertEqual(ex.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
