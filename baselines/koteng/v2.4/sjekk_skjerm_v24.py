"""Display check for new Koteng Windows computers; no browser/network activity."""
from __future__ import annotations
import json
from pathlib import Path
from koteng_scanner import windows_primary_work_area, work_area_fits_locked_edge, locked_edge_context_options
from profile_lock import load_verified_lock
ROOT=Path(__file__).resolve().parent
EVENT='6aaceecebfe408c38e1712dd'

def main():
    profile=json.loads((ROOT/'koteng_profile.json').read_text(encoding='utf-8'))
    anchors,digest=load_verified_lock(profile,ROOT/'ankerpunkter_koteng.json',EVENT)
    viewport=locked_edge_context_options(anchors)['viewport']
    required=(viewport['width'],viewport['height'])
    work_area=windows_primary_work_area()
    print('KOTENG V2.4 - KONTROLL AV DENNE PC-ENS SKJERM')
    print('Laast profil verifisert, SHA256:',digest[:16]+'...')
    print('Edge innholdsvindu:',required[0],'x',required[1],'CSS-piksler')
    if work_area is None:
        print('Kunne ikke lese Windows-skrivebord. Edge-sjekk skjer under lokal test.')
        return 0
    print('Brukbart hovedskjermareal:',work_area[0],'x',work_area[1])
    print('Anbefalt minimum inkl. vindusramme:',required[0]+12,'x',required[1]+85)
    if not work_area_fits_locked_edge(work_area,required):
        print('STOPP: Skjermen har ikke plass til laast kartvisning med gjeldende skalering.')
        print('Proev Windows Innstillinger -> System -> Skjerm -> Skalering 100%, eller stoerre skjerm.')
        print('Ingen koordinater eller profiler endres.')
        return 2
    print('OK: Skjermen har trolig plass. Kjoer 02_TEST_EN_GANG.bat for virkelig kartkontroll.')
    print('Denne skjermtesten alene godkjenner IKKE live telling.')
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('STOPP:',exc)
        raise SystemExit(2)
