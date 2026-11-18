"""Regression: final published MP4 must retain full story and audible narration."""
from __future__ import annotations
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.app.comic_panels import MAX_PANELS_LANDSCAPE, layout
from backend.app.video_integrity import (
    concat_video_only,concat_with_audio,validate_video,verify_audible_audio,
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg and ffprobe are required")
class VideoIntegrityTests(unittest.TestCase):
    def make_clip(self,folder:Path,name:str,seconds:int=1,muted:bool=False,
                  size:str="320x180")->Path:
        dst=folder/name
        audio=("anullsrc=channel_layout=stereo:sample_rate=48000"
               if muted else "sine=frequency=440:sample_rate=48000")
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-f","lavfi","-i",f"color=c=blue:s={size}:r=12",
            "-f","lavfi","-i",audio,
            "-t",str(seconds),"-c:v","libx264","-pix_fmt","yuv420p",
            "-c:a","aac","-shortest",str(dst)
        ],check=True,timeout=40)
        return dst

    def test_landscape_scene_uses_one_large_frame(self):
        self.assertEqual(MAX_PANELS_LANDSCAPE,1)
        panels=layout(1280,720,False)
        self.assertEqual(len(panels),1)
        left,top,right,bottom=panels[0]
        self.assertGreater((right-left)*(bottom-top)/(1280*720),.70)

    def test_audio_safe_branding_matches_expected_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            intro=self.make_clip(root,"intro.mp4",1)
            body=self.make_clip(root,"story.mp4",3,size="160x90")
            outro=self.make_clip(root,"outro.mp4",1)
            target=root/"final.mp4"
            stats=concat_with_audio([intro,body,outro],target,fps=12)
            self.assertAlmostEqual(stats["duration"],5,delta=.7)
            self.assertIsNotNone(stats["audio"])
            self.assertIsNotNone(stats["video"])
            self.assertGreater(verify_audible_audio(target,segment_seconds=1),-65)

    def test_scene_join_rewrites_timestamps_and_duration(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            clips=[self.make_clip(root,f"clip-{i}.mp4",1) for i in range(3)]
            dst=root/"silent.mp4"
            result=concat_video_only(clips,dst,fps=12)
            self.assertAlmostEqual(result["duration"],3,delta=.65)
            self.assertIsNone(result["audio"])

    def test_silent_audio_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            muted=self.make_clip(root,"muted.mp4",1,muted=True)
            validate_video(muted,require_audio=True)
            with self.assertRaisesRegex(RuntimeError,"mudo|inaudível"):
                verify_audible_audio(muted,segment_seconds=1)


if __name__=="__main__":
    unittest.main()
