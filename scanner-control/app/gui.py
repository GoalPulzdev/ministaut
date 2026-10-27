"""Local Tkinter application. No exposed HTTP server, no browser auth or secrets."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from .model import Job, checkout_key, parse_utc
from .runner import Controller
from .storage import Store

BG='#09160f'; PANEL='#14271b'; PANEL2='#1d3526'; FG='#eaf8ec'; DIM='#9dbba4'; ACC='#79e8a2'


def date_text(value: str) -> str:
    try:
        return parse_utc(value).astimezone().strftime('%d.%m.%Y %H:%M')
    except (ValueError, TypeError):
        return '—'


class Editor(tk.Toplevel):
    def __init__(self, master, base: Path, on_save, existing: Job | None = None):
        super().__init__(master)
        self.base=base;self.on_save=on_save
        self.title('Registrer kamp'); self.resizable(False, False)
        self.configure(bg=BG); self.transient(master); self.grab_set()
        self.values={}
        sample={'label':'Rosenborg – ny kamp','team':'rbk-herrer','venue':'lerkendal',
                'profile':'lerkendal_legacy','url':'https://billett.rbk.no/checkout/',
                'kickoff_at':'2026-11-28T17:00:00+00:00',
                'scanner_path':'sources/ministaut/scanner','interval_minutes':'60'}
        if existing:sample.update({k:str(v) for k,v in existing.as_json().items()})
        fields=[('Kampnavn','label'),('Lag','team'),('Arena (lerkendal/koteng_arena)','venue'),
                ('Motor (lerkendal_legacy/koteng_v24)','profile'),('Full billett-URL','url'),
                ('Avspark ISO-8601 med tidssone','kickoff_at'),('Mappe med skannermotor','scanner_path'),
                ('Intervall minutter','interval_minutes')]
        for i,(label,key) in enumerate(fields):
            tk.Label(self,text=label,bg=BG,fg=FG,font=('Segoe UI',10)).grid(row=i,column=0,padx=15,pady=7,sticky='w')
            var=tk.StringVar(value=sample[key]);self.values[key]=var
            e=tk.Entry(self,textvariable=var,width=53,bg='#213729',fg=FG,insertbackground=ACC,relief='flat')
            e.grid(row=i,column=1,padx=12,pady=7,sticky='ew')
        ttk.Button(self,text='Velg mappe',command=self.browse).grid(row=8,column=1,pady=6,sticky='w')
        ttk.Button(self,text='Lagre (ikke aktiver)',command=self.save).grid(row=9,column=1,padx=10,pady=14,sticky='e')
        self.bind('<Escape>',lambda _e:self.destroy())

    def browse(self):
        dest=filedialog.askdirectory(parent=self,initialdir=str(self.base))
        if dest:self.values['scanner_path'].set(dest)

    def save(self):
        try:
            data={k:v.get().strip() for k,v in self.values.items()}
            data['interval_minutes']=int(data['interval_minutes'])
            url=data['url'];data['key']=checkout_key(url)
            data['enabled']=False;data['upload']=False
            job=Job(**data)
            self.on_save(job)
            self.destroy()
        except Exception as exc:
            messagebox.showerror('Kan ikke lagre kamp',str(exc),parent=self)


class App:
    def __init__(self, base: Path):
        self.base=base
        self.store=Store(base/'state'/'control.sqlite3')
        self.controller=Controller(base,self.store)
        self.root=tk.Tk();self.root.title('MINISTAUT · Scanner Control 0.1')
        self.root.geometry('1160x710');self.root.minsize(880,600)
        self.root.configure(bg=BG)
        self._style()
        self._seed()
        self.selected: str | None=None
        tk.Label(self.root,text='MINISTAUT  /  SCANNER CONTROL',bg=BG,fg=ACC,
                 font=('Segoe UI',11,'bold')).pack(fill='x',padx=24,pady=(20,2),anchor='w')
        tk.Label(self.root,text='Én oversikt. Separate, kontrollerte skannermotorer.',bg=BG,fg=FG,
                 font=('Segoe UI',21,'bold')).pack(fill='x',padx=24,pady=(0,16),anchor='w')
        strip=tk.Frame(self.root,bg=BG);strip.pack(fill='x',padx=23,pady=(0,10))
        self.summary=tk.Label(strip,text='',bg=BG,fg=DIM,font=('Segoe UI',10));self.summary.pack(side='left')
        ttk.Button(strip,text='+ Legg til kamp',command=self.add).pack(side='right',padx=6)
        ttk.Button(strip,text='Åpne scanner-mappe',command=self.folder).pack(side='right',padx=6)
        columns=('team','event','venue','free','mode','kickoff','status','next')
        table=tk.Frame(self.root,bg=BG);table.pack(fill='both',expand=True,padx=24,pady=(0,6))
        self.tree=ttk.Treeview(table,columns=columns,show='headings',height=10,selectmode='browse')
        for c,label,w in [('team','LAG',130),('event','KAMP',240),('venue','ARENA',115),
                          ('free','LEDIGE',85),('mode','DRIFT',120),('kickoff','AVSPARK',120),('status','STATUS',115),('next','NESTE',130)]:
            self.tree.heading(c,text=label);self.tree.column(c,width=w,anchor='w',stretch=(c=='event'))
        self.tree.pack(side='left',fill='both',expand=True)
        sb=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);sb.pack(side='right',fill='y');self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind('<<TreeviewSelect>>',self.on_select)
        buttons=tk.Frame(self.root,bg=BG);buttons.pack(fill='x',padx=24,pady=7)
        for label,fun in [('Test én gang',self.test),('Aktiver / Deaktiver',self.toggle),
                          ('Live AV/PÅ',self.live),('Start nå',self.start_now),
                          ('Stopp jobb',self.stop),('Vis logg',self.log_file)]:
            ttk.Button(buttons,text=label,command=fun).pack(side='left',padx=(0,8),pady=4)
        tk.Label(self.root,text='DRIFTSLOGG  ·  LOKAL',bg=BG,fg=ACC,font=('Segoe UI',10,'bold')).pack(fill='x',padx=24,pady=(15,5),anchor='w')
        self.log=tk.Text(self.root,bg=PANEL,fg=FG,insertbackground=ACC,height=9,
                         font=('Consolas',10),borderwidth=0,wrap='word')
        self.log.pack(fill='both',expand=False,padx=24,pady=(0,10));self.log.configure(state='disabled')
        self.footer=tk.Label(self.root,text='Skannere starter aldri automatisk ved første installasjon.',bg=BG,fg=DIM,font=('Segoe UI',9))
        self.footer.pack(fill='x',padx=24,pady=(0,15),anchor='w')
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh()

    def _style(self):
        st=ttk.Style(self.root);st.theme_use('clam')
        st.configure('Treeview',background=PANEL,fieldbackground=PANEL,foreground=FG,rowheight=43,
                     font=('Segoe UI',10),borderwidth=0)
        st.configure('Treeview.Heading',background=PANEL2,foreground=ACC,font=('Segoe UI',9,'bold'),relief='flat')
        st.map('Treeview',background=[('selected','#276a45')],foreground=[('selected','#ffffff')])
        st.configure('TButton',background='#28523a',foreground=FG,font=('Segoe UI',9,'bold'),padding=(11,9),borderwidth=0)
        st.map('TButton',background=[('active','#33734d')])

    def _seed(self):
        if self.store.jobs():return
        defaults=[
            Job('6aaceecebfe408c38e1712dd','Rosenborg – Røa','RBK Kvinner','koteng_arena',
                'https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd',
                '2026-11-01T13:30:00Z','koteng_v24','adapters/koteng'),
            Job('6a9a7e3f3f93920b289b0675','Rosenborg – Molde','RBK Herrer','lerkendal',
                'https://billett.rbk.no/checkout/6a9a7e3f3f93920b289b0675',
                '2026-11-28T17:00:00Z','lerkendal_legacy','sources/ministaut/scanner'),
            Job('6a9a7c2b15599587216e21f3','Rosenborg – Start','RBK Herrer','lerkendal',
                'https://billett.rbk.no/checkout/6a9a7c2b15599587216e21f3',
                '2026-11-07T17:00:00Z','lerkendal_legacy','sources/ministaut/scanner'),
        ]
        for job in defaults:self.store.put_job(job)

    def get_selected(self) -> Job:
        if not self.selected:raise ValueError('Velg en kamp i tabellen først')
        return next(j for j in self.store.jobs() if j.key==self.selected)

    def handle(self, callback):
        try:callback()
        except Exception as exc:messagebox.showerror('Stoppet for sikkerhet',str(exc),parent=self.root)
        self.refresh()

    def add(self):
        Editor(self.root,self.base,self.store.put_job)

    def on_select(self,_evt):
        ids=self.tree.selection();self.selected=ids[0] if ids else None
        self.show_recent()

    def folder(self):
        def work():
            job=self.get_selected();path=job.path(self.base)
            if not path.is_dir():raise FileNotFoundError(str(path))
            if os.name=='nt':os.startfile(str(path))
            else:self._append('Scanner mappe: '+str(path))
        self.handle(work)

    def toggle(self):
        def work():
            j=self.get_selected();self.controller.enable(j.key,not j.enabled,False)
            self._append(j.label+(': planlagt (uten publisering)' if not j.enabled else ': deaktivert'))
        self.handle(work)

    def live(self):
        def work():
            j=self.get_selected()
            if j.profile!='koteng_v24':
                raise ValueError('Lerkendal styrer opplasting i egen godkjent motor; endre ikke denne fra kontrollpanelet.')
            if not j.enabled:raise ValueError('Aktiver jobben først')
            desired=not j.upload
            if desired and not messagebox.askyesno('Aktivere live?',
                   'ER original Koteng-skanner på andre PC-er stoppet?\n\nDette vil publisere observerte, dobbeltkontrollerte sitteplasser til Ministaut.',parent=self.root):
                return
            self.controller.enable(j.key,True,desired)
            self._append('Live '+('aktivert' if desired else 'deaktivert')+' for '+j.label)
        self.handle(work)

    def test(self):
        def work():
            j=self.get_selected()
            if j.profile!='koteng_v24':raise ValueError('Lerkendal krever interaktiv Edge-sesjon, bruk Start nå.')
            if not messagebox.askyesno('Start lokal test?',
                  'Start én Koteng-skanning UTEN overføring?\nKontroller at ingen andre lokale skannere bruker samme kamp.',parent=self.root):
                return
            self._append(self.controller.start(replace(j,upload=False),force=True))
        self.handle(work)

    def start_now(self):
        def work():
            j=self.get_selected()
            if not messagebox.askyesno('Start nå?',
                    'Start '+j.label+' med '+('LIVE OPPLASTING' if j.upload else 'lokal registrering')+'?\nStopp eksisterende skanner for samme kamp først.',parent=self.root):
                return
            self._append(self.controller.start(j,force=True))
        self.handle(work)

    def stop(self):
        def work():
            j=self.get_selected()
            if j.key not in self.controller.active:return
            if messagebox.askyesno('Stopp skanning?',
                     'Stoppe kjørende skanneprosess? En avbrutt måling skal ikke publiseres.',parent=self.root):
                self.controller.stop(j.key);self._append('Avslutter '+j.label)
        self.handle(work)

    def log_file(self):
        def work():
            j=self.get_selected();path=self.store.state(j.key)['last_log']
            if not path or not Path(path).exists():raise FileNotFoundError('Ingen lokal logg ennå')
            if os.name=='nt':os.startfile(str(path))
            else:self._append('Logg: '+path)
        self.handle(work)

    def _append(self,msg):
        stamp=datetime.now().strftime('%H:%M:%S')
        self.log.configure(state='normal');self.log.insert('end',stamp+'  '+msg+'\n')
        self.log.see('end');self.log.configure(state='disabled')

    def show_recent(self):
        if not self.selected:return
        recent=self.store.recent(self.selected,4)
        self.log.configure(state='normal');self.log.delete('1.0','end')
        for r in reversed(recent):
            self.log.insert('end',f"{r['started']}  {r['status']}  (exit {r['exit_code']})\n")
        self.log.configure(state='disabled')

    def refresh(self):
        self.controller.poll()
        existing=self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        jobs=self.store.jobs();running=len(self.controller.active)
        for j in jobs:
            state=self.store.state(j.key)
            status='SKANNER AKTIV' if j.key in self.controller.active else state['last_status']
            mode='LIVE' if j.upload else ('PLANLAGT' if j.enabled else 'AV')
            if j.profile=='lerkendal_legacy':mode='LEGACY • '+mode
            due=state['next_due']
            latest=self.store.latest(j.key)
            free=str(latest['available_seated']) if latest else '—'
            self.tree.insert('', 'end', iid=j.key,values=(j.team,j.label,j.venue,free,mode,
                                date_text(j.kickoff_at),status,date_text(due) if due else '—'))
        for key in existing:
            if self.tree.exists(key):self.tree.selection_set(key)
        self.summary.configure(text=f'{len(jobs)} kampjobber  •  {running} prosesser  •  '+'Separat datalagring / ingen falske salgstall')
        if self.controller.error:
            self._append(self.controller.error);self.controller.error=''
        self.root.after(2000,self.refresh)

    def close(self):
        if self.controller.active:
            messagebox.showwarning('Skannere kjører',
                'Stopp aktive jobber i programmet og vent til de er avsluttet før kontrollpanelet lukkes.',parent=self.root)
            return
        self.store.close();self.root.destroy()

    def run(self):
        self.root.mainloop()
