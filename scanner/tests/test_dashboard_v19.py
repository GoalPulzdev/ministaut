"""V19 UI regression tests. Browser actions are read-only and queued in page state."""
import unittest
from pathlib import Path
from sys import path
path.insert(0,str(Path(__file__).resolve().parents[1]))
from hurtigkart import panel_install,panel_show,panel_command
ROOT=Path(__file__).resolve().parents[1]

class DashboardTests(unittest.TestCase):
    def setUp(self):
        try:from playwright.sync_api import sync_playwright
        except ImportError:self.skipTest('Playwright ikke installert')
        if not Path('/usr/bin/chromium').exists():self.skipTest('Chromium ikke tilgjengelig')
        self.context_manager=sync_playwright()
        self.pw=self.context_manager.start()
        self.browser=self.pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        self.ctx=self.browser.new_context(viewport={'width':1380,'height':900})
        self.page=self.ctx.new_page()
        self.page.set_content((ROOT/'fixtures'/'demo_21_fields.html').read_text(encoding='utf-8'))
        self.assertTrue(panel_install(self.page))
    def tearDown(self):
        if hasattr(self,'browser'):
            self.ctx.close();self.browser.close();self.context_manager.__exit__(None,None,None)
    def payload(self,**kw):
        base={'mode':'Klar for ny sjekk','found':58,'covered':60,'total':60,'free':6491,
          'estimated':14932,'locked':2,'locked_names':['RB','TB'],'complete':True,
          'missing':[],'conflicts':0,'last':'XA: 100/300', 'title':'Rosenborg – Molde',
          'match_date':'28.11.2026 18:00','event_key':'6a9a7e3f3f93920b289b0675',
          'delta':60,'delta_label':'Estimert flere ikke tilgjengelige',
          'chart':[6700,6600,6491],'clock':'09:30:00','busy':False}
        base.update(kw)
        return base
    def test_full_dashboard(self):
        panel_show(self.page,self.payload())
        self.assertEqual(self.page.locator('#rbk-free').inner_text(),'6 491')
        self.assertEqual(self.page.locator('#rbk-estimated').inner_text(),'14 932')
        self.assertEqual(self.page.locator('#rbk-found').inner_text(),'60/60')
        self.assertEqual(self.page.locator('#rbk-delta').inner_text(),'+60')
        self.assertEqual(self.page.locator('#rbk-spark polyline').count(),1)
    def test_incomplete_never_claims_estimated(self):
        panel_show(self.page,self.payload(complete=False,found=14,covered=16,missing=['A','AA'],delta=None))
        self.assertEqual(self.page.locator('#rbk-estimated').inner_text(),'–')
        self.assertEqual(self.page.locator('#rbk-missing button').count(),2)
        panel_show(self.page,self.payload(complete=True,missing=[]))
        self.assertEqual(self.page.locator('#rbk-missing button').count(),0)
    def test_repeat_and_locked_commands(self):
        # Intentionally do NOT install a Playwright dialog acceptor here.
        # This reproduces actual production conditions and exposes V19 defect.
        panel_show(self.page,self.payload())
        self.page.locator('[data-action="new_scan"]').click()
        self.assertEqual(self.page.locator('#rbk-confirm-title').inner_text(),'Start ny sjekk?')
        self.assertEqual(panel_command(self.page),'')
        self.page.locator('[data-action="approve"]').click()
        self.assertEqual(panel_command(self.page),'new_scan')
        self.assertEqual(panel_command(self.page),'')
        self.page.locator('details summary').click()
        self.page.locator('#rbk-locked-input').fill('RB')
        self.page.locator('[data-action="config_locked"]').click()
        self.page.locator('[data-action="approve"]').click()
        self.assertEqual(panel_command(self.page),'locked:RB')
        self.page.locator('#rbk-switch-url').fill('https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3')
        self.page.locator('[data-action="switch"]').click()
        self.assertEqual(panel_command(self.page),'')
        self.assertIn('Bytt til en annen kamp?',self.page.locator('#rbk-confirm-title').inner_text())
        self.page.locator('[data-action="approve"]').click()
        self.assertEqual(panel_command(self.page),'switch:https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3')
    def test_cancel_does_not_queue_or_start_scan(self):
        self.page.locator('[data-action="new_scan"]').click()
        self.page.locator('[data-action="cancel"]').click()
        self.assertEqual(panel_command(self.page),'')
        self.assertTrue(self.page.locator('#rbk-confirm').is_hidden())

    def test_invalid_switch_url_shows_inline_error(self):
        self.page.locator('details summary').click()
        self.page.locator('#rbk-switch-url').fill('https://billett.rbk.no.evil.example/checkout/fake')
        self.page.locator('[data-action="switch"]').click()
        self.assertIn('Ugyldig adresse',self.page.locator('#rbk-action-notice').inner_text())
        self.assertEqual(panel_command(self.page),'')

    def test_new_scan_and_switch_after_navigation(self):
        self.page.locator('[data-action="new_scan"]').click()
        self.page.locator('[data-action="approve"]').click()
        self.assertEqual(panel_command(self.page),'new_scan')
        # The checkout SPA can replace its main document after reload.
        self.page.set_content('<html><body>New event</body></html>')
        self.assertTrue(panel_install(self.page))
        self.page.locator('details summary').click()
        url='https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3'
        self.page.locator('#rbk-switch-url').fill(url)
        self.page.locator('[data-action="switch"]').click()
        self.page.locator('[data-action="approve"]').click()
        self.assertEqual(panel_command(self.page),'switch:'+url)
        self.assertNotEqual(self.page.locator('#rbk-action-notice').inner_text(),'')

    def test_autoscan_and_chart_controls(self):
        panel_show(self.page,self.payload(auto_enabled=True,auto_remaining=10800,
            chart_points=[{'time_utc':'2026-11-24T09:00:00+00:00','free':5000},
                          {'time_utc':'2026-11-24T12:00:00+00:00','free':4930}],
            forecast={'state':'estimate','value':4100,'low':3700,'high':4450,'daily_change':-560,
                'kickoff_utc':'2026-11-28T17:00:00+00:00','message':'Grovt scenario'}))
        self.assertIn('4 100',self.page.locator('#rbk-forecast-num').inner_text())
        self.assertEqual(self.page.locator('#rbk-history-chart polyline').count(),1)
        self.assertGreaterEqual(self.page.locator('#rbk-history-chart line').count(),4)
        self.assertIn('Neste om 3 t',self.page.locator('#rbk-auto-next').inner_text())
        self.page.locator('[data-action="auto_toggle"]').click()
        self.assertEqual(panel_command(self.page),'auto_toggle')
        self.page.locator('[data-action="open_chart"]').click()
        self.assertEqual(panel_command(self.page),'open_chart')

    def test_forecast_waits_when_too_far(self):
        panel_show(self.page,self.payload(auto_enabled=False,auto_remaining=None,
            chart_points=[],forecast={'state':'too_far','message':'Mer enn 14 dager til avspark.'}))
        self.assertEqual(self.page.locator('#rbk-forecast-num').inner_text(),'Avventer prognose')
        self.assertIn('Mer enn 14',self.page.locator('#rbk-forecast-note').inner_text())
        self.assertIn('Avslått',self.page.locator('#rbk-auto-next').inner_text())

    def test_busy_lock_preserves_input(self):
        panel_show(self.page,self.payload())
        self.page.locator('details summary').click()
        self.page.locator('#rbk-locked-input').fill('A')
        panel_show(self.page,self.payload(busy=True))
        self.assertEqual(self.page.locator('#rbk-locked-input').input_value(),'A')
        self.assertTrue(self.page.locator('[data-action="new_scan"]').is_disabled())

if __name__=='__main__':unittest.main()