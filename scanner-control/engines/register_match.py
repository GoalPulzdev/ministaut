"""Publish one match on the Ministaut web page (title, kickoff, venue).

Runs as its own process in the engine folder, like the senders: the token is read
here from .ministaut-token or MINISTAUT_TOKEN, never by the control program.
Prints one JSON line; exit code 0 = registered.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = 'https://khetbokxbcujwcurvviu.supabase.co/functions/v1/ministaut-register-match'


def token() -> str:
    value = os.environ.get('MINISTAUT_TOKEN', '').strip()
    path = Path('.ministaut-token')
    if not value and path.is_file():
        value = path.read_text(encoding='utf-8').strip()
    if not value:
        raise SystemExit(json.dumps({'ok': False, 'error': 'Token mangler (.ministaut-token)'}))
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--event-key', required=True)
    ap.add_argument('--title', required=True)
    ap.add_argument('--kickoff', required=True)
    ap.add_argument('--venue', required=True, choices=['lerkendal', 'koteng_arena'])
    a = ap.parse_args()
    body = json.dumps({'event_key': a.event_key, 'title': a.title, 'kickoff_at': a.kickoff,
                       'venue_id': a.venue}, ensure_ascii=False).encode('utf-8')
    req = Request(ENDPOINT, data=body, method='POST',
                  headers={'Content-Type': 'application/json', 'x-ministaut-token': token()})
    try:
        with urlopen(req, timeout=25) as reply:
            print(json.dumps(json.load(reply), ensure_ascii=False))
            return 0
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')[:300]
        print(json.dumps({'ok': False, 'status': exc.code, 'error': detail}, ensure_ascii=False))
    except (URLError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': 'Nettverksfeil: ' + str(exc)[:200]}, ensure_ascii=False))
    return 2


if __name__ == '__main__':
    sys.exit(main())
