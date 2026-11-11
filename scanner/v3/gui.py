"""Ministaut V3 local STAGING UI. Never scans or publishes tickets.

Launch from scanner/: python -m v3.gui
The legacy START_BILLETTMONITOR.bat remains the only live scanner.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from tkinter import Tk, ttk, StringVar, messagebox
import tkinter as tk
import uuid
import webbrowser
from zoneinfo import ZoneInfo
from .control import ControlPlane, Event
from .profiles import StadiumProfile, candidate_from_reference

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "v3_operator_state.json"
PROFILES = ROOT / "v3_profiles"
OSLO = ZoneInfo("Europe/Oslo")


def kickoff_iso(value):
    """Accept Norwegian date/time or explicit-offset ISO, store unambiguous UTC."""
    value = value.strip()
    try:
        dt = datetime.strptime(value, "%d.%m.%Y %H:%M")
    except ValueError:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            raise ValueError("Bruk DD.MM.ÅÅÅÅ HH:MM eller ISO med tidssone")
        return dt.isoformat()
    # Reject ambiguous/nonexistent clock times, rather than silently shift kickoff.
    aware = dt.replace(tzinfo=OSLO)
    other = dt.replace(tzinfo=OSLO, fold=1)
    if aware.utcoffset() != other.utcoffset():
        raise ValueError("Tvetydig lokal tid ved sommertidsskifte: bruk ISO med tidssone")
    from datetime import timezone
    if aware.astimezone(timezone.utc).astimezone(OSLO).replace(tzinfo=None) != dt:
        raise ValueError("Ugyldig lokal klokketid ved sommertidsskifte")
    return aware.isoformat()


class Panel:
    def __init__(self):
        self.root = Tk()
        self.root.title("Ministaut V3 – lokal testadministrasjon")
        self.root.minsize(940, 620)
        self.cp = ControlPlane(STATE)
        self.id_by_row = {}
        s = ttk.Style()
        if "clam" in s.theme_names():
            s.theme_use("clam")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        ttk.Label(self.root, text="MINISTAUT V3  |  TESTPANEL",
                  font=("Segoe UI", 19, "bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(20, 4))
        ttk.Label(self.root, text="Dette panelet tester kampregister og planlegger. Edge-telling og opplasting er IKKE koblet til.",
                  foreground="#a04d13", font=("Segoe UI", 10, "bold")).grid(
                      row=1, column=0, sticky="w", padx=22, pady=(0, 14))
        body = ttk.Frame(self.root)
        body.grid(row=2, column=0, sticky="nsew", padx=20)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        columns = ("title", "arena", "kickoff", "state", "last", "jobs")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", height=11, selectmode="browse")
        for key, text, width in (
            ("title", "Kamp", 250), ("arena", "Arena", 120), ("kickoff", "Avspark", 160),
            ("state", "Status", 110), ("last", "Siste godkjent", 160), ("jobs", "Testjobber", 95)):
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, stretch=key=="title")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        buttons = ttk.Frame(self.root)
        buttons.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        for label, method in [
            ("Aktiver testplan", lambda: self.change("monitoring")),
            ("Pause", lambda: self.change("paused")),
            ("Trenger kart", lambda: self.change("needs_map")),
            ("Test planlegger", self.tick),
            ("Åpne billettkart", self.open_map),
            ("Oppdater", self.refresh)
        ]:
            ttk.Button(buttons, text=label, command=lambda fn=method: self.safe(fn)).pack(side="left", padx=(0, 6))

        add = ttk.LabelFrame(self.root, text="Registrer ny kamp (lokal test)")
        add.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 6))
        add.columnconfigure(1, weight=1)
        add.columnconfigure(3, weight=1)
        self.title = StringVar()
        self.url = StringVar()
        self.arena = StringVar(value="lerkendal")
        self.kickoff = StringVar()
        self._entry(add, "Kampnavn", self.title, 0, 0)
        self._entry(add, "Billettlenke (Vivenu)", self.url, 1, 0)
        ttk.Label(add, text="Arena").grid(row=0, column=2, sticky="w", padx=(12, 4), pady=3)
        ttk.Combobox(add, textvariable=self.arena, values=["lerkendal", "koteng_arena"],
                     state="readonly", width=21).grid(row=0, column=3, sticky="w", pady=3)
        self._entry(add, "Avspark (f.eks. 28.11.2026 18:00)", self.kickoff, 1, 2)
        ttk.Button(add, text="Registrer kamp", command=lambda: self.safe(self.add)).grid(
            row=2, column=3, sticky="e", pady=8, padx=8)

        bottom = ttk.Frame(self.root)
        bottom.grid(row=5, column=0, sticky="ew", padx=20, pady=(4, 20))
        ttk.Button(bottom, text="Importer Lerkendals innlærte punkter (utkast)",
                   command=lambda: self.safe(self.import_lerkendal)).pack(side="left")
        ttk.Button(bottom, text="Vis læringsprofiler",
                   command=lambda: self.safe(self.show_profiles)).pack(side="left", padx=8)
        self.message = StringVar(value="Ingen aktive V3-skanninger. Endringer her påvirker ikke V20.")
        ttk.Label(bottom, textvariable=self.message, wraplength=390).pack(side="right", padx=4)
        self.refresh()

    def _entry(self, parent, label, variable, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(8, 4), pady=3)
        ttk.Entry(parent, textvariable=variable, width=37).grid(
            row=row, column=col+1, sticky="ew", padx=(0, 8), pady=3)

    def safe(self, action):
        try:
            action()
        except Exception as ex:
            messagebox.showerror("Ministaut V3", str(ex), parent=self.root)

    def selected(self):
        rows = self.tree.selection()
        if not rows:
            raise ValueError("Velg en kamp fra listen først")
        return self.id_by_row[rows[0]]

    def on_select(self, unused=None):
        rows = self.tree.selection()
        if rows:
            event = self.cp.events[self.id_by_row[rows[0]]]
            self.message.set(event.title + " · " + event.state + " · " + (event.error or "Ingen registrert feil"))

    def add(self):
        name = self.title.get().strip()
        url = self.url.get().strip()
        kickoff = kickoff_iso(self.kickoff.get())
        arena = self.arena.get()
        if not name or not url:
            raise ValueError("Kampnavn og billettlenke må fylles ut")
        if arena not in ("lerkendal", "koteng_arena"):
            raise ValueError("Velg en støttet arenaprofil")
        event = Event("evt-"+uuid.uuid4().hex[:12], url, arena, kickoff, name,
                      state="needs_map" if arena=="koteng_arena" else "paused")
        self.cp.add(event)
        self.title.set("");self.url.set("");self.kickoff.set("")
        self.message.set("Registrert lokalt: "+name+" (ingen skanning startet)")
        self.refresh()

    def change(self, state):
        key = self.selected()
        if state=="monitoring" and self.cp.events[key].venue_id=="koteng_arena":
            raise ValueError("Koteng er ennå ikke kartlagt. Ingen skanning kan aktiveres.")
        self.cp.set_state(key, state)
        self.message.set("Teststatus endret: " + state)
        self.refresh(select_key=key)

    def tick(self):
        jobs = self.cp.tick()
        self.refresh()
        self.message.set(f"Simulering: {len(jobs)} jobber lagt i lokal testkø. Ingen Edge-skanning utført.")

    def open_map(self):
        event = self.cp.events[self.selected()]
        if not messagebox.askyesno("Kun kartvisning",
                "Åpne billettkart i vanlig nettleser? Dette starter INGEN skanning.",
                parent=self.root):
            return
        webbrowser.open(event.url)

    def import_lerkendal(self):
        stadium = ROOT/"stadion_felt.json"
        anchors = ROOT/"bekreftede_posisjoner_v16.json"
        candidate = candidate_from_reference(stadium, anchors)
        dest = PROFILES/"lerkendal.v1.json"
        if dest.exists():
            raise ValueError("Profilutkast finnes allerede; overskriver ikke innlærte punkter")
        candidate.save(dest)
        self.message.set(f"Importert {len(candidate.sections)} felt og "
                         f"{len(candidate.anchors)} punktgrupper. Profilen er IKKE godkjent.")
        messagebox.showinfo("Lerkendal import", self.message.get(), parent=self.root)

    def show_profiles(self):
        PROFILES.mkdir(parents=True, exist_ok=True)
        text = []
        for path in sorted(PROFILES.glob("*.json")):
            p = StadiumProfile.load(path)
            text.append(f"{p.id} v{p.version}: {len(p.sections)} felt / "
                        f"{len(p.anchors)} punktgrupper · "
                        f"{'GODKJENT' if p.verified else 'UTKAST'}")
        messagebox.showinfo("Stadionprofiler", "\n".join(text) if text else
            "Ingen profilutkast ennå. Lerkendal kan importeres fra eksisterende punktdata.",
            parent=self.root)

    def refresh(self, select_key=None):
        current = select_key
        if current is None and self.tree.selection():
            current = self.id_by_row.get(self.tree.selection()[0])
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.id_by_row = {}
        for event in sorted(self.cp.events.values(), key=lambda e: e.kickoff_at):
            try:
                local = datetime.fromisoformat(event.kickoff_at).astimezone(OSLO).strftime("%d.%m.%Y %H:%M")
            except Exception:
                local = event.kickoff_at
            jobs = [job for job in self.cp.jobs.values() if job.event_id==event.id]
            item = self.tree.insert("", "end", values=(
                event.title, event.venue_id, local, event.state,
                event.last_success_at or "—", len(jobs)))
            self.id_by_row[item] = event.id
            if current == event.id:
                self.tree.selection_set(item)

    def run(self):
        self.root.mainloop()


if __name__=="__main__":
    Panel().run()
