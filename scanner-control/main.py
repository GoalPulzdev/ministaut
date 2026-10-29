"""Launch Ministaut Scanner Control (Windows desktop, Python 3.10+)."""
from datetime import datetime
import sys
import traceback
from app.runner_helpers import program_dir


def crash(exc: BaseException):
    # A windowed .exe has no console: write the error to a file and show it.
    base = program_dir()
    log = base / 'state' / 'logs' / ('app-feil-' + datetime.now().strftime('%Y%m%dT%H%M%S') + '.log')
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(''.join(traceback.format_exception(exc)), encoding='utf-8')
    except OSError:
        pass
    try:
        from tkinter import messagebox
        messagebox.showerror('Ministaut Scanner Control', f'Programmet stoppet med feil:\n\n{exc}\n\nDetaljer: {log}')
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)


if __name__ == '__main__':
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10 eller nyere kreves')
    try:
        from app.gui import App
        App(program_dir()).run()
    except SystemExit:
        raise
    except BaseException as exc:
        crash(exc)
        raise SystemExit(1)
