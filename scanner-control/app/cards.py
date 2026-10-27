"""Match cards for the main view: one glanceable card per monitored match."""
from __future__ import annotations
import tkinter as tk

BG = '#09160f'; CARD = '#11241a'; CARD_SEL = '#173826'; LINE = '#24452f'
FG = '#eaf8ec'; DIM = '#8fb09a'; FAINT = '#5f7d68'; ACC = '#79e8a2'
FONT = 'Segoe UI'

# status -> (pill text colour, pill background)
TONES = {
    'live': ('#06150c', ACC), 'scan': ('#04121f', '#7cc4ff'), 'ok': (ACC, '#1c3a28'),
    'warn': ('#1d1404', '#ffcf7a'), 'bad': ('#230707', '#ff8f8f'), 'off': (DIM, '#1a2c21'),
}


class MatchCard(tk.Frame):
    WIDTH = 360
    HEIGHT = 282

    def __init__(self, master, key: str, on_click, on_double):
        super().__init__(master, bg=CARD, highlightthickness=2, highlightbackground=CARD,
                         highlightcolor=CARD, width=self.WIDTH, cursor='hand2')
        self.key = key
        self.pack_propagate(False)
        self.configure(height=self.HEIGHT)
        pad = dict(bg=CARD)
        top = tk.Frame(self, **pad); top.pack(fill='x', padx=18, pady=(16, 0))
        self.team = tk.Label(top, font=(FONT, 9, 'bold'), fg=DIM, **pad); self.team.pack(side='left')
        self.pill = tk.Label(top, font=(FONT, 8, 'bold'), padx=9, pady=3); self.pill.pack(side='right')
        self.title = tk.Label(self, font=(FONT, 15, 'bold'), fg=FG, anchor='w', **pad)
        self.title.pack(fill='x', padx=18, pady=(8, 0))
        self.kickoff = tk.Label(self, font=(FONT, 9), fg=DIM, anchor='w', **pad)
        self.kickoff.pack(fill='x', padx=18)
        mid = tk.Frame(self, **pad); mid.pack(fill='x', padx=18, pady=(14, 0))
        self.free = tk.Label(mid, font=(FONT, 30, 'bold'), fg=FG, **pad); self.free.pack(side='left', anchor='s')
        side = tk.Frame(mid, **pad); side.pack(side='left', anchor='s', padx=(10, 0), pady=(0, 7))
        self.delta = tk.Label(side, font=(FONT, 10, 'bold'), anchor='w', **pad); self.delta.pack(anchor='w')
        tk.Label(side, text='ledige sitteplasser', font=(FONT, 9), fg=DIM, anchor='w', **pad).pack(anchor='w')
        self.spark = tk.Canvas(self, height=46, bg=CARD, highlightthickness=0)
        self.spark.pack(fill='x', padx=18, pady=(10, 0))
        tk.Frame(self, bg=LINE, height=1).pack(fill='x', padx=18, pady=(12, 0))
        foot = tk.Frame(self, **pad); foot.pack(fill='x', padx=18, pady=(9, 14))
        self.measured = tk.Label(foot, font=(FONT, 9), fg=DIM, **pad); self.measured.pack(side='left')
        self.next = tk.Label(foot, font=(FONT, 9), fg=DIM, **pad); self.next.pack(side='right')
        self._points: list[int] = []
        for w in self._all(self):
            w.bind('<Button-1>', lambda _e: on_click(self.key))
            w.bind('<Double-1>', lambda _e: on_double(self.key))
        self.spark.bind('<Configure>', lambda _e: self._draw())

    def _all(self, w):
        yield w
        for c in w.winfo_children():
            yield from self._all(c)

    def select(self, on: bool):
        bg = CARD_SEL if on else CARD
        self.configure(highlightbackground=ACC if on else CARD, highlightcolor=ACC if on else CARD)
        for w in self._all(self):
            if w is not self.pill and isinstance(w, (tk.Frame, tk.Label, tk.Canvas)) and w.cget('bg') in (CARD, CARD_SEL):
                w.configure(bg=bg)

    def update(self, d: dict):
        self.team.configure(text=d['team'].upper() + '  ·  ' + d['venue'])
        fg, bg = TONES[d['tone']]
        self.pill.configure(text=d['status'], fg=fg, bg=bg)
        self.title.configure(text=d['label'])
        self.kickoff.configure(text=d['kickoff'])
        self.free.configure(text=d['free'], fg=FG if d['free'] != '—' else FAINT)
        delta = d['delta']
        if delta is None:
            self.delta.configure(text='første måling' if d['free'] != '—' else 'ingen måling ennå', fg=FAINT)
        elif delta == 0:
            self.delta.configure(text='uendret', fg=DIM)
        else:
            # Fewer free seats = tickets moving: shown in the accent colour.
            self.delta.configure(text=('▼ ' if delta < 0 else '▲ ') + f'{abs(delta):,}'.replace(',', ' '),
                                 fg=ACC if delta < 0 else '#ffcf7a')
        self.measured.configure(text=d['measured'])
        self.next.configure(text=d['next'], fg=ACC if d['tone'] == 'scan' else DIM)
        if d['points'] != self._points:
            self._points = d['points']
            self._draw()

    def _draw(self):
        c = self.spark; c.delete('all')
        w, h = max(c.winfo_width(), 40), int(c.cget('height'))
        pts = self._points
        if len(pts) < 2:
            c.create_line(0, h - 6, w, h - 6, fill=LINE, dash=(3, 4))
            c.create_text(0, h / 2 - 4, text='Graf vises etter to målinger', anchor='w', fill=FAINT, font=(FONT, 8))
            return
        lo, hi = min(pts), max(pts)
        span = (hi - lo) or 1
        xy = []
        for i, v in enumerate(pts):
            xy += [i * (w - 8) / (len(pts) - 1) + 4, 6 + (hi - v) * (h - 14) / span]
        c.create_polygon(*xy, xy[-2], h, xy[0], h, fill='#16382a', outline='')
        c.create_line(*xy, fill=ACC, width=2, smooth=True)
        c.create_oval(xy[-2] - 3.5, xy[-1] - 3.5, xy[-2] + 3.5, xy[-1] + 3.5, fill=ACC, outline=CARD)


