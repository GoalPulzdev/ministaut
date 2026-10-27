"""Koteng Arena read-only Edge seat-map reconnaissance.

Independent of the Lerkendal scanner: does not import/modify scanner/, does not
request private endpoints, reserve seats, write to Supabase, or publish results.
Observed availability only comes from fresh, visible section tooltips.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from anchor_training import (build_anchor_document, mapped_points,
                             save_anchor_document, teach_from_screenshot)
from anchor_scan import scan_anchor_pass
from profile_lock import load_verified_lock

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "koteng_profile.json"
DEFAULT_URL = "https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd"
AVAIL = re.compile(
    r"(?:free\s+seats?|available\s+seats?|ledige\s+(?:seter|plasser|billetter)|"
    r"tilgjengelige\s+(?:seter|plasser))\s*[:\-]?\s*"
    r"(?P<free>[\d .,\u00a0]+)\s*(?:/|of|av)\s*(?P<capacity>[\d .,\u00a0]+)", re.I)
SECTION = re.compile(r"\b(?:(?:felt|section|seksjon|block)\s*[:#\-]?\s*"
                     r"(?:felt\s*[- ]?)?(?P<index>\d{1,2}|VIP)|(?P<vip>VIP))\b", re.I)

# Read only tooltip text that is visibly rendered. Never inspect checkout form data.
READ_TEXT_JS = r"""() => {
 const re=/(free\s+seats?|available\s+seats?|ledige\s+(seter|plasser|billetter)|tilgjengelige\s+(seter|plasser))/i;
 const selectors=['[role="tooltip"]','[class*="tooltip" i]','[id*="tooltip" i]',
   '[class*="popover" i]','[id*="popover" i]'];
 const found=[]; const seen=new Set();
 for(const s of selectors) for(const e of document.querySelectorAll(s)) {
   if(seen.has(e))continue;seen.add(e);
   const st=getComputedStyle(e),r=e.getBoundingClientRect();
   if(st.visibility==='hidden'||st.display==='none'||Number(st.opacity)===0||r.width<3||r.height<3)continue;
   const t=(e.innerText||'').trim();if(t.length<1500&&re.test(t))found.push(t);
 }
 if(found.length)return found;
 const text=(document.body?.innerText||'');
 const m=[...text.matchAll(new RegExp(re.source,'ig'))];
 return m.slice(-3).map(x=>text.slice(Math.max(0,x.index-130),Math.min(text.length,x.index+85)));
}"""
MAP_JS = r"""() => [...document.querySelectorAll('svg,canvas,[class*="seatmap" i],[id*="seatmap" i],[class*="seat-map" i],[id*="seat-map" i]')]
 .map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,tag:e.tagName.toLowerCase()}})
 .filter(r=>r.w>280&&r.h>160&&r.w<5000&&r.h<4000).slice(0,30)"""
SVG_JS = r"""() => [...document.querySelectorAll('svg path,svg polygon,svg rect,svg circle')]
 .map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);
   return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,
           visible:s.visibility!=='hidden'&&s.display!=='none'&&s.pointerEvents!=='none'};})
 .filter(r=>r.visible&&r.w>=4&&r.h>=4&&r.w<=350&&r.h<=350).slice(0,4000)"""


@dataclass(frozen=True)
class Observation:
    section: str
    free: int
    capacity: int
    x: int = -1
    y: int = -1


def event_key(url: str) -> str:
    u = urlparse(url)
    m = re.fullmatch(r"/checkout/([a-zA-Z0-9_-]{8,100})/?", u.path)
    if u.scheme != "https" or u.hostname != "billett.rbk.no" or not m:
        raise ValueError("Bare gyldige https://billett.rbk.no/checkout/<id> støttes")
    return m.group(1)


def normalize_section(raw: str) -> str:
    raw = raw.upper().strip()
    if raw == "VIP":
        return "VIP"
    if raw.isdigit():
        return "FELT-" + str(int(raw))
    raise ValueError("Ukjent feltnavn")


def parse_tooltip(text: str, x: int = -1, y: int = -1) -> Observation | None:
    if not isinstance(text, str) or len(text) > 15000:
        return None
    clean = re.sub(r"[\t\r\n\u00a0]+", " ", text)
    for match in AVAIL.finditer(clean):
        try:
            free = int(re.sub(r"[^\d]", "", match.group("free")))
            capacity = int(re.sub(r"[^\d]", "", match.group("capacity")))
        except ValueError:
            continue
        if capacity < 1 or capacity > 10000 or not (0 <= free <= capacity):
            continue
        before = clean[max(0, match.start()-180):match.start()]
        sections = list(SECTION.finditer(before))
        if not sections:
            continue
        s = sections[-1]
        return Observation(normalize_section(s.group("index") or s.group("vip")), free, capacity, x, y)
    return None


def validate(profile: dict, observations_by_pass: list[dict], unexpected: list[str] | None = None,
             *, lock_integrity_verified: bool = False) -> dict:
    """Never silently turn an unseen/locked section into zero availability."""
    reference = profile["reference_sections"]
    event = profile["event_configs"][event_key(profile["active_url"])]
    locked = set(event.get("locked_sections", []))
    confirmed_lock = event.get("locked_confirmation") == "BEKREFTET_MANUELT"
    errors = []
    if locked and not confirmed_lock:
        errors.append("Låste felt mangler skriftlig manuell bekreftelse")
    if locked - set(reference):
        errors.append("Ukjente låste felt")
    active = set(reference) - (locked if confirmed_lock else set())
    # Two independent confirmations may be obtained in any two distinct
    # passes.  A missing response in pass 1 must NOT invalidate matching fresh
    # responses in passes 2 and 3.  Never count two attempts in the same pass.
    all_samples = {section: [(index + 1, p[section])
                             for index, p in enumerate(observations_by_pass)
                             if section in p] for section in active}
    missing = sorted(section for section, rows in all_samples.items() if len(rows) < 2)
    if missing:
        errors.append("Mangler to uavhengige avlesninger for: " + ", ".join(missing))
    detected = set().union(*(set(p) for p in observations_by_pass)) if observations_by_pass else set()
    unknown = sorted((detected - set(reference)) | set(unexpected or []))
    if unknown:
        errors.append("Ukjente områder registrert: " + ", ".join(unknown))
    accepted = {}
    conflicts = {}
    for section in sorted(active):
        rows = all_samples[section]
        if len(rows) < 2:
            continue
        observations = [value for _, value in rows]
        capacities = {o.capacity for o in observations}
        frees = [o.free for o in observations]
        if capacities != {reference[section]} or max(frees) - min(frees) > 2:
            conflicts[section] = [{"pass": index, **asdict(obs)} for index, obs in rows]
            errors.append(f"Konflikt for {section}: kapasitet eller ledighet")
        else:
            accepted[section] = asdict(observations[-1])
            accepted[section]["min_free"] = min(frees)
            accepted[section]["max_free"] = max(frees)
            accepted[section]["verified_passes"] = [index for index, _ in rows]
    counted = sum(x["free"] for x in accepted.values())
    coverage = not errors and len(accepted) == len(active) and len(observations_by_pass) >= 2
    candidate = coverage and profile.get("map_full_coverage_verified") is True
    local_verified = (coverage and lock_integrity_verified
                      and profile.get("local_seated_profile_approved") is True
                      and profile.get("local_profile_lock", {}).get("state") == "LOCKED")
    return {
        "quality_status": "LOCKED_LOCAL_VERIFIED" if local_verified else ("CANDIDATE_COMPLETE" if candidate else "NEEDS_REVIEW"),
        "local_seated_coverage_verified": local_verified,
        "public_approved": False,
        "two_read_coverage_complete": coverage,
        "reference_sections": len(reference),
        "counted_sections": len(accepted),
        "confirmation_count_by_section": {section: len(rows) for section, rows in sorted(all_samples.items())},
        "locked_confirmed": sorted(locked) if confirmed_lock else [],
        "missing_sections": missing,
        "unknown_sections": unknown,
        "conflicts": conflicts,
        "errors": errors,
        "observed_available_in_verified_fields": counted,
        "observed_min": sum(x["min_free"] for x in accepted.values()),
        "observed_max": sum(x["max_free"] for x in accepted.values()),
        "complete": candidate,
        "publishable": False,
        "sections": accepted,
        "note": ("Lokal seksjonsprofil er låst og kontrollert; salgbarhet per kategori, "
                 "VIP/HC og Felt 5 er ikke bekreftet for publisering.") if local_verified
                else "Ikke offentliggjørbart: kapasitet/kart og salgbart inventar må kontrolleres manuelt.",
    }


def frame_offset(frame):
    if frame.parent_frame is None:
        return 0., 0., 1., 1.
    try:
        box = frame.frame_element().bounding_box()
        size = frame.evaluate("() => ({w:innerWidth,h:innerHeight})")
        if box:
            return box["x"], box["y"], box["width"]/max(1,size["w"]), box["height"]/max(1,size["h"])
    except Exception:
        pass
    return 0., 0., 1., 1.


def candidate_regions(page):
    regions = []
    for frame in page.frames:
        try:
            ox, oy, sx, sy = frame_offset(frame)
            for r in frame.evaluate(MAP_JS):
                box = [ox + r["x"]*sx, oy + r["y"]*sy,
                       ox + (r["x"]+r["w"])*sx, oy + (r["y"]+r["h"])*sy]
                regions.append({"rect": [round(v,1) for v in box],
                                "area": round((box[2]-box[0])*(box[3]-box[1])),
                                "tag": r["tag"], "frame": frame.url[:160]})
        except Exception:
            continue
    return sorted(regions, key=lambda x:x["area"], reverse=True)


def locked_edge_context_options(anchors: dict) -> dict:
    """Use the original verified CSS content viewport on any host display.

    No resize of normalized points, no retraining, no changes to the SHA lock.
    On a screen too small to show this window, the live scan must stop.
    """
    dimensions = anchors.get("reference_viewport")
    if (not isinstance(dimensions,list) or len(dimensions)!=2
            or any(not isinstance(v,int) or isinstance(v,bool) or v<400 for v in dimensions)):
        raise ValueError("Mangler gyldig referansevindu i laast Koteng-profil")
    if dimensions != [1294,642]:
        raise ValueError("Uventet referansevindu: ingen automatisk skalering av laaste punkter")
    return {"viewport":{"width":dimensions[0],"height":dimensions[1]},
            "device_scale_factor":1,
            "args":["--window-position=0,0"]}


def current_display_info(page):
    """Diagnostic only: physical desktop screen vs Playwright CSS viewport."""
    return page.evaluate("""() => ({
      contentWidth: window.innerWidth, contentHeight: window.innerHeight,
      outerWidth: window.outerWidth, outerHeight: window.outerHeight,
      desktopWidth: window.screen.availWidth, desktopHeight: window.screen.availHeight,
      pixelRatio: window.devicePixelRatio
    })""")


def desktop_can_show_locked_window(info, viewport):
    """Reject obviously cropped interactive UI before attempting live hover."""
    return (info["contentWidth"] == viewport[0]
            and info["contentHeight"] == viewport[1]
            and info["desktopWidth"] >= max(info["outerWidth"], viewport[0])
            and info["desktopHeight"] >= max(info["outerHeight"], viewport[1]))


def windows_primary_work_area():
    """Approximate usable Windows desktop CSS size; non-Windows returns None.

    Playwright emulates window.screen with fixed viewport, so use native Win32
    API instead of trusting screen.availWidth in the web page.
    """
    import os
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        class Rect(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                        ("right", wintypes.LONG), ("bottom", wintypes.LONG)]
        rc = Rect()
        # SPI_GETWORKAREA = 0x0030. Respects Windows taskbar.
        if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0):
            return None
        width, height = int(rc.right - rc.left), int(rc.bottom - rc.top)
        if width <= 0 or height <= 0:
            return None
        return width, height
    except (AttributeError, OSError, ValueError):
        return None


def work_area_fits_locked_edge(work_area, viewport):
    """Conservative headroom for Windows title bar, tabs and window borders."""
    return (work_area[0] >= viewport[0] + 12
            and work_area[1] >= viewport[1] + 85)


def browser_viewport(page):
    """Actual visible content area, not a fixed Playwright emulated viewport.

    With no_viewport=True, page.viewport_size is None. Reading innerWidth and
    innerHeight also handles the real Windows Edge window and display scaling.
    """
    value = page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
    return int(value["width"]), int(value["height"])


def maximize_edge_window(context, page):
    """Best-effort native window maximize; safe on unsupported environments."""
    try:
        session = context.new_cdp_session(page)
        result = session.send("Browser.getWindowForTarget")
        session.send("Browser.setWindowBounds", {
            "windowId": result["windowId"], "bounds": {"windowState": "maximized"}
        })
        session.detach()
        page.wait_for_timeout(350)
        return True
    except Exception:
        return False


def region_is_visible(rect, viewport, margin=8):
    """The WHOLE detected map must fit; a crop cannot count as complete."""
    width, height = viewport
    x1, y1, x2, y2 = rect
    return (0 <= x1 < x2 <= width - margin
            and 0 <= y1 < y2 <= height - margin)


def choose_map_candidate(regions, viewport):
    """Choose the largest actual canvas/SVG within the seating portion."""
    width, _ = viewport
    candidates = [r for r in regions
                  if r["rect"][0] < width * .8 and r["rect"][1] >= -30]
    # Restrict to plausible seat-map geometry, not right-side checkout graphics.
    return max(candidates, key=lambda r: r["area"]) if candidates else None


def fit_map_to_edge(page, *, enabled=True, minimum=0.50):
    """Fit rendered seat map by *page* zoom; do not alter the map's own zoom.

    Zooming the root document keeps pointer geometry consistent with Playwright
    bounding boxes and frame_offset. Every step re-measures responsive layouts
    because the ticket site can reflow after page zoom. Never fabricate a fit.
    """
    steps = [1.0] if not enabled else [1.0, .90, .80, .75, .70, .65, .60, .55, .50]
    steps = [z for z in steps if z >= minimum - .001]
    attempts = []
    for zoom in steps:
        try:
            page.evaluate("""(zoom) => {
              document.documentElement.style.zoom = String(zoom);
              window.scrollTo(0, 0);
            }""", zoom)
            page.wait_for_timeout(280)
            viewport = browser_viewport(page)
            candidates = candidate_regions(page)
            selected = choose_map_candidate(candidates, viewport)
            box = selected["rect"] if selected else None
            good = bool(box and region_is_visible(box, viewport))
            attempts.append({"zoom": zoom, "viewport": list(viewport),
                             "region": box, "fits": good})
            if good:
                return {"fits": True, "page_zoom": zoom,
                        "viewport": list(viewport), "map": selected,
                        "attempts": attempts}
        except Exception as exc:
            attempts.append({"zoom": zoom, "error": type(exc).__name__})
    return {"fits": False, "page_zoom": steps[-1], "attempts": attempts}


def candidate_points(page, region, spacing=25):
    x1,y1,x2,y2 = region
    points = []
    for frame in page.frames:
        try:
            ox,oy,sx,sy = frame_offset(frame)
            for r in frame.evaluate(SVG_JS):
                x = round(ox + r["x"]*sx); y = round(oy + r["y"]*sy)
                if x1<=x<=x2 and y1<=y<=y2:
                    points.append((x,y))
        except Exception:
            continue
    # Grid covers canvas/irregular geometry even when SVG provides no shapes.
    yy = int(y1) + spacing//2
    row = 0
    while yy < y2:
        xx = list(range(int(x1)+spacing//2, int(x2), spacing))
        if row % 2: xx.reverse()
        points.extend((x,yy) for x in xx)
        yy += spacing; row += 1
    result = []; seen = set()
    for x,y in points:
        p = (round(x/4)*4,round(y/4)*4)
        if p not in seen:
            seen.add(p); result.append(p)
    return result


def read_current(page):
    found = {}
    for frame in page.frames:
        try:
            for text in frame.evaluate(READ_TEXT_JS):
                o = parse_tooltip(text)
                if o: found[(o.section,o.capacity,o.free)] = o
        except Exception:
            continue
    return list(found.values())


def hover_target_metadata(page, point):
    """Local debug only. Never retain cookie, form, seat IDs or page text."""
    x,y = point
    try:
        page.mouse.move(x,y)
        page.wait_for_timeout(180)
        return page.evaluate("""p => {
          const e=document.elementFromPoint(p[0],p[1]);
          if(!e)return {element:null};
          const r=e.getBoundingClientRect(),s=getComputedStyle(e);
          return {tag:e.tagName.toLowerCase(), id:(e.id||'').slice(0,50),
                  class_name:typeof e.className==='string'?e.className.slice(0,90):'',
                  bounds:[r.x,r.y,r.width,r.height].map(v=>Math.round(v)),
                  pointer_events:s.pointerEvents};
        }""", [x,y])
    except Exception as e:
        return {"error_type":type(e).__name__}


def fresh_hover(page, x, y, dwell_ms=85):
    """Reject stale popups: clear off-map, then read the same value twice."""
    width, height = browser_viewport(page)
    page.mouse.move(width-15, 15)
    page.wait_for_timeout(95)
    # Some seatmaps leave a stale popup at the neutral point. Capture its
    # signature so it cannot be mistaken for a new hover observation.
    baseline = {(v.section,v.capacity,v.free) for v in read_current(page)}
    page.mouse.move(x,y)
    page.wait_for_timeout(dwell_ms)
    one = {(v.section,v.capacity,v.free):v for v in read_current(page)}
    page.wait_for_timeout(80)
    two = {(v.section,v.capacity,v.free):v for v in read_current(page)}
    return [Observation(v.section,v.free,v.capacity,x,y) for k,v in two.items()
            if k in one and k not in baseline]


def scan_pass(page, points, dwell_ms=85):
    by_section = {}; discrepancies = {}; observed = 0
    for idx,(x,y) in enumerate(points):
        try:
            for o in fresh_hover(page,x,y,dwell_ms):
                observed += 1
                before = by_section.get(o.section)
                if before and (o.capacity != before.capacity or abs(o.free-before.free)>2):
                    discrepancies.setdefault(o.section, []).extend([asdict(before), asdict(o)])
                else:
                    by_section[o.section] = o
        except Exception:
            continue
        if idx and idx % 200 == 0:
            print(f"    {idx}/{len(points)} punkter, {len(by_section)} felt, {observed} treff", flush=True)
    return by_section, discrepancies, observed


def sections_needing_recheck(profile: dict, passes: list[dict]) -> set[str]:
    """Fields with fewer than two independent successful read rounds.

    Never assume a failed field has zero availability.  Locked sections are
    omitted only if explicitly manually confirmed for the active event.
    """
    reference = profile["reference_sections"]
    event = profile["event_configs"][event_key(profile["active_url"])]
    locked = (set(event.get("locked_sections", []))
              if event.get("locked_confirmation") == "BEKREFTET_MANUELT" else set())
    return {name for name in reference if name not in locked and
            sum(name in result for result in passes) < 2}


def run(args):
    from playwright.sync_api import sync_playwright
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    key = event_key(args.url)
    if key not in profile["event_configs"]:
        raise ValueError("Kamp er ikke registrert i Koteng-profilen. Opprett eget kampoppsett først.")
    profile["active_url"] = args.url
    if args.teach:
        raise ValueError("Koteng-profil V1.8 er LÅST. Ikke lær opp på nytt eller overskriv ankere. "
                         "Bruk en separat kopi og ny profilversjon ved endret kart.")
    if args.region and not args.fixture:
        raise ValueError("Manuell kart-region er sperret for låst produksjonskalibrering.")
    locked_anchors, lock_digest = load_verified_lock(profile, Path(args.anchors).resolve(), key)
    locked_context = locked_edge_context_options(locked_anchors)
    out = Path(args.output).resolve() / key / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    details = {"event_key":key,"venue_id":"koteng_arena","url":args.url,
               "profile_lock": {"state":"LOCKED", "digest_sha256":lock_digest,
                                "scope":"local_seat_sections_only"},
               "profile_version":profile["profile_version"],
               "scanned_at_utc":datetime.now(timezone.utc).isoformat(),"network_publication":False,
               "selected_ticket_category":args.category,
               "cross_category_union_verified":False}
    context = None
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str((ROOT/"edge_koteng_profile" if not args.fixture else ROOT/"edge_fixture_profile").resolve()),
                channel="msedge",
                headless=bool(args.headless),
                viewport=locked_context["viewport"],
                device_scale_factor=locked_context["device_scale_factor"],
                args=locked_context["args"],
                accept_downloads=False)
            page = context.pages[0] if context.pages else context.new_page()
            # V2.4: do not maximize. Maximizing changes the CSS viewport on
            # a different Windows resolution and invalidates locked anchors.
            details["edge_maximized"] = False
            details["viewport_mode"] = "fixed_locked_css_viewport_v24"
            details["locked_css_viewport"] = locked_anchors["reference_viewport"]
            page.goto(Path(args.fixture).resolve().as_uri() if args.fixture else args.url,
                      wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(800)
            if not args.fixture:
                display = current_display_info(page)
                details["host_display_geometry"] = display
                expected = tuple(locked_anchors["reference_viewport"])
                print("Koteng V2.4: laast Edge-innhold",expected[0],"x",expected[1],
                      "CSS-piksler; skjerm",display["desktopWidth"],"x",display["desktopHeight"])
                if not desktop_can_show_locked_window(display, expected):
                    raise RuntimeError(
                        "Denne skjermen er for liten til aa vise laast Edge-vindu uten utsnitt. "
                        "Endre Windows-skalering/opploesning slik at Edge faar plass, "
                        "eller bestill kontrollert ny kalibrering. IKKE publiser telling. "
                        "Laast Edge-vindu: 1294x642 CSS-piksler; "
                        f"Edge emulert skjerm: {display['desktopWidth']}x{display['desktopHeight']}; "
                        f"vindu: {display['outerWidth']}x{display['outerHeight']}.")
                print("Ingen ny opplaering noedvendig dersom Edge-kartgeometrien matcher profilen.")
                initial = fit_map_to_edge(page, enabled=not args.no_auto_fit)
                details["edge_initial_fit"] = initial
                print("Karttilpasning:", "OK" if initial["fits"] else "ikke fullført",
                      "| sidezoom:", initial["page_zoom"])
                if not args.no_pause:
                    input("Kontroller kartet og billettkategori i Edge. Trykk ENTER for telling: ")
            if not args.fixture and (urlparse(page.url).hostname != "billett.rbk.no" or key not in page.url):
                raise RuntimeError("Billettvinduet er omdirigert til en annen kamp eller side.")
            page.wait_for_timeout(400)
            # After user interactions the responsive site may re-render its map.
            layout = fit_map_to_edge(page, enabled=not args.no_auto_fit) if not args.fixture else None
            if layout:
                details["edge_final_fit"] = layout
            try:
                page.screenshot(path=str(out/"referanse_edge.png"), full_page=False, scale="css")
                details["local_screenshot"] = "referanse_edge.png"
            except Exception:
                details["local_screenshot"] = None
            regions = candidate_regions(page)
            details["map_region_candidates"] = regions[:12]
            vw, vh = browser_viewport(page)
            if (vw,vh)!=tuple(locked_anchors["reference_viewport"]):
                raise RuntimeError("CSS-visningen avviker fra laast Koteng-profil; ingen telling")
            selected = choose_map_candidate(regions, (vw, vh))
            if args.region:
                region = [float(v) for v in args.region.split(",")]
                if len(region)!=4: raise ValueError("--region må være x1,y1,x2,y2")
            elif selected:
                region = selected["rect"]
            else:
                raise RuntimeError("Fant ikke billettkart som SVG/canvas. Se referanse_edge.png i diagnostikk.")
            details["scan_region"] = region
            details["viewport"] = [vw,vh]
            if not region_is_visible(region, (vw, vh)):
                raise RuntimeError("Kartet er fortsatt delvis utenfor Edge-vinduet. "
                                   "Maksimer Edge og prøv Ctrl+- (sidezoom, ikke +/- i stadionkartet). "
                                   "Ingen telling ble godkjent; se referanse_edge.png.")
            # The earlier broad canvas ROI excludes the small stand labels on
            # Koteng. User-selected points are calibrated to the screenshot / real
            # viewport, not to an unreliable pitch-only bounding rectangle.
            anchors_path = Path(args.anchors).resolve()
            use_manual = not args.fixture and not args.grid_diagnostic
            if use_manual:
                # Profile and anchors were verified before launching Edge. No
                # implicit training or overwriting is allowed in the locked build.
                document = locked_anchors
                print("LÅST KOTENG-PROFIL: ankerpunkter og seksjonskapasiteter er kontrollert.")
                anchors = mapped_points(document, profile["reference_sections"],
                                        (vw,vh), region, layout["page_zoom"])
                details["scan_mode"] = "manual_koteng_anchors"
                details["anchor_file"] = anchors_path.name
                details["anchor_training_event"] = document["training_event_key"]
                details["anchor_points_per_section"] = {k:len(v) for k,v in anchors.items()}
                details["probe_points"] = sum(map(len,anchors.values()))
                try:
                    from anchor_training import draw_anchor_overlay
                    draw_anchor_overlay(out / "referanse_edge.png", anchors, out / "kontrollpunkter.png",
                                        viewport=(vw,vh))
                    details["anchor_preview"] = "kontrollpunkter.png"
                except Exception as exc:
                    details["anchor_preview_error"] = type(exc).__name__
                print("KART: seks manuelt markerte felt; minst 2 uavhengige avlesninger per felt")
                print("      Ufullstendige felt faar opptil 2 egne etterkontrollrunder")
            else:
                points = candidate_points(page,region,args.spacing)
                details["scan_mode"] = "diagnostic_grid_not_manual"
                details["probe_points"] = len(points)
                if len(points)>args.max_points:
                    raise RuntimeError(f"Kartet krever {len(points)} punkter (> {args.max_points}). Øk --max-points eller --spacing.")
                print(f"KART: {region}; {len(points)} probe-punkter; 2 uavhengige pass")
            # Historical points only if the viewport/map profile exactly matches
            # the first real (but unapproved) hover pass on 2026-10-26.
            # They are strictly candidate coordinates, never proven counts.
            historical = {}
            if use_manual and (vw, vh)==(1726,856) and abs(layout["page_zoom"]-0.9)<.01 and all(
                abs(a-b)<12 for a,b in zip(region, [0,250,1151,770.4])):
                historical={
                    "VIP": [(612,288)], "FELT-1": [(336,312)],
                    "FELT-2": [(360,312)], "FELT-3": [(512,312)],
                    "FELT-4": [(664,312)], "FELT-5": [(812,312)]}
            details["historical_hints_enabled"] = bool(historical)
            passes = []; issues = []; anchor_issues = []; preferred = {}
            # Two complete discovery rounds, followed by targeted rounds ONLY
            # for sections that still lack two distinct validated observations.
            # A targeted round re-hovers/re-reads; it does not clone pass-2 data.
            total_rounds = 2 + (args.retry_rounds if use_manual else 0)
            for k in range(total_rounds):
                if use_manual:
                    needed = set(profile["reference_sections"])
                    if k >= 2:
                        needed = sections_needing_recheck(profile, passes)
                        if not needed:
                            break
                        page.wait_for_timeout(args.retry_pause_ms)
                        print(f"  Etterkontroll {k-1}/{args.retry_rounds}: "
                              + ", ".join(sorted(needed)), flush=True)
                    else:
                        print(f"  Pass {k+1}/2", flush=True)
                    observations, conflict, hit_count, rejected = scan_anchor_pass(
                        page, anchors, profile["reference_sections"], args.dwell_ms,
                        read_current, Observation, viewport=(vw,vh), scouts=True,
                        historical=historical, preferred=preferred,
                        max_scout_per_section=args.max_scout,
                        only_sections=needed)
                    anchor_issues.append(rejected)
                    for section, obs in observations.items():
                        preferred[section] = [(obs.x,obs.y)]
                else:
                    print(f"  Pass {k+1}/2", flush=True)
                    observations, conflict, hit_count = scan_pass(page, points, args.dwell_ms)
                details[f"pass_{k+1}_hover_hits"] = hit_count
                passes.append(observations)
                issues.append(conflict)
            if use_manual:
                details["anchor_point_checks_by_pass"] = anchor_issues
                for pass_number, (observations, checks) in enumerate(zip(passes, anchor_issues), 1):
                    label = "Pass" if pass_number <= 2 else "Etterkontroll"
                    print(f"  {label} {pass_number if pass_number <= 2 else pass_number-2}: "
                          f"{len(observations)} felt; "
                          + ", ".join(f"{r['field']}={r['result']}" for r in checks), flush=True)
            if use_manual and sum(map(len, passes)) == 0:
                # Independent metadata-level visibility clue, not a fallback
                # count. Never capture checkout state or hidden seat IDs.
                details["top_page_hit_test_at_anchors"] = {
                    n:hover_target_metadata(page,pts[0])
                    for n,pts in anchors.items() if pts}
            # Revalidate disk files after scanning too: local profile and points
            # must not change between Edge startup and the final verdict.
            _, lock_digest_after = load_verified_lock(profile, anchors_path, key)
            if lock_digest_after != lock_digest:
                raise ValueError("Koteng-låsen ble endret under skanning; avbryt kontrollen")
            validation = validate(profile,passes,lock_integrity_verified=use_manual and not args.fixture)
            if use_manual:
                # Save suggested coordinates only after >=2 independent hits.
                recovered = {name:[data["x"],data["y"]]
                             for name,data in validation["sections"].items()}
                details["two_pass_anchor_candidates"] = recovered
                (out/"forslag_kontrollpunkter.json").write_text(
                    json.dumps({"event_key":key,"suggested_points":recovered,
                                "source_rounds":len(passes),"public_approved":False},
                               indent=2),encoding="utf-8")
            if any(issues):
                validation["errors"].append("Interne observasjonskonflikter i ett eller flere pass")
                validation["quality_status"]="NEEDS_REVIEW"
                validation["local_seated_coverage_verified"]=False
                validation["complete"]=False
            validation["within_pass_discrepancies"] = issues
            details["validation"] = validation
            details["observations_by_pass"] = [{k:asdict(v) for k,v in d.items()} for d in passes]
            print("Feltkontroll:", f"{validation['counted_sections']}/{validation['reference_sections']}",
                  "bekreftet i minst 2 uavhengige runder.")
            print("Resultat:", validation["quality_status"],
                  "| observert ledige i kontrollerte felt:", validation["observed_available_in_verified_fields"],
                  "(IKKE et publisert totalresultat)")
            if validation["local_seated_coverage_verified"]:
                print("KORREKT LOKAL FELTTELLING: profil låst. Billetter og kategorier må fortsatt godkjennes før offentliggjøring.")
            elif validation["two_read_coverage_complete"] and not validation["complete"]:
                print("Alle referansefelt har >=2 samsvarende avlesninger, men arena-/kategoriinventaret er IKKE manuelt godkjent.")
            print("Mangler:",validation["missing_sections"],"Feil:",validation["errors"])
            return details
        finally:
            if context:
                try:context.close()
                except Exception:pass
            (out/"diagnostikk.json").write_text(json.dumps(details,indent=2,ensure_ascii=False),encoding="utf-8")
            print("Lokal rapport:",out/"diagnostikk.json")


def main(argv=None):
    ap=argparse.ArgumentParser(description="Isolert Koteng Arena Edge-skanner, KUN lokal diagnostikk")
    ap.add_argument("--url",default=DEFAULT_URL)
    ap.add_argument("--profile",default=str(PROFILE))
    ap.add_argument("--anchors",default=str(ROOT/"ankerpunkter_koteng.json"),help="Lokal stadionfil med manuelt lagrede markeringer")
    ap.add_argument("--teach",action="store_true",help="Marker Koteng-punkter på lokal Edge-screenshot og lagre dem på nytt")
    ap.add_argument("--grid-diagnostic",action="store_true",help="Eksplisitt gammel rutenettskanning kun for diagnose")
    ap.add_argument("--category",default="ukjent",help="Valgt billettkategori ved manuell inspeksjon, f.eks. voksen/HC/VIP")
    ap.add_argument("--fixture",help="Lokal syntetisk HTML for kontroll")
    ap.add_argument("--region",help="x1,y1,x2,y2 i synlige Edge viewport-piksler")
    ap.add_argument("--no-auto-fit",action="store_true",help="Skru av automatisk sidezoom i Edge")
    ap.add_argument("--spacing",type=int,default=25)
    ap.add_argument("--dwell-ms",type=int,default=150)
    ap.add_argument("--max-scout",type=int,default=18,
                    help="Maksimalt antall kandidatpunkter per felt og pass")
    ap.add_argument("--retry-rounds",type=int,default=2,
                    help="Ekstra uavhengige kontrollrunder for felt med under to treff (standard 2)")
    ap.add_argument("--retry-pause-ms",type=int,default=500,
                    help="Kort hvile mellom kontrollrundene (standard 500 ms)")
    ap.add_argument("--max-points",type=int,default=7000)
    ap.add_argument("--headless",action="store_true",help="Kun for offline-test, ikke virkelig Edge")
    ap.add_argument("--no-pause",action="store_true")
    ap.add_argument("--output",default=str(ROOT/"diagnostikk"))
    args=ap.parse_args(argv)
    if args.spacing<8 or args.spacing>80 or args.dwell_ms<60 or not (1<=args.max_scout<=60) or not (0<=args.retry_rounds<=5) or not (200<=args.retry_pause_ms<=5000):ap.error("Ugyldig spacing/dwell-ms/retry-parameter")
    try:run(args);return 0
    except Exception as e:
        print("Kan ikke godkjenne telling:",str(e),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
