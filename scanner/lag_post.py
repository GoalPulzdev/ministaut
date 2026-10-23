"""Render public graphics from a previously completed read-only scan."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from publication import publish,validate_complete

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description='Generer delbar status (4:5 og Story) fra resultat.json')
    p.add_argument('--input',required=True)
    p.add_argument('--output',default='')
    p.add_argument('--approve-large-change',action='store_true',help='Godkjenn en kontrollert endring over 1000 seter')
    args=p.parse_args()
    data=json.loads(Path(args.input).read_text(encoding='utf-8'))
    ok,reason=validate_complete(data)
    if not ok:
        print('Ikke publiserbart:',reason)
        return 2
    out=(Path(args.output) if args.output else ROOT/'output'/('delingspost_'+datetime.now().strftime('%Y%m%d_%H%M%S')))
    try:from playwright.sync_api import sync_playwright
    except ImportError:
        print('Mangler Playwright. Kjør INSTALLER.bat.')
        return 2
    import os
    with sync_playwright() as pw:
        opt={'headless':True}
        if sys.platform.startswith('win'):
            opt['channel']='msedge'
        elif Path('/usr/bin/chromium').exists():
            opt['executable_path']='/usr/bin/chromium'
            opt['args']=['--no-sandbox']
        b=pw.chromium.launch(**opt)
        try:info=publish(data,out,ROOT/'historikk',browser=b,source='historisk_import',approve_large_change=args.approve_large_change)
        finally:b.close()
    if info['published']:
        print('Delbar post er laget:')
        for name in info['files']:print(name)
        return 0
    print('Ingen bilder:',info['reason'])
    return 2

if __name__=='__main__':raise SystemExit(main())