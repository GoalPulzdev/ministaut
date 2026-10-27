"""Read-only pre-flight check for the pilot PC. Never reads token contents."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .model import Job
from .observations import token_configured
from .runner_helpers import interpreter_for, no_window

EDGE = [Path(os.environ.get(v, '')) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
        for v in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')]
KOTENG_FILES = ('hourly_koteng.py', 'koteng_scanner.py', 'profile_lock.py',
                'koteng_profile.json', 'ankerpunkter_koteng.json', 'sync_koteng.py')
LERKENDAL_FILES = ('hurtigkart.py', 'match_config.py', 'stadion_felt.json')


def _imports(python: str, cwd: Path, module: str) -> bool:
    try:
        return subprocess.run([python, '-c', f'import {module}'], cwd=str(cwd), capture_output=True,
                              timeout=30, check=False, **no_window()).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check(base: Path, jobs: list[Job]) -> list[tuple[bool | None, str]]:
    """(True=ok, False=blocking, None=warning, text)."""
    out: list[tuple[bool | None, str]] = []
    out.append((sys.version_info >= (3, 10), ('Kontrollsenter (Windows-app)' if getattr(sys, 'frozen', False)
                                             else f'Python {sys.version.split()[0]}')))
    if os.name == 'nt':
        out.append((any(p.is_file() for p in EDGE), 'Microsoft Edge installert'))
    usage = shutil.disk_usage(base)
    out.append((usage.free > 2 * 1024 ** 3 or None, f'Ledig disk: {usage.free // 1024 ** 3} GB'))
    out.append((shutil.which('git') is not None or None, 'Git for Windows (trengs bare for 03_LAST_NED_LERKENDAL)'))
    seen: set[Path] = set()
    for job in jobs:
        home = job.path(base)
        if home in seen:
            continue
        seen.add(home)
        files = KOTENG_FILES if job.profile == 'koteng_v24' else LERKENDAL_FILES
        name = 'Koteng' if job.profile == 'koteng_v24' else 'Lerkendal'
        missing = [f for f in files if not (home / f).is_file()]
        if not home.is_dir():
            out.append((False, f'{name}: mappe mangler ({home})'))
            continue
        out.append((not missing, f'{name}: motorfiler' + (' mangler ' + ', '.join(missing) if missing else ' komplette')))
        python = interpreter_for(home)
        venv = Path(python).parent.parent.name == '.venv'
        out.append((venv or None, f'{name}: eget .venv' + ('' if venv else ' mangler (bruker system-Python)')))
        out.append((_imports(python, home, 'playwright'), f'{name}: Playwright installert'))
        if job.profile == 'koteng_v24':
            out.append((token_configured(home) or None,
                        'Koteng: token for Live ' + ('er satt opp lokalt' if token_configured(home)
                                                     else 'mangler (kun nødvendig for Live)')))
    return out
