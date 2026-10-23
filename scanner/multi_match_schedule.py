"""Safe per-match rotation for the existing RBK Edge hover scanner.

Only schedules scans. Does not touch the browser, select seats, or bypass the
existing 60-field quality gate. Runtime deadlines use a monotonic clock; UTC
wall-clock deadlines are only used to restore cooldowns after PC restarts.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

from publication import event_key


def load_matches(filename: Path) -> list[dict]:
    """Load explicit, enabled RBK checkout URLs; reject invalid or duplicate IDs."""
    raw = json.loads(Path(filename).read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('matches'), list):
        raise ValueError('kamper.json må inneholde en liste med matches')
    items = raw['matches']
    if not 1 <= len(items) <= 12:
        raise ValueError('Kampoversikten må inneholde mellom 1 og 12 kamper')
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict) or type(item.get('enabled', True)) is not bool:
            raise ValueError('Hver kamp må ha et objekt og enabled=true/false')
        url = item.get('url', '')
        if not isinstance(url, str):
            raise ValueError('Kamp-URL må være tekst')
        parsed = urlsplit(url)
        if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port is not None:
            raise ValueError('Kamp-URL skal bare inneholde en ren checkout-adresse')
        key = event_key(url)
        if key in seen:
            raise ValueError('Samme kamp-ID er registrert flere ganger: ' + key)
        seen.add(key)
        title = item.get('name', 'RBK kamp')
        if not isinstance(title, str) or not 3 <= len(title.strip()) <= 120:
            raise ValueError('Kampnavnet må være 3–120 tegn')
        if item.get('enabled', True):
            result.append({'key': key, 'url': url, 'name': title.strip()})
    if not result:
        raise ValueError('Ingen kamper er aktivert i kamper.json')
    return result


class MatchRotation:
    """One independent deadline per game, without catch-up storms."""

    def __init__(self, matches: list[dict], state_path: Path, interval_seconds=3600,
                 retry_seconds=900, *, tick=None, utc_now=None):
        if not matches or not 180 <= interval_seconds <= 7 * 86400:
            raise ValueError('Ugyldig kampoversikt eller intervall')
        if not 60 <= retry_seconds <= interval_seconds:
            raise ValueError('Ugyldig retryintervall')
        self.matches = list(matches)
        self.urls = {m['key']: m['url'] for m in self.matches}
        self.names = {m['key']: m['name'] for m in self.matches}
        if len(self.urls) != len(self.matches):
            raise ValueError('Duplikate kamper i tidsplanen')
        self.state_path = Path(state_path)
        self.interval_seconds = float(interval_seconds)
        self.retry_seconds = float(retry_seconds)
        self._tick = tick or monotonic
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._deadlines = {m['key']: self._tick() for m in self.matches}
        self._restore()

    @property
    def count(self) -> int:
        return len(self.matches)

    def _restore(self) -> None:
        if not self.state_path.is_file():
            return
        try:
            state = json.loads(self.state_path.read_text(encoding='utf-8'))
            saved = state.get('next_due_utc', {})
            if not isinstance(saved, dict):
                return
            now = self._utc_now()
            for key, iso in saved.items():
                if key not in self._deadlines or not isinstance(iso, str):
                    continue
                deadline = datetime.fromisoformat(iso.replace('Z', '+00:00'))
                if deadline.utcoffset() is None:
                    continue
                remaining = (deadline.astimezone(timezone.utc) - now).total_seconds()
                if 0 < remaining <= self.interval_seconds:
                    self._deadlines[key] = self._tick() + remaining
        except (OSError, ValueError, TypeError, OverflowError):
            # Bad/outdated local status must never prevent scanning.
            return

    def next(self, now=None) -> str | None:
        when = self._tick() if now is None else now
        key = min(self._deadlines, key=self._deadlines.get)
        return self.urls[key] if self._deadlines[key] <= when else None

    def next_status(self, now=None) -> tuple[str, int]:
        when = self._tick() if now is None else now
        key = min(self._deadlines, key=self._deadlines.get)
        return self.names[key], max(0, int(self._deadlines[key] - when))

    def finished(self, url: str, approved: bool, now=None) -> None:
        """Success: one hour. Missing/unapproved result or navigation error: 15 min."""
        key = event_key(url)
        if key not in self._deadlines:
            return  # Manual one-off switches do not silently enter the roster.
        seconds = self.interval_seconds if approved else self.retry_seconds
        self._deadlines[key] = (self._tick() if now is None else now) + seconds
        self._save()

    def _save(self) -> None:
        wall = self._utc_now().astimezone(timezone.utc)
        tick = self._tick()
        status = {'version': 1, 'next_due_utc': {
            key: (wall + timedelta(seconds=max(0, due - tick))).isoformat()
            for key, due in self._deadlines.items()
        }}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(self.state_path.suffix + '.tmp')
        temp.write_text(json.dumps(status, indent=2), encoding='utf-8')
        os.replace(temp, self.state_path)
