"""Non-live synthetic chart preview. Not included in user history."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
from analytics import create_chart_html
root=Path(__file__).resolve().parent
out=root/'forhandsvisning';out.mkdir(exist_ok=True)
base=datetime(2026,11,24,9,tzinfo=timezone.utc)
samples=[5000,4930,4880,4812,4778,4720,4641,4583,4548,4434]
rows=[{'time_utc':(base+timedelta(hours=i*3)).isoformat(),
       'available_seated':v,'locked_fields':[],'standing_availability':'unknown','total':21423}
      for i,v in enumerate(samples)]
doc=create_chart_html(rows,'DEMO: Rosenborg – Molde','28.11.2026 kl. 18:00','DEMO')
doc=doc.replace('LERKENDAL · UTVIKLING I LEDIGE PLASSER','DEMONSTRASJON · SYNTETISKE MÅLINGER · IKKE FAKTISKE RBK-TALL')
(out/'DEMO_historikk_og_prognose.html').write_text(doc,encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1250,'height':900},device_scale_factor=1)
    page.set_content(doc,wait_until='load')
    page.screenshot(path=str(out/'DEMO_historikk_og_prognose.png'),full_page=True)
    browser.close()
print(out/'DEMO_historikk_og_prognose.png')