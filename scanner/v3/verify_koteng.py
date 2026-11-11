"""Fast Koteng verification of SIX already learned seated sections.

Reads public tooltip values via Microsoft Edge. It never buys/reserves seats,
publishes to Supabase, or scans Lerkendal. Missing readings are NOT zero.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from v3.learn_koteng import KOTENG_URL, parse_visible, cookie_overlay, focused_koteng_region
from v3.profiles import StadiumProfile
from v3.koteng_reference import EXPECTED_SEATED, TOTAL_SEATED, validate_koteng_profile

# Original viewport-specific region was recorded by the first real Koteng
# training report on 24 Oct 2026. Never mix these with the V2 normalized space.
V1_FIRST_TRAINING_REGION = (5.0, 423.75, 1590.0, 950.0)
VIEWPORT = {"width": 1600, "height": 960}


def profile_location(explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise ValueError("Cannot find the supplied Koteng profile: " + str(path))
        return path
    folder = ROOT / "v3_profiles"
    errors = []
    for name in ("koteng_arena.v2.json", "koteng_arena.v1.json"):
        candidate = folder / name
        if candidate.is_file():
            try:
                validate_koteng_profile(StadiumProfile.load(candidate))
                return candidate
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"{name}: {exc}")
    if errors:
        raise ValueError("Ingen komplett Koteng-profil med 6 felt: " + "; ".join(errors))
    raise FileNotFoundError(
        "Ingen Koteng-profil funnet. Kopier koteng_arena.v1.json fra den "
        "forste fungerende opplaeringsmappen til scanner/v3_profiles/."
    )


def region_from_profile(page, profile):
    if profile.version == 1:
        return V1_FIRST_TRAINING_REGION, "original_training_v1_1600x960"
    if profile.version == 2:
        return focused_koteng_region(page)
    raise ValueError("Unknown map coordinate version")


def position(anchor, region):
    if not isinstance(anchor, dict):
        raise ValueError("Invalid saved hover point")
    x1, y1, x2, y2 = region
    fx, fy = anchor["ref"]
    if not 0 <= fx <= 1 or not 0 <= fy <= 1:
        raise ValueError("Invalid normalized Koteng hover point")
    return round(x1 + fx*(x2-x1)), round(y1 + fy*(y2-y1))


def fresh_stable_reading(page, section, positions, wait_ms=110):
    """Two stable visible-tooltip reads per point and a neutral baseline.

    Rejected stale tooltips cannot masquerade as data from the new hover.
    """
    viewport = page.viewport_size or VIEWPORT
    for x, y in positions:
        page.mouse.move(viewport["width"]-15, viewport["height"]-15)
        page.wait_for_timeout(120)
        before = {(v.section, v.capacity, v.free)
                  for v in parse_visible(page, -1, -1)}
        page.mouse.move(x, y)
        page.wait_for_timeout(wait_ms)
        first = {(v.section, v.capacity, v.free): v
                 for v in parse_visible(page, x, y)}
        page.wait_for_timeout(wait_ms)
        second = {(v.section, v.capacity, v.free): v
                  for v in parse_visible(page, x, y)}
        stable = [(signature, value) for signature, value in second.items()
                  if signature in first and signature not in before
                  and value.section == section]
        # A changed field capacity is a real anomaly, not a new baseline.
        if stable:
            return stable[0][1]
    return None


def verify(profile_path=None, passes=2):
    path = profile_location(profile_path)
    profile = validate_koteng_profile(StadiumProfile.load(path))
    output = ROOT / "v3_learning" / "koteng_arena"
    output.mkdir(parents=True, exist_ok=True)
    print("KOTENG: VERIFISER 6 KJENTE SITTEFELT – INGEN NY OPPDAGELSE")
    print("Innlert profil:", path)
    print("Bekreftet feltsum:", TOTAL_SEATED, "(ikke total stadionkapasitet)")
    print("Alle avlesninger forblir lokale. Ståplass A er ikke med.")
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "edge_koteng_training_profile"),
            channel="msedge", headless=False, viewport=VIEWPORT,
            args=["--no-first-run"]
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(KOTENG_URL, wait_until="domcontentloaded", timeout=45000)
            print("Lukk eventuelt personvernbanner i Edge, og vis stadionkartet.")
            input("Nar kartet med Felt 1–5 og VIP synes, trykk ENTER her: ")
            if cookie_overlay(page):
                raise RuntimeError("Personvernbanneret dekker kartet. Lukk det manuelt.")
            region, method = region_from_profile(page, profile)
            observed = {section: [] for section in EXPECTED_SEATED}
            for number in range(passes):
                print("Kontrollrunde", number+1, "av", passes)
                names = list(EXPECTED_SEATED)
                if number % 2:
                    names.reverse()
                for section in names:
                    points = [position(anchor, region)
                              for anchor in profile.anchors[section]]
                    hit = fresh_stable_reading(page, section, points)
                    if not hit:
                        print("  !", section, "ikke bekreftet")
                        continue
                    if hit.capacity != EXPECTED_SEATED[section]:
                        print("  !", section, "KAPASITETSAVVIK", hit.capacity,
                              "mot", EXPECTED_SEATED[section])
                        observed[section].append({
                            "free": hit.free, "capacity": hit.capacity, "quality": "capacity_mismatch"})
                        continue
                    observed[section].append({
                        "free": hit.free, "capacity": hit.capacity, "quality": "observed"})
                    print("  +", section, hit.free, "/", hit.capacity)
            complete = all(
                len(observed[name]) == passes
                and all(x["quality"]=="observed" for x in observed[name])
                for name in EXPECTED_SEATED
            )
            # A single run may observe minor changes while tickets move. This
            # is not proof of confirmed sales; reject large intra-run swings.
            unstable = {
                name: [x["free"] for x in values]
                for name, values in observed.items()
                if len(values) == passes and max(x["free"] for x in values)
                - min(x["free"] for x in values) > 2
            }
            accepted = complete and not unstable
            last_reading = {
                name: values[-1]["free"] for name, values in observed.items()
                if len(values)==passes and all(x["quality"]=="observed" for x in values)
            }
            now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            report = {
                "timestamp": now,
                "arena": "koteng_arena",
                "source_profile": str(path),
                "profile_version": profile.version,
                "event_url": KOTENG_URL,
                "method": "two_pass_saved_hover_points",
                "map_region": list(region),
                "region_method": method,
                "expected_seated": EXPECTED_SEATED,
                "observations": observed,
                "missing_or_invalid": sorted(set(EXPECTED_SEATED)-set(last_reading)),
                "unstable_readings": unstable,
                "readings_complete": accepted,
                "available_seated_if_complete": sum(last_reading.values()) if accepted else None,
                "total_seated_in_six_areas": TOTAL_SEATED,
                "standing_a": "not_measured",
                "publication": "LOCAL_TEST_ONLY_NEVER_UPLOADED",
            }
            target = output / (now + "_six_fields_verification.json")
            target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print("\n", "6/6 DOBBELTKONTROLLERT" if accepted else
                  "IKKE FULLSTENDIG – trenger justering av innlerte punkter")
            if accepted:
                print("Ledige sitteplasser:", sum(last_reading.values()))
            print("Rapport:", target)
            return accepted
        finally:
            context.close()


def main():
    parser = argparse.ArgumentParser(
        description="Verify only Koteng's six previously learned seating sections"
    )
    parser.add_argument("--profile", default=None)
    parser.add_argument("--passes", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.passes <= 5:
        parser.error("passes must be between 1 and 5")
    success = verify(args.profile, args.passes)
    if not success:
        raise SystemExit(2)


if __name__=="__main__":
    main()
