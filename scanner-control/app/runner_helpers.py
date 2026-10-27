"""Dependency-free path resolution shared between process and observation gate."""
import os
import sys
from pathlib import Path


def interpreter_for(path: Path) -> str:
    bins=([path / '.venv' / 'Scripts' / 'python.exe'] if os.name=='nt'
          else [path / '.venv' / 'bin' / 'python'])
    return str(next((p for p in bins if p.is_file()),Path(sys.executable)))
