import copy
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from backend.app.worlds import build_episode_plan
import backend.app.renderer as renderer
from backend.app.renderer import render_episode, VOICE_PROFILE
from backend.app.runtime import blender_available



class ProbeDurationFallbackTests(unittest.TestCase):
    def test_reads_duration_from_ffmpeg_when_ffprobe_and_mutagen_are_unavailable(self):
        class FakeProcess:
            def __init__(self):
                self.stderr = iter([
                    "Input #0, mov,mp4,m4a, from 'sample.mp4':\\n",
                    "  Duration: 00:05:12.50, start: 0.000000, bitrate: 1200 kb/s\\n",
                ])
                self.returncode = None

            def poll(self):
                return self.returncode

            def terminate(self):
                self.returncode = 0

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

            def kill(self):
                self.returncode = -9

        with tempfile.TemporaryDirectory(prefix="anima-probe-test-") as tmp:
            media = Path(tmp) / "sample.mp4"
            media.write_bytes(b"fake-media")
            with (
                mock.patch.object(renderer.shutil, "which", return_value=None),
                mock.patch.object(renderer, "_ffmpeg_executable", return_value="/usr/bin/ffmpeg"),
                mock.patch.object(renderer.subprocess, "Popen", return_value=FakeProcess()),
                mock.patch("mutagen.File", return_value=None),
            ):
                self.assertEqual(renderer._probe_duration(media), 312.5)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and shutil.which("espeak-ng") and blender_available(),
                     "FFmpeg/ffprobe/espeak-ng/Blender 3D runtime not installed")
class RenderDurationTests(unittest.TestCase):
    def test_blender_3d_is_the_only_video_renderer_and_voice_cast_is_stable(self):
        source = Path(renderer.__file__).read_text(encoding="utf-8")
        self.assertIn("find_blender_runtime", source)
        self.assertIn("_render_blender_frames(", source)
        self.assertNotIn("draw_scene_frame", source)
        self.assertNotIn('engine == "2d"', source)
        self.assertNotIn("from backend.app.cartoon2d", source)
        self.assertEqual(
            {name: profile["voice"] for name, profile in VOICE_PROFILE.items()},
            {
                "Narrador": "pt-BR-ThalitaMultilingualNeural",
                "Luna": "pt-BR-FranciscaNeural",
                "Tomi": "pt-BR-AntonioNeural",
                "Pipo": "pt-BR-AntonioNeural",
                "Moradora": "pt-BR-ThalitaMultilingualNeural",
            },
        )

    def test_horizontal_and_vertical_duration_contracts(self):
        plan = build_episode_plan(0)
        # A single representative shot keeps CI fast while still exercising
        # Blender 3D, voice assembly, FFmpeg muxing, duration and real output sizes.
        sample_plan = copy.deepcopy(plan)
        sample_plan["scenes"] = sample_plan["scenes"][:1]
        sample_plan["short_scene_indices"] = [0]
        sample_plan["audio_segments_long"] = [
            {"speaker": "Narrador", "text": " ".join(plan["long_script"]), "scene": 0},
            {"speaker": "Luna", "text": "Vamos investigar juntos!", "scene": 0},
            {"speaker": "Tomi", "text": "Vou organizar o plano com cuidado.", "scene": 0},
            {"speaker": "Pipo", "text": "Au! Encontrei uma pista!", "scene": 0},
            {"speaker": "Moradora", "text": "Muito obrigada por ouvirem nossa comunidade.", "scene": 0},
        ]
        sample_plan["audio_segments_short"] = [
            {"speaker": "Narrador", "text": plan["short_script"], "scene": 0},
            {"speaker": "Luna", "text": "Encontramos uma solução juntos!", "scene": 0},
            {"speaker": "Tomi", "text": "Equipe, vamos trabalhar!", "scene": 0},
            {"speaker": "Pipo", "text": "Au! Conseguimos!", "scene": 0},
        ]
        with tempfile.TemporaryDirectory(prefix="anima3d-test-") as tmp:
            root = Path(tmp)
            long_video = root / "episode-16x9.mp4"
            short_video = root / "episode-9x16.mp4"
            original_fps = renderer.FPS
            renderer.FPS = 0.003
            try:
                long_result = render_episode(
                    sample_plan["title"], sample_plan["long_script"], "16:9", long_video, root,
                    planet_name=sample_plan["planet"], story_plan=sample_plan
                )
                short_result = render_episode(
                    sample_plan["title"], sample_plan["short_script"], "9:16", short_video, root,
                    planet_name=sample_plan["planet"], story_plan=sample_plan
                )
            finally:
                renderer.FPS = original_fps

            self.assertTrue(long_video.exists())
            self.assertTrue(short_video.exists())
            self.assertGreater(long_result["duration_seconds"], 300)
            self.assertLessEqual(long_result["duration_seconds"], 600)
            self.assertTrue({"Luna", "Tomi", "Pipo", "Narrador"}.issubset(set(long_result["speakers"])))
            self.assertGreaterEqual(short_result["duration_seconds"], 60)
            self.assertLessEqual(short_result["duration_seconds"], 90)
            self.assertTrue({"Luna", "Tomi", "Pipo", "Narrador"}.issubset(set(short_result["speakers"])))
            self.assertEqual(short_result["scene_count"], 1)
            self.assertEqual(long_result["resolution"], "1920x1080")
            self.assertEqual(short_result["resolution"], "1080x1920")
            self.assertEqual(long_result["render_engine"], "Blender 3D Cartoon infantil")
            self.assertEqual(short_result["render_engine"], "Blender 3D Cartoon infantil")


if __name__ == "__main__":
    unittest.main()
