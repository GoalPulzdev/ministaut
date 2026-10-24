"""Persistent per-match lifecycle; never infer an unknown kickoff."""
from __future__ import annotations
import json,os
from datetime import datetime,timezone
from pathlib import Path
from publication import event_key

def kickoff_utc(value):
    if value in (None,''):return None
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Kampstart må ha tidssone')
    return dt.astimezone(timezone.utc).isoformat()

class EventRegistry:
    def __init__(self,path):
        self.path=Path(path);self.items=[]
        if self.path.exists():
            raw=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw,list):raise ValueError('Ugyldig kampliste')
            for item in raw:
                self.add(item['url'],item.get('title',''),item.get('venue','lerkendal'),
                         kickoff_at=item.get('kickoff_at'),save=False)
    def add(self,url,title='',venue='lerkendal',kickoff_at=None,save=True):
        key=event_key(url)
        if venue not in ('lerkendal','koteng_arena'):raise ValueError('Ukjent stadionprofil')
        current=self.get(key)
        title=str(title or current and current['title'] or 'RBK-kamp').strip()[:90]
        if not title:raise ValueError('Kampnavn mangler')
        # Preserve verified metadata when a known URL is added again.
        kickoff=kickoff_utc(kickoff_at) if kickoff_at else (current or {}).get('kickoff_at')
        venue=venue if not current else current['venue']
        entry={'key':key,'url':'https://billett.rbk.no/checkout/'+key,'title':title,
               'venue':venue,'kickoff_at':kickoff}
        self.items=[i for i in self.items if i['key']!=key]+[entry]
        if save:self.save()
        return entry
    def update(self,key,*,title=None,venue=None,kickoff_at=None):
        item=self.get(key)
        if not item:raise ValueError('Ukjent kamp')
        if venue is not None and venue not in ('lerkendal','koteng_arena'):raise ValueError('Ukjent arena')
        if title is not None:item['title']=str(title).strip()[:90]
        if venue is not None:item['venue']=venue
        if kickoff_at is not None:item['kickoff_at']=kickoff_utc(kickoff_at)
        self.save()
        return item
    def status(self,item,now=None):
        now=now or datetime.now(timezone.utc)
        start=item.get('kickoff_at')
        if not start:return 'awaiting_kickoff'
        if datetime.fromisoformat(start)>now:return 'scheduled' if item['venue']=='lerkendal' else 'awaiting_map'
        return 'finished'
    def eligible(self,now=None):
        return [i for i in self.items if self.status(i,now)=='scheduled']
    def remove(self,key):
        self.items=[i for i in self.items if i['key']!=key];self.save()
    def get(self,key):
        return next((i for i in self.items if i['key']==key),None)
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.items,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,self.path)
