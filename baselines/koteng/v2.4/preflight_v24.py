"""Offline first-run checks; never sends scanner data or modifies the locked profile."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parent
KEY='6aaceecebfe408c38e1712dd'

def edge_candidates() -> list[Path]:
    dirs=[os.environ.get('PROGRAMFILES(X86)'),os.environ.get('PROGRAMFILES'),os.environ.get('LOCALAPPDATA')]
    return [Path(d)/'Microsoft'/'Edge'/'Application'/'msedge.exe' for d in dirs if d]

def check(require_token:bool=False,check_deps:bool=True)->bool:
    failed=[]
    print('KOTENG 2.4 - FORHÅNDSKONTROLL')
    if sys.version_info<(3,10):failed.append('Python 3.10 eller nyere er nødvendig')
    for name in ('koteng_scanner.py','anchor_scan.py','anchor_training.py','profile_lock.py',
                 'koteng_profile.json','ankerpunkter_koteng.json',
                 'hourly_koteng.py','sync_koteng.py'):
        if not (ROOT/name).is_file():failed.append('Mangler fil: '+name)
    if (ROOT/'koteng_profile.json').exists() and (ROOT/'ankerpunkter_koteng.json').exists():
        try:
            import json
            from profile_lock import load_verified_lock
            profile=json.loads((ROOT/'koteng_profile.json').read_text(encoding='utf-8'))
            anchors,digest=load_verified_lock(profile,ROOT/'ankerpunkter_koteng.json',KEY)
            if anchors.get('reference_viewport') != [1294,642]:
                failed.append('Ikke forventet låst Edge-vindu (1294 x 642 CSS-piksler)')
            if profile.get('reference_sections') != {'VIP':71,'FELT-1':49,'FELT-2':160,'FELT-3':120,'FELT-4':152,'FELT-5':49}:
                failed.append('Seksjonskapasitet avviker fra godkjent profil')
            print('Profil: LOCKED, SHA256',digest[:16]+'...')
            print('Edge referansevindu: 1294 x 642 CSS-piksler, sidezoom 90 %')
        except Exception as e: failed.append('Profilkontroll feilet: '+str(e))
    if os.name=='nt' and not any(p.is_file() for p in edge_candidates()):
        failed.append('Microsoft Edge er ikke funnet. Installer Edge via Microsoft.')
    if check_deps:
        try:import playwright.sync_api  # noqa: F401
        except ImportError:failed.append('Playwright mangler. Kjør 01_INSTALLER.bat.')
        try:import PIL  # noqa: F401
        except ImportError:failed.append('Pillow mangler. Kjør 01_INSTALLER.bat.')
    token_path=ROOT/'.ministaut-token'
    if require_token:
        token=os.environ.get('MINISTAUT_TOKEN','').strip()
        if not token and token_path.exists():token=token_path.read_text(encoding='utf-8-sig').strip()
        if not re.fullmatch(r'(?:[a-f0-9]{64}|[A-Za-z0-9_-]{30,200})',token):
            failed.append('Ministaut-token mangler/er ugyldig. Kjør 03_KONFIGURER_TOKEN.bat (eller kopier fra gammel PC).')
        else:print('Opplastingstoken: format gyldig (autorisering kontrolleres ved sending)')
    if failed:
        print('\nSTOPP:')
        for item in failed:print(' -',item)
        return False
    print('OK: nødvendige filer og låst profil er på plass. Lerkendal påvirkes ikke.')
    print('V2.4 bruker laast Edge-innhold 1294x642 uavhengig av fysisk skjermopploesning.')
    print('En skjerm som er for liten, eller endret billettkartgeometri, avvises sikkert.')
    return True

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--require-token',action='store_true')
    p.add_argument('--no-deps',action='store_true')
    args=p.parse_args()
    raise SystemExit(0 if check(args.require_token,not args.no_deps) else 2)
