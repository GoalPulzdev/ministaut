"""Parse RBK public tooltip counts and distinguish live changes from contradictions.

A section's free count may move during a scan. For a stable capacity and
one/two-seat change we keep a bounded value (min..max), not a phantom conflict.
Different capacities or larger discrepancies remain unresolved and excluded.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import re
from typing import Optional

NUMBER = r"(?:\d{1,3}(?:[ .\u00a0]\d{3})+|\d+)"
AVAILABILITY = re.compile(
    rf"(?:FREE\s+SEATS?|AVAILABLE\s+SEATS?|LEDIGE\s+(?:SETER|PLASSER|BILLETTER)|TILGJENGELIGE\s+(?:SETER|PLASSER))"
    rf"\s*[:\-]?\s*(?P<available>{NUMBER})\s*(?:/|OF|AV)\s*(?P<capacity>{NUMBER})\b", re.IGNORECASE)
SECTION = re.compile(r"\b(?:SECTION|SEKSJON|FELT|BLOCK)\s*:?\s*(PRESSE|[A-Z\u00c6\u00d8\u00c5]{1,3}\s?\d{0,2})\b",re.IGNORECASE)
GATE = re.compile(r"\b(?:GATE|INNGANG|PORT)\s*:?\s*([A-Z0-9\-]+(?:\s*[,/]\s*[A-Z0-9\-]+)*)\b",re.IGNORECASE)


@dataclass(frozen=True)
class Observation:
    section: str
    gate: str
    free: int
    capacity: int
    source: str
    x: int = -1
    y: int = -1

    def as_dict(self) -> dict:
        return asdict(self)


def parse_tooltip(text: str, source: str = "hover", x: int = -1, y: int = -1) -> Optional[Observation]:
    if not text or len(text)>25000: return None
    clean = re.sub(r"[\t\r\n\u00a0]+", " ", text)
    clean = re.sub(r" {2,}", " ", clean).strip()
    for match in AVAILABILITY.finditer(clean):
        free = int(re.sub(r"[ .\u00a0]", "", match.group('available')))
        cap  = int(re.sub(r"[ .\u00a0]", "", match.group('capacity')))
        if not (1 <= cap <= 100000 and 0 <= free <= cap): continue
        context = clean[max(0,match.start()-220):match.start()]
        section_matches = list(SECTION.finditer(context))
        if not section_matches: continue
        section_match = section_matches[-1]
        section = section_match.group(1).upper().replace(' ','')
        if section in {'AV','OF'}: continue
        gate_context = context[section_match.start():] + clean[match.end():match.end()+30]
        gate_match = GATE.search(gate_context)
        gate = gate_match.group(1).upper() if gate_match else ''
        return Observation(section,gate,free,cap,source,x,y)
    return None


class Counts:
    """Independent field-by-field observations, small live changes tracked as ranges."""

    def __init__(self, minor_variation: int=2):
        self._groups: dict[str,list[dict]] = {}
        self.samples=0
        self.minor_variation=minor_variation

    def add(self, row: Observation) -> str:
        self.samples+=1
        key=row.section.upper().strip()
        observations=self._groups.setdefault(key,[])
        if not observations:
            observations.append(row.as_dict())
            return 'new'
        if any(x['capacity']==row.capacity and x['free']==row.free for x in observations):
            return 'duplicate'
        observations.append(row.as_dict())
        capacities={x['capacity'] for x in observations}
        spread=max(x['free'] for x in observations)-min(x['free'] for x in observations)
        if len(capacities)==1 and spread<=self.minor_variation:
            return 'variable'
        return 'conflict'

    def export(self)->dict:
        fields=[]
        conflicts={}
        variable=[]
        for section,observations in sorted(self._groups.items()):
            capacities={x['capacity'] for x in observations}
            free_values=[x['free'] for x in observations]
            if len(capacities)>1 or max(free_values)-min(free_values)>self.minor_variation:
                conflicts[section]=observations
                continue
            # 'free' is a recent observation, not a sales or attendance estimate.
            picked=observations[-1].copy()
            picked['min_free']=min(free_values)
            picked['max_free']=max(free_values)
            picked['availability_state']='variable' if len(set(free_values))>1 else 'stable'
            picked['variants']=len(set(free_values))
            fields.append(picked)
            if picked['availability_state']=='variable': variable.append(section)
        return {
            'fields':fields,'conflicts':conflicts,'field_count':len(fields),
            'conflict_count':len(conflicts),'variable_fields':variable,
            'variable_count':len(variable),'observed_field_count':len(self._groups),
            'observations':self.samples,
            'free_seats_confirmed':sum(f['free'] for f in fields),
            'free_seats_min':sum(f['min_free'] for f in fields),
            'free_seats_max':sum(f['max_free'] for f in fields),
            'capacity_confirmed':sum(f['capacity'] for f in fields),
            'not_available_confirmed_fields':sum(f['capacity']-f['free'] for f in fields),
            'coverage_complete':False,
            'important_note': 'Only observed fields are summed. Capacity minus free does NOT equal tickets sold.',
        }