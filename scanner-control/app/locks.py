"""Per-event and per-program lock files with PID ownership.

A lock is never removed silently: after a crash the operator sees
TRENGER GJENNOMGANG and releases it explicitly, and only once no recorded
process is still alive (an orphaned scanner could otherwise publish twice).
"""
from __future__ import annotations
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import socket


class LockBusy(RuntimeError):
    pass


def lock_name(key: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', key):
        raise ValueError('Ugyldig ID')
    return 'event-' + key + '.lock'


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return kernel32.GetLastError() == 5  # access denied: exists, owned by someone else
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write(path: Path, info: dict, create: bool):
    flags = os.O_WRONLY | (os.O_CREAT | os.O_EXCL if create else os.O_TRUNC)
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(''.join(f'{k}={v}\n' for k, v in info.items()))


def acquire(path: Path, **extra):
    """Atomic create; raises FileExistsError if the lock exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, {'controller_pid': os.getpid(), 'host': socket.gethostname(),
                  'started_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **extra}, True)


def read(path: Path) -> dict:
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return {}
    return dict(line.split('=', 1) for line in lines if '=' in line)


def record_child(path: Path, pid: int):
    info = read(path)
    info['child_pid'] = pid
    _write(path, info, False)


def pids(info: dict) -> list[int]:
    out = []
    for k in ('controller_pid', 'child_pid'):
        try:
            out.append(int(info.get(k, '')))
        except ValueError:
            pass
    return out


def living(path: Path, ignore: int | None = None) -> list[int]:
    return [p for p in pids(read(path)) if p != ignore and pid_alive(p)]


def release(path: Path, force_own: bool = False):
    """Remove a stale lock. Refuses while a recorded process is still alive."""
    if not path.exists():
        return
    alive = living(path, ignore=os.getpid() if force_own else None)
    if alive:
        raise LockBusy('Prosess ' + ', '.join(map(str, alive)) + ' kjører fortsatt. '
                       'Stopp den (Oppgavebehandling) før låsen frigis.')
    path.unlink(missing_ok=True)


def acquire_program(path: Path):
    """Single control centre per folder. Replaces the lock only if its owner is gone."""
    try:
        acquire(path)
        return
    except FileExistsError:
        if living(path):
            raise LockBusy('Kontrollsenteret kjører allerede på denne PC-en.')
    path.unlink(missing_ok=True)
    acquire(path)
