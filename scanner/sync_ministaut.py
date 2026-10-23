"""Upload one quality-approved V20 result to Ministaut (run from V20 folder).

Only upload confirmed final results; never upload partial runs. Tokens are stored
locally in MINISTAUT_TOKEN env var or a private .ministaut-token file, not Git.
"""
import json, os, re, sys, hashlib
from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime

ENDPOINT='https://khetbokxbcujwcurvviu.supabase.co/functions/v1/ministaut-ingest'
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

def prepare(result_path):
 from publication import event_key,event_labels,validate_complete
 from analytics import kickoff_time
 path=Path(result_path);result=json.loads(path.read_text(encoding='utf-8'))
 ok,why=validate_complete(result)
 if not ok:raise ValueError('Only verified complete scans can upload: '+why)
 url=result['url'];ev=event_key(url)
 title,date=event_labels(url)
 # Read last published record to preserve verified title/date from the scanner.
 history_file=ROOT/'historikk'/f'{ev}.json'
 if history_file.exists():
  entries=json.loads(history_file.read_text(encoding='utf-8'))
  latest=next((r for r in reversed(entries) if r.get('time_utc')==result.get('time_utc')),None)
  if latest:title=latest.get('title') or title;date=latest.get('match_date') or date
 kickoff=kickoff_time(date)
 locked=result.get('locked_fields',[])
 data={'event_key':ev,'source_run_id':hashlib.sha256((ev+'|'+result['time_utc']).encode()).hexdigest()[:32],
       'observed_at':result['time_utc'],'title':title,'kickoff_at':kickoff.isoformat() if kickoff else None,
       'total_capacity':21423,'available_seated':result['free_confirmed_fields'],
       'quality_approved':True,'locked_fields_confirmed':True,'locked_fields':locked,
       'sections':[{'section':s['section'],'free':s['free'],'capacity':s['capacity']} for s in result['confirmed_fields']]}
 return data

def send(payload):
 token=os.getenv('MINISTAUT_TOKEN','').strip()
 p=ROOT/'.ministaut-token'
 if not token and p.exists():token=p.read_text(encoding='utf-8').strip()
 if not token:raise RuntimeError('Missing MINISTAUT_TOKEN or .ministaut-token (keep it private)')
 req=Request(ENDPOINT,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','x-ministaut-token':token},method='POST')
 with urlopen(req,timeout=30) as r:
  answer=json.loads(r.read().decode('utf-8'))
  if not answer.get('ok'):raise RuntimeError('Server did not confirm ingest')
  return answer

def upload(result_path):
    # Durable one-way queue: network failures never discard an approved scan.
    spool=ROOT/'ministaut_ventende_opplastinger.json'
    queue=[]
    if spool.exists():
        queue=json.loads(spool.read_text(encoding='utf-8'))
    item=prepare(result_path)
    if not any(x.get('source_run_id')==item['source_run_id'] for x in queue):queue.append(item)
    spool.write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
    sent=0
    while queue:
        try:reply=send(queue[0])
        except Exception:
            # Leave remaining data for retry when the next complete run finishes.
            raise
        queue.pop(0);sent+=1
        spool.write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Ministaut: synced',sent,'complete run(s)')

if __name__=='__main__':
 if len(sys.argv)!=2:sys.exit('Usage: python sync_ministaut.py output\\...\\resultat.json')
 upload(sys.argv[1])