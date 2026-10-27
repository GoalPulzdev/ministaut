"""Never trust process output as a measurement; revalidate source diagnostic."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from .model import Job
from .runner_helpers import interpreter_for  # imported helper isolated from controller to avoid cycles


VALIDATE = '''import json,sys
from pathlib import Path
from sync_koteng import build_payload
p=build_payload(Path(sys.argv[1]))
print(json.dumps({'run_id':p['source_run_id'],'observed_at':p['observed_at'],
 'available_seated':p['available_seated'],'sections':p['sections'],
 'event_key':p['event_key'],'quality_status':p['quality_status']}))
'''


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
                       stderr=subprocess.PIPE, timeout=35, check=False)
    if p.returncode != 0:
        raise RuntimeError('Skannerens profil-/kvalitetskontroll avviste rapporten')
    try:data=json.loads(p.stdout.strip())
    except (ValueError, TypeError) as e:raise RuntimeError('Skannerens diagnostikk kunne ikke tolkes') from e
    if data['event_key']!=job.key or data['quality_status']!='LOCKED_LOCAL_VERIFIED' or len(data['sections'])!=6:
        raise RuntimeError('Ugyldig kamp eller feltantall i diagnostikk')
    return data
