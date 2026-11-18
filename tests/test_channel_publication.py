"""Original channel identity, SEO metadata and child-safe publication tests."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest import mock

from PIL import Image
from backend.app.channel_branding import brand_frame
from backend.app.youtube_package import content_metadata,prepare_package
from backend.app.youtube_publisher import next_publish_time


class ChannelAutomationTests(unittest.TestCase):
    PLAN={
        "planet":"Aurora-7","title":"A Missão de Aurora-7",
        "value":"paciência e trabalho em equipe",
        "synopsis":"Luna, Tomi e Pipo ajudam os Lumins a recuperar o farol."
    }
    def test_original_intro_and_kid_friendly_outro(self):
        picture=Image.new("RGB",(1280,720),(100,150,180))
        opening=brand_frame("16:9",False,.3,backdrop=picture)
        ending=brand_frame("16:9",True,.8,backdrop=picture)
        vertical=brand_frame("9:16",True,.5,backdrop=picture)
        self.assertEqual(opening.size,(1280,720))
        self.assertEqual(ending.size,(1280,720))
        self.assertEqual(vertical.size,(720,1280))
        self.assertNotEqual(opening.tobytes(),ending.tobytes())

    def test_seo_derived_only_from_approved_story(self):
        data=content_metadata(self.PLAN,"16:9")
        self.assertIn("Aurora-7",data["title"])
        self.assertIn("Lumins",data["description"])
        self.assertIn("paciência",data["description"])
        self.assertIn("#PequenosGuardioes",data["description"])
        self.assertNotIn("sininho",data["description"].lower())
        self.assertTrue(data["selfDeclaredMadeForKids"])
        self.assertLessEqual(len(data["title"]),100)
        self.assertEqual(data["categoryId"],"1")

    def test_short_metadata(self):
        data=content_metadata(self.PLAN,"9:16")
        self.assertIn("#Shorts",data["title"])
        self.assertIn("#Shorts",data["description"])

    def test_publication_slots_are_brazil_timezone(self):
        conf={"publish_days":["Tuesday","Thursday"],
              "publish_time":"18:00"}
        # Monday Nov 16, 2026 at 18:00 Brasilia = 21:00 UTC.
        now=datetime(2026,11,16,21,0,tzinfo=timezone.utc)
        next_slot=datetime.fromisoformat(next_publish_time(conf,now=now))
        self.assertEqual(next_slot.astimezone(timezone.utc).isoformat(),
                         "2026-11-17T21:00:00+00:00")

    def test_prepared_package_persists_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            video=root/"episode.mp4"
            video.write_bytes(b"stub")
            def fake_thumbnail(video,destination,metadata):
                Image.new("RGB",(1280,720),(40,80,120)).save(destination)
                return destination
            with mock.patch("backend.app.youtube_package._thumbnail",
                            side_effect=fake_thumbnail):
                result=prepare_package(self.PLAN,"16:9",video,root)
            self.assertTrue(Path(result["thumbnail_path"]).is_file())
            self.assertTrue((root/"youtube-ready"/"16x9"/"metadata.json").is_file())


if __name__=="__main__":
    unittest.main()
