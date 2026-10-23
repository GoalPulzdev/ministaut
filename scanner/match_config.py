"""User-confirmed per-event exceptions for sections unavailable to regular buyers.

A locked section is NOT a sale. It is omitted from the mouse scan and must
never be silently inferred from a missing tooltip or a zero availability value.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from publication import event_key

ROOT = Path(__file__).resolve().parent
STADIUM = json.loads((ROOT/'stadion_felt.json').read_text(encoding='utf-8'))
SEATS: dict[str, int] = STADIUM['seat_sections']
TOTAL_SEATED = STADIUM['total_seated']
assert len(SEATS)==60 and sum(SEATS.values())==TOTAL_SEATED


def normalize_locked(sections):
    if isinstance(sections, str):
        sections = [x.strip().upper() for x in sections.replace(';',',').split(',') if x.strip()]
    if not isinstance(sections, (tuple,list,set)):
        raise ValueError('Låste felt må oppgis som liste.')
    raw = list(sections)
    data = [str(x).strip().upper() for x in raw]
    if len(data)!=len(set(data)):
        raise ValueError('Duplikat i listen over bortefelt.')
    invalid = [x for x in data if x not in SEATS]
    if invalid: raise ValueError('Ukjent sittefelt: '+', '.join(invalid))
    if len(data)>2:
        raise ValueError('Kun inntil to bekreftede bortefelt per kamp støttes.')
    return sorted(data)


def config_path(root: Path, url: str) -> Path:
    return root/(event_key(url)+'.json')


def load_locked(root: Path, url: str) -> tuple[str, ...]:
    path=config_path(root,url)
    if not path.is_file():return ()
    data=json.loads(path.read_text(encoding='utf-8'))
    locked=normalize_locked(data.get('locked_fields',[]))
    if data.get('event_key')!=event_key(url) or data.get('confirmation')!='BEKREFTET_MANUELT':
        raise ValueError('Kampoppsett ikke bekreftet korrekt. Gjenopprett konfigurasjonen.')
    return tuple(locked)


def save_locked(root: Path, url: str, sections, *, confirmed: bool, reason: str='Bortefelt låst for ordinært billettsalg') -> Path:
    if not confirmed:raise ValueError('Låste felter må bekreftes av bruker.')
    locked=normalize_locked(sections)
    path=config_path(root,url); path.parent.mkdir(parents=True,exist_ok=True)
    body={'version':18,'event_key':event_key(url),'locked_fields':locked,
          'confirmation':'BEKREFTET_MANUELT','note':reason.strip()[:250],
          'saved_utc':datetime.now(timezone.utc).isoformat(timespec='seconds')}
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(body,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)
    return path


def check_map_against_reference(names: set, capacities: dict, locked: tuple[str, ...]):
    """Locked seats can be absent from the live sale map; active seats must match."""
    names=set(names)
    unexpected=names-set(SEATS)
    missing_active=(set(SEATS)-set(locked))-names
    wrong={name:(capacities.get(name),SEATS[name]) for name in names & (set(SEATS)-set(locked))
           if capacities.get(name)!=SEATS[name]}
    return not (unexpected or missing_active or wrong), {
        'unexpected_sections':sorted(unexpected),'missing_active_sections':sorted(missing_active),
        'capacity_mismatch':wrong,
    }