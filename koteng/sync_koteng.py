"""Read-only Koteng V1.8 diagnostic -> private, pending Ministaut scan.
Never changes the locked scanner, seat references or publication flags.
"""
from __future__ import annotations
import hashlib,json,os,re,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parent
ENDPOINT='https://khetbokxbcujwcurvviu.supabase.co/functions/v1/ministaut-koteng-ingest'
EVENT='6aaceecebfe408c38e1712dd'
VERSION='koteng-v1.8-geometry-locked-20261026'
CAP={'VIP':71,'FELT-1':49,'FELT-2':160,'FELT-3':120,'FELT-4':152,'FELT-5':49}

def build_payload(path:Path)->dict:
    from profile_lock import load_verified_lock
    profile_path=ROOT/'koteng_profile.json'
    anchors_path=ROOT/'ankerpunkter_koteng.json'
    profile=json.loads(profile_path.read_text(encoding='utf-8'))
    if profile.get('profile_version')!=VERSION or profile.get('local_profile_lock',{}).get('state')!='LOCKED':
        raise ValueError('Koteng V1.8 profil er ikke låst')
    _, lock_digest=load_verified_lock(profile,anchors_path,EVENT)
    if profile.get('reference_sections')!=CAP:raise ValueError('Kapasitet stemmer ikke med låst profil')
    d=json.loads(Path(path).read_text(encoding='utf-8'))
    if (d.get('profile_lock') or {}).get('digest_sha256')!=lock_digest:
        raise ValueError('Skanningsfilens profil-SHA256 stemmer ikke med gjeldende lås')
    if d.get('network_publication') is not False:
        raise ValueError('Uventet aktiv skannerpublisering')
    v=d.get('validation') or {}
    if d.get('event_key')!=EVENT or d.get('venue_id')!='koteng_arena' or d.get('profile_version')!=VERSION:
        raise ValueError('Feil kamp, arena eller Koteng-profil')
    if v.get('quality_status')!='LOCKED_LOCAL_VERIFIED' or v.get('local_seated_coverage_verified') is not True or v.get('two_read_coverage_complete') is not True:
        raise ValueError('Ingen komplett, lokal godkjent felttelling')
    if v.get('errors') or v.get('conflicts') or v.get('missing_sections') or v.get('unknown_sections'):
        raise ValueError('Kvalitetsavvik: data kan ikke lastes opp')
    sections=v.get('sections') or {}
    if set(sections)!=set(CAP) or any(sections[s].get('capacity')!=CAP[s] for s in CAP):
        raise ValueError('Seks felt og kapasitet må samsvare med låst profil')
    rows=[]
    for name,cap in CAP.items():
        s=sections[name]
        observed=s.get('free')
        passes=s.get('verified_passes',[])
        if not isinstance(observed,int) or isinstance(observed,bool) or not 0<=observed<=cap:
            raise ValueError('Ugyldig ledighet: '+name)
        if len(set(passes))<2 or s.get('min_free')!=observed or s.get('max_free')!=observed:
            raise ValueError('Ustabil avlesning: '+name)
        rows.append({'section':name,'free':observed,'capacity':cap,'confirmed_passes':len(set(passes)),'min_free':observed,'max_free':observed})
    total=sum(s['free'] for s in rows)
    if total!=v.get('observed_available_in_verified_fields') or total!=v.get('observed_min') or total!=v.get('observed_max'):
        raise ValueError('Totalsummen samsvarer ikke')
    if v.get('locked_confirmed') or v.get('public_approved') is not False:
        raise ValueError('Uventet status for låst Koteng-profil')
    observed_at=d.get('scanned_at_utc')
    ts=datetime.fromisoformat(observed_at.replace('Z','+00:00'))
    if ts.utcoffset() is None:raise ValueError('Måling mangler UTC-tidssone')
    run=hashlib.sha256((EVENT+'|'+ts.astimezone(timezone.utc).isoformat()).encode()).hexdigest()[:40]
    return {'event_key':EVENT,'venue_id':'koteng_arena','profile_version':VERSION,
      'quality_status':'LOCKED_LOCAL_VERIFIED','two_read_coverage_complete':True,
      'local_seated_coverage_verified':True,'lock_integrity_verified':True,
      'public_approved':False,'reading_status':'pending',
      'ticket_category':d.get('selected_ticket_category') or 'ukjent',
      'source_run_id':run,'observed_at':ts.astimezone(timezone.utc).isoformat(),
      'reference_capacity_seated':601,'available_seated':total,
      'locked_fields':[],'sections':rows}

def submit(payload:dict)->dict:
    token=os.environ.get('MINISTAUT_TOKEN','').strip()
    private=ROOT/'.ministaut-token'
    if not token and private.exists():token=private.read_text(encoding='utf-8').strip()
    if not token:raise RuntimeError('MINISTAUT_TOKEN må angis lokalt, aldri i Git')
    request=Request(ENDPOINT,data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={
      'Content-Type':'application/json','x-ministaut-token':token},method='POST')
    try:
        with urlopen(request,timeout=25) as reply: result=json.load(reply)
    except HTTPError as error:
        raise RuntimeError('Supabase avviste innlesingen (HTTP '+str(error.code)+')') from error
    if result.get('ok') is not True or result.get('status')!='pending':
        raise RuntimeError('Mangler bekreftet privat innlesing')
    return result

def main(argv=None):
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('diagnostic',type=Path)
    ap.add_argument('--send',action='store_true',help='Last opp privat når MINISTAUT_TOKEN er konfigurert')
    args=ap.parse_args(argv)
    payload=build_payload(args.diagnostic)
    print('Kontrollert:',payload['available_seated'],'ledige,',len(payload['sections']),'felt. Offentlig: NEI')
    if args.send:
        response=submit(payload)
        print('Lagret privat som',response.get('status'),'scan_id:',response.get('scan_id'))
    else:print('Ingen overføring. Bruk --send først når autorisert token er konfigurert.')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:print('STOPP:',str(exc),file=sys.stderr);raise SystemExit(2)
