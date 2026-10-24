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
        names = list(SECTION.finditer(clean[max(0, count.start()-250):count.start()]))
        if names:
            label = names[-1].group("name").upper().replace(" ", "")
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
    profile_file = ROOT / "v3_profiles" / "koteng_arena.v1.json"
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
            input("Gå til STADIONKARTET i Edge og vent til feltene synes. Trykk ENTER her for å lære inn: ")
            region, method = choose_map_region(page)
            print("Stadionkart:", method, tuple(round(x) for x in region))
            x1, y1, x2, y2 = region
            if x2-x1 < 150 or y2-y1 < 150:
                raise RuntimeError("Fant ikke en stor nok stadionkart-region; læring stoppet")
            points = collect_dom_points(page, region)
            # Follow proven Lerkendal rescue principle: bounded grid if SVG points miss fields.
            points += grid_points(region, step)
            selected = []
            used = set()
            for x, y in points:
                key = (round(x/8), round(y/8))
                if key not in used and len(selected) < max_points:
                    used.add(key)
                    selected.append((x, y))
            if not selected:
                raise RuntimeError("Ingen tilgjengelige skannepunkter")
            print(f"Kontrollerer opptil {len(selected)} hoverpunkter uten å klikke seter.")
            measurements = {}
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
                    if name in measurements and measurements[name]["capacity"] != hit.capacity:
                        conflicts[name] = [measurements[name]["capacity"], hit.capacity]
                        continue
                    if name not in measurements:
                        print(f"  + {name}: {hit.free}/{hit.capacity}", flush=True)
                        measurements[name] = {"capacity": hit.capacity, "available_sample": hit.free}
                    px = round((x-x1)/(x2-x1), 6)
                    py = round((y-y1)/(y2-y1), 6)
                    if 0 <= px <= 1 and 0 <= py <= 1 and len(anchors[name]) < 5:
                        anchor = {"ref": [px, py], "coordinate_system": "map_normalized",
                                  "source": "visible_hover_training"}
                        if all(math.dist(a["ref"], anchor["ref"]) > 0.015 for a in anchors[name]):
                            anchors[name].append(anchor)
                if i % 50 == 0:
                    print(f"  Sjekket {i}/{len(selected)} · {len(measurements)} felt funnet", flush=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            report = {"timestamp": stamp, "url": url, "arena": "koteng_arena",
                      "region_method": method, "map_region": region,
                      "checked_points": len(selected), "found_sections": measurements,
                      "capacity_conflicts": conflicts, "coordinate_system": "map_normalized",
                      "map_full_coverage_verified": False,
                      "approval": "NOT_APPROVED_NO_PUBLICATION"}
            report_path = output / (stamp + "_training.json")
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if conflicts:
                print("ADVARSEL: Kapasitetskonflikter. Ingen profil blir godkjent.")
            if not measurements:
                print("Ingen felter kunne leses. Kontroller at kartet er synlig og viser felt-tooltip.")
            elif profile_file.exists():
                print("Eksisterende Koteng-profil overskrives IKKE automatisk:", profile_file)
                print("Ny diagnostikk:", report_path)
            else:
                profile = StadiumProfile("koteng_arena", 1, "vivenu",
                                         {k:v["capacity"] for k,v in measurements.items()},
                                         dict(anchors), False)
                profile.save(profile_file)
                print("LAGRET PROFILUTKAST:", profile_file)
            print(f"Resultat: {len(measurements)} observerte felt; {len(conflicts)} kapasitetskonflikter.")
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
