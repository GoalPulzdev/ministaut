"""External scanner coordinator. Legacy engines remain immutable and separate.

- All jobs are opt-in. No automatic scan starts from opening the program.
- Koteng runs one-shot (`hourly_koteng.py --once`) WITHOUT upload. Publishing
  happens afterwards from the durable outbox, and only for a diagnostic that
  passed the controller's own re-verification (V0.1 uploaded before that gate).
- Lerkendal V23 runs one unattended cycle through engines/lerkendal_once.py
  (unchanged engine, own Edge profile/port, engine upload blocked) and is then
  re-verified and published exactly like Koteng.
- lerkendal_legacy still launches the old interactive controller.
- No scan count is inferred from stdout.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import random
import subprocess
from typing import Callable
from . import locks
from .locks import lock_name, acquire  # noqa: F401  (re-exported for tests/tools)
from .model import Job, ONE_SHOT, parse_utc
from .storage import Store, now_iso
from .runner_helpers import interpreter_for, no_window as _no_window

# Statuses shown to the operator (stored in jobs.last_status).
READY, PLANNED, SCANNING, VERIFIED, QUEUED = 'klar', 'planlagt', 'skanner', 'bekreftet lokalt', 'køet for sending'
FAILED, STOPPED, KICKOFF, DONE, REVIEW, OFF = ('feil', 'stoppet', 'stoppet ved avspark', 'ferdig',
                                               'trenger gjennomgang', 'av')
REJECTED, TIMEOUT = 'avvist av kvalitetskontroll', 'tidsavbrudd'
MAX_RUNTIME = timedelta(minutes=30)  # a one-shot scan that hangs is stopped
LERKENDAL_PORT = 9231  # never 9222: that is the production V23 scanner's Edge
NAMES = {'koteng_v24': 'Koteng', 'lerkendal_v23': 'Lerkendal', 'lerkendal_legacy': 'Lerkendal (legacy)'}

# Same payload and source_run_id as the V23 engine's own upload; ingest upserts on it.
SEND_LERKENDAL = ('import sys;from pathlib import Path;sys.path.insert(0,".");'
                  'from sync_ministaut import prepare,send;'
                  'a=send(prepare(Path(sys.argv[1])));print("Registrert:",a.get("scan_id",""))')

# Koteng: same payload as sync_koteng, with the per-match identity from koteng_once.
SEND_KOTENG = ('import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);sys.path.insert(1,".");'
               'from koteng_once import install_multi_event;_,_,s=install_multi_event(sys.argv[2]);'
               'send=getattr(s,"send",None) or s.submit;a=send(s.build_payload(Path(sys.argv[3])));'
               'print("Registrert:",a.get("scan_id",""))')

OUTBOX_MAX_ATTEMPTS = 8
OUTBOX_MAX_AGE = timedelta(hours=6)


@dataclass
class Active:
    job: Job
    process: subprocess.Popen
    run_id: int
    lock: Path
    log: object | None
    started: datetime
    previous_reports: set[Path]
    stop_reason: str | None = None
    report: Path | None = None


@dataclass
class Sending:
    row: dict
    process: subprocess.Popen
    log: object


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec='seconds')


def get_python(path: Path) -> str:
    return interpreter_for(path)


def command(job: Job, base: Path, python: str | None = None,
            report: Path | None = None) -> tuple[list[str], Path, bool]:
    home = job.path(base)
    exe = python or get_python(home)
    if job.profile == 'koteng_v24':
        expected = ('hourly_koteng.py', 'koteng_scanner.py', 'profile_lock.py',
                    'koteng_profile.json', 'ankerpunkter_koteng.json', 'sync_koteng.py')
        if not all((home / p).is_file() for p in expected):
            raise FileNotFoundError('Koteng V2.4 er ikke komplett i ' + str(home))
        # engines/koteng_once.py: any approved match on the sealed stadium lock;
        # never uploads itself, publication goes through the outbox.
        wrapper = Path(base) / 'engines' / 'koteng_once.py'
        if not wrapper.is_file():
            raise FileNotFoundError('Mangler ' + str(wrapper))
        if report is None:
            raise ValueError('Koteng trenger en rapportfil')
        return ([exe, str(wrapper), '--url', job.url, '--report', str(report)], home, False)
    if job.profile == 'lerkendal_v23':
        expected = ('hurtigkart.py', 'publication.py', 'sync_ministaut.py', 'match_config.py',
                    'verified_navigation.py', 'stadion_felt.json')
        if not all((home / p).is_file() for p in expected):
            raise FileNotFoundError('Lerkendal V23 er ikke komplett i ' + str(home))
        wrapper = Path(base) / 'engines' / 'lerkendal_once.py'
        if not wrapper.is_file():
            raise FileNotFoundError('Mangler ' + str(wrapper))
        if report is None:
            raise ValueError('Lerkendal trenger en rapportfil')
        return ([exe, str(wrapper), '--url', job.url, '--port', str(LERKENDAL_PORT),
                 '--report', str(report)], home, False)
    if job.profile == 'lerkendal_legacy':
        expected = ('hurtigkart.py', 'match_config.py', 'stadion_felt.json')
        if not all((home / p).is_file() for p in expected):
            raise FileNotFoundError('Lerkendal skannermotor mangler i ' + str(home))
        # The legacy scanner reads the first event by URL then manages its own
        # hourly loop, confirmation ENTER, browser window and reporting.
        return ([exe, str(home / 'hurtigkart.py'), '--url', job.url,
                 '--auto-hours', str(job.interval_minutes / 60), '--port', '9222'], home, True)
    raise ValueError('Ukjent skannermotor')


def register_koteng(job: Job, base: Path):
    """Operator approval of a Koteng match: the engine refuses matches not listed here."""
    import json
    path = job.path(base) / 'godkjente_kamper.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    data[job.key] = {'venue_id': 'koteng_arena', 'label': job.label, 'kickoff_at': job.kickoff_at,
                     'approved_by': 'scanner_control_operator', 'approved_at': now_iso(), 'ticket_category': 'ukjent'}
    if path.parent.is_dir():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def schedule_after(job: Job, failures: int, time: datetime) -> str:
    minutes = job.interval_minutes if failures == 0 else min(60, 5 * (2 ** min(failures, 4)))
    return iso(time + timedelta(minutes=minutes))


def outbox_retry(attempts: int, time: datetime, jitter: float | None = None) -> str:
    """2, 4, 8 … max 60 min, plus up to 60 s jitter so retries do not align."""
    seconds = min(3600, 60 * 2 ** attempts) + (random.uniform(0, 60) if jitter is None else jitter)
    return iso(time + timedelta(seconds=seconds))


class Controller:
    def __init__(self, base: Path, store: Store, popen: Callable = subprocess.Popen):
        self.base = Path(base).resolve()
        self.store = store
        self.popen = popen
        self.active: dict[str, Active] = {}
        self.sending: Sending | None = None
        self.messages: list[str] = []
        self.locks_dir = self.base / 'state' / 'locks'
        self.logs_dir = self.base / 'state' / 'logs'

    def say(self, msg: str):
        self.messages.append(msg)

    def lock_path(self, key: str) -> Path:
        return self.locks_dir / lock_name(key)

    # --- locks after a crash ----------------------------------------------
    def stale_locks(self) -> list[str]:
        """Event keys whose lock exists without a running job in this program."""
        if not self.locks_dir.is_dir():
            return []
        keys = [p.name[len('event-'):-len('.lock')] for p in self.locks_dir.glob('event-*.lock')]
        return [k for k in keys if k not in self.active]

    def mark_stale_locks(self):
        for key in self.stale_locks():
            if self.store.job(key) is None:
                continue
            alive = locks.living(self.lock_path(key), ignore=os.getpid())
            note = ('Skanneprosess ' + ', '.join(map(str, alive)) + ' kjører fortsatt uten kontroll.' if alive
                    else 'Låsen ble ikke ryddet (krasj eller strømbrudd). Kontroller og trykk «Frigi lås».')
            self.store.set_due(key, None, REVIEW, note=note)

    def release_lock(self, key: str):
        if key in self.active:
            raise RuntimeError('Jobben kjører; stopp den først')
        locks.release(self.lock_path(key), force_own=True)
        job = self.store.job(key)
        if job is not None:
            due = now_iso() if job.enabled and job.profile in ONE_SHOT else None
            self.store.set_due(key, due, PLANNED if due else READY, failures=0)

    # --- jobs ----------------------------------------------------------------
    def save_job(self, job: Job, original_key: str | None = None):
        if job.key in self.active or (original_key and original_key in self.active):
            raise RuntimeError('Stopp kjørende jobb før endring')
        if original_key and original_key != job.key:
            raise ValueError('Billett-URL kan ikke endres. Slett kampen og legg den til på nytt.')
        exists = self.store.job(job.key) is not None
        if exists and original_key is None:
            raise ValueError('Kampen finnes allerede i listen')
        self.store.put_job(job)
        if job.profile == 'koteng_v24':
            register_koteng(job, self.base)
        # Edits always land deactivated: the operator re-enables deliberately.
        self.store.set_due(job.key, None, OFF if exists else READY)

    def delete_job(self, key: str):
        if key in self.active:
            raise RuntimeError('Stopp kjørende jobb før sletting')
        if self.lock_path(key).exists():
            raise RuntimeError('Kampen har en aktiv lås; frigi den først')
        self.store.delete_job(key)

    def enable(self, key: str, enable: bool, upload: bool = False):
        old = self.store.job(key)
        if old is None:
            raise KeyError(key)
        if key in self.active:
            raise RuntimeError('Stopp kjørende jobb før endring')
        job = Job(**{**old.as_json(), 'enabled': enable, 'upload': upload if enable else False})
        self.store.put_job(job)
        due = now_iso() if enable and job.profile in ONE_SHOT else None
        self.store.set_due(key, due, PLANNED if enable else OFF)

    # --- scans ---------------------------------------------------------------
    def start(self, job: Job, force: bool = False, when: datetime | None = None) -> str:
        now = when or datetime.now(timezone.utc)
        if job.key in self.active:
            raise RuntimeError('Kamp er allerede i gang')
        if job.kickoff() <= now:
            self.store.set_due(job.key, None, DONE)
            raise RuntimeError('Kampstart er passert; skanneren stoppes')
        if job.last_start() <= now:
            self.store.set_due(job.key, None, DONE, note=f'Ingen nye skanninger de siste {job.stop_before_minutes} min før avspark.')
            raise RuntimeError(f'For nær avspark (sperre {job.stop_before_minutes} min)')
        if not force and not job.enabled:
            raise RuntimeError('Aktiver først jobben i kontrollpanelet')
        # One engine folder = one Edge profile/CDP port. Never two of a kind at once.
        if any(x.job.profile == job.profile for x in self.active.values()):
            raise RuntimeError(f'Bare én {NAMES[job.profile]}-skanning kan kjøre om gangen på denne PC-en')
        guard = self.lock_path(job.key)
        report = (self.base / 'state' / 'runs' / f"{job.key}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
                  if job.profile in ONE_SHOT else None)
        command_args, cwd, interactive = command(job, self.base, report=report)
        try:
            acquire(guard, event=job.key)
        except FileExistsError:
            self.mark_stale_locks()
            raise RuntimeError('Kampen har en gammel lås fra en tidligere kjøring. Se status og «Frigi lås».') from None
        from .observations import reports_for
        previous_reports = reports_for(job, cwd)
        log_stream = None
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = self.logs_dir / (job.key + '-' + now.strftime('%Y%m%dT%H%M%SZ') + '.log')
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
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  **_no_window())
            locks.record_child(guard, proc.pid)
            run_id = self.store.begin(job.key, log_path)
            self.active[job.key] = Active(job, proc, run_id, guard, log_stream, now, previous_reports, report=report)
            return 'Kjører: ' + job.label
        except Exception:
            if log_stream:
                log_stream.close()
            guard.unlink(missing_ok=True)
            raise

    def stop(self, key: str, reason: str = STOPPED):
        a = self.active.get(key)
        if a is None:
            return
        a.stop_reason = reason
        _kill_tree(a.process)
        # poll() cleans up when the child has exited. If it never exits the
        # lock stays, forcing a human review of a possible orphan publisher.

    def stop_all(self):
        for key in tuple(self.active):
            self.stop(key)

    def poll(self, when: datetime | None = None):
        now = when or datetime.now(timezone.utc)
        for key, active in tuple(self.active.items()):
            if active.job.kickoff() <= now and active.process.poll() is None and active.stop_reason is None:
                try:
                    self.stop(key, KICKOFF)  # an in-progress scan must not continue past kickoff
                except Exception as exc:
                    self.say(f'{active.job.label}: {exc}')
            elif (active.job.profile in ONE_SHOT and active.stop_reason is None
                  and now - active.started > MAX_RUNTIME and active.process.poll() is None):
                try:
                    self.stop(key, TIMEOUT)
                    self.say(f'{active.job.label}: skanningen brukte over {int(MAX_RUNTIME.total_seconds() // 60)} min og ble stoppet')
                except Exception as exc:
                    self.say(f'{active.job.label}: {exc}')
            code = active.process.poll()
            if code is None:
                continue
            self._finish(key, active, code, now)
        self._outbox(now)
        # One-shot engines are scheduled here; the legacy Lerkendal UI owns its own timing.
        busy = {a.job.profile for a in self.active.values()}
        for job in self.store.jobs():
            if job.key in self.active or not job.enabled or job.profile not in ONE_SHOT or job.profile in busy:
                continue
            state = self.store.state(job.key)
            if state['last_status'] == REVIEW:
                continue
            if job.last_start() <= now:
                if state['next_due'] or state['last_status'] != DONE:
                    self.store.set_due(job.key, None, DONE)
                continue
            due = state['next_due']
            if due and parse_utc(due) <= now:
                try:
                    self.start(job, when=now)
                except Exception as exc:
                    self.say(f'{job.label}: {exc}')
                    if self.store.state(job.key)['last_status'] not in (REVIEW, DONE):
                        self.store.set_due(job.key, iso(now + timedelta(minutes=15)), FAILED, note=str(exc))
                busy.add(job.profile)

    def _finish(self, key: str, active: Active, code: int, now: datetime):
        if active.log:
            active.log.close()
        job = active.job
        status, summary = FAILED, f'Skanneren avsluttet med kode {code}. Se logg.'
        if active.stop_reason:
            status, summary = active.stop_reason, {KICKOFF: 'Stoppet ved avspark.',
                                                   TIMEOUT: 'Stoppet etter tidsavbrudd. Målingen er forkastet.'
                                                   }.get(active.stop_reason, 'Stoppet av operatør. Målingen er forkastet.')
        elif code == 4 and job.profile in ONE_SHOT:
            from .observations import lerkendal_report
            try:
                reason = lerkendal_report(active.report).get('reason') or 'ukjent årsak'
            except RuntimeError as exc:
                reason = str(exc)
            status, summary = REJECTED, 'Ikke publiserbar: ' + reason
        elif code == 0 and job.profile in ONE_SHOT:
            try:
                from .observations import verified_koteng, verified_lerkendal
                verify = verified_lerkendal if job.profile == 'lerkendal_v23' else verified_koteng
                result = verify(job, job.path(self.base), active.report, self.base / 'engines')
                self.store.observation(result, job.upload)
                status, summary = VERIFIED, f"Bekreftet lokalt: {result['available_seated']} ledige i {len(result['sections'])} felt."
                if job.upload and self.store.enqueue(result, result['diagnostic']):
                    status, summary = QUEUED, summary + ' Lagt i utboks for publisering.'
            except Exception as exc:
                # No false success if post-scan revalidation fails.
                code = 3
                summary = f'Kontroll av fersk rapport feilet: {exc}'
                self.say(f'{job.label}: {summary}')
        elif code == 0:
            status, summary = DONE, 'Lerkendal-sesjonen ble avsluttet.'
        if not locks.living(active.lock, ignore=os.getpid()):
            active.lock.unlink(missing_ok=True)
        self.active.pop(key, None)
        ok = status in (VERIFIED, QUEUED)
        fails = 0 if ok or status in (STOPPED, KICKOFF, DONE) else self.store.state(key)['failures'] + 1
        current = self.store.job(key) or job
        due = None
        if current.enabled and current.profile in ONE_SHOT and current.last_start() > now and status not in (STOPPED, KICKOFF):
            due = schedule_after(current, fails, now)
        self.store.finish(active.run_id, key, status, code, due, fails, summary)
        if active.lock.exists():
            self.store.set_due(key, None, REVIEW, failures=fails,
                               note='Skanneprosessen svarer ikke på stopp. Kontroller Oppgavebehandling.')

    # --- outbox --------------------------------------------------------------
    def _outbox(self, now: datetime):
        if self.sending is not None:
            code = self.sending.process.poll()
            if code is None:
                return
            self.sending.log.close()
            row, self.sending = self.sending.row, None
            attempts = row['attempts'] + 1
            if code == 0:
                self.store.outbox_done(row['id'], 'sendt', attempts=attempts)
                self._job_status(row['event_key'], 'publisert observasjon',
                                 f"Publisert til Ministaut som observert (måle-ID {row['run_id'][:12]}).")
            else:
                error = _tail(Path(self.logs_dir / f"outbox-{row['run_id']}.log"))
                too_old = now - parse_utc(row['observed_at']) > OUTBOX_MAX_AGE
                if attempts >= OUTBOX_MAX_ATTEMPTS or too_old:
                    self.store.outbox_done(row['id'], 'forkastet', error, attempts=attempts)
                    self.say(f"Utboks: måling {row['run_id'][:10]} ble ikke publisert ({error}).")
                else:
                    self.store.outbox_done(row['id'], 'venter', error, outbox_retry(attempts, now), attempts)
        row = self.store.due_outbox(iso(now))
        if row is None:
            return
        job = self.store.job(row['event_key'])
        if job is None or not job.upload:
            # Live switched off after queueing: never publish behind the operator's back.
            self.store.outbox_done(row['id'], 'stoppet', 'Live er slått av')
            return
        home = job.path(self.base)
        if job.profile == 'lerkendal_v23':
            sync, args = home / 'sync_ministaut.py', ['-c', SEND_LERKENDAL, row['diagnostic']]
        else:
            sync, args = home / 'sync_koteng.py', ['-c', SEND_KOTENG, str(self.base / 'engines'),
                                                   row['event_key'], row['diagnostic']]
        if not sync.is_file() or not Path(row['diagnostic']).is_file():
            self.store.outbox_done(row['id'], 'forkastet', 'Måling eller ' + sync.name + ' mangler')
            return
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log = (self.logs_dir / f"outbox-{row['run_id']}.log").open('w', encoding='utf-8', errors='replace')
        try:
            proc = self.popen([get_python(home), *args], cwd=str(home),
                              stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **_no_window())
        except Exception as exc:
            log.close()
            self.store.outbox_done(row['id'], 'venter', str(exc), outbox_retry(row['attempts'] + 1, now), row['attempts'] + 1)
            return
        self.store.outbox_done(row['id'], 'sender')
        self.sending = Sending(row, proc, log)

    def _job_status(self, key: str, status: str, note: str):
        if key in self.active or self.store.job(key) is None:
            return
        with self.store.write() as db:
            db.execute('UPDATE jobs SET last_status=?, note=? WHERE key=?', (status, note, key))

    def recover_outbox(self):
        """Rows left in 'sender' by a crash go back to the queue (ingest is idempotent per run_id)."""
        with self.store.write() as db:
            db.execute("UPDATE outbox SET status='venter' WHERE status='sender'")


def _kill_tree(process):
    # On Windows kill only descendants of this launched PID, not other
    # independent Edge windows. Prevent orphan one-shot scanner publishing.
    if os.name == 'nt':
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=20, check=False, **_no_window())
        if result.returncode not in (0, 128, 255) and process.poll() is None:
            raise RuntimeError('Kunne ikke stoppe skannerens prosessgruppe')
    else:
        process.terminate()


def _tail(path: Path, chars: int = 160) -> str:
    try:
        text = path.read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return 'ukjent feil'
    lines = [l for l in text.splitlines() if l.strip()]
    return (lines[-1] if lines else 'ukjent feil')[-chars:]