class CardGrid(tk.Frame):
    """Scrollable, responsive grid of MatchCards."""

    def __init__(self, master, on_click, on_double):
        super().__init__(master, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.bar = tk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda _e: self._scroll_region())
        self.canvas.bind('<Configure>', lambda _e: self._layout())
        self.canvas.bind_all('<MouseWheel>', self._wheel, add='+')
        self.on_click, self.on_double = on_click, on_double
        self.cards: dict[str, MatchCard] = {}
        self.order: list[str] = []
        self.empty = tk.Label(self.inner, text='Ingen kamper ennå. Trykk «+ Legg til kamp».',
                              bg=BG, fg=DIM, font=(FONT, 11))

    def _wheel(self, e):
        if self.canvas.winfo_containing(e.x_root, e.y_root) and str(self.canvas.winfo_containing(e.x_root, e.y_root)).startswith(str(self)):
            self.canvas.yview_scroll(int(-e.delta / 120), 'units')

    def _scroll_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        need = self.inner.winfo_reqheight() > self.canvas.winfo_height()
        if need and not self.bar.winfo_ismapped():
            self.bar.pack(side='right', fill='y')
        elif not need and self.bar.winfo_ismapped():
            self.bar.pack_forget()

    def _layout(self):
        width = max(self.canvas.winfo_width(), MatchCard.WIDTH + 16)
        cols = max(1, width // (MatchCard.WIDTH + 16))
        card_w = (width - 16 * cols) // cols
        for i, key in enumerate(self.order):
            card = self.cards[key]
            card.configure(width=card_w)
            card.grid(row=i // cols, column=i % cols, padx=(0, 16), pady=(0, 16), sticky='nw')
        self.canvas.itemconfigure(self.window, width=width)
        self._scroll_region()

    def sync(self, data: list[dict], selected: str | None):
        keys = [d['key'] for d in data]
        for key in list(self.cards):
            if key not in keys:
                self.cards.pop(key).destroy()
        for d in data:
            if d['key'] not in self.cards:
                self.cards[d['key']] = MatchCard(self.inner, d['key'], self.on_click, self.on_double)
            self.cards[d['key']].update(d)
            self.cards[d['key']].select(d['key'] == selected)
        if keys != self.order:
            self.order = keys
            for c in self.cards.values():
                c.grid_forget()
            self._layout()
        if keys:
            self.empty.grid_forget()
        else:
            self.empty.grid(row=0, column=0, sticky='w', pady=20)
