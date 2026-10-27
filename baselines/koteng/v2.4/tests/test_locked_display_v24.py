"""V2.4: different host monitor dimensions cannot change locked CSS geometry."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from koteng_scanner import locked_edge_context_options, desktop_can_show_locked_window, work_area_fits_locked_edge, windows_primary_work_area
from anchor_training import mapped_points
from profile_lock import verify_profile_lock
ROOT=Path(__file__).resolve().parents[1]

class LockedDisplayV24(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anchors=json.loads((ROOT/'ankerpunkter_koteng.json').read_text())
        cls.profile=json.loads((ROOT/'koteng_profile.json').read_text())
    def test_same_locked_digest(self):
        self.assertEqual(verify_profile_lock(self.profile,self.anchors,'6aaceecebfe408c38e1712dd'),
            '0ce2718f54f209d0ce2442f1052139c928430d4409073f6912c43f4eebc6d7fb')
    def test_fixed_reference_viewport_not_monitor_size(self):
        args=locked_edge_context_options(self.anchors)
        self.assertEqual(args['viewport'],{'width':1294,'height':642})
        self.assertEqual(args['device_scale_factor'],1)
        self.assertFalse(any('maximized' in s for s in args['args']))
        self.assertEqual(mapped_points(self.anchors,self.profile['reference_sections'],
               (1294,642),[0,201.6,863.3,577.8],0.9)['VIP'][0],(436,225))
    def test_changed_stored_dimensions_rejected(self):
        changed=dict(self.anchors,reference_viewport=[1600,900])
        with self.assertRaises(ValueError):locked_edge_context_options(changed)
    def test_too_small_desktop_rejected(self):
        info={'contentWidth':1294,'contentHeight':642,'outerWidth':1304,
              'outerHeight':750,'desktopWidth':1280,'desktopHeight':720}
        self.assertFalse(desktop_can_show_locked_window(info,(1294,642)))
    def test_large_desktop_accepted(self):
        info={'contentWidth':1294,'contentHeight':642,'outerWidth':1304,
              'outerHeight':750,'desktopWidth':1920,'desktopHeight':1040}
        self.assertTrue(desktop_can_show_locked_window(info,(1294,642)))
    def test_css_viewport_mismatch_rejected(self):
        info={'contentWidth':1366,'contentHeight':768,'outerWidth':1366,
              'outerHeight':780,'desktopWidth':1920,'desktopHeight':1040}
        self.assertFalse(desktop_can_show_locked_window(info,(1294,642)))
    def test_primary_work_area_on_non_windows(self):
        if sys.platform!='win32':self.assertIsNone(windows_primary_work_area())
    def test_native_work_area_rejects_taskbar_crop(self):
        self.assertFalse(work_area_fits_locked_edge((1366,720),(1294,642)))
        self.assertTrue(work_area_fits_locked_edge((1920,1040),(1294,642)))
    def test_v24_install_and_revised_instructions(self):
        self.assertTrue((ROOT/'installer_v24.ps1').is_file())
        self.assertTrue((ROOT/'preflight_v24.py').is_file())
        self.assertTrue((ROOT/'requirements_v24.txt').is_file())
        self.assertTrue((ROOT/'V2_4_NY_SKJERM.txt').is_file())
        self.assertTrue((ROOT/'07_SJEKK_SKJERM.bat').is_file())
        self.assertIn('preflight_v24.py',(ROOT/'02_TEST_EN_GANG.bat').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
