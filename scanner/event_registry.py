"""Local persistent event list. Does not change validated stadium scanners."""
from __future__ import annotations
import json,os
from pathlib import Path
from publication import event_key

class EventRegistry:
    def __init__(self,path):
        self.path=Path(path)
        self.items=[]
        if self.path.exists():
            raw=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(raw,list):raise ValueError('Ugyldig kampliste')
            for item in raw:
                self.add(item['url'],item.get('title',''),item.get('venue','lerkendal'),save=False)
    def add(self,url,title='',venue='lerkendal',save=True):
        key=event_key(url)
        if venue not in ('lerkendal','koteng_arena'):
            raise ValueError('Ukjent stadionprofil')
        title=str(title or 'RBK-kamp').strip()[:90]
        normalized='https://billett.rbk.no/checkout/'+key
        entry={'key':key,'url':normalized,'title':title,'venue':venue}
        self.items=[i for i in self.items if i['key']!=key]+[entry]
        if save:self.save()
        return entry
    def remove(self,key):
        self.items=[i for i in self.items if i['key']!=key]
        self.save()
    def get(self,key):
        return next((i for i in self.items if i['key']==key),None)
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.items,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,self.path)
