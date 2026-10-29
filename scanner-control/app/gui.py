"""Local Tkinter application. No exposed HTTP server, no browser auth or secrets."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from . import __version__, health, locks, oslo
from .model import ENGINES, ONE_SHOT, Job, checkout_key, parse_utc
from .observations import token_configured
from .publish import register_on_web
from .runner import Controller, REVIEW, FAILED, PLANNED, REJECTED, TIMEOUT
from .storage import Store
from .cards import CardGrid

BG = '#09160f'; PANEL = '#14271b'; PANEL2 = '#1d3526'; FG = '#eaf8ec'; DIM = '#9dbba4'; ACC = '#79e8a2'
WARN = '#ffcf7a'; BAD = '#ff8f8f'
TICK_MS = 2000
# Compact badge text for the cards; full status stays in the detail line.
# Team -> engine for a home match; editing the team picks the matching scanner.
TEAM_ENGINE = {'RBK Herrer': 'lerkendal_v23', 'RBK Kvinner': 'koteng_v24'}
SHORT = {'publisert observasjon': 'PUBLISERT', 'bekreftet lokalt': 'BEKREFTET', 'køet for sending': 'SENDES',
         'avvist av kvalitetskontroll': 'AVVIST', 'trenger gjennomgang': 'SJEKK LÅS', 'stoppet ved avspark': 'AVSPARK',
         'tidsavbrudd': 'TIDSAVBRUDD', 'planlagt': 'PLANLAGT', 'ferdig': 'FERDIG', 'feil': 'FEIL', 'klar': 'KLAR',
         'av': 'PAUSE', 'stoppet': 'STOPPET'}


def clean_checkout(url: str) -> str:
    """Accept a pasted ticket link with tracking parameters or a trailing slash."""
    url = url.strip().split('#', 1)[0].split('?', 1)[0].rstrip('/')
    return url.replace('http://', 'https://', 1)


def when_text(value: str | None) -> str:
    try:
        return oslo.text(parse_utc(value))
    except (ValueError, TypeError, AttributeError):
        return '—'


def age_text(value: str | None, now: datetime) -> str:
    try:
        minutes = int((now - parse_utc(value)).total_seconds() // 60)
    except (ValueError, TypeError, AttributeError):
        return '—'
    if minutes < 2:
        return 'nå'
    if minutes < 120:
        return f'{minutes} min'
    return f'{minutes // 60} t' if minutes < 48 * 60 else f'{minutes // 1440} d'


def delta_text(value: int | None) -> str:
    return '—' if value is None else ('±0' if value == 0 else f'{value:+d}')


class Editor(tk.Toplevel):
    def __init__(self, master, base: Path, on_save, teams: list[str], existing: Job | None = None):
        super().__init__(master)
        self.base = base; self.on_save = on_save; self.existing = existing
        self.title('Rediger kamp' if existing else 'Legg til kamp'); self.resizable(False, False)
        self.configure(bg=BG); self.transient(master); self.grab_set()
        j = existing
        kickoff = oslo.to_oslo(j.kickoff()) if j else None
        self.v = {k: tk.StringVar(value=val) for k, val in {
            'label': j.label if j else 'Rosenborg – ',
            'team': j.team if j else 'RBK Herrer',
            'profile': j.profile if j else 'lerkendal_v23',
            'url': j.url if j else 'https://billett.rbk.no/checkout/',
            'date': kickoff.strftime('%d.%m.%Y') if kickoff else '',
            'time': kickoff.strftime('%H:%M') if kickoff else '',
            'scanner_path': j.scanner_path if j else ENGINES['lerkendal_v23'][1],
            'interval_minutes': str(j.interval_minutes if j else 60),
            'stop_before_minutes': str(j.stop_before_minutes if j else -5),
            'final_window_minutes': str(j.final_window_minutes if j else 90),
            'final_interval_minutes': str(j.final_interval_minutes if j else 15)}.items()}
        rows = [('Kampnavn', 'label', 'entry'), ('Lag', 'team', 'team'), ('Skannermotor', 'profile', 'profile'),
                ('Billett-URL (checkout)', 'url', 'url'), ('Avspark dato (dd.mm.åååå)', 'date', 'entry'),
                ('Avspark klokkeslett, norsk tid', 'time', 'entry'), ('Mappe med skannermotor', 'scanner_path', 'entry'),
                ('Intervall (minutter)', 'interval_minutes', 'entry'),
                ('Siste skanning, min før avspark (−5 = 5 min etter)', 'stop_before_minutes', 'entry'),
                ('Sluttfase: siste … min før avspark', 'final_window_minutes', 'entry'),
                ('Intervall i sluttfasen (minutter)', 'final_interval_minutes', 'entry')]
        for i, (label, key, kind) in enumerate(rows):
            tk.Label(self, text=label, bg=BG, fg=FG, font=('Segoe UI', 10)).grid(row=i, column=0, padx=15, pady=6, sticky='w')
            if kind == 'team':
                w = ttk.Combobox(self, textvariable=self.v[key], values=teams, width=50)
                w.bind('<<ComboboxSelected>>', self.team_changed)
            elif kind == 'profile':
                w = ttk.Combobox(self, textvariable=self.v[key], values=sorted(ENGINES), state='readonly', width=50)
                w.bind('<<ComboboxSelected>>', self.engine_changed)
            else:
                w = tk.Entry(self, textvariable=self.v[key], width=53, bg='#213729', fg=FG,
                             insertbackground=ACC, relief='flat', disabledbackground=PANEL, disabledforeground=DIM)
                if kind == 'url' and existing:
                    w.configure(state='disabled')
            w.grid(row=i, column=1, padx=12, pady=6, sticky='ew')
        self.venue = tk.Label(self, bg=BG, fg=DIM, font=('Segoe UI', 9)); self.venue.grid(row=len(rows), column=1, sticky='w', padx=12)
        self.engine_changed(keep_path=True)
        bar = tk.Frame(self, bg=BG); bar.grid(row=len(rows) + 1, column=1, sticky='ew', padx=10, pady=14)
        ttk.Button(bar, text='Velg mappe', command=self.browse).pack(side='left')
        ttk.Button(bar, text='Lagre og aktiver', command=lambda: self.save(True), style='Primary.TButton').pack(side='right')
        ttk.Button(bar, text='Lagre (deaktivert)', command=self.save).pack(side='right', padx=(0, 6))
        self.bind('<Escape>', lambda _e: self.destroy())

    def team_changed(self, _evt=None):
        engine = TEAM_ENGINE.get(self.v['team'].get())
        if engine and not self.existing:
            self.v['profile'].set(engine)
            self.engine_changed()

    def engine_changed(self, _evt=None, keep_path=False):
        venue, folder = ENGINES[self.v['profile'].get()]
        self.venue.configure(text='Arena: ' + venue.replace('_', ' ').title()
                             + '   ·   publiseres på nettsiden når du slår på Live')
        if not keep_path:
            self.v['scanner_path'].set(folder)

    def browse(self):
        dest = filedialog.askdirectory(parent=self, initialdir=str(self.base))
        if dest:
            self.v['scanner_path'].set(dest)

    def save(self, activate: bool = False):
        try:
            v = {k: x.get().strip() for k, x in self.v.items()}
            v['url'] = clean_checkout(v['url'])
            kickoff = oslo.parse_local(v.pop('date'), v.pop('time'))
            for k in ('interval_minutes', 'stop_before_minutes', 'final_window_minutes', 'final_interval_minutes'):
                try:
                    v[k] = int(v[k].replace('−', '-'))
                except ValueError:
                    raise ValueError('Intervall og sperre må være hele minutter') from None
            v['venue'] = ENGINES[v['profile']][0]
            v['key'] = checkout_key(v['url'])
            v['kickoff_at'] = kickoff.isoformat()
            job = Job(**v, enabled=False, upload=False)
            self.on_save(job, self.existing.key if self.existing else None, activate)
            self.destroy()
        except Exception as exc:
            messagebox.showerror('Kan ikke lagre kamp', str(exc), parent=self)


class App:
    def __init__(self, base: Path):
        self.base = base
        self.root = tk.Tk(); self.root.withdraw()
        self.app_lock = base / 'state' / 'app.lock'
        try:
            locks.acquire_program(self.app_lock)
        except locks.LockBusy as exc:
            messagebox.showerror('Allerede åpen', str(exc)); self.root.destroy()
            raise SystemExit(1) from None
        self.store = Store(base / 'state' / 'control.sqlite3')
        self.controller = Controller(base, self.store)
        self.controller.recover_outbox()
        self._seed()
        self.controller.mark_stale_locks()
        self.selected: str | None = None
        self.show_archive = False
        self.closing = False
        self._log_shown = ('', 0.0)
        self._detail_shown = None
        self._build()
        self.root.deiconify()
        self._tick()

    # --- layout --------------------------------------------------------------
    def _build(self):
        r = self.root
        r.title(f'MINISTAUT · Scanner Control {__version__}')
        r.geometry('1280x940'); r.minsize(980, 700); r.configure(bg=BG)
        icon = Path(getattr(sys, '_MEIPASS', self.base)) / 'ministaut.ico'
        if icon.is_file():
            try:
                r.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        self._style()
        head = tk.Frame(r, bg=BG); head.pack(fill='x', padx=24, pady=(18, 4))
        brand = tk.Frame(head, bg=BG); brand.pack(side='left')
        tk.Label(brand, text='M', bg=ACC, fg=BG, font=('Segoe UI', 15, 'bold'), width=2).pack(side='left', padx=(0, 12))
        names = tk.Frame(brand, bg=BG); names.pack(side='left')
        tk.Label(names, text='Ministaut Scanner Control', anchor='w', bg=BG, fg=FG,
                 font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        self.summary = tk.Label(names, text='', anchor='w', bg=BG, fg=DIM, font=('Segoe UI', 9))
        self.summary.pack(anchor='w')
        self.live_pill = tk.Label(head, font=('Segoe UI', 10, 'bold'), padx=14, pady=6)
        self.live_pill.pack(side='right')

        bar = tk.Frame(r, bg=BG); bar.pack(fill='x', padx=24, pady=(12, 12))
        for label, fun, style in [('Test én gang', self.test, 'Primary.TButton'), ('Start nå', self.start_now, 'TButton'),
                                  ('Aktiver / Pause', self.toggle, 'TButton'), ('Live av/på', self.live, 'TButton'),
                                  ('Stopp', self.stop, 'Danger.TButton')]:
            ttk.Button(bar, text=label, command=fun, style=style).pack(side='left', padx=(0, 6))
        self.archive_button = ttk.Button(bar, text='Arkiv', command=self.toggle_archive, style='Ghost.TButton')
        self.archive_button.pack(side='right', padx=(6, 0))
        for label, fun in [('Systemsjekk', self.health), ('Frigi lås', self.release), ('Åpne mappe', self.folder),
                           ('Slett', self.delete), ('Rediger', self.edit), ('+ Legg til kamp', self.add)]:
            ttk.Button(bar, text=label, command=fun, style='Ghost.TButton' if label[0] != '+' else 'Primary.TButton'
                       ).pack(side='right', padx=(6, 0))

        self.cards = CardGrid(r, self.pick, lambda key: (self.pick(key), self.edit()))
        self.cards.pack(fill='both', expand=True, padx=24)

        self.note = tk.Label(r, text='Velg en kamp for detaljer.', bg=BG, fg=DIM, font=('Segoe UI', 10),
                             anchor='w', justify='left', wraplength=1150)
        self.note.pack(fill='x', padx=24, pady=(4, 6))
        book = ttk.Notebook(r); book.pack(fill='x', padx=24, pady=(0, 8))
        self.hist = self._table(book, 'Målinger', [('time', 'MÅLT (NORSK TID)', 150), ('free', 'LEDIGE', 80),
                                                   ('delta', 'ENDRING', 80), ('fields', 'FELT', 60),
                                                   ('pub', 'PUBLISERING', 160), ('run', 'MÅLE-ID', 200)])
        self.runs = self._table(book, 'Kjøringer', [('start', 'START', 140), ('end', 'SLUTT', 140),
                                                    ('status', 'STATUS', 150), ('code', 'KODE', 55), ('sum', 'OPPSUMMERING', 520)])
        self.logview = self._text(book, 'Skannerlogg')
        self.events = self._text(book, 'Hendelser')
        self.footer = tk.Label(r, text='', anchor='w', bg=BG, fg=DIM, font=('Segoe UI', 9))
        self.footer.pack(fill='x', padx=24, pady=(0, 12), anchor='w')
        r.protocol('WM_DELETE_WINDOW', self.close)

    def _table(self, book, title, cols):
        frame = tk.Frame(book, bg=PANEL); book.add(frame, text=title)
        t = ttk.Treeview(frame, columns=[c[0] for c in cols], show='headings', height=4, style='Detail.Treeview')
        for c, label, w in cols:
            t.heading(c, text=label); t.column(c, width=w, anchor='w', stretch=(c == cols[-1][0]))
        t.pack(fill='both', expand=True)
        return t

    def _text(self, book, title):
        frame = tk.Frame(book, bg=PANEL); book.add(frame, text=title)
        t = tk.Text(frame, bg=PANEL, fg=FG, insertbackground=ACC, height=6, font=('Consolas', 9),
                    borderwidth=0, wrap='word', state='disabled')
        t.pack(fill='both', expand=True)
        return t

    def _style(self):
        st = ttk.Style(self.root); st.theme_use('clam')
        st.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=34,
                     font=('Segoe UI', 10), borderwidth=0)
        st.configure('Detail.Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=26,
                     font=('Segoe UI', 9), borderwidth=0)
        st.map('Detail.Treeview', background=[('selected', '#276a45')])
        st.configure('Treeview.Heading', background=PANEL2, foreground=ACC, font=('Segoe UI', 9, 'bold'), relief='flat')
        st.map('Treeview', background=[('selected', '#276a45')], foreground=[('selected', '#ffffff')])
        st.configure('TButton', background='#28523a', foreground=FG, font=('Segoe UI', 9, 'bold'), padding=(10, 8), borderwidth=0)
        st.map('TButton', background=[('active', '#33734d')])
        st.configure('Primary.TButton', background=ACC, foreground=BG)
        st.map('Primary.TButton', background=[('active', '#a3f0c0')])
        st.configure('Danger.TButton', background='#4a1f1f', foreground='#ffb4b4')
        st.map('Danger.TButton', background=[('active', '#6a2a2a')])
        st.configure('Ghost.TButton', background=BG, foreground=DIM, padding=(8, 8))
        st.map('Ghost.TButton', background=[('active', PANEL2)], foreground=[('active', FG)])
        st.configure('TNotebook', background=BG, borderwidth=0)
        st.configure('TNotebook.Tab', background=PANEL2, foreground=DIM, padding=(14, 6), font=('Segoe UI', 9, 'bold'))
        st.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', ACC)])
        st.configure('TCombobox', fieldbackground='#213729', foreground=FG, background=PANEL2)

    def _seed(self):
        if self.store.jobs():
            return
        for job in [
            Job('6aaceecebfe408c38e1712dd', 'Rosenborg – Røa', 'RBK Kvinner', 'koteng_arena',
                'https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd',
                '2026-11-01T13:30:00Z', 'koteng_v24', 'adapters/koteng'),
            Job('6a9a7e3f3f93920b289b0675', 'Rosenborg – Molde', 'RBK Herrer', 'lerkendal',
                'https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675',
                '2026-11-28T17:00:00Z', 'lerkendal_legacy', 'sources/ministaut/scanner'),
            Job('6a9a7c2b15599587216e21f3', 'Rosenborg – Start', 'RBK Herrer', 'lerkendal',
                'https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3',
                '2026-11-07T17:00:00Z', 'lerkendal_legacy', 'sources/ministaut/scanner')]:
            self.store.put_job(job)

    # --- helpers -------------------------------------------------------------
    def get_selected(self) -> Job:
        job = self.store.job(self.selected) if self.selected else None
        if job is None:
            raise ValueError('Velg en kamp i tabellen først')
        return job

    def handle(self, callback):
        try:
            callback()
        except Exception as exc:
            messagebox.showerror('Stoppet for sikkerhet', str(exc), parent=self.root)
        self.render()

    def ask(self, title, text):
        return messagebox.askyesno(title, text, parent=self.root)

    def event(self, msg: str):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.events.configure(state='normal'); self.events.insert('end', stamp + '  ' + msg + '\n')
        self.events.see('end'); self.events.configure(state='disabled')

    # --- actions -------------------------------------------------------------
    def save_job(self, job: Job, original: str | None, activate: bool = False):
        self.controller.save_job(job, original)
        self.selected = job.key
        if activate:
            self.controller.enable(job.key, True, False)
            self.event(f'{job.label}: lagret og aktivert (lokal skanning, slå på Live for å publisere)')
        else:
            self.event(f'{job.label}: lagret (deaktivert til du aktiverer)')
        self.render()

    def teams(self) -> list[str]:
        return sorted({j.team for j in self.store.jobs()} | {'RBK Herrer', 'RBK Kvinner'})

    def add(self):
        Editor(self.root, self.base, self.save_job, self.teams())

    def edit(self):
        self.handle(lambda: Editor(self.root, self.base, self.save_job, self.teams(), self.get_selected()))

    def delete(self):
        def work():
            j = self.get_selected()
            if self.ask('Slette kamp?', f'Fjerne «{j.label}» fra listen?\n\nLokal historikk beholdes i databasen.'):
                self.controller.delete_job(j.key); self.event(j.label + ': slettet'); self.selected = None
        self.handle(work)

    def folder(self):
        def work():
            path = self.get_selected().path(self.base)
            if not path.is_dir():
                raise FileNotFoundError('Mappen finnes ikke: ' + str(path))
            if os.name == 'nt':
                os.startfile(str(path))
            else:
                self.event('Skannermappe: ' + str(path))
        self.handle(work)

    def toggle(self):
        def work():
            j = self.get_selected(); self.controller.enable(j.key, not j.enabled, False)
            if j.enabled:
                self.event(j.label + ': deaktivert')
            elif j.profile in ONE_SHOT:
                self.event(j.label + ': planlagt hver ' + str(j.interval_minutes) + ' min (uten publisering)')
            else:
                self.event(j.label + ': aktivert. Lerkendal startes manuelt med «Start nå».')
        self.handle(work)

    def live(self):
        def work():
            j = self.get_selected()
            if j.profile not in ONE_SHOT:
                raise ValueError('Legacy-Lerkendal styrer publisering i egen motor. Bytt kampen til lerkendal_v23.')
            if not j.enabled:
                raise ValueError('Aktiver jobben først')
            desired = not j.upload
            if desired and not token_configured(j.path(self.base)):
                raise ValueError('Token mangler i motormappen (.ministaut-token). Sett det opp lokalt, aldri i chat/Git.')
            old = ('Er den gamle Lerkendal-skanneren (START_TO_KAMPER_1_TIME / hurtigkart --multi) stoppet, '
                   'eller er denne kampen fjernet fra dens kamper.json? Ellers publiserer to skannere samme kamp.'
                   if j.profile == 'lerkendal_v23' else 'Er den gamle Koteng-skanneren på andre PC-er stoppet?')
            if desired and not self.ask('Aktivere live?', old + '\n\n'
                    'Bare målinger som består kontrollprogrammets egen etterkontroll publiseres som observerte '
                    'sitteplasser til Ministaut. Feilede sendinger prøves på nytt automatisk.'):
                return
            if desired and not self.publish_match(j):
                return
            self.controller.enable(j.key, True, desired)
            self.event('Live ' + ('aktivert' if desired else 'deaktivert') + ' for ' + j.label)
        self.handle(work)

    def publish_match(self, j: Job) -> bool:
        """Put the match on the web page (title, kickoff) before the first live scan."""
        self.root.config(cursor='watch'); self.root.update_idletasks()
        try:
            match = register_on_web(j, self.base)
        except RuntimeError as exc:
            koteng = j.venue == 'koteng_arena'
            return self.ask('Ikke publisert på nettsiden', f'Kunne ikke publisere «{j.label}» på nettsiden:\n{exc}\n\n'
                            + ('Koteng-målinger blir liggende i utboksen til kampen er registrert.'
                               if koteng else 'Lerkendal-kampen opprettes uansett ved første godkjente måling.')
                            + '\n\nSlå på Live likevel?')
        finally:
            self.root.config(cursor='')
        self.event(f"{j.label}: publisert på nettsiden (avspark {when_text(match.get('kickoff_at'))})")
        return True

    def test(self):
        def work():
            j = self.get_selected()
            if j.profile not in ONE_SHOT:
                raise ValueError('Legacy-Lerkendal krever en interaktiv Edge-sesjon. Bruk «Start nå».')
            if self.ask('Start lokal test?', f'Start én {j.venue}-skanning UTEN publisering?\n'
                        'Kontroller at ingen andre skannere bruker samme kamp.'):
                self.event(self.controller.start(replace(j, upload=False), force=True))
        self.handle(work)

    def start_now(self):
        def work():
            j = self.get_selected()
            if j.profile == 'lerkendal_legacy':
                warning = ('Starter den eksisterende Lerkendal-motoren. Den kan publisere til Supabase etter sin egen '
                           'kvalitetskontroll, uavhengig av Live-bryteren her.\n\nEr den gamle Lerkendal-skanneren stoppet?')
            else:
                warning = ('Start ' + j.label + ' nå, ' + ('med publisering via utboks' if j.upload else 'kun lokal kontroll')
                           + '?\nStopp andre skannere for samme kamp først.')
            if self.ask('Start nå?', warning):
                self.event(self.controller.start(j, force=True))
        self.handle(work)

    def stop(self):
        def work():
            j = self.get_selected()
            if j.key not in self.controller.active:
                raise ValueError('Kampen har ingen kjørende skanning')
            if self.ask('Stopp skanning?', 'Stoppe skanneprosessen? En avbrutt måling blir aldri publisert.'):
                self.controller.stop(j.key); self.event('Stopper ' + j.label)
        self.handle(work)

    def release(self):
        def work():
            j = self.get_selected()
            path = self.controller.lock_path(j.key)
            if not path.exists():
                raise ValueError('Kampen har ingen lås')
            info = locks.read(path)
            if self.ask('Frigi lås?', f"Låsen ble laget {info.get('started_at', '?')} på {info.get('host', '?')}.\n\n"
                        'Er du sikker på at ingen skanner for denne kampen kjører, verken her eller i et annet vindu?'):
                self.controller.release_lock(j.key); self.event(j.label + ': lås frigitt')
        self.handle(work)

    def health(self):
        def work():
            self.root.config(cursor='watch'); self.root.update_idletasks()
            try:
                rows = health.check(self.base, self.store.jobs())
            finally:
                self.root.config(cursor='')
            mark = {True: '✓', False: '✗', None: '!'}
            text = '\n'.join(f'{mark[ok]}  {msg}' for ok, msg in rows)
            stale = self.controller.stale_locks()
            if stale:
                text += '\n!  Gamle låser: ' + ', '.join(stale)
            blocking = any(ok is False for ok, _ in rows)
            (messagebox.showwarning if blocking else messagebox.showinfo)('Systemsjekk', text, parent=self.root)
            self.event('Systemsjekk: ' + ('avvik funnet' if blocking else 'ingen blokkerende feil'))
        self.handle(work)

    def toggle_archive(self):
        self.show_archive = not self.show_archive
        self.selected = None
        self._detail_shown = None
        self.render()

    def pick(self, key: str):
        self.selected = key
        self._log_shown = ('', 0.0)
        self._detail_shown = None
        self.render()

    # --- rendering -----------------------------------------------------------
    def _tick(self):
        if self.closing:
            return
        try:
            self.controller.poll()
        except Exception as exc:  # never let one bad poll kill the scheduler loop
            self.controller.say('Planlegger: ' + str(exc))
        self.render()
        self.root.after(TICK_MS, self._tick)

    def render(self):
        for msg in self.controller.messages:
            self.event(msg)
        self.controller.messages.clear()
        now = datetime.now(timezone.utc)
        jobs = self.store.jobs()
        # Played matches leave the scanner view; a scan still running is never hidden.
        archived = [j for j in jobs if j.finished(now) and j.key not in self.controller.active]
        current = [j for j in jobs if j not in archived]
        busy = {a.job.profile for a in self.controller.active.values()}
        cards = []
        shown = sorted(archived, key=Job.kickoff, reverse=True) if self.show_archive else current
        for j in shown:
            st = self.store.state(j.key)
            hist = self.store.history(j.key, 24)
            latest = hist[0] if hist else None
            status, tone = SHORT.get(st['last_status'], st['last_status']), 'ok'
            due = parse_utc(st['next_due']) if st['next_due'] else None
            if j.key in self.controller.active:
                a = self.controller.active[j.key]
                status, tone = f'SKANNER · {int((now - a.started).total_seconds() // 60)} MIN', 'scan'
            elif st['last_status'] == REVIEW:
                tone = 'warn'
            elif st['last_status'] in (FAILED, REJECTED, TIMEOUT):
                tone = 'bad'
            elif not j.enabled:
                status, tone = 'PAUSE', 'off'
            elif status == PLANNED and j.profile in busy and due and due <= now:
                status, tone = 'I KØ', 'scan'
            elif j.upload:
                tone = 'live'
            if j.enabled and j.upload and tone in ('ok', 'live'):
                status = 'LIVE · ' + status if status != 'PLANLAGT' else 'LIVE'
            if j.profile == 'lerkendal_legacy':
                status = 'LEGACY · ' + status
            if j in archived:
                status, tone = 'SPILT', 'off'
            kick = j.kickoff()
            days = (kick - now).days
            until = 'spilt' if j in archived else 'passert' if kick <= now else (f'om {days} d' if days >= 1 else f'om {int((kick - now).total_seconds() // 3600)} t')
            if j in archived:
                nxt = 'arkivert'
            elif j.key in self.controller.active:
                nxt = 'skanner nå …'
            elif due and j.enabled:
                mins = int((due - now).total_seconds() // 60)
                nxt = ('neste: straks' if mins <= 0 else f'neste {oslo.text(due, "%H:%M")} (om {mins} min)' if mins < 120
                       else f'neste {oslo.text(due, "%d.%m %H:%M")}')
            else:
                nxt = 'ingen planlagt'
            cards.append({'key': j.key, 'team': j.team, 'venue': j.venue.replace('_', ' ').title(), 'label': j.label,
                          'status': status.upper(), 'tone': tone,
                          'kickoff': f'Avspark {oslo.text(kick, "%d.%m kl %H:%M")}  ·  {until}',
                          'free': f"{latest['available_seated']:,}".replace(',', ' ') if latest else '—',
                          'delta': latest['delta'] if latest else None,
                          'measured': ('målt ' + age_text(latest['observed_at'], now) + ' siden').replace('målt nå siden', 'målt nå')
                                      if latest else 'ikke målt ennå',
                          'next': nxt, 'points': [h['available_seated'] for h in reversed(hist)]})
        self.cards.sync(cards, self.selected, 'Ingen spilte kamper ennå.' if self.show_archive else None)
        self.archive_button.configure(text='← Tilbake til kamper' if self.show_archive else f'Arkiv ({len(archived)})')
        live = [j for j in current if j.upload]
        if self.controller.active:
            self.live_pill.configure(text=f'●  SKANNER  {len(self.controller.active)}', bg='#7cc4ff', fg='#04121f')
        elif live:
            self.live_pill.configure(text=f'●  LIVE  ·  {len(live)} kamper publiserer', bg=ACC, fg=BG)
        else:
            self.live_pill.configure(text='○  INGEN LIVE-KAMPER', bg=PANEL2, fg=DIM)
        box = self.store.outbox_counts()
        pending = box.get('venter', 0) + box.get('sender', 0)
        self.summary.configure(text=f'{len(current)} kamper  ·  {len(archived)} i arkiv  ·  {pending} i utboks  ·  {box.get("sendt", 0)} målinger publisert'
                                    f'  ·  versjon {__version__}')
        self.footer.configure(text='Tider vises i norsk tid. Ledige = observerte ledige sitteplasser i valgt '
                                   'billettkategori, ikke bekreftet salg. Ingen skanning starter før du aktiverer en kamp.')
        self.render_detail()

    def render_detail(self):
        j = self.store.job(self.selected) if self.selected else None
        st = self.store.state(j.key) if j else {}
        if j:
            self._render_log(st['last_log'])
        # Rebuild the tables only when something changed, so scrolling survives the 2 s tick.
        signature = (j, tuple(st.items()), tuple(sorted(self.store.outbox_counts().items())))
        if signature == self._detail_shown:
            return
        self._detail_shown = signature
        for t in (self.hist, self.runs):
            t.delete(*t.get_children())
        if j is None:
            self.note.configure(text='Velg en kamp for detaljer.', fg=DIM)
            return
        lead = f'{j.label}  ·  {j.team}  ·  avspark {when_text(j.kickoff_at)}  ·  siste skanning {oslo.text(j.last_start(), "%d.%m %H:%M")}'
        note = st.get('note') or ''
        self.note.configure(text=lead + (('\n' + note) if note else ''),
                            fg=WARN if st['last_status'] == REVIEW else BAD if st['last_status'] == FAILED else DIM)
        for h in self.store.history(j.key, 24):
            pub = h['publish_status'] or ('ikke valgt' if not h['upload_requested'] else '—')
            self.hist.insert('', 'end', values=(when_text(h['observed_at']), h['available_seated'], delta_text(h['delta']),
                                                h['section_count'], pub, h['run_id']))
        for run in self.store.recent(j.key, 20):
            self.runs.insert('', 'end', values=(when_text(run['started']), when_text(run['ended']), run['status'],
                                                '' if run['exit_code'] is None else run['exit_code'], run['summary'] or ''))

    def _render_log(self, path: str | None):
        try:
            mtime = Path(path).stat().st_mtime if path else 0.0
        except OSError:
            mtime = 0.0
        if (path or '', mtime) == self._log_shown:
            return
        self._log_shown = (path or '', mtime)
        try:
            lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()[-80:] if mtime else []
            text = '\n'.join(lines) or 'Loggen er tom ennå.'
        except OSError:
            text = 'Ingen lokal logg (Lerkendal logger i sitt eget konsollvindu).'
        if not path:
            text = 'Ingen kjøring ennå.'
        self.logview.configure(state='normal'); self.logview.delete('1.0', 'end')
        self.logview.insert('end', text); self.logview.see('end'); self.logview.configure(state='disabled')

    # --- shutdown ------------------------------------------------------------
    def close(self):
        if self.controller.active:
            if not self.ask('Skannere kjører', 'Stoppe alle kjørende skanninger og lukke kontrollsenteret?\n'
                            'Avbrutte målinger publiseres aldri.'):
                return
            try:
                self.controller.stop_all()
            except Exception as exc:
                messagebox.showerror('Kunne ikke stoppe', str(exc), parent=self.root)
                return
            self._wait_then_close(20)
            return
        self._shutdown()

    def _wait_then_close(self, tries: int):
        self.controller.poll()
        if self.controller.active and tries > 0:
            self.root.after(500, lambda: self._wait_then_close(tries - 1))
            return
        if self.controller.active:
            messagebox.showwarning('Fortsatt aktiv', 'En skanneprosess svarer ikke. Låsen beholdes til du har kontrollert den.',
                                   parent=self.root)
        self._shutdown()

    def _shutdown(self):
        self.closing = True
        self.store.close()
        self.app_lock.unlink(missing_ok=True)
        self.root.destroy()

    def run(self):
        self.root.mainloop()
