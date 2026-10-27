"""External scanner coordinator. Legacy engines remain immutable and separate.

- All jobs are opt-in. No automatic scan starts from opening the program.
- Koteng has one-shot invocation using its proven V2.4 profile.
- Lerkendal launches its own interactive controller (not a fabricated one-shot).
- No scan count is inferred from stdout. Public upload belongs to legacy QA.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable
from .model import Job, parse_utc
from .storage import Store, now_iso
from .runner_helpers import interpreter_for


@dataclass
class Active:
    job: Job
    process: subprocess.Popen
    run_id: int
    lock: Path
    log: object | None
    started: datetime
    previous_reports: set[Path]


def get_python(path: Path) -> str:
    return interpreter_for(path)


def command(job: Job, base: Path, python: str | None = None) -> tuple[list[str], Path, bool]:
    home = job.path(base)
    exe = python or get_python(home)
    if job.profile == 'koteng_v24':
        expected = ('hourly_koteng.py', 'koteng_scanner.py', 'profile_lock.py',
                    'koteng_profile.json', 'ankerpunkter_koteng.json', 'sync_koteng.py')
        if not all((home / p).is_file() for p in expected):
            raise FileNotFoundError('Koteng V2.4 er ikke komplett i ' + str(home))
        return ([exe, str(home / 'hourly_koteng.py'), '--once'] + (['--upload'] if job.upload else []), home, False)
    if job.profile == 'lerkendal_legacy':
        expected = ('hurtigkart.py', 'match_config.py', 'stadion_felt.json')
        if not all((home / p).is_file() for p in expected):
            raise FileNotFoundError('Lerkendal skannermotor mangler i ' + str(home))
        # The legacy scanner reads the first event by URL then manages its own
        # hourly loop, confirmation ENTER, browser window and reporting.
        return ([exe, str(home / 'hurtigkart.py'), '--url', job.url,
                 '--auto-hours', str(job.interval_minutes / 60), '--port', '9222'], home, True)
    raise ValueError('Ukjent skannermotor')


def lock_name(key: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key):
        raise ValueError('Ugyldig ID')
    return 'event-' + key + '.lock'


def acquire(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic create: NEVER auto-delete a stale lock. A crash needs manual review
    # to avoid inadvertently running two publishers against one checkout event.
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(f'controller_pid={os.getpid()}\nstarted_at={now_iso()}\n')


def schedule_after(job: Job, failures: int, time: datetime) -> str:
    minutes = job.interval_minutes if failures == 0 else min(60, 5 * (2 ** min(failures, 4)))
    return (time + timedelta(minutes=minutes)).isoformat(timespec='seconds')


class Controller:
    def __init__(self, base: Path, store: Store, popen: Callable = subprocess.Popen):
        self.base = Path(base).resolve()
        self.store = store
        self.popen = popen
        self.active: dict[str, Active] = {}
        self.error = ''

    def start(self, job: Job, force: bool = False) -> str:
        if job.key in self.active:
            raise RuntimeError('Kamp er allerede i gang')
        if parse_utc(job.kickoff_at) <= datetime.now(timezone.utc):
            self.store.set_due(job.key, None, 'ferdig')
            raise RuntimeError('Kampstart er passert; skanneren stoppes')
        if not force and not job.enabled:
            raise RuntimeError('Aktiver først jobben i kontrollpanelet')
        # A single provider can still use multiple stadium profiles; until
        # isolated CDP ports are proven, NEVER start two Lerkendal instances.
        if job.profile == 'lerkendal_legacy' and any(
                x.job.profile == 'lerkendal_legacy' for x in self.active.values()):
            raise RuntimeError('Bare én Lerkendal-sesjon kan starte på samme PC')
        # Prevent two concurrent scan processes (including cross-UI starts) for
        # the same event on this PC. Cross-machine leadership is NOT guaranteed.
        guard = self.base / 'state' / 'locks' / lock_name(job.key)
        command_args, cwd, interactive = command(job, self.base)
        acquire(guard)
        from .observations import reports_for
        previous_reports = reports_for(job,cwd)
        log_stream = None
        try:
            logs_dir = self.base / 'state' / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = logs_dir / (job.key + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.log')
            if interactive:
                if os.name != 'nt':
                    raise RuntimeError('Lerkendal krever et interaktivt Windows-konsollvindu')
                # Lerkendal expects ENTER from the operator and runs internally
                # every hour. It is not treated as a short-lived batch job.
                proc = self.popen(command_args, cwd=str(cwd),
                                  creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                log_stream = log_path.open('w', encoding='utf-8', errors='replace')
                proc = self.popen(command_args, cwd=str(cwd), stdout=log_stream,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            run_id = self.store.begin(job.key, log_path)
            self.active[job.key] = Active(job, proc, run_id, guard, log_stream, datetime.now(timezone.utc), previous_reports)
            return 'Kjører: ' + job.label
        except Exception:
            if log_stream:
                log_stream.close()
            guard.unlink(missing_ok=True)
            raise

    def poll(self, when: datetime | None = None):
        now = when or datetime.now(timezone.utc)
        for key, active in tuple(self.active.items()):
            if parse_utc(active.job.kickoff_at) <= now and active.process.poll() is None:
                # An in-progress scan must not continue beyond kickoff.
                self.stop(key)
            code = active.process.poll()
            if code is None:
                continue
            if active.log:
                active.log.close()
            if code == 0 and active.job.profile=='koteng_v24':
                try:
                    from .observations import verified_new_report
                    result=verified_new_report(active.job,active.job.path(self.base),active.previous_reports)
                    self.store.observation(result, active.job.upload)
                except Exception as exc:
                    # No false success if post-scan revalidation fails.
                    code=3
                    self.error=f'{active.job.label}: kontroll av fersk rapport feilet: {exc}'
            active.lock.unlink(missing_ok=True)
            self.active.pop(key, None)
            prior = self.store.state(key)
            fails = 0 if code == 0 else prior['failures'] + 1
            status = 'fullført' if code == 0 else 'feil'
            due = None if parse_utc(active.job.kickoff_at) <= now or not active.job.enabled or active.job.profile!='koteng_v24' else schedule_after(active.job, fails, now)
            self.store.finish(active.run_id, key, status, code, due, fails,
                              'Kontrollprosess avsluttet. Se logg; bekreftet publisering avgjøres av kildemotor.')
        # No automatic Lerkendal launch: its long-running UI owns scheduling.
        # Operator starts it manually after ensuring no existing production run.
        if any(a.job.profile == 'koteng_v24' for a in self.active.values()):
            return
        for job in self.store.jobs():
            if job.key in self.active or not job.enabled or job.profile != 'koteng_v24':
                continue
            if parse_utc(job.kickoff_at) <= now:
                self.store.set_due(job.key, None, 'ferdig')
                continue
            due = self.store.state(job.key)['next_due']
            if due and parse_utc(due) <= now:
                try:
                    self.start(job)
                except Exception as exc:
                    self.error = f'{job.label}: {exc}'
                    self.store.set_due(job.key, (now + timedelta(minutes=15)).isoformat(), 'stoppet')
                break

    def enable(self, key: str, enable: bool, upload: bool = False):
        old = next((j for j in self.store.jobs() if j.key == key), None)
        if old is None:
            raise KeyError(key)
        if key in self.active:
            raise RuntimeError('Stopp kjørende jobb før endring')
        job = Job(**{**old.as_json(), 'enabled': enable, 'upload': upload if enable else False})
        self.store.put_job(job)
        due = now_iso() if enable and job.profile == 'koteng_v24' else None
        self.store.set_due(key, due, 'planlagt' if enable else 'av')

    def stop(self, key: str):
        a = self.active.get(key)
        if a is None:
            return
        # On Windows kill only descendants of this launched PID, not other
        # independent Edge windows. Prevent orphan one-shot scanner publishing.
        if os.name=='nt':
            result=subprocess.run(['taskkill','/PID',str(a.process.pid),'/T','/F'],
                                  capture_output=True, timeout=20, check=False)
            if result.returncode not in (0, 128, 255) and a.process.poll() is None:
                raise RuntimeError('Kunne ikke stoppe skannerens prosessgruppe')
        else:
            a.process.terminate()
        # poll() cleans up when the child has exited. In a crash, the lock
        # remains intentionally to force human review of possible orphan child.
