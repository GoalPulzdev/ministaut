"""Explicit, validated configurations: no guessed venue or category."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
import re

START_GRACE = timedelta(minutes=2)
EVENT = re.compile(r'^[A-Za-z0-9_-]{8,100}$')
PROFILES = {'koteng_v24', 'lerkendal_v23', 'lerkendal_legacy'}
# Engines the control program runs as one unattended scan per job.
ONE_SHOT = {'koteng_v24', 'lerkendal_v23'}
# Engine -> (venue, default engine folder relative to the control program)
ENGINES = {'koteng_v24': ('koteng_arena', 'adapters/koteng'),
           'lerkendal_v23': ('lerkendal', 'adapters/lerkendal'),
           'lerkendal_legacy': ('lerkendal', 'sources/ministaut/scanner')}


def checkout_key(url: str) -> str:
    p = urlsplit(url)
    if p.scheme != 'https' or (p.hostname or '').lower() != 'billett.rbk.no' or p.username or p.password or p.port or p.query or p.fragment:
        raise ValueError('Krever offentlig https://billett.rbk.no/checkout/<kamp-ID>')
    parts = p.path.strip('/').split('/')
    if len(parts) != 2 or parts[0] != 'checkout' or not EVENT.fullmatch(parts[1]):
        raise ValueError('Ugyldig billettadresse/kamp-ID')
    return parts[1]


def parse_utc(value: str) -> datetime:
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Oppgi tidspunkt i ISO-8601 med tidssone') from exc
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError('Kampstart mangler tidssone')
    return d.astimezone(timezone.utc)


@dataclass(frozen=True)
class Job:
    key: str
    label: str
    team: str
    venue: str
    url: str
    kickoff_at: str
    profile: str
    scanner_path: str
    interval_minutes: int = 60
    enabled: bool = False
    upload: bool = False
    # Last scan slot relative to kickoff; negative = after kickoff (-5: last scan 5 min after kickoff).
    stop_before_minutes: int = -5
    # Final phase: denser scans right before kickoff to show the sales trend.
    final_window_minutes: int = 90
    final_interval_minutes: int = 15

    def __post_init__(self):
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,100}', self.key):
            raise ValueError('Ugyldig intern jobb-ID')
        if not (self.label.strip() and self.team.strip() and self.venue.strip()):
            raise ValueError('Kampnavn, lag og arena kreves')
        if self.profile not in PROFILES:
            raise ValueError('Ukjent motor; ny arena må læres opp og godkjennes')
        if checkout_key(self.url) != self.key:
            raise ValueError('Kamp-ID og URL samsvarer ikke')
        parse_utc(self.kickoff_at)
        if type(self.interval_minutes) is not int or not (30 <= self.interval_minutes <= 720):
            raise ValueError('Intervall må være 30–720 minutter')
        if type(self.stop_before_minutes) is not int or not (-30 <= self.stop_before_minutes <= 180):
            raise ValueError('Siste skanning må være mellom 30 min etter og 180 min før avspark')
        if type(self.final_window_minutes) is not int or not (0 <= self.final_window_minutes <= 360):
            raise ValueError('Sluttfase må være 0–360 minutter')
        if type(self.final_interval_minutes) is not int or not (10 <= self.final_interval_minutes <= 60):
            raise ValueError('Intervall i sluttfasen må være 10–60 minutter')
        if not self.scanner_path or '\x00' in self.scanner_path:
            raise ValueError('Skannermappe kreves')
        if self.profile == 'koteng_v24' and self.venue != 'koteng_arena':
            raise ValueError('Koteng-motoren kan ikke kjøres på en annen arena')
        if self.profile in ('lerkendal_legacy', 'lerkendal_v23') and self.venue != 'lerkendal':
            raise ValueError('Lerkendal-motoren krever Lerkendal')
        if self.upload and not self.enabled:
            raise ValueError('Aktiver jobben før opplasting kan slås på')

    def as_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, value: dict) -> 'Job':
        return cls(**value)

    def kickoff(self) -> datetime:
        return parse_utc(self.kickoff_at)

    def last_start(self) -> datetime:
        """Planned slot of the last scan."""
        return self.kickoff() - timedelta(minutes=self.stop_before_minutes)

    def start_deadline(self) -> datetime:
        """No new scan may begin after this (the last slot plus a short grace)."""
        return self.last_start() + START_GRACE

    def hard_stop(self) -> datetime:
        """A running scan is stopped here: kickoff, or after the last slot's scan has had time."""
        return max(self.kickoff(), self.last_start() + timedelta(minutes=15))

    def _grid(self, n: int) -> datetime:
        return self.last_start() - timedelta(minutes=n * self.final_interval_minutes)

    def final_start(self) -> datetime:
        """First slot of the final phase. Slots run every final_interval_minutes and end on last_start()."""
        span = self.last_start() - (self.kickoff() - timedelta(minutes=self.final_window_minutes))
        return self._grid(max(0, span // timedelta(minutes=self.final_interval_minutes)))

    def next_slot(self, time: datetime) -> datetime:
        """First final-phase slot later than time (+1 min so a finished slot is not repeated)."""
        span = self.last_start() - time - timedelta(minutes=1)
        if span < timedelta(0):
            return self.last_start() + timedelta(minutes=self.final_interval_minutes)
        return self._grid(-(-span // timedelta(minutes=self.final_interval_minutes)) - 1)

    def next_after(self, time: datetime, minutes: int | None = None) -> datetime:
        """Next scan: never skip the final phase, and follow its slots inside it."""
        fs = self.final_start()
        if time >= fs - timedelta(minutes=1):
            return self.next_slot(time)
        return min(time + timedelta(minutes=minutes or self.interval_minutes), fs)

    def effective_due(self, due: datetime, now: datetime) -> datetime:
        """Pull forward a slot planned with the normal interval once the final phase applies."""
        fs = self.final_start()
        if now < fs:
            return min(due, fs)
        return min(due, self.next_slot(now - timedelta(minutes=1)))

    def path(self, base: Path) -> Path:
        p = Path(self.scanner_path)
        return p.resolve() if p.is_absolute() else (base / p).resolve()
