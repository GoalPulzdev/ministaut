"""Public-facing RBK match availability summaries.

Private section-scanner diagnostics remain in resultat.json. The public design
shows only match, overall availability and change since the preceding complete
measurement of that exact checkout event. It never claims official ticket sales.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from urllib.parse import urlparse

TOTAL_PLACES = 21423  # Stadion total oppgitt av bruker (sitte- og staaomraader).
EXPECTED_SEATED_MAP = 19015  # Bevisst intern kontroll; ikke vist i delbar grafikk.
KNOWN_EVENTS = {
    '6a9a7e3f3f93920b289b0675': ('Rosenborg – Molde', '28.11.2026 kl. 18:00'),
    '6a9a7c2b15599587216e21f3': ('Rosenborg – Start', '07.11.2026 kl. 18:00'),
}


def event_key(url: str) -> str:
    parsed = urlparse(url)
    match = re.fullmatch(r'/checkout/([A-Za-z0-9_-]{8,100})/?', parsed.path)
    if parsed.hostname != 'billett.rbk.no' or parsed.scheme != 'https' or not match:
        raise ValueError('Ugyldig RBK checkout-URL')
    return match.group(1)


def parse_match_header(text: str) -> tuple[str, str] | None:
    # Typical RBK header: Rosenborg-Molde 28.11.2026 18:00
    m = re.search(r'\b(Rosenborg|RBK)\s*[-–]\s*([\wÀ-ž. -]{2,50}?)\s+'
                  r'(\d{2}[./]\d{2}[./]\d{4})\s+(\d{1,2}:\d{2})', text or '', re.IGNORECASE)
    if not m:
        return None
    home = 'Rosenborg' if m.group(1).upper() == 'RBK' else m.group(1).strip().title()
    away = m.group(2).strip().title()
    if len(away) > 35:
        return None
    return f'{home} – {away}', f'{m.group(3)} kl. {m.group(4)}'


def event_labels(url: str, header_text: str = '') -> tuple[str, str]:
    return parse_match_header(header_text) or KNOWN_EVENTS.get(event_key(url), ('Rosenborg – Kampstatus', ''))


def validate_complete(result: dict, total: int = TOTAL_PLACES) -> tuple[bool, str]:
    """All fixed seats must be explained by either a read tooltip or a CONFIRMED lock."""
    # Only the separate, fixed seat reference is authoritative for identifying
    # the complete stadium. No guessed zeroes and no pretending hidden seats sold.
    from match_config import SEATS, TOTAL_SEATED, normalize_locked
    if result.get('mode') != 'final':
        return False, 'Skanningen er ikke endelig lagret.'
    if result.get('expected_fields') != len(SEATS):
        return False, 'Forventet 60 faste sittefelt.'
    try:
        raw = result.get('locked_fields', [])
        locked = normalize_locked(raw)
    except ValueError as e:
        return False, str(e)
    if locked and result.get('locked_fields_confirmed') is not True:
        return False, 'Bortefelt må bekreftes eksplisitt per kamp.'
    if locked and result.get('map_structure_verified') is not True:
        return False, 'Ingen verifisert kartstruktur for gjenværende aktive felt.'
    if result.get('missing_fields') or result.get('conflicts'):
        return False, 'Uavklarte eller motstridende felt. Publisering blokkert.'
    if result.get('map_structure_verified') is False:
        return False, 'Kartstrukturen er ikke verifisert mot fast stadionmodell.'
    fields = result.get('confirmed_fields', [])
    observed = [f.get('section') for f in fields if isinstance(f,dict)]
    if len(observed)!=len(fields) or len(set(observed))!=len(observed):
        return False, 'Uentydig feltliste.'
    if set(observed) & set(locked):
        return False, 'Samme felt kan ikke både være avlest og bekreftet låst.'
    if set(observed) | set(locked) != set(SEATS):
        return False, 'Ikke full kontroll over 60 felt: '+', '.join(sorted(set(SEATS)-(set(observed)|set(locked))))
    if result.get('captured_fields')!=len(fields):
        return False, 'Antall avleste felt stemmer ikke.'
    if result.get('covered_fields',len(fields)+len(locked))!=len(SEATS):
        return False, 'Feltdekningen er ikke komplett.'
    if any(not isinstance(f.get('free'),int) or isinstance(f.get('free'),bool) or
           f.get('capacity')!=SEATS[f['section']] or
           not 0<=f['free']<=SEATS[f['section']] or
           f.get('min_free',f['free'])!=f.get('max_free',f['free'])
           for f in fields):
        return False, 'Ugyldig eller varierende kapasitet/ledighet i sittefelt.'
    if result.get('capacity_verified_fields')!=sum(SEATS[n] for n in observed):
        return False, 'Avlest kapasitet stemmer ikke med faste felter.'
    cap=result.get('map_field_capacities',{})
    if not isinstance(cap,dict) or set(cap)!=set(SEATS) or any(cap[n]!=SEATS[n] for n in SEATS):
        return False, 'Kartkapasitet samsvarer ikke med fast stadionmodell.'
    if sum(cap.values())!=TOTAL_SEATED:
        return False, 'Avvik i sittekapasitet.'
    free=result.get('free_confirmed_fields')
    if not isinstance(free,int) or isinstance(free,bool) or free!=sum(f['free'] for f in fields) or not 0<=free<=total:
        return False, 'Ledige plasser kan ikke avstemmes.'
    return True, ''


def snapshot_from_result(result: dict, title: str, match_date: str,
                         total: int = TOTAL_PLACES, source: str = 'scan') -> dict:
    from match_config import SEATS, normalize_locked
    ok, reason = validate_complete(result, total)
    if not ok:raise ValueError(reason)
    date = datetime.fromisoformat(result['time_utc'].replace('Z','+00:00'))
    if date.utcoffset() is None:
        raise ValueError('Ugyldig tidssone i måling')
    available = result['free_confirmed_fields']
    locked = normalize_locked(result.get('locked_fields', []))
    return {
        'event_key':event_key(result['url']),
        'title':title, 'match_date':match_date,
        'time_utc':date.astimezone(timezone.utc).isoformat(timespec='seconds'),
        'total':total,
        'available_seated':available,
        'confirmed_available_for_purchase':available,
        'calculated_unavailable':total-available,
        'estimated_sold':total-available,
        'locked_fields':locked,
        'locked_capacity':sum(SEATS[x] for x in locked),
        'standing_availability':'unknown',
        'section_free':{f['section']:f['free'] for f in result['confirmed_fields']},
        'source':source,
        'note': 'Estimert solgte = fast totalkapasitet minus dokumentert tilgjengelige plasser. Dette er ikke faktiske salgstall.'
    }


def history_file(root: Path, key: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key):
        raise ValueError('Ugyldig hendelsesnøkkel')
    return Path(root) / (key + '.json')


def load_history(root: Path, key: str) -> list[dict]:
    path = history_file(root, key)
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    return sorted([d for d in data if d.get('event_key') == key], key=lambda x: x['time_utc'])


def store_snapshot(root: Path, record: dict) -> tuple[list[dict], dict | None]:
    """Store only complete, time-stamped measurements. Idempotent on reruns."""
    path = history_file(root, record['event_key'])
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_records = load_history(root, record['event_key'])
    earlier = [r for r in previous_records if r['time_utc'] < record['time_utc']]
    previous = earlier[-1] if earlier else None
    updated = [r for r in previous_records if r['time_utc'] != record['time_utc']]
    updated.append(record)
    updated.sort(key=lambda r: r['time_utc'])
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)
    return updated, previous


def compatible_previous(previous: dict | None, current: dict) -> bool:
    """Never equate newly closed/opened inventory with sales movement."""
    return bool(previous and previous.get('total')==current['total'] and
                sorted(previous.get('locked_fields',[]))==sorted(current.get('locked_fields',[])) and
                previous.get('standing_availability','unknown')==current.get('standing_availability','unknown'))


def large_change(previous: dict | None, current: dict, threshold: int = 1000) -> tuple[bool, int]:
    if not compatible_previous(previous,current):return False,0
    delta=previous['available_seated']-current['available_seated']
    return abs(delta)>threshold,delta


def fmt(v: int) -> str:
    return f'{v:,}'.replace(',', ' ')


def local_time(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    try:
        from zoneinfo import ZoneInfo
        dt = dt.astimezone(ZoneInfo('Europe/Oslo'))
    except Exception:
        dt = dt.astimezone()
    months = ['jan.', 'feb.', 'mars', 'apr.', 'mai', 'juni', 'juli', 'aug.', 'sep.', 'okt.', 'nov.', 'des.']
    return f'{dt.day}. {months[dt.month-1]} {dt.year} kl. {dt:%H:%M}'


def relative_interval(older: str, newer: str) -> str:
    a = datetime.fromisoformat(older.replace('Z', '+00:00'))
    b = datetime.fromisoformat(newer.replace('Z', '+00:00'))
    minutes = max(0, round((b-a).total_seconds()/60))
    if minutes < 90:
        return f'{minutes} min'
    if minutes >= 48*60:
        days, remainder = divmod(minutes, 24*60)
        return f'{days} døgn' if remainder < 60 else f'{days} døgn {remainder//60} t'
    hours = minutes // 60
    return f'{hours} t' if minutes % 60 == 0 else f'{hours} t {minutes%60} min'


def sparkline(records: list[dict], current: dict) -> str:
    selected = [r for r in records if r['time_utc'] <= current['time_utc'] and (r is current or compatible_previous(r,current))][-14:]
    if len(selected) < 2:
        return '<path d="M0 52 H800" stroke="#37644E" stroke-width="3" stroke-dasharray="12 14" fill="none"/>'
    vals = [r['calculated_unavailable'] for r in selected]
    lo, hi = min(vals), max(vals)
    spread = max(4, hi - lo)
    points = [(round(i*800/(len(vals)-1)),round(98-(v-lo)*76/spread)) for i,v in enumerate(vals)]
    path = ' '.join((('M' if i==0 else 'L') + f'{x},{y}') for i,(x,y) in enumerate(points))
    area = path + ' L800,118 L0,118 Z'
    dots = ''.join(f'<circle cx="{x}" cy="{y}" r="{7 if i == len(points)-1 else 4}" fill="{ "#5af3b3" if i == len(points)-1 else "#438e72" }"/>' for i,(x,y) in enumerate(points))
    return (f'<path d="{area}" fill="url(#areaFill)"/>'
            f'<path d="{path}" stroke="#5af3b3" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>{dots}')


# A self-contained vector-like stadium graphic. No logos, photos or external assets.
PITCH = '''<svg class="stadium-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 200" aria-hidden="true">
<defs><linearGradient id="turf" x1="0" x2="1"><stop stop-color="#082e25"/><stop offset=".5" stop-color="#11634b"/><stop offset="1" stop-color="#062920"/></linearGradient>
<linearGradient id="stand" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#285848"/><stop offset="1" stop-color="#122e27"/></linearGradient></defs>
<ellipse cx="460" cy="103" rx="426" ry="95" fill="#122c25" stroke="#448166" stroke-width="2"/>
<ellipse cx="460" cy="103" rx="409" ry="85" fill="none" stroke="#244b3c" stroke-width="14" stroke-dasharray="21 5"/>
<ellipse cx="460" cy="103" rx="375" ry="73" fill="url(#stand)" stroke="#355749" stroke-width="6"/>
<rect x="214" y="41" width="493" height="125" rx="4" fill="url(#turf)" stroke="#d7e9dd" stroke-width="3"/>
<path d="M245 43 V164 M308 43 V164 M371 43 V164 M434 43 V164 M497 43 V164 M560 43 V164 M623 43 V164 M686 43 V164" stroke="#1f7759" stroke-width="28" opacity=".25"/>
<g stroke="#d7f6e6" fill="none" stroke-width="2" opacity=".84"><rect x="229" y="54" width="463" height="100"/><path d="M460 54 V154"/><ellipse cx="460" cy="104" rx="38" ry="37"/><path d="M229 75 H272 V132 H229 M692 75 H649 V132 H692"/></g>
<g stroke="#5ae0a9" fill="none" opacity=".6"><path d="M96 103 h84 M739 103 h83" stroke-width="3"/></g>
</svg>'''

BASE_STYLE = r'''
*{box-sizing:border-box}html,body{margin:0;padding:0;background:#06130f;color:#fff;font-family:Inter,Segoe UI,Arial,sans-serif}
.poster{position:relative;width:1080px;height:1350px;overflow:hidden;padding:64px 68px 42px;display:flex;flex-direction:column;gap:20px;background:radial-gradient(ellipse 690px 390px at 95% 6%,#164635 0%,transparent 65%),radial-gradient(ellipse 710px 520px at 1% 80%,#0c3729 0%,transparent 70%),linear-gradient(164deg,#030b0a 0%,#061813 54%,#020a09 100%)}
.poster:before{content:'';position:absolute;inset:0;opacity:.14;pointer-events:none;background-image:linear-gradient(to right,transparent 98%,#63c995 99%),linear-gradient(to bottom,transparent 98%,#63c995 99%);background-size:48px 48px}
.poster:after{content:'';position:absolute;top:-340px;right:-210px;width:600px;height:600px;border:1px solid #34684c;border-radius:50%;box-shadow:0 0 0 60px #1c4b3520,0 0 0 145px #1b453020;pointer-events:none}
.poster>*{position:relative;z-index:1;flex-shrink:0}
.headline{height:172px;display:flex;flex-direction:column;justify-content:space-between}
.eyebrow{font-size:23px;color:#5ff1ad;font-weight:800;letter-spacing:5px;text-transform:uppercase;display:flex;align-items:center;gap:18px}
.eyebrow:before{content:'';width:11px;height:11px;border-radius:50%;background:#62f6b7;box-shadow:0 0 18px #35e19a}
.title{font-size:76px;line-height:1.03;letter-spacing:-3.4px;font-weight:850;white-space:nowrap}
.match-meta{font-size:25px;color:#b4d3c5;letter-spacing:.6px;display:flex;align-items:center;justify-content:space-between}
.update{font-size:22px;color:#8fae9d}
.primary-card{height:324px;padding:35px 42px;border-radius:28px;border:1px solid #307e58;background:linear-gradient(125deg,#164833d9,#0a261dcc 66%,#071710e8);box-shadow:inset 0 1px 0 #6cf2af2b,0 24px 55px #0004}
.kicker{font-size:23px;letter-spacing:2px;font-weight:800;color:#abdbbf;text-transform:uppercase}
.primary-num{font-size:140px;letter-spacing:-7px;font-weight:850;line-height:1.2;margin-top:3px;color:#f2fff9;font-variant-numeric:tabular-nums}
.micro{color:#b2cbbd;font-size:20px;line-height:1.35}
.progress{margin-top:19px;height:14px;border-radius:8px;background:#305444;overflow:hidden;position:relative}
.progress>.fill{display:block;height:100%;border-radius:8px;background:linear-gradient(90deg,#20aa77,#59f9ad);width:var(--pct)}
.progress-copy{display:flex;justify-content:space-between;color:#a7cbb8;font-size:18px;margin-top:8px}
.side-grid{height:164px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.small-card{padding:28px 31px;border-radius:23px;background:#0a221ae8;border:1px solid #24533f;box-shadow:inset 0 1px 0 #ffffff0c}
.small-card .kicker{font-size:18px;color:#80bd9f;letter-spacing:2px}
.small-num{font-size:65px;letter-spacing:-3px;line-height:1.15;margin-top:15px;font-weight:800;font-variant-numeric:tabular-nums}
.trend-card{height:177px;padding:23px 30px 20px;border-radius:23px;border:1px solid #2e684d;background:linear-gradient(120deg,#112e24ed,#0a241bdb)}
.trend-top{display:flex;align-items:center;justify-content:space-between}
.trend-title{font-size:22px;font-weight:800;color:#b3dcc5;letter-spacing:1px;text-transform:uppercase}
.trend-value{font-size:64px;font-weight:850;letter-spacing:-1px;color:#62f0ad}
.trend-desc{font-size:18px;color:#b7d3c4}
.spark{height:85px;width:100%;overflow:visible;margin-top:3px}
.stadium-card{height:177px;border-radius:23px;border:1px solid #25503c;background:linear-gradient(0deg,#061b16b8,#13382994);overflow:hidden;position:relative}
.stadium-header{position:absolute;z-index:2;top:18px;left:29px;color:#9fd3b6;font-size:17px;letter-spacing:2.5px;font-weight:800}
.stadium-svg{width:100%;height:100%;margin:5px 0 0}
.footer{font-size:19px;line-height:1.5;color:#b1c9b9;display:flex;align-items:center;min-height:66px;border-top:1px solid #31604a;padding-top:14px}
.footer b{color:#d7efe0}
.story{height:1920px;padding:91px 70px 88px;gap:32px}
.story .headline{height:260px}.story .title{font-size:80px}.story .match-meta{font-size:28px}
.story .primary-card{height:380px;padding:60px 43px}.story .primary-num{font-size:154px;margin-top:18px}.story .progress{margin-top:32px}
.story .side-grid{height:213px}.story .small-card{padding:48px 35px}.story .small-num{font-size:70px}
.story .trend-card{height:280px;padding:37px 35px}.story .spark{height:145px}
.story .stadium-card{height:336px}.story .stadium-svg{height:95%;margin-top:12px}.story .stadium-header{top:35px;font-size:20px}
.story .footer{font-size:23px;line-height:1.45;min-height:150px;align-items:flex-start;padding-top:32px}
'''


def render_html(record: dict, previous: dict | None, records: list[dict], story: bool = False) -> str:
    sold = record['calculated_unavailable']; available = record['available_seated'];total=record['total']
    rate=round(100*sold/total,1)
    if previous:
        delta = sold - previous['calculated_unavailable']
        delta_display = ('+' if delta>=0 else '−') + fmt(abs(delta))
        sign_text = 'flere' if delta>=0 else 'færre'
        interval = relative_interval(previous['time_utc'],record['time_utc'])
        desc = f'{sign_text} utilgjengelige siden forrige måling ({interval})'
    else:
        delta_display='—';desc='Første komplette måling for denne kampen'
    note = ('* Beregnet som fast totalkapasitet minus avleste ledige sitteplasser. '
            'Kan inkludere reserverte, stengte bortefelt og ståplasser uten separat ledighetstall. '
            'Ikke et offisielt salgstall.')
    title=html.escape(record['title']);date=html.escape(record['match_date'])
    local=html.escape(local_time(record['time_utc']))
    placeholders = {
        'mode': 'story' if story else 'feed',
        'title': title, 'date': date, 'updated': local,
        'sold': fmt(sold), 'available':fmt(available),'total':fmt(total),
        'pct':f'{rate:.1f}', 'delta':delta_display,'desc':html.escape(desc),
        'spark':sparkline(records,record),'pitch':PITCH,'note':html.escape(note),
        'style':BASE_STYLE
    }
    doc=r'''<!doctype html><html lang="no"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Billettstatus – $title</title>
<style>$style</style></head><body><article class="poster $mode">
<section class="headline">
  <div class="eyebrow">LERKENDAL · BILLETTSTATUS</div>
  <div class="title">$title</div>
  <div class="match-meta"><span>$date</span><span class="update">Oppdatert $updated</span></div>
</section>
<section class="primary-card">
  <div class="kicker">Estimert solgte *</div>
  <div class="primary-num">$sold</div>
  <div class="progress" style="--pct:$pct%"><span class="fill"></span></div>
  <div class="progress-copy"><span>$pct % av total kapasitet</span><span>Beregnet andel</span></div>
</section>
<section class="side-grid">
  <div class="small-card"><div class="kicker">Bekreftet ledige sitteplasser</div><div class="small-num">$available</div></div>
  <div class="small-card"><div class="kicker">Total kapasitet</div><div class="small-num">$total</div></div>
</section>
<section class="trend-card">
  <div class="trend-top"><div><div class="trend-title">Endring siden sist</div><div class="trend-desc">$desc</div></div>
     <div class="trend-value">$delta</div></div>
  <svg class="spark" viewBox="0 0 800 124" preserveAspectRatio="none" aria-label="Utvikling i beregnet antall ikke ledige">
    <defs><linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#52e6a6" stop-opacity=".23"/><stop offset="1" stop-color="#52e6a6" stop-opacity="0"/></linearGradient></defs>
    $spark
  </svg>
</section>
<section class="stadium-card"><div class="stadium-header">KAMPDAG PÅ LERKENDAL</div>$pitch</section>
<div class="footer"><span><b>Estimat.</b> $note</span></div>
</article></body></html>'''
    return Template(doc).substitute(placeholders)


def screenshot_post(browser, html_doc: str, filename: Path, story: bool = False) -> None:
    width, height=1080,(1920 if story else 1350)
    context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1,
                                color_scheme='dark',accept_downloads=False)
    try:
        page=context.new_page()
        page.set_content(html_doc,wait_until='load',timeout=15000)
        page.screenshot(path=str(filename),full_page=False,animations='disabled',timeout=20000)
    finally:
        context.close()


def publish(result: dict, out: Path, history_dir: Path, browser=None,
            header_text: str = '', source: str = 'scan',
            approve_large_change: bool = False) -> dict:
    ok, reason = validate_complete(result)
    if not ok:
        return {'published':False,'reason':reason,'files':[]}
    title,match_date = event_labels(result['url'],header_text)
    record=snapshot_from_result(result,title,match_date,source=source)
    earlier=[r for r in load_history(history_dir,record['event_key']) if r['time_utc']<record['time_utc']]
    latest=earlier[-1] if earlier else None
    same_scope=compatible_previous(latest,record)
    previous=latest if same_scope else None
    alert,delta=large_change(previous,record)
    out.mkdir(parents=True,exist_ok=True)
    if alert and not approve_large_change:
        details={'type':'stor_endring','reason':'Krever manuell kontroll før ny måling publiseres eller legges i historikk.',
                 'change_estimated_sold':delta,'previous':previous['time_utc'],'current':record['time_utc'],
                 'threshold_seats':1000,'note':'Kan være nye billettkvoter, reservasjoner eller annet enn salg.'}
        (out/'kvalitetsvarsel_v18.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
        return {'published':False,'reason':f'Uvanlig endring ({delta:+} plasser). Se kvalitetsvarsel_v18.json.',
                'files':[str(out/'kvalitetsvarsel_v18.json')]}
    history,_=store_snapshot(history_dir,record)
    paths=[]
    for story,suffix in ((False,'4x5'),(True,'story_9x16')):
        doc=render_html(record,previous,history,story)
        html_path=out/f'delbar_status_{suffix}.html'
        html_path.write_text(doc,encoding='utf-8')
        paths.append(str(html_path))
        if browser is not None:
            filename=out/f'delbar_status_{suffix}.png'
            try:
                screenshot_post(browser,doc,filename,story)
                paths.append(str(filename))
            except Exception as ex:
                print('Bildet kunne ikke rendres, men HTML er lagret:',type(ex).__name__,str(ex)[:130])
    public={
        'match':title,'match_date':match_date,'updated':local_time(record['time_utc']),
        'total':record['total'],'available':record['available_seated'],
        'estimated_sold':record['estimated_sold'],
        'calculated_unavailable':record['calculated_unavailable'],
        'delta_since_previous':None if not previous else record['estimated_sold']-previous['estimated_sold'] if 'estimated_sold' in previous else record['calculated_unavailable']-previous['calculated_unavailable'],
        'previous_timestamp':previous['time_utc'] if previous else None,
        'comparison_scope_changed':bool(latest and not same_scope),
        'estimated_not_official':True,
        'scope_note':'Bekreftet ledige = avlest tilgjengelig i åpne sittefelt. Ståplasser ikke medregnet som ledige.',
        'assumptions':'Bekreftet låste bortefelt regnes ikke som tilgjengelige. Estimatet kan ikke brukes som offisielt solgt antall.'
    }
    public_json=out/'deling_status.json'
    public_json.write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8')
    paths.append(str(public_json))
    return {'published':True,'reason':'','files':paths,'previous':previous,'record':record}