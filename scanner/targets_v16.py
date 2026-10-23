"""Verified pitch-relative section targets and a bounded recovery scan.

Never infers a section's counts: coordinates are only hover candidates.
Recorded points are intentionally separate from checkout/event details.
"""
from __future__ import annotations
import json, math
from pathlib import Path
from pitch_locator import to_screen, to_reference


def confirmed_load(path: Path) -> dict[str, list[dict]]:
    try:
        content=json.loads(path.read_text(encoding='utf-8'))
        fields=content.get('fields',{})
        if not isinstance(fields,dict):return {}
        result={}
        for key,values in fields.items():
            if not isinstance(key,str) or not isinstance(values,list):continue
            good=[]
            for item in values:
                if not isinstance(item,dict):continue
                pair=item.get('ref')
                if (isinstance(pair,list) and len(pair)==2 and all(isinstance(n,(int,float))
                    and math.isfinite(n) and -1000<n<1800 for n in pair)):
                    good.append(item)
            if good:result[key.upper()]=good[:8]
        return result
    except (OSError,ValueError,TypeError):return {}


def record_verified(path:Path,store:dict,field:str,pixel:tuple,pitch,tag:str):
    """Persist verified hover position, but never the seat status or counts."""
    ref=list(to_reference(pixel,pitch))
    if not all(math.isfinite(v) and -500<v<1500 for v in ref):return False
    field=field.upper()
    items=store.setdefault(field,[])
    row={'ref':ref,'source':tag}
    old=next((i for i,entry in enumerate(items) if math.dist(entry['ref'],ref)<2.5),None)
    if old is not None:items.pop(old)
    items.insert(0,row)
    store[field]=items[:4]
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'version':16,'fields':store},ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(path)
    return True


def field_bases(field,pitch,legacy,live,confirmed,dom,known,old):
    """Deduplicate proven points before older guess coordinates."""
    options=[]
    def add(origin,coord,is_ref=True):
        if not isinstance(coord,(list,tuple)) or len(coord)!=2:return
        try:
            x,y=to_screen(coord,pitch) if is_ref else (round(coord[0]),round(coord[1]))
        except (ValueError,TypeError,ZeroDivisionError):return
        if x<0 or y<0:return
        if any((x-a[1])**2+(y-a[2])**2<=4 for a in options):return
        options.append((origin,x,y))
    if field in legacy:add('manuell_v15',legacy[field])
    for row in live.get(field,[]):add('bekreftet_v16',row['ref'])
    for row in confirmed.get(field,[]):add('begge_kamper_'+row.get('sample',''),row['ref'])
    for point in dom.get(field,[])[:2]:add('svg',point,False)
    if field in known:add('referansekart',known[field])
    if field in old:add('historisk',(old[field]['x'],old[field]['y']))
    return options


def field_candidates(field,pitch,legacy,live,confirmed,dom,known,old,deep=False):
    """First candidate is strongest; others are only used for missed fields.

    A short series of small offsets helps if the responsive map places a
    thin polygon a couple of pixels away from a saved point.
    """
    bases=field_bases(field,pitch,legacy,live,confirmed,dom,known,old)
    if not bases:return []
    result=[];used=set()
    def add(origin,x,y):
        if (x,y) in used:return
        used.add((x,y));result.append((origin,x,y))
    for origin,x,y in bases:add(origin,x,y)
    offsets=[(0,-3),(0,3),(-3,0),(3,0),(-5,0),(5,0),(0,-6),(0,6),(-3,-3),(3,3)]
    if deep:offsets.extend([(-6,-4),(6,-4),(-6,4),(6,4),(-9,0),(9,0),(0,-9),(0,9)])
    # Sample offsets around the two best real confirmed points, rather than
    # around obsolete screenshot guesses and every nearby polygon.
    for dx,dy in offsets:
        for origin,x,y in bases[:2]:add(origin+'+offset',x+dx,y+dy)
    return result


def round_robin_recovery(candidates,attempted,per_field_limit=9):
    """Fairly spread fallback probes over remaining fields."""
    pending={}
    for name,rows in candidates.items():
        earlier=attempted.get(name,set())
        pending[name]=[(org,x,y) for org,x,y in rows if (x,y) not in earlier][:per_field_limit]
    size=max((len(values) for values in pending.values()),default=0)
    for idx in range(size):
        for name in sorted(pending):
            if idx<len(pending[name]):
                org,x,y=pending[name][idx]
                yield name,x,y,org