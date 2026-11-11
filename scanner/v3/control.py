"""Single-process V3 control plane. Isolated from the production Edge scanner.

Persistent JSON is intentionally a LOCAL STAGING implementation. Do not run
multiple writers or present its jobs as scans. Supabase transaction leases are
required for multi-machine production workers.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import uuid


def utc(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Kickoff and timestamps require an explicit timezone")
    return dt.astimezone(timezone.utc)


@dataclass
class Event:
    id: str
    url: str
    venue_id: str
    kickoff_at: str
    title: str
    state: str = "paused"
    interval_minutes: int = 60
    last_scheduled_at: str | None = None
    last_success_at: str | None = None
    error: str | None = None

    def validate(self):
        parsed = urlparse(self.url)
        if (not self.id or len(self.id) > 80 or not self.title.strip()
                or not self.venue_id.strip() or parsed.scheme != "https"
                or parsed.hostname != "billett.rbk.no"
                or not parsed.path.startswith("/checkout/")):
            raise ValueError("Invalid ticket link, event ID, title or venue")
        if type(self.interval_minutes) is not int or self.interval_minutes < 15:
            raise ValueError("Minimum scan interval is 15 minutes")
        utc(self.kickoff_at)
        if self.state not in ("paused", "monitoring", "completed", "needs_map"):
            raise ValueError("Invalid state")
        return self


@dataclass
class Job:
    id: str
    event_id: str
    created_at: str
    state: str = "queued"
    claimed_at: str | None = None
    lease_until: str | None = None
    attempts: int = 0
    worker_id: str | None = None


class ControlPlane:
    def __init__(self, path):
        self.path = Path(path)
        self.events = {}
        self.jobs = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.events = {e["id"]: Event(**e).validate() for e in data.get("events", [])}
            self.jobs = {j["id"]: Job(**j) for j in data.get("jobs", [])}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "events": [asdict(x) for x in self.events.values()],
            "jobs": [asdict(x) for x in self.jobs.values()]
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, self.path)

    def add(self, event):
        event.validate()
        if event.id in self.events:
            raise ValueError("A match with that ID already exists")
        if any(e.url.rstrip("/") == event.url.rstrip("/") for e in self.events.values()):
            raise ValueError("This checkout event is already registered")
        self.events[event.id] = event
        self.save()

    def update_kickoff(self, key, kickoff_at, now=None):
        """Explicit correction; never silently resurrect a previously completed event."""
        now = now or datetime.now(timezone.utc)
        new_start = utc(kickoff_at)
        if new_start <= now:
            raise ValueError("Corrected kickoff must be in the future")
        event = self.events[key]
        for job in self.jobs.values():
            if job.event_id == key and job.state in ("queued", "running"):
                job.state = "cancelled"
        event.kickoff_at = new_start.isoformat()
        event.state = "paused"
        event.last_scheduled_at = None
        event.error = None
        self.save()

    def set_state(self, key, state, now=None):
        now = now or datetime.now(timezone.utc)
        event = self.events[key]
        if event.state == "completed":
            raise ValueError("Finished fixtures cannot be reactivated")
        if state not in ("paused", "monitoring", "needs_map"):
            raise ValueError("Invalid state transition")
        if utc(event.kickoff_at) <= now:
            self.tick(now)
            raise ValueError("Kickoff has passed")
        event.state = state
        if state != "monitoring":
            for job in self.jobs.values():
                if job.event_id == key and job.state == "queued":
                    job.state = "cancelled"
        self.save()

    def tick(self, now=None):
        """Create at most one pending job per event, and archive past kickoffs."""
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("Scheduler time must be timezone-aware")
        created, changed = [], False
        for event in self.events.values():
            if utc(event.kickoff_at) <= now:
                if event.state != "completed":
                    event.state = "completed"
                    changed = True
                for job in self.jobs.values():
                    if job.event_id == event.id and job.state in ("queued", "running"):
                        job.state = "cancelled"
                        changed = True
                continue
            if event.state != "monitoring":
                continue
            if any(j.event_id == event.id and j.state in ("queued", "running")
                   for j in self.jobs.values()):
                continue
            previous = utc(event.last_scheduled_at) if event.last_scheduled_at else None
            if previous and now - previous < timedelta(minutes=event.interval_minutes):
                continue
            job = Job(str(uuid.uuid4()), event.id, now.isoformat())
            self.jobs[job.id] = job
            event.last_scheduled_at = now.isoformat()
            created.append(job)
            changed = True
        if changed:
            self.save()
        return created

    def claim(self, worker_id, now=None, lease_minutes=10):
        """Single-process lease. Future distributed workers need a DB transaction."""
        if not worker_id or lease_minutes <= 0:
            raise ValueError("Worker ID and positive lease are required")
        now = now or datetime.now(timezone.utc)
        changed = False
        for job in sorted(self.jobs.values(), key=lambda j: j.created_at):
            event = self.events[job.event_id]
            if event.state != "monitoring" or utc(event.kickoff_at) <= now:
                if job.state in ("queued", "running"):
                    job.state = "cancelled"
                    changed = True
                continue
            if job.state == "running" and job.lease_until and utc(job.lease_until) <= now:
                if job.attempts >= 3:
                    job.state = "failed"
                    event.error = "Lease expired 3 times; requires next scheduled cycle"
                    changed = True
                    continue
                job.state = "queued"
                changed = True
            if job.state != "queued":
                continue
            job.state = "running"
            job.claimed_at = now.isoformat()
            job.lease_until = (now + timedelta(minutes=lease_minutes)).isoformat()
            job.attempts += 1
            job.worker_id = worker_id
            self.save()
            return job
        if changed:
            self.save()
        return None

    def finish(self, job_id, success, now=None, error=None, worker_id=None):
        """Do not accept a late completion or a replaced lease holder."""
        now = now or datetime.now(timezone.utc)
        job = self.jobs[job_id]
        event = self.events[job.event_id]
        if job.state != "running":
            raise ValueError("Job is not running")
        if worker_id is not None and job.worker_id != worker_id:
            raise ValueError("Worker no longer holds this job")
        if utc(event.kickoff_at) <= now or event.state != "monitoring":
            job.state = "cancelled"
            if utc(event.kickoff_at) <= now:
                event.state = "completed"
        elif success:
            job.state = "succeeded"
            event.last_success_at = now.isoformat()
            event.error = None
        else:
            job.state = "failed"
            event.error = str(error or "Unknown error")[:250]
        self.save()
        return job.state
