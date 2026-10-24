"""Persistent, per-event scheduler. No browser code and no hidden global scan clock."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,uuid

def utc(value):
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timestamp requires timezone")
    return dt.astimezone(timezone.utc)

@dataclass
class Event:
    id:str
    url:str
    venue_id:str
    kickoff_at:str
    title:str
    state:str="paused"
    interval_minutes:int=60
    last_scheduled_at:str|None=None
    last_success_at:str|None=None
    error:str|None=None
    def validate(self):
        if not self.id or not self.url.startswith("https://billett.rbk.no/checkout/"):raise ValueError("Invalid event")
        if self.interval_minutes<15:raise ValueError("Minimum interval 15 minutes")
        utc(self.kickoff_at)
        if self.state not in ("paused","monitoring","completed","needs_map"):raise ValueError("Invalid state")
        return self

@dataclass
class Job:
    id:str
    event_id:str
    created_at:str
    state:str="queued"
    claimed_at:str|None=None
    lease_until:str|None=None
    attempts:int=0

class ControlPlane:
    def __init__(self,path):
        self.path=Path(path);self.events={};self.jobs={}
        if self.path.exists():
            data=json.loads(self.path.read_text(encoding="utf-8"))
            self.events={e["id"]:Event(**e).validate() for e in data.get("events",[])}
            self.jobs={j["id"]:Job(**j) for j in data.get("jobs",[])}
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        dest=self.path.with_suffix(".tmp")
        dest.write_text(json.dumps({"events":[asdict(x) for x in self.events.values()],"jobs":[asdict(x) for x in self.jobs.values()]},indent=2,ensure_ascii=False),encoding="utf-8")
        dest.replace(self.path)
    def add(self,event):
        event.validate()
        if event.id in self.events:raise ValueError("Duplicate event")
        self.events[event.id]=event;self.save()
    def set_state(self,key,state):
        e=self.events[key]
        if e.state=="completed":raise ValueError("Completed event cannot resume")
        if state not in ("paused","monitoring","needs_map"):raise ValueError("Bad transition")
        if utc(e.kickoff_at)<=datetime.now(timezone.utc):raise ValueError("Kickoff passed")
        e.state=state;self.save()
    def tick(self,now=None):
        now=now or datetime.now(timezone.utc)
        changed=False;created=[]
        for e in self.events.values():
            if utc(e.kickoff_at)<=now:
                if e.state!="completed":
                    e.state="completed";changed=True
                for j in self.jobs.values():
                    if j.event_id==e.id and j.state=="queued":j.state="cancelled";changed=True
                continue
            if e.state!="monitoring":continue
            if any(j.event_id==e.id and j.state in ("queued","running") for j in self.jobs.values()):continue
            previous=utc(e.last_scheduled_at) if e.last_scheduled_at else None
            if previous and now-previous<timedelta(minutes=e.interval_minutes):continue
            j=Job(str(uuid.uuid4()),e.id,now.isoformat())
            self.jobs[j.id]=j;e.last_scheduled_at=now.isoformat();created.append(j);changed=True
        if changed:self.save()
        return created
    def claim(self,worker_id,now=None,lease_minutes=10):
        now=now or datetime.now(timezone.utc)
        for j in sorted(self.jobs.values(),key=lambda j:j.created_at):
            event=self.events[j.event_id]
            if event.state!="monitoring" or utc(event.kickoff_at)<=now:continue
            if j.state=="running" and j.lease_until and utc(j.lease_until)<=now:j.state="queued"
            if j.state!="queued":continue
            j.state="running";j.claimed_at=now.isoformat();j.lease_until=(now+timedelta(minutes=lease_minutes)).isoformat();j.attempts+=1
            self.save();return j
        self.save();return None
    def finish(self,job_id,success,now=None,error=None):
        now=now or datetime.now(timezone.utc)
        j=self.jobs[job_id];e=self.events[j.event_id]
        if j.state!="running":raise ValueError("Job not running")
        if utc(e.kickoff_at)<=now:
            j.state="cancelled";e.state="completed"
        elif success:
            j.state="succeeded";e.last_success_at=now.isoformat();e.error=None
        else:
            j.state="failed";e.error=str(error or "Unknown error")[:250]
        self.save()
        return j.state
