"""Europe/Oslo <-> UTC without tzdata (Windows Python often lacks zoneinfo data).

EU rule: summer time (UTC+2) from last Sunday of March 01:00 UTC to last
Sunday of October 01:00 UTC; otherwise UTC+1.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re


def _last_sunday(year: int, month: int) -> datetime:
    d = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def is_summer(utc: datetime) -> bool:
    utc = utc.astimezone(timezone.utc)
    start = _last_sunday(utc.year, 3).replace(hour=1)
    end = _last_sunday(utc.year, 10).replace(hour=1)
    return start <= utc < end


def offset(utc: datetime) -> timedelta:
    return timedelta(hours=2 if is_summer(utc) else 1)


def to_oslo(utc: datetime) -> datetime:
    u = utc.astimezone(timezone.utc)
    return (u + offset(u)).replace(tzinfo=None)


def from_oslo(local: datetime) -> datetime:
    """Naive Oslo wall time -> aware UTC. Rejects the non-existent spring hour;
    the repeated autumn hour resolves to the first (summer time) occurrence."""
    if local.tzinfo is not None:
        raise ValueError('Forventer lokal Oslo-tid uten tidssone')
    for hours in (2, 1):
        utc = (local - timedelta(hours=hours)).replace(tzinfo=timezone.utc)
        if is_summer(utc) == (hours == 2):
            return utc
    raise ValueError('Klokkeslettet finnes ikke i Norge (overgang til sommertid)')


def parse_local(date_text: str, time_text: str) -> datetime:
    m = re.fullmatch(r'\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*', date_text or '')
    t = re.fullmatch(r'\s*(\d{1,2})[:.](\d{2})\s*', time_text or '')
    if not m or not t:
        raise ValueError('Avspark: bruk dato dd.mm.åååå og klokkeslett tt:mm')
    try:
        local = datetime(int(m[3]), int(m[2]), int(m[1]), int(t[1]), int(t[2]))
    except ValueError as exc:
        raise ValueError('Ugyldig dato eller klokkeslett') from exc
    return from_oslo(local)


def text(utc: datetime | None, fmt: str = '%d.%m.%Y %H:%M') -> str:
    return to_oslo(utc).strftime(fmt) if utc else '—'
