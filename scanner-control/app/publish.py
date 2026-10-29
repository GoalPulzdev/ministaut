"""Publish a match on the web page before its first live scan (engines/register_match.py)."""
from __future__ import annotations
from pathlib import Path
import json
import subprocess
from .model import Job
from .runner_helpers import interpreter_for, no_window


def register_command(job: Job, base: Path) -> list[str]:
    return [interpreter_for(job.path(base)), str(base / 'engines' / 'register_match.py'),
            '--event-key', job.key, '--title', job.label, '--kickoff', job.kickoff_at, '--venue', job.venue]


def register_on_web(job: Job, base: Path, run=subprocess.run) -> dict:
    """Returns the registered match; raises RuntimeError with a readable reason."""
    home = job.path(base)
    if not home.is_dir():
        raise RuntimeError('Motormappen finnes ikke: ' + str(home))
    try:
        done = run(register_command(job, base), cwd=str(home), capture_output=True, text=True,
                   encoding='utf-8', errors='replace', timeout=40, stdin=subprocess.DEVNULL, **no_window())
    except subprocess.TimeoutExpired:
        raise RuntimeError('Nettsiden svarte ikke innen 40 sekunder') from None
    lines = [l for l in (done.stdout or '').splitlines() if l.strip()]
    try:
        reply = json.loads(lines[-1]) if lines else {}
    except ValueError:
        reply = {}
    if done.returncode != 0 or not reply.get('ok'):
        raise RuntimeError(reply.get('error') or (done.stderr or 'ukjent feil').strip()[-300:])
    return reply['match']
