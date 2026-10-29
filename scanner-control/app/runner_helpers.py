"""Dependency-free path resolution shared between process and observation gate."""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def program_dir() -> Path:
    """Folder holding state/ and adapters/: next to the .exe when built, else next to main.py."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def interpreter_for(path: Path) -> str:
    bins=([path / '.venv' / 'Scripts' / 'python.exe'] if os.name=='nt'
          else [path / '.venv' / 'bin' / 'python'])
    found = next((p for p in bins if p.is_file()), None)
    if found:
        return str(found)
    # Built .exe: sys.executable is the app itself, never a Python interpreter.
    if getattr(sys, 'frozen', False):
        return shutil.which('python') or shutil.which('py') or 'python'
    return sys.executable


def no_window() -> dict:
    """Hide console windows of helper processes when running as a windowed app."""
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
