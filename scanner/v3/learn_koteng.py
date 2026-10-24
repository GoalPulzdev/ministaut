"""Koteng Arena: supervised, read-only stadium hover-learning pilot.

This file NEVER counts for publication, clicks seats, reserves tickets, or
modifies the Lerkendal scanner. It creates a separate unapproved profile.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

# Reuse exactly the working DOM/seatmap probing primitives from Lerkendal.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scanner import choose_map_region, collect_dom_points, grid_points, read_text
from parser import AVAILABILITY, Observation
from v3.profiles import StadiumProfile
import re

KOTENG_URL = "https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd"
SECTION = re.compile(r"\b(?:SECTION|SEKSJON|FELT|BLOCK|SECTOR|SEKTOR)\s*[:#-]?\s*"
                     r"(?P<name>(?:[A-ZÆØÅ]{1,4}[- ]?\d{0,3}|\d{1,3}))\b", re.I)
STANDING = re.compile(r"\b(?:STÅPLASS|STAAPLASS|STANDING)\s*[:#-]?\s*(?P<name>[A-ZÆØÅ0-9-]{1,8})\b", re.I)
# Expected labels from the user's Koteng screen and first measured report,
# NOT a verified complete stadium inventory.
REFERENCE_SEAT_FIELDS = {"FELT-1", "FELT-2", "FELT-3", "FELT-4", "FELT-5", "VIP"}


def cookie_overlay(page):
    try:
        return bool(page.evaluate("""() => {
            const t = document.body?.innerText || '';
            return t.includes('Sikkerheten til dataene dine') &&
                   t.includes('Bare nødvendig');
        }"""))
    except Exception:
        return False


def focused_koteng_region(page):
    """Crop away checkout basket and include the top seating row.

    The existing generic SVG detector covered x=5..1590 and started at y=424
    in the uploaded 1600x960 screenshot. Koteng's seating map is in the left
    checkout column with the top row near y=316. This is a Koteng-only
    supervised training crop, not a change to the Lerkendal scanner.
    """
    original, source = choose_map_region(page)
    vp = page.viewport_size or {"width": 1600, "height": 960}
    width, height = vp["width"], vp["height"]
    region = (
        max(0, min(original[0], width * .04)),
        max(0, min(original[1], height * .28)),
        min(original[2], width * .665),
        min(original[3], height - 10),
    )
    if region[2] - region[0] < 200 or region[3] - region[1] < 200:
        raise RuntimeError("Fant ingen pålitelig stadionkart-region")
    return region, source + "+koteng-left-column"


def even_sample(points, limit):
    """Sample whole spatial range, not just first rows of a grid."""
    if limit <= 0 or not points:
        return []
    if len(points) <= limit:
        return list(points)
    if limit == 1:
        return [points[len(points) // 2]]
    return [points[round(i * (len(points) - 1) / (limit - 1))]
            for i in range(limit)]


def parse_training_tooltip(text, x, y):
    """Same visible-tooltip approach; Koteng may have numbered sections."""
    if not isinstance(text, str) or len(text) > 25000:
        return None
    clean = re.sub(r"[\t\r\n\u00a0]+", " ", text)
    clean = re.sub(r" {2,}", " ", clean)
    for count in AVAILABILITY.finditer(clean):
        free = int(re.sub(r"[ .\u00a0]", "", count.group("available")))
        capacity = int(re.sub(r"[ .\u00a0]", "", count.group("capacity")))
        if not 1 <= capacity <= 100000 or not 0 <= free <= capacity:
            continue
        context = clean[max(0, count.start()-250):count.start()]
        seats = list(SECTION.finditer(context))
        standing = list(STANDING.finditer(context))
        if standing and (not seats or standing[-1].start() > seats[-1].start()):
            label = "STÅPLASS-" + standing[-1].group("name").upper()
            return Observation(label, "", free, capacity, "standing-training", x, y)
        if seats:
            label = seats[-1].group("name").upper().replace(" ", "")
            return Observation(label, "", free, capacity, "koteng-training", x, y)
    return None


def parse_visible(page, x, y):
    found = {}
    for visible in read_text(page):
        obs = parse_training_tooltip(visible, x, y)
        if obs:
            found[(obs.section, obs.capacity, obs.free)] = obs
    return list(found.values())


def train(url=KOTENG_URL, max_points=450, step=38):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "billett.rbk.no" or not parsed.path.startswith("/checkout/"):
        raise ValueError("Koteng-opplæring støtter kun offentlig RBK Vivenu-checkout")
    output = ROOT / "v3_learning" / "koteng_arena"
    output.mkdir(parents=True, exist_ok=True)
    # V2 anchor space differs from the original overbroad detector; do not merge
    # historical V1 coordinates with this new focused region.
    profile_file = ROOT / "v3_profiles" / "koteng_arena.v2.json"
    print("\nKOTENG ARENA - LÆR OPP STADION (TESTMODUS)")
    print("Ingen billetter klikkes eller reserveres. Ingenting publiseres.")
    print("Lerkendals data forblir urørt. Edge åpnes med egen V3-profil.\n")
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "edge_koteng_training_profile"),
            channel="msedge", headless=False,
            viewport={"width": 1600, "height": 960}, args=["--no-first-run"])
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            print("Billettsiden er åpnet i Edge.")
            print("VIKTIG: Lukk samtykkevinduet selv, for eksempel med 'Bare nødvendig'.")
            input("Vis HELE STADIONKARTET i Edge (inkl. Felt 1–5, VIP og Ståplass A), så trykk ENTER: ")
            if cookie_overlay(page):
                raise RuntimeError("Personvernbanneret ligger fortsatt over stadionkartet. Lukk det manuelt og prøv igjen.")
            region, method = focused_koteng_region(page)
            print("Stadionkart:", method, tuple(round(x) for x in region))
            x1, y1, x2, y2 = region
            if x2-x1 < 150 or y2-y1 < 150:
                raise RuntimeError("Fant ikke en stor nok stadionkart-region; læring stoppet")
            dom = collect_dom_points(page, region)
            grid = grid_points(region, step)
            # The old algorithm consumed up to 450 DOM positions before it
            # reached the lower areas. Spread both discovery and rescue probes.
            candidates = even_sample(dom, max_points // 2) + even_sample(
                grid, max_points - max_points // 2)
            selected = []
            used = set()
            for x, y in candidates:
                key = (round(x/8), round(y/8))
                if key not in used and len(selected) < max_points:
                    used.add(key)
                    selected.append((x, y))
            print(f"Fordelte hoverpunkter: {len(dom)} SVG-kandidater, {len(grid)} rutepunkter; "
                  f"{len(selected)} valgt på tvers av hele kartet.")
            if not selected:
                raise RuntimeError("Ingen tilgjengelige skannepunkter")
            print(f"Kontrollerer opptil {len(selected)} hoverpunkter uten å klikke seter.")
            measurements = {}
            standing_measurements = {}
            anchors = defaultdict(list)
            conflicts = {}
            prior_popup = None
            screenshot = output / ("koteng_before_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png")
            page.screenshot(path=str(screenshot))
            viewport = page.viewport_size or {"width": 1600, "height": 960}
            page.mouse.move(viewport["width"]-15, viewport["height"]-15)
            page.wait_for_timeout(180)
            prior_popup = {(h.section, h.capacity, h.free) for h in parse_visible(page, -1, -1)}
            for i, (x, y) in enumerate(selected, 1):
                page.mouse.move(x, y)
                page.wait_for_timeout(100)
                one = {(h.section, h.capacity, h.free): h for h in parse_visible(page, x, y)}
                page.wait_for_timeout(100)
                two = {(h.section, h.capacity, h.free): h for h in parse_visible(page, x, y)}
                stable = [hit for key, hit in two.items() if key in one and key not in prior_popup]
                prior_popup = set(two)
                for hit in stable:
                    name = hit.section
                    if name.startswith("STÅPLASS-"):
                        standing_measurements[name] = {
                            "available_sample": hit.free,
                            "capacity": hit.capacity,
                            "status": "provisional_separate_inventory"}
                        print(f"  ? Ståplasskandidat {name}: {hit.free}/{hit.capacity} "
                              "(holdes utenfor sitteplasstellingen)", flush=True)
                        continue
                    if name in measurements and measurements[name]["capacity"] != hit.capacity:
                        conflicts[name] = [measurements[name]["capacity"], hit.capacity]
                        continue
                    if name not in measurements:
                        print(f"  + {name}: {hit.free}/{hit.capacity}", flush=True)
                        measurements[name] = {"capacity": hit.capacity, "available_sample": hit.free}
                    px = round((x-x1)/(x2-x1), 6)
                    py = round((y-y1)/(y2-y1), 6)
                    if 0 <= px <= 1 and 0 <= py <= 1 and len(anchors[name]) < 5:
                        anchor = {"ref": [px, py], "coordinate_system": "map_normalized_v2",
                                  "source": "visible_hover_training"}
                        if all(math.dist(a["ref"], anchor["ref"]) > 0.015 for a in anchors[name]):
                            anchors[name].append(anchor)
                if i % 50 == 0:
                    print(f"  Sjekket {i}/{len(selected)} · {len(measurements)} sittefelt funnet", flush=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            report = {"timestamp": stamp, "url": url, "arena": "koteng_arena",
                      "region_method": method, "map_region": region,
                      "checked_points": len(selected), "found_sections": measurements,
                      "expected_seat_fields_from_reference": sorted(REFERENCE_SEAT_FIELDS),
                      "missing_reference_seat_fields": sorted(REFERENCE_SEAT_FIELDS-set(measurements)),
                      "standing_areas_from_visible_tooltips": standing_measurements,
                      "standing_area_from_user_image": "Ståplass A – beholdning ikke bekreftet",
                      "available_seated_sample": sum(x["available_sample"] for x in measurements.values()),
                      "seated_capacity_in_observed_fields": sum(x["capacity"] for x in measurements.values()),
                      "capacity_conflicts": conflicts, "coordinate_system": "map_normalized_v2",
                      "map_full_coverage_verified": False,
                      "approval": "NOT_APPROVED_NO_PUBLICATION"}
            report_path = output / (stamp + "_training.json")
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if conflicts:
                print("ADVARSEL: Kapasitetskonflikter. Ingen profil blir godkjent.")
            if not measurements:
                print("Ingen felter kunne leses. Kontroller at kartet er synlig og viser felt-tooltip.")
            else:
                current_sections = {k: v["capacity"] for k, v in measurements.items()}
                current_anchors = dict(anchors)
                if profile_file.exists():
                    old = StadiumProfile.load(profile_file)
                    if old.verified:
                        raise ValueError("Godkjent Koteng-profil kan ikke oppdateres fra en treningsrunde")
                    for key, capacity in old.sections.items():
                        if key in current_sections and current_sections[key] != capacity:
                            conflicts[key] = [capacity, current_sections[key]]
                        current_sections[key] = capacity
                        current_anchors[key] = list(old.anchors.get(key, [])) + [
                            point for point in current_anchors.get(key, [])
                            if all(math.dist(point["ref"], previous["ref"]) > .015
                                   for previous in old.anchors.get(key, []))
                        ]
                        current_anchors[key] = current_anchors[key][:8]
                if conflicts:
                    print("ADVARSEL: Ulike feltkapasiteter mellom opplæringsrunder.")
                    print("Profilen oppdateres IKKE. Kontroller rapporten:", report_path)
                else:
                    profile = StadiumProfile("koteng_arena", 2, "vivenu",
                                             current_sections, current_anchors, False)
                    profile.save(profile_file)
                    print("LAGRET/OPPDATERT PROFILUTKAST:", profile_file)
            print(f"Resultat: {len(measurements)} observerte sittefelt; "
                  f"{len(conflicts)} kapasitetskonflikter.")
            print("Mangler fra skjermreferansen:", ", ".join(sorted(
                  REFERENCE_SEAT_FIELDS-set(measurements))) or "Ingen")
            print("Ståplass A er IKKE dokumentert komplett i sitteplasstallet.")
            print("Dette er et opplæringsutkast, IKKE en fullstendig eller publiserbar telling.")
            print("Rapport:", report_path)
        finally:
            context.close()


def main():
    parser = argparse.ArgumentParser(description="Lær Koteng Arena med samme offentlige hoverteknikk som Lerkendal")
    parser.add_argument("--url", default=KOTENG_URL)
    parser.add_argument("--max-points", type=int, default=450)
    parser.add_argument("--step", type=int, default=38)
    args = parser.parse_args()
    if not 40 <= args.max_points <= 1500 or not 15 <= args.step <= 100:
        parser.error("Ugyldige grenser for hoverpunkter")
    train(args.url, args.max_points, args.step)


if __name__=="__main__":
    main()
