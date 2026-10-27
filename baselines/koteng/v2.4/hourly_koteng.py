"""Hourly Koteng Edge runner. Scans only until kickoff, never modifies Lerkendal."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import time
from sync_koteng import EVENT, ROOT, build_payload, send, verify_local_lock

KICKOFF = datetime(2026, 11, 1, 13, 30, tzinfo=timezone.utc)


def run_once(*, upload: bool = False) -> dict:
    verify_local_lock()
    diagnostic_root = ROOT / 'diagnostikk' / EVENT
    existing = set(diagnostic_root.glob('*/diagnostikk.json'))
    print('Koteng: starter låst Edge-telling', datetime.now(timezone.utc).isoformat(), flush=True)
    result = subprocess.run([sys.executable, str(ROOT / 'koteng_scanner.py'), '--no-pause'],
                            cwd=ROOT, timeout=1200, check=False)
    if result.returncode != 0:
        raise RuntimeError('Skanner returnerte feil. Ingen data er overført.')
    current = set(diagnostic_root.glob('*/diagnostikk.json')) - existing
    if len(current) != 1:
        raise RuntimeError('Forventet én fersk diagnostikk; fikk ' + str(len(current)))
    item = next(iter(current))
    payload = build_payload(item)
    print('Kontroll OK: ', payload['available_seated'], 'observerte ledige på', len(payload['sections']), 'felt', flush=True)
    if upload:
        confirmation = send(payload)
        print('Ministaut LIVE: offentlig observert telling registrert:', confirmation['status'], flush=True)
    else:
        print('Kun lokal test - ingenting sendt', flush=True)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Én skanning nå')
    parser.add_argument('--upload', action='store_true', help='Send kun dobbeltkontrollerte Koteng-tellinger som observerte ledige sitteplasser')
    args = parser.parse_args(argv)
    verify_local_lock()
    if args.upload and not (os.environ.get('MINISTAUT_TOKEN') or (ROOT / '.ministaut-token').exists()):
        raise RuntimeError('Token mangler. Kontroller MINISTAUT_TOKEN eller .ministaut-token.')
    while datetime.now(timezone.utc) < KICKOFF:
        started = time.monotonic()
        try:
            run_once(upload=args.upload)
        except Exception as error:
            print('Skanning stoppet/avvist:', str(error), file=sys.stderr, flush=True)
            if args.once:
                raise RuntimeError('Testen feilet; ingen data er publisert') from error
        if args.once:
            break
        remaining = (KICKOFF - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            break
        pause = min(remaining, max(5, 3600 - (time.monotonic() - started)))
        print('Neste skanning om ca.', int(pause / 60), 'min', flush=True)
        time.sleep(pause)
    print('Koteng: kampstart eller enkeltkjøring nådd. Stoppet.', flush=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Manuelt stoppet')
    except Exception as error:
        print('STOPP:', str(error), file=sys.stderr)
        raise SystemExit(2)
