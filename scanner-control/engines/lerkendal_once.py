"""One unattended Lerkendal scan with the UNCHANGED V23 engine (hurtigkart.py).

Run with the engine's Python, cwd = the engine folder (a separate copy owned by
the control program, never the production folder):

    python lerkendal_once.py --url <checkout> --port 9231 --report <file.json>

What this wrapper changes, from the outside only:
- the "press ENTER when the map is visible" prompt waits for the map instead;
- the engine's own Supabase upload is blocked; publishing happens later from
  the control program's outbox, and only after its own re-verification;
- the page must show the requested checkout event before counting starts;
- exactly one automatic cycle (first + rescue phase), then exit.
Everything else (60-field model, hover sampling, locked away sections, map
structure check, large-change gate, history) is the engine's own code.

Exit codes: 0 = complete scan that passed the engine's quality gate,
4 = scan finished but rejected by the quality gate, 2 = technical stop.
"""
from __future__ import annotations
import argparse
import builtins
import json
from pathlib import Path
import sys
import time

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))


def newest_output(after: float) -> Path | None:
    runs = [p for p in (ROOT / 'output').glob('*/resultat.json') if p.stat().st_mtime >= after]
    return max(runs, key=lambda p: p.stat().st_mtime).parent if runs else None


def dismiss_cookie_banner(page):
    """A fresh Edge profile shows a consent dialog over the lower map (fields
    C-J). Choose the minimal option once; it is remembered in this profile.
    This is the step an operator did before pressing ENTER. No ticket clicks."""
    for label in ('Bare nødvendig', 'Only necessary'):
        try:
            button = page.get_by_role('button', name=label)
            if button.count() and button.first.is_visible():
                button.first.click(timeout=3000)
                page.wait_for_timeout(900)
                print('Informasjonskapsler: valgte «' + label + '»', flush=True)
                return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--port', type=int, default=9231)
    ap.add_argument('--report', type=Path, required=True)
    ap.add_argument('--map-wait', type=float, default=6.0)
    args = ap.parse_args()

    import hurtigkart
    import sync_ministaut
    from publication import event_key, validate_complete
    from verified_navigation import verify_event

    wanted = event_key(args.url)
    if args.port == 9222:
        raise SystemExit('Port 9222 tilhører produksjonsskanneren; bruk en egen port.')

    def blocked_upload(_path):
        raise RuntimeError('Publisering skjer fra kontrollsenterets utboks etter etterkontroll')
    sync_ministaut.upload = blocked_upload

    def wait_for_map(prompt=''):
        print('Automatisk: venter', args.map_wait, 's på at billettkartet er ferdig tegnet', flush=True)
        time.sleep(args.map_wait)
        return ''
    builtins.input = wait_for_map

    original_install = hurtigkart.panel_install
    checked = {'done': False}

    def install_after_event_check(page):
        if not checked['done']:
            verify_event(page, args.url)  # never count another fixture's map
            checked['done'] = True
            print('Kamp verifisert i Edge:', wanted, flush=True)
            dismiss_cookie_banner(page)
        return original_install(page)
    hurtigkart.panel_install = install_after_event_check

    started = time.time()
    sys.argv = ['hurtigkart.py', '--url', args.url, '--port', str(args.port),
                '--no-auto', '--manual-seconds', '1']
    code = hurtigkart.main()
    out = newest_output(started)
    report = {'event_key': wanted, 'engine_exit': code, 'output_dir': str(out) if out else None,
              'accepted': False, 'reason': ''}
    if code != 0 or out is None:
        report['reason'] = 'Motoren avsluttet uten resultat (kode %s)' % code
    else:
        result = json.loads((out / 'resultat.json').read_text(encoding='utf-8'))
        ok, why = validate_complete(result)
        alert = out / 'kvalitetsvarsel_v18.json'
        if result.get('url', '').rstrip('/') != args.url.rstrip('/'):
            ok, why = False, 'Resultatet gjelder en annen URL'
        elif ok and alert.is_file():
            ok, why = False, 'Stor endring krever manuell godkjenning (kvalitetsvarsel_v18.json)'
        report.update(accepted=ok, reason=why, time_utc=result.get('time_utc'),
                      available_seated=result.get('free_confirmed_fields'),
                      captured_fields=result.get('captured_fields'),
                      locked_fields=result.get('locked_fields', []))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Kontrollresultat:', 'GODKJENT' if report['accepted'] else 'AVVIST', report['reason'], flush=True)
    if report['output_dir'] is None or code != 0:
        return 2
    return 0 if report['accepted'] else 4


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print('STOPP:', type(exc).__name__, str(exc)[:300], file=sys.stderr, flush=True)
        raise SystemExit(2)
