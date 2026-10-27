from pathlib import Path
import tempfile
import sys
import unittest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from anchor_training import screenshot_to_css, css_to_screenshot, stand_focus_css, draw_anchor_overlay

class TestImageCoordinatesV17(unittest.TestCase):
    def test_real_edge_screenshot_ratio(self):
        png=(2048,1015)
        viewport=(1726,856)
        # The user-marked field 1 is on the actual seat band around PNG y=271.
        ax,ay=css_to_screenshot(235,229,png,viewport)
        self.assertAlmostEqual(ax,279,delta=1)
        self.assertAlmostEqual(ay,271.5,delta=1)
        bx,by=screenshot_to_css(ax,ay,png,viewport)
        self.assertAlmostEqual(bx,235,places=5)
        self.assertAlmostEqual(by,229,places=5)

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            css_to_screenshot(2,3,(0,400),(1726,856))

    def test_crop_tries_stand_strip_just_above_pitch(self):
        x,y=stand_focus_css((0,250,1151,770.4))
        self.assertAlmostEqual(x,529.46,delta=1)
        self.assertEqual(y,235)

    def test_overlay_renders_on_scaled_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            pic=Path(tmp)/'in.png';out=Path(tmp)/'out.png'
            Image.new('RGB',(2048,1015),(0,0,0)).save(pic)
            draw_anchor_overlay(pic,{'FELT-1':[(235,229)]},out,(1726,856))
            image=Image.open(out)
            self.assertNotEqual(image.getpixel((279,271)),(0,0,0))
            self.assertEqual(image.getpixel((235,229)),(0,0,0))

if __name__=='__main__':unittest.main()
