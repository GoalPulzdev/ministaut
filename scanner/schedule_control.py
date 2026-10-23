"""In-process configurable schedule; never performs scans without the Edge session.

Uses monotonic time so local clock edits/DST do not cause drift or repeated jobs.
Missed intervals are coalesced into one scan; no catch-up storms.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from time import monotonic

DEFAULT_HOURS=1

class ScanSchedule:
    def __init__(self, path:Path, hours=DEFAULT_HOURS, enabled=True):
        self.path=Path(path)
        self.hours=float(hours)
        self.enabled=bool(enabled)
        if self.path.exists():
            try:
                stored=json.loads(self.path.read_text(encoding='utf-8'))
                self.enabled=stored['enabled'] if type(stored.get('enabled')) is bool else self.enabled
            except (OSError,ValueError,TypeError):pass
        self.next_due=None
        self.last_complete=None

    @property
    def seconds(self):return int(self.hours*3600)

    def scan_finished(self,now=None):
        when=monotonic() if now is None else now
        self.last_complete=when
        self.next_due=when+self.seconds if self.enabled else None

    def enable(self,flag:bool,now=None):
        self.enabled=bool(flag)
        if self.enabled:
            start=monotonic() if now is None else now
            self.next_due=start+self.seconds if self.last_complete is None else max(start,self.last_complete)+self.seconds
        else:self.next_due=None
        self.save()

    def due(self,now=None):
        current=monotonic() if now is None else now
        return bool(self.enabled and self.next_due is not None and current>=self.next_due)

    def postpone_after_error(self,now=None,minutes=15):
        current=monotonic() if now is None else now
        self.next_due=current+minutes*60 if self.enabled else None

    def seconds_remaining(self,now=None):
        if not self.enabled or self.next_due is None:return None
        current=monotonic() if now is None else now
        return max(0,int(self.next_due-current))

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp')
        temp.write_text(json.dumps({'enabled':self.enabled,'interval_hours':self.hours},indent=2),encoding='utf-8')
        os.replace(temp,self.path)