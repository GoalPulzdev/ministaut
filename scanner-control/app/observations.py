"""Never trust process output as a measurement; revalidate source diagnostic."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from .model import Job
from .runner_helpers import interpreter_for, no_window  # imported helper isolated from controller to avoid cycles


VALIDATE = '''import json,sys
from pathlib import Path
from sync_koteng import build_payload
p=build_payload(Path(sys.argv[1]))
print(json.dumps({'run_id':p['source_run_id'],'observed_at':p['observed_at'],
 'available_seated':p['available_seated'],'sections':p['sections'],
 'event_key':p['event_key'],'quality_status':p['quality_status']}))
'''


# Lerkendal: re-run the engine's own completeness gate on the saved result and
# derive the same source_run_id as sync_ministaut.prepare (idempotent ingest).
VALIDATE_LERKENDAL = '''import hashlib,json,sys
from pathlib import Path
from publication import event_key,validate_complete
from match_config import SEATS
r=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
ok,why=validate_complete(r)
if not ok:raise SystemExit('AVVIST: '+why)
ev=event_key(r['url'])
print(json.dumps({'event_key':ev,'run_id':hashlib.sha256((ev+'|'+r['time_utc']).encode()).hexdigest()[:32],
 'observed_at':r['time_utc'],'available_seated':r['free_confirmed_fields'],
 'sections':[f['section'] for f in r['confirmed_fields']]+list(r.get('locked_fields',[])),
 'expected':len(SEATS),'quality_status':'LERKENDAL_60_VERIFIED'}))
'''


def lerkendal_report(report: Path) -> dict:
    try:
        return json.loads(report.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RuntimeError('Lerkendal-adapteren skrev ingen kontrollrapport') from exc


def verified_lerkendal(job: Job, scanner_dir: Path, report: Path) -> dict:
    rep = lerkendal_report(report)
    if rep.get('event_key') != job.key or rep.get('accepted') is not True or not rep.get('output_dir'):
        raise RuntimeError('Adapteren godkjente ikke målingen: ' + str(rep.get('reason') or 'ukjent'))
    source = Path(rep['output_dir']) / 'resultat.json'
    p = subprocess.run([interpreter_for(scanner_dir), '-c', VALIDATE_LERKENDAL, str(source)],
                       cwd=str(scanner_dir), text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=35, check=False, **no_window())
    if p.returncode != 0:
        raise RuntimeError('Etterkontroll avviste resultatet: ' + (p.stderr.strip().splitlines() or ['ukjent'])[-1][:160])
    try:data=json.loads(p.stdout.strip())
    except (ValueError, TypeError) as e:raise RuntimeError('Lerkendal-resultatet kunne ikke tolkes') from e
    if data['event_key'] != job.key or len(set(data['sections'])) != data['expected']:
        raise RuntimeError('Feil kamp eller ufullstendig feltdekning i resultatet')
    if data['observed_at'] != rep.get('time_utc') or data['available_seated'] != rep.get('available_seated'):
        raise RuntimeError('Kontrollrapport og resultat stemmer ikke overens')
    data['diagnostic'] = str(source)
    return data


def reports_for(job: Job, scanner_dir: Path) -> set[Path]:
    if job.profile != 'koteng_v24':return set()
    return set((scanner_dir / 'diagnostikk' / job.key).glob('*/diagnostikk.json'))


def verified_new_report(job: Job, scanner_dir: Path, previous: set[Path]):
    new = reports_for(job, scanner_dir) - previous
    if len(new) != 1:
        raise RuntimeError(f'Forventet én ny Koteng-diagnostikk, fikk {len(new)}')
    source = new.pop()
    p = subprocess.run([interpreter_for(scanner_dir), '-c', VALIDATE, str(source)],
                       cwd=str(scanner_dir), text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=35, check=False, **no_window())
    if p.returncode != 0:
        raise RuntimeError('Skannerens profil-/kvalitetskontroll avviste rapporten')
    try:data=json.loads(p.stdout.strip())
    except (ValueError, TypeError) as e:raise RuntimeError('Skannerens diagnostikk kunne ikke tolkes') from e
    if data['event_key']!=job.key or data['quality_status']!='LOCKED_LOCAL_VERIFIED' or len(data['sections'])!=6:
        raise RuntimeError('Ugyldig kamp eller feltantall i diagnostikk')
    data['diagnostic'] = str(source)
    return data


def token_configured(scanner_dir: Path) -> bool:
    """Presence only; the token itself is never read by the control program."""
    return bool(os.environ.get('MINISTAUT_TOKEN', '').strip()) or (scanner_dir / '.ministaut-token').is_file()
