"""SQLite WAL event history, status, job recurrence and durable publish outbox."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from .model import Job


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=10000')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs (
            key TEXT PRIMARY KEY, config_json TEXT NOT NULL,
            next_due TEXT, failures INTEGER NOT NULL DEFAULT 0,
            last_status TEXT NOT NULL DEFAULT 'klar', last_finished TEXT,
            last_log TEXT);
          CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL,
            started TEXT NOT NULL, ended TEXT, status TEXT NOT NULL,
            log_file TEXT, exit_code INTEGER, summary TEXT,
            FOREIGN KEY(key) REFERENCES jobs(key));
          CREATE INDEX IF NOT EXISTS run_latest ON runs(key, started DESC);
          CREATE TABLE IF NOT EXISTS observations (
            event_key TEXT NOT NULL, run_id TEXT NOT NULL,
            observed_at TEXT NOT NULL, available_seated INTEGER NOT NULL,
            section_count INTEGER NOT NULL, upload_requested INTEGER NOT NULL,
            quality_status TEXT NOT NULL, PRIMARY KEY(event_key, run_id));
          CREATE INDEX IF NOT EXISTS observation_latest ON observations(event_key, observed_at DESC);
          CREATE TABLE IF NOT EXISTS outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_key TEXT NOT NULL,
            run_id TEXT NOT NULL UNIQUE, diagnostic TEXT NOT NULL,
            observed_at TEXT NOT NULL, created TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'venter', attempts INTEGER NOT NULL DEFAULT 0,
            next_try TEXT NOT NULL, last_error TEXT, sent_at TEXT);
          CREATE INDEX IF NOT EXISTS outbox_due ON outbox(status, next_try);
        ''')
        # V0.1 databases: add columns in place, never drop history.
        self._column('jobs', 'note', 'TEXT')
        self.db.commit()

    def _column(self, table: str, name: str, decl: str):
        if name not in {r['name'] for r in self.db.execute(f'PRAGMA table_info({table})')}:
            self.db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {decl}')

    @contextmanager
    def write(self):
        with self.db:
            yield self.db

    def close(self):
        self.db.close()

    def put_job(self, job: Job):
        with self.write() as db:
            db.execute('''INSERT INTO jobs(key,config_json) VALUES (?,?)
              ON CONFLICT(key) DO UPDATE SET config_json=excluded.config_json''',
              (job.key, json.dumps(job.as_json(), ensure_ascii=False)))

    def delete_job(self, key: str):
        with self.write() as db:
            db.execute('DELETE FROM jobs WHERE key=?', (key,))
            db.execute("UPDATE outbox SET status='stoppet',last_error='Kamp slettet' WHERE event_key=? AND status='venter'", (key,))

    def jobs(self) -> list[Job]:
        return [Job.from_json(json.loads(row['config_json'])) for row in
                self.db.execute('SELECT config_json FROM jobs ORDER BY key')]

    def job(self, key: str) -> Job | None:
        row = self.db.execute('SELECT config_json FROM jobs WHERE key=?', (key,)).fetchone()
        return Job.from_json(json.loads(row['config_json'])) if row else None

    def state(self, key: str) -> dict:
        row = self.db.execute('SELECT * FROM jobs WHERE key=?', (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return dict(row)

    def set_due(self, key: str, due: str | None, status: str | None = None,
                failures: int | None = None, note: str | None = None):
        with self.write() as db:
            db.execute('''UPDATE jobs SET next_due=?, last_status=COALESCE(?,last_status),
                          failures=COALESCE(?,failures), note=? WHERE key=?''',
                       (due, status, failures, note, key))

    def begin(self, key: str, path: Path) -> int:
        with self.write() as db:
            cur = db.execute('INSERT INTO runs(key,started,status,log_file) VALUES (?,?,?,?)',
                             (key, now_iso(), 'running', str(path)))
            db.execute('UPDATE jobs SET last_status=?,last_log=?,note=NULL WHERE key=?', ('skanner', str(path), key))
            return cur.lastrowid

    def finish(self, run_id: int, key: str, status: str, returncode: int | None, due: str | None,
               failures: int, summary: str):
        with self.write() as db:
            db.execute('UPDATE runs SET ended=?,status=?,exit_code=?,summary=? WHERE id=?',
                       (now_iso(), status, returncode, summary[:300], run_id))
            db.execute('UPDATE jobs SET last_status=?,last_finished=?,failures=?,next_due=?,note=? WHERE key=?',
                       (status, now_iso(), failures, due, summary[:300], key))

    def observation(self, verified: dict, requested_upload: bool):
        with self.write() as db:
            db.execute('''INSERT OR IGNORE INTO observations
              (event_key,run_id,observed_at,available_seated,section_count,upload_requested,quality_status)
              VALUES (?,?,?,?,?,?,?)''',
              (verified['event_key'], verified['run_id'], verified['observed_at'],
               verified['available_seated'], len(verified['sections']), int(requested_upload),
               verified['quality_status']))

    def latest(self, key: str) -> dict | None:
        row = self.db.execute('SELECT * FROM observations WHERE event_key=? ORDER BY observed_at DESC LIMIT 1', (key,)).fetchone()
        return dict(row) if row else None

    def history(self, key: str, limit: int = 12) -> list[dict]:
        """Newest first, with change vs. the previous verified observation and send status."""
        rows = [dict(r) for r in self.db.execute('''
            SELECT o.*, x.status AS publish_status FROM observations o
            LEFT JOIN outbox x ON x.run_id=o.run_id
            WHERE o.event_key=? ORDER BY o.observed_at DESC LIMIT ?''', (key, limit + 1))]
        for i, row in enumerate(rows):
            nxt = rows[i + 1] if i + 1 < len(rows) else None
            row['delta'] = None if nxt is None else row['available_seated'] - nxt['available_seated']
        return rows[:limit]

    def recent(self, key: str, limit: int = 10) -> list[dict]:
        return [dict(row) for row in self.db.execute('SELECT * FROM runs WHERE key=? ORDER BY id DESC LIMIT ?', (key, limit))]

    # --- outbox: publish only after the controller's own quality gate -------
    def enqueue(self, verified: dict, diagnostic: str) -> bool:
        with self.write() as db:
            cur = db.execute('''INSERT OR IGNORE INTO outbox(event_key,run_id,diagnostic,observed_at,created,next_try)
                                VALUES (?,?,?,?,?,?)''',
                             (verified['event_key'], verified['run_id'], diagnostic,
                              verified['observed_at'], now_iso(), now_iso()))
            return cur.rowcount == 1

    def due_outbox(self, now: str) -> dict | None:
        row = self.db.execute("SELECT * FROM outbox WHERE status='venter' AND next_try<=? ORDER BY id LIMIT 1", (now,)).fetchone()
        return dict(row) if row else None

    def outbox_done(self, row_id: int, status: str, error: str | None = None,
                    next_try: str | None = None, attempts: int | None = None):
        with self.write() as db:
            db.execute('''UPDATE outbox SET status=?, last_error=?, next_try=COALESCE(?,next_try),
                          attempts=COALESCE(?,attempts), sent_at=CASE WHEN ?='sendt' THEN ? ELSE sent_at END
                          WHERE id=?''', (status, error, next_try, attempts, status, now_iso(), row_id))

    def outbox_counts(self) -> dict:
        return {r['status']: r['n'] for r in self.db.execute('SELECT status, COUNT(*) AS n FROM outbox GROUP BY status')}
