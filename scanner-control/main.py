"""Launch Ministaut Scanner Control (Windows desktop, Python 3.10+)."""
from pathlib import Path
import sys
from app.gui import App

if __name__ == '__main__':
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 eller nyere kreves')
    App(Path(__file__).resolve().parent).run()
