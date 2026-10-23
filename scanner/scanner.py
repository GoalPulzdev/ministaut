"""RBK–Molde public seat map: read-only browser hover scanner.

The scanner NEVER clicks on or reserves a seat, never submits a form, and
never estimates the number sold from the unavailable count. It reads the
free/total values displayed to normal visitors in section tooltips.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
from datetime import datetime
from time import monotonic
from urllib.parse import urlparse, unquote

from parser import Counts, Observation, parse_tooltip
from report import write_report
from strategies import stadium_roi, reference_points, scan_grid, missing_fields
from verification import parse_visible_texts
from hover_sampler import HoverTransitionSampler
from network_inspector import capture as capture_public_schema

DEFAULT_URL = 'https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675'
ROOT = Path(__file__).resolve().parent

# Intentionally only reads visibly rendered text. No authenticated/private APIs.
EXTRACT_TEXT_JS = r"""() => {
  const re = /(free\s+seats?|available\s+seats?|ledige\s+(?:seter|plasser|billetter)|tilgjengelige\s+(?:seter|plasser))/i;
  const selectors = ['[role="tooltip"]','[class*="tooltip" i]','[class*="popover" i]',
    '[id*="tooltip" i]', '[id*="popover" i]', '[class*="hover" i]'];
  const all = [];
  const seen = new Set();
  for (const selector of selectors) {
    for (const el of document.querySelectorAll(selector)) {
      if (seen.has(el)) continue;
      seen.add(el);
      const style = window.getComputedStyle(el);
      if (!style || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
      const r = el.getBoundingClientRect();
      if (r.width < 4 || r.height < 4) continue;
      const t = (el.innerText || '').trim();
      if (t && t.length < 2000 && re.test(t)) all.push(t);
    }
  }
  if (all.length) return all;
  const body = document.body?.innerText || '';
  if (!re.test(body)) return [];
  // Recover section lines around any visible availability label. The parser
  // further validates section + free/total pair and rejects implausible data.
  const terms = [...body.matchAll(/free\s+seats?|available\s+seats?|ledige\s+(?:seter|plasser|billetter)|tilgjengelige\s+(?:seter|plasser)/ig)];
  return terms.slice(-4).map(m => body.slice(Math.max(0,m.index-160),Math.min(body.length,m.index+100)));
}"""

# Collect vector shapes as candidate hover points. No event generation here.
SVG_POINTS_JS = r"""() => {
  const shapes = document.querySelectorAll('svg path,svg polygon,svg rect,svg ellipse,svg circle,svg polyline');
  let points = [];
  for (const el of shapes) {
    const r = el.getBoundingClientRect();
    if (r.width < 9 || r.height < 9 || r.width > 620 || r.height > 620) continue;
    if (r.bottom < 0 || r.right < 0 || r.top > innerHeight || r.left > innerWidth) continue;
    const s = getComputedStyle(el);
    if (s.display==='none' || s.visibility==='hidden' || s.pointerEvents==='none') continue;
    const priority = s.cursor === 'pointer' ? 2 : 1;
    const xx = [0.5]; const yy = [0.5];
    // Irregular polygons may have an empty center.
    if (r.width >= 70 && r.height >= 25) {xx.push(0.3,0.7); yy.push(0.45,0.55)}
    for (let i=0; i<xx.length; i++) {
      points.push([Math.round(r.left+r.width*xx[i]),Math.round(r.top+r.height*yy[i]),priority]);
    }
  }
  return points.slice(0,9000);
}"""

MAP_RECTS_JS = r"""() => {
  const elements = [...document.querySelectorAll('svg,canvas,[id*="seatmap" i],[class*="seatmap" i],[id*="seat-map" i],[class*="seat-map" i]')];
  return elements.map(e=>{
    const r=e.getBoundingClientRect();return {x:r.left,y:r.top,w:r.width,h:r.height,tag:e.tagName.toLowerCase()}
  }).filter(r=>r.w>320&&r.h>220&&r.w<5000&&r.h<4000).slice(0,30);
}"""


def frame_transform(frame):
    """Map iframe viewport coordinates into the top-level browser viewport.

    In particular, CSS zoom on the top document scales the iframe element,
    but coordinates returned from inside the iframe remain in its own CSS
    pixels. Adding the iframe offset without scaling would hover wrong fields.
    """
    if frame.parent_frame is None:
        return 0.0, 0.0, 1.0, 1.0
    try:
        element = frame.frame_element()
        box = element.bounding_box()
        if box:
            inner = frame.evaluate('({w:window.innerWidth,h:window.innerHeight})')
            sx = box['width'] / max(1, inner['w'])
            sy = box['height'] / max(1, inner['h'])
            return box['x'], box['y'], sx, sy
    except Exception:
        pass
    return 0.0, 0.0, 1.0, 1.0


def map_bounds(page):
    """Find the likely entire map WITHOUT clipping it to the viewport."""
    W = (page.viewport_size or {'width': 1600})['width']
    candidates = []
    for frame in page.frames:
        dx, dy, sx, sy = frame_transform(frame)
        try:
            for r in frame.evaluate(MAP_RECTS_JS):
                x, y, w, h = dx + r['x'] * sx, dy + r['y'] * sy, r['w'] * sx, r['h'] * sy
                # Exclude sidebar graphics and objects way below the actual map.
                if x >= W * .80 or y > 1400 or w < 280 or h < 180:
                    continue
                # Prefer large stadium drawings (including inside iframes).
                candidates.append((w * h, {'x': x, 'y': y, 'w': w, 'h': h,
                                            'right': x + w, 'bottom': y + h,
                                            'frame': 'main' if frame.parent_frame is None else 'iframe'}))
        except Exception:
            continue
    return max(candidates, key=lambda pair: pair[0])[1] if candidates else None


def configure_visible_map(page, zoom: float, do_fit: bool = True):
    """Shrink the checkout page until the entire map is visible if possible.

    This only changes local rendering, never ticket availability, seats, or
    page requests. User can override with --zoom or disable via --no-auto-fit.
    """
    viewport = page.viewport_size or {'width': 1600, 'height': 900}
    W, H = viewport['width'], viewport['height']
    initial = min(1.0, max(.45, float(zoom)))
    candidates = [initial]
    if do_fit:
        candidates += [z for z in (0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45)
                       if z < initial - .001]
    result = {'requested_zoom': initial, 'applied_zoom': initial,
              'viewport': [W, H], 'map_bounds': None, 'fits_viewport': None,
              'map_detected': False}
    for index, factor in enumerate(candidates):
        page.evaluate('''(value) => {
            document.documentElement.style.zoom = String(value);
            window.scrollTo(0, 0);
        }''', factor)
        page.wait_for_timeout(180 if index else 400)
        rect = map_bounds(page)
        result['applied_zoom'] = factor
        if rect is None:
            continue
        result['map_detected'] = True
        result['map_bounds'] = {k: round(v, 1) if isinstance(v, float) else v
                                for k, v in rect.items()}
        result['fits_viewport'] = (rect['bottom'] <= H - 10 and rect['right'] <= W - 10
                                   and rect['y'] >= 0 and rect['x'] >= -12)
        if result['fits_viewport'] or not do_fit:
            break
    return result


def valid_target_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme == 'https' and parsed.hostname == 'billett.rbk.no':
        return True
    # This option is for self-contained offline tests.
    if parsed.scheme == 'file':
        return True
    return False


def read_text(page):
    values = []
    for frame in page.frames:
        try:
            values.extend(frame.evaluate(EXTRACT_TEXT_JS))
        except Exception:
            pass  # Frames can appear/disappear while the site is updating.
    return values


def choose_map_region(page):
    """Prefer the largest SVG/canvas in the left checkout area; else left panel."""
    viewport = page.viewport_size or {'width': 1600, 'height': 960}
    W, H = viewport['width'], viewport['height']
    possible = []
    for frame in page.frames:
        dx, dy, sx, sy = frame_transform(frame)
        try:
            rects = frame.evaluate(MAP_RECTS_JS)
            for r in rects:
                x, y = r['x'] * sx + dx, r['y'] * sy + dy
                w, h = r['w'] * sx, r['h'] * sy
                clipped = (max(5,x), max(70,y), min(W-10,x+w), min(H-10,y+h))
                x1,y1,x2,y2 = clipped
                if x2-x1 < 300 or y2-y1 < 200:
                    continue
                # Avoid the payment/checkout sidebar.
                if x1 > W*0.72: continue
                area = (x2-x1) * (y2-y1)
                possible.append((area, (x1,y1,x2,y2)))
        except Exception:
            continue
    if possible:
        return max(possible, key=lambda p:p[0])[1], 'svg/canvas'
    return (20, 120, round(W*0.68), H-20), 'fallback-left-pane'


def collect_dom_points(page, region):
    vp = page.viewport_size or {'width': 1600, 'height': 960}
    W, H = vp['width'], vp['height']
    x1,y1,x2,y2 = region
    points = []
    for frame in page.frames:
        dx, dy, sx, sy = frame_transform(frame)
        try:
            for x,y,priority in frame.evaluate(SVG_POINTS_JS):
                x = round(x*sx+dx)
                y = round(y*sy+dy)
                if (x1 <= x <= x2 and y1 <= y <= y2 and 5 <= x < W-5 and 5 <= y < H-5):
                    points.append((x, y, priority))
        except Exception:
            pass
    points.sort(key=lambda p: (-p[2], p[1], p[0]))
    result = []
    used = set()
    for x,y,p in points:
        key = (round(x/8),round(y/8))
        if key not in used:
            used.add(key)
            result.append((x,y))
    return result


def grid_points(region, step: int):
    x1,y1,x2,y2 = region
    # Serpentine reduces mouse travel and crossing multiple sections fast.
    rows = []
    y = math.ceil((y1+5)/step)*step
    while y <= y2-5:
        xs = range(math.ceil((x1+5)/step)*step, int(x2-5), step)
        row = [(x,y) for x in xs]
        if len(rows)%2:
            row.reverse()
        rows.append(row)
        y += step
    return [p for row in rows for p in row]


def observe_hits(counts, hits):
    """Register confirmed visible data; never infer from coordinates alone."""
    updates = 0
    for hit in hits:
        earlier = counts._groups.get(hit.section, [])
        if any(row['free'] == hit.free and row['capacity'] == hit.capacity for row in earlier):
            continue
        state = counts.add(hit)
        if state == 'new':
            print(f'  + Felt {hit.section:4} | Ledig {hit.free:>5} / {hit.capacity:<5} | Inngang {hit.gate or "?"}', flush=True)
            updates += 1
        elif state == 'variable':
            print(f'  ~ Felt {hit.section}: liten endring i ledige plasser (lagres som intervall)', flush=True)
        elif state == 'conflict':
            print(f'  ! Større avvik for felt {hit.section}; blir ekskludert inntil kontroll', flush=True)
    return updates


def reference_sections(path):
    if not path or not Path(path).is_file(): return set()
    result = set()
    with Path(path).open(encoding='utf-8-sig',newline='') as input_file:
        for row in csv.DictReader(input_file):
            name=(row.get('section') or row.get('felt') or '').upper().strip()
            if name: result.add(name)
    return result


def capture_assisted(page, counts, seconds=1200, source='assisted', expected=None):
    """Watch a human-operated cursor. Require two consecutive stable reads."""
    expected = expected or set()
    print('Før musepekeren sakte over de manglende feltene (ca. 1 sekund per felt).')
    print('Trykk ENTER i dette kommandovinduet for å avslutte og lagre rapporten.')
    stopped = threading.Event()
    def wait_for_enter():
        try: input()
        except EOFError: pass
        stopped.set()
    threading.Thread(target=wait_for_enter,daemon=True).start()
    last_values=set()
    start=monotonic()
    while not stopped.is_set() and monotonic()-start<seconds:
        hits=parse_visible_texts(read_text(page),source,-1,-1)
        current={(h.section,h.free,h.capacity) for h in hits}
        for hit in hits:
            if (hit.section,hit.free,hit.capacity) not in last_values:
                continue
            observe_existing=counts._groups.get(hit.section,[])
            if any(v['free']==hit.free and v['capacity']==hit.capacity for v in observe_existing):
                continue
            outcome=counts.add(hit)
            if outcome=='new':print(f'  + Manuelt felt {hit.section}: {hit.free}/{hit.capacity}',flush=True)
            elif outcome=='variable':print(f'  ~ Manuelt felt {hit.section}: endret til {hit.free}/{hit.capacity}',flush=True)
            elif outcome=='conflict':print(f'  ! Manuelt felt {hit.section}: større avvik',flush=True)
        last_values=current
        page.wait_for_timeout(260)
        if expected and not missing_fields(expected,counts._groups):
            print('Alle feltene i referanselisten er observert. Avslutter manuell kontroll.')
            break
    return round(monotonic()-start)

def create_output_dir(output_root: Path, mode: str) -> Path:
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = output_root / f'{stamp}_{mode}'
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def record_network_metadata(page, diagnostics):
    seen=set()
    def handle(response):
        try:
            parsed=urlparse(response.url)
            if response.request.method!='GET': return
            if not (parsed.hostname and (parsed.hostname.endswith('.vivenu.com') or parsed.hostname=='billett.rbk.no')):return
            if not re.search(r'/api/|seatmap',parsed.path,re.I):return
            entry=f'{parsed.hostname}{parsed.path}'
            if entry not in seen:
                seen.add(entry)
                diagnostics['network_paths'].append({'path':entry[:220],'status':response.status})
            # Schema-only inspection of already-loaded PUBLIC map/status/resources.
            # Do not store or transmit the response body.
            capture_public_schema(response,diagnostics)
        except Exception:
            pass
    page.on('response',handle)

def open_browser(playwright, args):
    """Use installed Microsoft Edge on Windows, without touching Edge's user profile."""
    browser_choice = args.browser
    if browser_choice == 'auto':
        browser_choice = 'edge' if sys.platform.startswith('win') else 'chromium'
    opts = {'headless': args.headless}
    if args.chrome_path:
        opts['executable_path'] = args.chrome_path
        browser_choice = 'custom'
    elif browser_choice == 'edge':
        # This launches the REAL installed Edge, not Playwright Chromium.
        opts['channel'] = 'msedge'
    elif browser_choice == 'chrome':
        opts['channel'] = 'chrome'
    elif browser_choice != 'chromium':
        raise ValueError(f'Ukjent nettleser: {browser_choice}')

    if sys.platform.startswith('linux') and os.geteuid() == 0:
        opts['args'] = ['--no-sandbox']
    try:
        browser = playwright.chromium.launch(**opts)
    except Exception as exc:
        if browser_choice == 'edge':
            raise RuntimeError('Microsoft Edge kunne ikke startes. Sjekk at Edge er installert. '
                               'Hvis du vil bruke Chromium i stedet: --browser chromium. '
                               f'Teknisk feilmelding: {str(exc)[:260]}') from exc
        raise
    return browser, browser_choice


def run_scan(args):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Playwright mangler. Kjør INSTALLER.bat først, eller: pip install playwright')
        return 2

    url = args.url
    if not valid_target_url(url):
        print('Av sikkerhetshensyn er scanneren begrenset til billett.rbk.no (eller lokale testfiler).')
        return 2
    counts = Counts()
    diagnostics = {'network_paths': [], 'public_response_schemas': {}, 'scan_passes': [], 'map_detection': None, 'warning': None}
    folder = create_output_dir(Path(args.output).resolve(), args.mode)
    print('\nRBK–Molde | Lesing av offentlig setekart (kun leseoperasjoner)')
    print('Rapportmappe:', folder)
    print('Åpner:', url)
    interrupted = False
    with sync_playwright() as p:
        try:
            browser, browser_choice = open_browser(p, args)
        except Exception as error:
            print('\nKunne ikke starte nettleseren:', error)
            return 2
        diagnostics['browser'] = browser_choice
        print('Nettleser:', 'Microsoft Edge' if browser_choice == 'edge' else browser_choice)
        context = browser.new_context(viewport={'width': args.width, 'height': args.height}, locale='en-US', device_scale_factor=1.0)
        page = context.new_page()
        record_network_metadata(page, diagnostics)
        try:
            try:
                if urlparse(url).scheme == 'file':
                    # Offline demo: inject a local fixture without network navigation.
                    fixture = Path(unquote(urlparse(url).path))
                    page.set_content(fixture.read_text(encoding='utf-8'), wait_until='load', timeout=15000)
                else:
                    page.goto(url, wait_until='domcontentloaded', timeout=args.timeout*1000)
            except Exception as error:
                print('Lasting ga advarsel:', str(error)[:190])
                diagnostics['warning'] = f'Page navigation: {str(error)[:200]}'
            page.wait_for_timeout(2600 if not args.headless else 900)
            diagnostics['zoom'] = configure_visible_map(page, args.zoom, not args.no_auto_fit)
            fit = diagnostics['zoom']
            print(f'Visningsskalering: {round(fit["applied_zoom"] * 100)} %',
                  '(kartet får plass)' if fit['fits_viewport'] else
                  '(kunne ikke bekrefte at HELE kartet får plass)')
            if not fit['fits_viewport'] and not args.headless:
                print('Tips: Prøv --zoom 0.60 eller trykk Ctrl+- i Edge for å zoome lenger ut.')
            if not args.no_pause and not args.headless:
                print('\nSørg for at hele stadionkartet vises i Edge-vinduet.')
                print('Om nødvendig: Ctrl+- for zoom ut, Ctrl+0 for standardvisning.')
                print('Ikke klikk på billetter.')
                input('Trykk ENTER her når kartet er synlig og klart: ')
                page.wait_for_timeout(350)
                if not fit['map_detected']:
                    # Some real seat maps are loaded only after user interaction
                    # or after the initial SPA render has finished.
                    diagnostics['zoom_after_load'] = configure_visible_map(
                        page, fit['applied_zoom'], not args.no_auto_fit)
                    print('Kartet ble kontrollert på nytt etter innlasting.')
                # If the user has adjusted zoom manually, geometry must be
                # measured again instead of assuming the previous map bounds.
                diagnostics['map_bounds_after_user_pause'] = map_bounds(page)
            try:
                page.screenshot(path=str(folder / 'kart_ved_start.png'), full_page=False, timeout=15000)
            except Exception:
                pass
            region, detection = choose_map_region(page)
            diagnostics['map_detection'] = {'region': [round(n) for n in region], 'type': detection, 'frames': len(page.frames)}
            print(f'Kartområde: {tuple(round(n) for n in region)} ({detection})')
            expected = reference_sections(args.reference)
            if expected:
                print(f'Referanse fra video: {len(expected)} identifiserte felt. Kun navnene brukes for dekningskontroll.')
            if args.mode=='assist':
                duration=capture_assisted(page,counts,args.assist_seconds,expected=expected)
                diagnostics['scan_passes'].append({'type':'assist','duration_seconds':duration})
            else:
                max_points=args.max_points
                used=set()
                focused=stadium_roi(region) if urlparse(url).scheme=='https' else region
                diagnostics['focused_region']=[round(v) for v in focused]
                print(f'Prioritert område med tribuneseksjoner: {tuple(round(v) for v in focused)}')
                planned=[]
                if args.smoke_test:
                    # Only a few high-confidence historical points, always
                    # re-read from the live page; never use historical values.
                    anchors={'QA','QB','PA','PB','SA','MB','LB','AA','BA','TA','UA','WA','OA','NA','HB','J','FA','VB','RA'}
                    quick=[(x,y) for x,y,field in reference_points(region) if field in anchors]
                    if not quick:
                        print('Ingen historiske kontrollposisjoner; bruker kartets SVG-punkter.')
                        quick=collect_dom_points(page,region)[:18]
                    planned.append(('quick-check',quick))
                    max_points=min(max_points, len(quick))
                    print('HURTIGTEST: kontrollerer bare noen kjente felt før du starter full skanning.')
                elif urlparse(url).scheme=='https' or args.use_guides_on_local:
                    guided=[(x,y) for x,y,field in reference_points(region)]
                    planned.append(('guided-field-probes',guided))
                svg_points=collect_dom_points(page,region)
                if not args.smoke_test:
                    if svg_points:planned.append(('svg',svg_points))
                    else:print('Kartet har ingen direkte tilgjengelige SVG-felt. Bruker presis hover-strategi.')
                    planned.extend([
                        ('focused-coarse',scan_grid(focused,16)),
                        ('focused-fine',scan_grid(focused,9)),
                    ])
                    if args.deep:
                        planned.append(('focused-ultrafine',scan_grid(focused,5,exclude_pitch=True)))
                hovered=0
                started=monotonic()
                sampler=HoverTransitionSampler(page,read_text,args.hover_ms,diagnostics)
                sampler.initialize()
                for name,points in planned:
                    if hovered>=max_points:break
                    before=counts.export()['observed_field_count']
                    scanned_in_pass=0
                    print(f'\nFase {name}: opptil {min(len(points),max_points-hovered)} posisjoner')
                    for x,y in points:
                        if hovered>=max_points:break
                        key=(int(x),int(y)) # DO NOT round to 8px: 5px wide sections were skipped in V3.
                        if key in used:continue
                        used.add(key)
                        if x<5 or y<5 or x>=args.width-5 or y>=args.height-5:continue
                        try:
                            hits = sampler.hover(x,y,f'auto-{name}')
                            observe_hits(counts,hits)
                        except KeyboardInterrupt:
                            interrupted=True;break
                        except Exception as exc:
                            diagnostics['failed_hover_points']=diagnostics.get('failed_hover_points',0)+1
                        hovered+=1;scanned_in_pass+=1
                        if hovered%250==0:
                            print(f' ... {hovered}/{max_points} posisjoner; {counts.export()["observed_field_count"]} felt observert')
                    new_fields=counts.export()['observed_field_count']-before
                    remaining=missing_fields(expected,counts._groups) if expected else []
                    diagnostics['scan_passes'].append({'type':name,'points_scanned':scanned_in_pass,
                      'unique_field_gain':new_fields,'remaining_reference_fields':len(remaining)})
                    if expected:
                        print(f'Dekning nå: {len(expected)-len(remaining)}/{len(expected)} fra videoreferansen.')
                    # If the publicly visible tooltip never appears at all,
                    # stop rather than waste thousands of hover positions.
                    # Further diagnosis/manual-mode can be done in this run.
                    if counts.export()['observed_field_count']==0 and hovered >= 400:
                        seen=diagnostics.get('hover_positions_with_visible_popups',0)
                        diagnostics['warning']='No fields after '+str(hovered)+' hover positions; visible popup positions='+str(seen)
                        print('ADVARSEL: 0 felt etter',hovered,'posisjoner. Avbryter blindskanning.')
                        print('Synlige popuper under testen:',seen)
                        print('Hvis tallet er 0 reagerer ikke kartet som forventet på automatiske musebevegelser.')
                        print('Hvis tallet er over 0, send resultat.json slik at vi kan se hvorfor de ble avvist.')
                        break
                    if interrupted or (expected and not remaining):break
                diagnostics['scan_passes'].append({'duration_seconds':round(monotonic()-started),
                                                    'total_hover_positions':hovered})
                if not counts.export()['observed_field_count']:
                    # Save a screenshot at the hover position rather than only
                    # an empty pre-scan picture. Useful if live page markup
                    # differs from the local fixtures.
                    try:
                        page.screenshot(path=str(folder/'debug_hover_0_felt.png'),
                                        full_page=False,timeout=15000)
                        diagnostics['zero_field_debug_image']='debug_hover_0_felt.png'
                    except Exception:
                        pass
                    diagnostics['zero_field_detail'] = (
                        'No tooltip transition accepted. Check whether the '
                        'live popup appears when the pointer moves over a field.')
                    print('0 FELT: lagret diagnostikk. IKKE fortsett med nye automatiske runder uten kontroll.')
                if expected:
                    remaining=missing_fields(expected,counts._groups)
                    diagnostics['missing_reference_fields']=remaining
                    print('\nGjenstående referansefelt:',', '.join(remaining) if remaining else 'Ingen')
                    if remaining and args.finish_assist and not args.headless and not interrupted:
                        print('\nAUTOMATISK RUNDE FULLFØRT. Du kan nå fylle hullene manuelt.')
                        duration=capture_assisted(page,counts,args.assist_seconds,source='after-auto',expected=expected)
                        diagnostics['scan_passes'].append({'type':'assisted-completion','duration_seconds':duration})
                        diagnostics['missing_reference_fields']=missing_fields(expected,counts._groups)
        except KeyboardInterrupt:
            interrupted = True
            print('\nAvbrutt av bruker. Lagrer de observasjonene som finnes.')
        except Exception as e:
            diagnostics['warning'] = f'Unexpected scan error: {type(e).__name__} {str(e)[:250]}'
            print('Advarsel:', diagnostics['warning'])
        finally:
            diagnostics['interrupted'] = interrupted
            try:
                page.screenshot(path=str(folder / 'kart_etter.png'), full_page=False, timeout=15000)
            except Exception:
                pass
            context.close()
            browser.close()
    report = write_report(counts, folder, url, args.mode, diagnostics)
    summary = counts.export()
    print('\n====================================================')
    print('FELT MED GODKJENT TELLING:', summary['field_count'])
    print('LEDIGE I DISSE FELTENE:', summary['free_seats_min'], '-', summary['free_seats_max'])
    print('FELT MED SMÅ VARIASJONER:', summary['variable_count'])
    print('FELT MED ALVORLIGE KONFLIKTER:', summary['conflict_count'])
    print('DEKNING: Ukjent – dette er IKKE et fullstendig billettsalgstall')
    print('Rapport:', report)
    if not summary['field_count']:
        print('FEIL: Ingen felter er lest av. Dette er IKKE en vellykket telling.')
    print('====================================================\n')
    return 0 if summary['field_count'] else 1


def import_csv(args):
    counts = Counts()
    path = Path(args.import_csv)
    if not path.is_file():
        print('Fant ikke CSV:',path)
        return 2
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        for line_no,row in enumerate(csv.DictReader(f),start=2):
            try:
                section = (row.get('section') or row.get('felt') or '').upper().strip().replace(' ','')
                if not re.fullmatch(r'(?:[A-Z\u00c6\u00d8\u00c5]{1,3}\d{0,2}|PRESSE)',section):
                    raise ValueError('ugyldig feltnavn')
                free = int((row.get('free') or row.get('ledige') or '').strip())
                capacity = int((row.get('capacity') or row.get('kapasitet') or '').strip())
                if capacity<1 or free<0 or free>capacity:
                    raise ValueError('ugyldige setetall')
                counts.add(Observation(section,(row.get('gate') or row.get('inngang') or '').strip(),free,capacity,'manual-csv'))
            except Exception as exc:
                print(f'Ignorerer CSV linje {line_no}: {exc}')
    folder = create_output_dir(Path(args.output).resolve(), 'csv')
    report = write_report(counts,folder,args.url,'manual-csv', {'note': 'Tall lest fra manuell CSV, ikke kontrollert mot live-nettside'})
    print('Rapport klar:',report)
    return 0 if counts.export()['field_count'] else 1


def cli():
    parser = argparse.ArgumentParser(description='Teller ledige billetter som vises i RBK sitt offentlige stadionkart.')
    parser.add_argument('--url',default=DEFAULT_URL,help='RBK billett-URL')
    parser.add_argument('--mode',choices=['auto','assist'],default='auto')
    parser.add_argument('--output',default=str(ROOT/'output'))
    parser.add_argument('--import-csv',help='Bruk manuell CSV i stedet for nettleser')
    parser.add_argument('--headless',action='store_true',help='Skjult browser (normalt kun for testing)')
    parser.add_argument('--no-pause',action='store_true',help='Ikke stopp før scanning')
    parser.add_argument('--chrome-path',help='Valgfri lokal Chrome/Chromium-sti')
    parser.add_argument('--browser', choices=['auto','edge','chromium','chrome'], default='auto',
                        help='Nettleser: Edge på Windows, Chromium på andre systemer')
    parser.add_argument('--width',type=int,default=1360,
                        help='Nettleservinduets innholdsbredde, standard 1360')
    parser.add_argument('--height',type=int,default=740,
                        help='Nettleservinduets innholdshøyde, standard 740')
    parser.add_argument('--zoom',type=float,default=.75,
                        help='Startskalering, fra 0.45 til 1.00 (standard 0.75)')
    parser.add_argument('--no-auto-fit',action='store_true',
                        help='Ikke reduser skaleringen automatisk hvis kartet er for stort')
    parser.add_argument('--hover-ms',type=int,default=85,help='Ventetid etter hver hover, minst 50ms')
    parser.add_argument('--max-points',type=int,default=6500,help='Maks hovringspunkter, ikke API-kall')
    parser.add_argument('--assist-seconds',type=int,default=1200,help='Maks tid i assistert modus')
    parser.add_argument('--timeout',type=int,default=35)
    parser.add_argument('--deep',action='store_true',help='Ta en ekstra 5px-runde rundt tribunene')
    parser.add_argument('--smoke-test',action='store_true',help='Kort kontroll av noen kjente felt og stopp')
    parser.add_argument('--use-guides-on-local',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--finish-assist',action='store_true',help='La bruker manuelt fylle gjenværende felt i samme økt')
    parser.add_argument('--reference',default=str(ROOT/'video_22_10_felter.csv'),help='Felt fra kontrollert video, kun navn')
    args=parser.parse_args()
    if not .45 <= args.zoom <= 1.0:
        parser.error('--zoom må være mellom 0.45 og 1.0')
    args.hover_ms=max(50,min(args.hover_ms,2000))
    if args.import_csv:
        return import_csv(args)
    return run_scan(args)


if __name__ == '__main__':
    sys.exit(cli())