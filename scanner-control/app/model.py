"""Explicit, validated configurations: no guessed venue or category."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
import re

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
    # No new scan may start this close to kickoff (a Koteng run takes up to 15 min).
    stop_before_minutes: int = 20

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
        if type(self.stop_before_minutes) is not int or not (0 <= self.stop_before_minutes <= 180):
            raise ValueError('Stopp før avspark må være 0–180 minutter')
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
        """Latest moment a new scan may begin."""
        return self.kickoff() - timedelta(minutes=self.stop_before_minutes)

    def path(self, base: Path) -> Path:
        p = Path(self.scanner_path)
        return p.resolve() if p.is_absolute() else (base / p).resolve()
