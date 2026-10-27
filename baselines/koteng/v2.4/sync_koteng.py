"""Koteng V1.8 -> Ministaut (observed availability only).
This sidecar never edits the locked scanner, training JSON or Lerkendal code.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from profile_lock import load_verified_lock

ROOT = Path(__file__).resolve().parent
ENDPOINT = 'https://khetbokxbcujwcurvviu.supabase.co/functions/v1/ministaut-koteng-ingest'
EVENT = '6aaceecebfe408c38e1712dd'
VERSION = 'koteng-v1.8-geometry-locked-20261026'
SECTIONS = {'VIP': 71, 'FELT-1': 49, 'FELT-2': 160, 'FELT-3': 120, 'FELT-4': 152, 'FELT-5': 49}

def verify_local_lock() -> str:
    profile = json.loads((ROOT / 'koteng_profile.json').read_text(encoding='utf-8'))
    if profile.get('profile_version') != VERSION:
        raise ValueError('Feil profilmotor: Bruk eksisterende fungerende Koteng V1.8')
    _, digest = load_verified_lock(profile, ROOT / 'ankerpunkter_koteng.json', EVENT)
    if profile.get('reference_sections') != SECTIONS:
        raise ValueError('Kapasitet er endret: stopp opplasting')
    return digest

def build_payload(path: Path) -> dict:
    digest = verify_local_lock()
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    v = d.get('validation') or {}
    if d.get('event_key') != EVENT or d.get('venue_id') != 'koteng_arena' or d.get('profile_version') != VERSION:
        raise ValueError('Feil arrangement eller profildata')
    if (d.get('profile_lock') or {}).get('digest_sha256') != digest:
        raise ValueError('Skanningsfilen og den låste profilens SHA256 samsvarer ikke')
    if d.get('network_publication') is not False:
        raise ValueError('Skanneren må fortsatt være isolert fra nettverkspublisering')
    if v.get('quality_status') != 'LOCKED_LOCAL_VERIFIED' or v.get('two_read_coverage_complete') is not True or v.get('local_seated_coverage_verified') is not True:
        raise ValueError('Skanningen er ikke kvalitetsgodkjent lokalt')
    if v.get('public_approved') is not False:
        raise ValueError('Forventet upublisert lokalrapport')
    if v.get('errors') or v.get('missing_sections') or v.get('conflicts') or v.get('unknown_sections'):
        raise ValueError('Rapporten inneholder feil eller ufullstendige felt')
    if v.get('counted_sections') != 6 or v.get('reference_sections') != 6 or v.get('locked_confirmed'):
        raise ValueError('Forventet seks avleste felt og ingen skjult lås')
    sections = v.get('sections') or {}
    if set(sections) != set(SECTIONS):
        raise ValueError('Ingen komplett dekning av VIP og fem sittefelt')
    payload_sections = []
    for name, capacity in SECTIONS.items():
        s = sections[name]
        free = s.get('free')
        passes = s.get('verified_passes') or []
        if (not isinstance(free, int) or isinstance(free, bool) or free < 0 or free > capacity
                or s.get('capacity') != capacity or len(set(passes)) < 2
                or s.get('min_free') != free or s.get('max_free') != free):
            raise ValueError('Ugyldig eller uenhetlig avlesning: ' + name)
        payload_sections.append(dict(section=name, free=free, capacity=capacity,
                                     confirmed_passes=len(set(passes)), min_free=free, max_free=free))
    available = sum(r['free'] for r in payload_sections)
    if any(v.get(k) != available for k in ('observed_available_in_verified_fields', 'observed_min', 'observed_max')):
        raise ValueError('Sum stemmer ikke med rapporten')
    time_str = d.get('scanned_at_utc')
    stamp = datetime.fromisoformat(str(time_str).replace('Z', '+00:00'))
    if stamp.utcoffset() is None:
        raise ValueError('Måling mangler UTC-tidssone')
    stamp = stamp.astimezone(timezone.utc)
    source_run_id = hashlib.sha256((EVENT + '|' + stamp.isoformat()).encode()).hexdigest()[:40]
    return dict(event_key=EVENT, venue_id='koteng_arena', profile_version=VERSION,
                quality_status='LOCKED_LOCAL_VERIFIED', two_read_coverage_complete=True,
                local_seated_coverage_verified=True, lock_integrity_verified=True,
                public_approved=False, reading_status='pending',
                ticket_category=d.get('selected_ticket_category') or 'ukjent',
                observed_at=stamp.isoformat(), source_run_id=source_run_id,
                available_seated=available, reference_capacity_seated=601,
                locked_fields=[], sections=payload_sections)

def send(payload: dict) -> dict:
    token = os.environ.get('MINISTAUT_TOKEN', '').strip()
    token_path = ROOT / '.ministaut-token'
    if not token and token_path.is_file():
        token = token_path.read_text(encoding='utf-8-sig').strip()
    if not re.fullmatch(r'(?:[a-f0-9]{64}|[A-Za-z0-9_-]{30,200})', token):
        raise RuntimeError('Mangler gyldig MINISTAUT_TOKEN / privat .ministaut-token')
    request = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                      headers={'Content-Type': 'application/json', 'x-ministaut-token': token}, method='POST')
    try:
        with urlopen(request, timeout=30) as response:
            value = json.load(response)
    except HTTPError as err:
        raise RuntimeError('Mottaker avviste skanningen med HTTP ' + str(err.code)) from err
    except URLError as err:
        raise RuntimeError('Nettverksfeil: Kun lokal rapport er bevart') from err
    if value.get('ok') is not True or value.get('status') != 'observed':
        raise RuntimeError('Innlesing ikke bekreftet av Supabase')
    return value

def main(argv=None):
    parser = argparse.ArgumentParser(description='Valider og eventuelt send Koteng V1.8 lokalmåling')
    parser.add_argument('diagnostic', type=Path)
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args(argv)
    payload = build_payload(args.diagnostic)
    print('KOTENG LOKALKONTROLL: OK')
    print('Felt:', len(payload['sections']), 'Ledige:', payload['available_seated'])
    if args.send:
        result = send(payload)
        print('SUPABASE:', result['status'], '| ID:', result.get('scan_id'))
        print('VERIFISERT OBSERVASJON: Publisert i RBK Kvinner / Koteng Arena.')
    else:
        print('Testmodus. Ingen data sendt. Bruk --send for publisering av observerte sitteplasser.')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('STOPP:', exc, file=sys.stderr)
        raise SystemExit(2)
