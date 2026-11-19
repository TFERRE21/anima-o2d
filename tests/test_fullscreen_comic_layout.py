"""Both Anima Studio video formats display one complete scene per frame."""
from __future__ import annotations
import unittest
from PIL import Image
from backend.app.comic_panels import (
    MAX_PANELS_LANDSCAPE, MAX_PANELS_PORTRAIT, layout, comic_page,
)


class FullscreenComicLayoutTests(unittest.TestCase):
    def test_only_one_frame_in_both_formats(self):
        self.assertEqual(MAX_PANELS_LANDSCAPE,1)
        self.assertEqual(MAX_PANELS_PORTRAIT,1)
        self.assertEqual(layout(1280,720,False),[(0,0,1280,720)])
        self.assertEqual(layout(720,1280,True),[(0,0,720,1280)])

    def test_landscape_has_no_paper_margins_or_split_panels(self):
        art=Image.new("RGB",(1280,720),(41,145,212))
        image,bounds=comic_page([art],(1280,720),"Aurora-7",False,"color",0)
        self.assertEqual(bounds,(0,0,1280,720))
        self.assertEqual(image.getpixel((3,3)),(41,145,212))
        self.assertEqual(image.getpixel((640,360)),(41,145,212))
        self.assertEqual(image.getpixel((1276,716)),(41,145,212))

    def test_portrait_wide_art_fills_all_pixels_without_cropping_trio(self):
        art=Image.new("RGB",(1280,720),(42,110,167))
        # Colored markers at the far left/right of wide artwork approximate
        # cast members who were previously cut out by a portrait center-crop.
        for x,color in [(30,(250,24,91)),(1250,(242,212,45))]:
            for xx in range(x-12,x+12):
                for yy in range(320,400):
                    art.putpixel((xx,yy),color)
        image,bounds=comic_page([art],(720,1280),"Flora-Lume",True,"color",0)
        self.assertEqual(bounds,(0,0,720,1280))
        self.assertEqual(image.size,(720,1280))
        self.assertNotEqual(image.getpixel((5,5)),(255,249,239))
        self.assertNotEqual(image.getpixel((700,1250)),(255,249,239))
        colors=image.getcolors(maxcolors=720*1280)
        self.assertIsNotNone(colors)
        present={rgb for _,rgb in colors}
        self.assertIn((250,24,91),present)
        self.assertIn((242,212,45),present)

    def test_reject_old_multi_panel_pages(self):
        art=Image.new("RGB",(1280,720))
        for format_size,portrait in [((1280,720),False),((720,1280),True)]:
            with self.assertRaisesRegex(ValueError,"tela inteira"):
                comic_page([art,art],format_size,"Teste",portrait,"color",1)

    def test_progressive_draw_stages_keep_frame_dimensions(self):
        art=Image.new("RGB",(1280,720),(39,110,190))
        for portrait,dimensions in [(False,(1280,720)),(True,(720,1280))]:
            variants=[comic_page([art],dimensions,"Teste",portrait,stage,0)[0]
                      for stage in ("paper","sketch","color")]
            self.assertTrue(all(img.size==dimensions for img in variants))
            self.assertNotEqual(variants[0].tobytes(),variants[2].tobytes())


if __name__=="__main__":
    unittest.main()
