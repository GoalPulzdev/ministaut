"""One unattended Koteng Arena scan for ANY approved match, with the locked engine.

Run with the engine's Python, cwd = the Koteng engine folder:

    python koteng_once.py --url <checkout> --report <file.json>

The Koteng V1.8 profile lock covers the stadium itself: six section
capacities, standing exclusions, CSS viewport, map region, page zoom and the
manually anchored points, sealed with SHA-256 for the match it was trained on
(Rosenborg-Røa). This wrapper keeps that lock exactly as it is and verifies it
on every run against the files on disk. What it adds:

- a list of approved matches (godkjente_kamper.json, written by Scanner
  Control when the operator adds a match); unknown matches are refused;
- a temporary profile copy that adds the approved match's event config, so the
  unchanged scanner can run it; the sealed geometry is never touched;
- the same diagnostic/payload checks as sync_koteng.build_payload, per match.

Every scan still has to pass the scanner's own geometry check (viewport within
8 px, map region within 12 px, zoom within 0.015) and 6/6 sections in two
independent passes. A match whose map differs from the locked one is rejected.

Exit codes: 0 = verified scan, 4 = finished but rejected, 2 = technical stop.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
REGISTRY = ROOT / 'godkjente_kamper.json'
GEOMETRY_KEYS = ('venue_id', 'profile_version', 'reference_sections', 'standing_sections',
                 'local_profile_lock', 'map_full_coverage_verified')


def approved(key: str) -> dict:
    try:
        data = json.loads(REGISTRY.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    entry = data.get(key)
    if not isinstance(entry, dict) or entry.get('venue_id') != 'koteng_arena':
        raise SystemExit('Kampen er ikke godkjent for Koteng i Scanner Control (' + key + ')')
    return entry


def install_multi_event(key: str):
    """Patch lock verification + payload identity in the loaded engine modules."""
    import profile_lock
    import sync_koteng
    original = json.loads((ROOT / 'koteng_profile.json').read_text(encoding='utf-8'))
    base_event = original['local_profile_lock']['event_key']
    real_verify = profile_lock.load_verified_lock

    def verified_stadium_lock(profile, anchor_path, event):
        # The sealed stadium lock is ALWAYS verified on the original files.
        anchors, digest = real_verify(original, ROOT / 'ankerpunkter_koteng.json', base_event)
        if Path(anchor_path).resolve() != (ROOT / 'ankerpunkter_koteng.json').resolve():
            raise ValueError('Bare de låste Koteng-ankerne kan brukes')
        if any(profile.get(k) != original.get(k) for k in GEOMETRY_KEYS):
            raise ValueError('Profilkopien avviker fra den låste stadionprofilen')
        if event != base_event and event != key:
            raise ValueError('Uventet kamp i låskontroll')
        return anchors, digest

    profile_lock.load_verified_lock = verified_stadium_lock
    sync_koteng.load_verified_lock = verified_stadium_lock
    sync_koteng.EVENT = key
    try:
        import koteng_scanner
        koteng_scanner.load_verified_lock = verified_stadium_lock
    except ImportError:
        koteng_scanner = None
    return original, koteng_scanner, sync_koteng


def profile_for(original: dict, key: str, entry: dict) -> dict:
    profile = json.loads(json.dumps(original))
    base = profile['event_configs'][original['local_profile_lock']['event_key']]
    profile['event_configs'][key] = {
        **base, 'checkout_url': 'https://billett.rbk.no/checkout/' + key,
        'venue_confirmation': entry.get('approved_by', 'scanner_control'),
        'locked_sections': [], 'locked_confirmation': None,
        'selected_ticket_category': entry.get('ticket_category', 'ukjent')}
    return profile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    from koteng_scanner import event_key
    key = event_key(args.url)
    original = json.loads((ROOT / 'koteng_profile.json').read_text(encoding='utf-8'))
    if key != original['local_profile_lock']['event_key']:
        entry = approved(key)
    else:
        entry = {'ticket_category': original['event_configs'][key].get('selected_ticket_category', 'ukjent')}
    original, scanner, sync = install_multi_event(key)
    root = ROOT / 'diagnostikk' / key
    before = set(root.glob('*/diagnostikk.json'))
    with tempfile.TemporaryDirectory() as tmp:
        prof = Path(tmp) / 'koteng_profile_aktiv.json'
        prof.write_text(json.dumps(profile_for(original, key, entry), ensure_ascii=False), encoding='utf-8')
        argv = ['--url', args.url, '--profile', str(prof), '--no-pause', '--output', str(ROOT / 'diagnostikk')]
        code = scanner.main(argv) if 'argv' in scanner.main.__code__.co_varnames else _run_cli(scanner, argv)
    fresh = set(root.glob('*/diagnostikk.json')) - before
    report = {'event_key': key, 'engine_exit': code, 'accepted': False, 'reason': '',
              'diagnostic': str(next(iter(fresh))) if len(fresh) == 1 else None}
    if code not in (0, None) or len(fresh) != 1:
        report['reason'] = f'Skanneren stoppet (kode {code}, {len(fresh)} nye diagnostikker)'
        _write(args.report, report)
        return 2 if len(fresh) != 1 else 4
    try:
        payload = sync.build_payload(Path(report['diagnostic']))
        report.update(accepted=True, available_seated=payload['available_seated'],
                      observed_at=payload['observed_at'], run_id=payload['source_run_id'])
    except ValueError as exc:
        report['reason'] = str(exc)
    _write(args.report, report)
    print('Kontrollresultat:', 'GODKJENT' if report['accepted'] else 'AVVIST', report['reason'], flush=True)
    return 0 if report['accepted'] else 4


def _run_cli(scanner, argv):
    old = sys.argv
    sys.argv = ['koteng_scanner.py', *argv]
    try:
        return scanner.main()
    except SystemExit as exc:
        return exc.code
    finally:
        sys.argv = old


def _write(path: Path, report: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print('STOPP:', type(exc).__name__, str(exc)[:300], file=sys.stderr, flush=True)
        raise SystemExit(2)
