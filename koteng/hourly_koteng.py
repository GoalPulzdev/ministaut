"""Isolated hourly Koteng monitor. Never schedules or modifies Lerkendal.
Use V1.8 locked scanner. Reports remain private until explicit admin approval.
"""
from __future__ import annotations
import argparse,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from sync_koteng import build_payload,submit

ROOT=Path(__file__).resolve().parent
KICKOFF=datetime(2026,11,1,13,30,tzinfo=timezone.utc)
EVENT='6aaceecebfe408c38e1712dd'

def newest(previous:set[Path])->Path:
    paths=set((ROOT/'diagnostikk'/EVENT).glob('*/diagnostikk.json'))
    fresh=paths-previous
    if len(fresh)!=1:raise RuntimeError('Forventet én ny diagnostikk; fant '+str(len(fresh)))
    return next(iter(fresh))

def cycle(*,upload:bool)->None:
    previous=set((ROOT/'diagnostikk'/EVENT).glob('*/diagnostikk.json'))
    cmd=[sys.executable,str(ROOT/'koteng_scanner.py'),'--no-pause']
    print('Starter ny låst Koteng-skanning',datetime.now(timezone.utc).isoformat(),flush=True)
    completed=subprocess.run(cmd,cwd=ROOT,check=False,timeout=900)
    if completed.returncode!=0:raise RuntimeError('Skanneren feilet. Resultat forkastes.')
    diagnostic=newest(previous)
    payload=build_payload(diagnostic)
    print('Verifisert:',payload['available_seated'],'ledige i seks felt.',flush=True)
    if upload:
        result=submit(payload)
        print('Lagret privat:',result['status'],result.get('scan_id'),flush=True)
    else:print('Ingen opplasting (testmodus).',flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--upload',action='store_true',help='Krever lokal MINISTAUT_TOKEN')
    ap.add_argument('--once',action='store_true')
    args=ap.parse_args()
    if args.upload and not (os.environ.get('MINISTAUT_TOKEN') or (ROOT/'.ministaut-token').exists()):
        raise RuntimeError('Privat token mangler; ingen opplasting startet')
    while datetime.now(timezone.utc)<KICKOFF:
        began=time.monotonic()
        try:cycle(upload=args.upload)
        except Exception as e:print('Kvalitetsstopp:',str(e),file=sys.stderr,flush=True)
        if args.once:break
        delay=max(0,3600-(time.monotonic()-began))
        remaining=(KICKOFF-datetime.now(timezone.utc)).total_seconds()
        if remaining<=0:break
        print('Neste kontroll om',round(min(delay,remaining)/60),'min',flush=True)
        time.sleep(min(delay,remaining))
    print('Kampstart passert / enkeltkjøring ferdig. Ingen flere skanninger.')
if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('Stoppet manuelt.')
    except Exception as e:print('STOPP:',str(e),file=sys.stderr);raise SystemExit(2)
