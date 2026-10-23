from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pitch_locator import Pitch,locate,to_screen,to_reference
from hurtigkart import checkout_url,expected_from_map,KNOWN,panel_install,panel_show,panel_command,mouse_location

ROOT=Path(__file__).resolve().parents[1]
class LogicTests(unittest.TestCase):
    def test_url_security(self):
        self.assertTrue(checkout_url('https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3'))
        self.assertFalse(checkout_url('https://evil.example/checkout/abcdef'))
        self.assertFalse(checkout_url('https://billett.rbk.no.evil.example/checkout/test'))
        self.assertFalse(checkout_url('http://billett.rbk.no/checkout/test'))
        self.assertFalse(checkout_url('https://billett.rbk.no/other/test'))
    def test_60_reference_points(self):
        self.assertEqual(len(KNOWN),60)
        self.assertIn('K',KNOWN);self.assertIn('LB',KNOWN);self.assertIn('PRESSE',KNOWN)
        self.assertNotIn('SB',KNOWN)
    def test_dynamic_map_names(self):
        fake={'seatMap':{'layers':[{'sections':[{'name':'LB','groups':[{'rows':[{'seats':[{'statusId':'1'},{'statusId':'2'}]}]}]},
              {'name':'K','groups':[{'rows':[{'seats':[{'statusId':'3'}]}]}]}],
              'ga':[{'name':'Øvre Øst'}]}]}}
        names,caps,stands=expected_from_map(fake)
        self.assertEqual(names,{'LB','K'});self.assertEqual(caps,{'LB':2,'K':1});self.assertIn('ØVRE ØST',stands)
    def test_pitch_relative_coordinates(self):
        pitch=Pitch(400,500,300,190)
        for point in [(337,298),(610,344),(400,230),(450,504)]:
            screen=to_screen(point,pitch)
            ref=to_reference(screen,pitch)
            self.assertAlmostEqual(ref[0],point[0],delta=1.5)
            self.assertAlmostEqual(ref[1],point[1],delta=1.5)
    def test_detect_synthetic_pitch(self):
        from io import BytesIO
        from PIL import Image,ImageDraw
        im=Image.new('RGB',(900,700),(240,240,240));d=ImageDraw.Draw(im)
        d.rectangle((300,300,542,456),fill=(12,94,67))
        bio=BytesIO();im.save(bio,format='PNG')
        pitch=locate(bio.getvalue())
        self.assertIsNotNone(pitch)
        self.assertAlmostEqual(pitch.x,300,delta=8)
        self.assertAlmostEqual(pitch.y,300,delta=8)
        self.assertAlmostEqual(pitch.w,243,delta=10)
    def test_fixture_file(self):
        f=ROOT/'fixtures'/'demo_21_fields.html'
        self.assertTrue(f.is_file());self.assertIn('TEST',f.read_text())

class BrowserPanelTests(unittest.TestCase):
    def test_panel_and_mouse_tracking(self):
        try:from playwright.sync_api import sync_playwright
        except ImportError:self.skipTest('Playwright mangler')
        if not Path('/usr/bin/chromium').is_file():self.skipTest('Chromium kun i Linux-testmiljø')
        with sync_playwright() as pw:
            b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            context=b.new_context(viewport={'width':1300,'height':800});page=context.new_page()
            page.set_content((ROOT/'fixtures/demo_21_fields.html').read_text(encoding='utf-8'))
            self.assertTrue(panel_install(page))
            panel_show(page,{'mode':'TEST','found':3,'total':60,'free':108,
                             'missing':['A','C','K'],'conflicts':0,'last':'TEST'})
            self.assertEqual(page.locator('#rbk-found').inner_text(),'3/60')
            self.assertEqual(page.locator('#rbk-missing button').count(),3)
            page.locator('[data-action="retry"]').click()
            self.assertEqual(panel_command(page),'retry')
            page.mouse.move(500,500)
            self.assertGreater(mouse_location(page)['t'],0)
            self.assertEqual(panel_command(page),'')
            context.close();b.close()

if __name__=='__main__':unittest.main()