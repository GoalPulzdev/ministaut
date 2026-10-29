from __future__ import annotations
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.publish import register_command, register_on_web
from tests.test_control import sample


class Done:
    def __init__(self, code, out, err=''):
        self.returncode, self.stdout, self.stderr = code, out, err


class PublishTests(unittest.TestCase):
    def test_command_carries_match_identity_but_no_token(self):
        with tempfile.TemporaryDirectory() as td:
            j = sample(Path(td))
            cmd = register_command(j, Path(td))
            self.assertIn('register_match.py', cmd[1])
            for value in (j.key, j.label, j.kickoff_at, j.venue):
                self.assertIn(value, cmd)
            self.assertFalse(any('token' in c.lower() for c in cmd))

    def test_success_and_failure(self):
        with tempfile.TemporaryDirectory() as td:
            j = sample(Path(td)); j.path(Path(td)).mkdir(parents=True, exist_ok=True)
            ok = lambda *a, **k: Done(0, 'noise\n' + json.dumps({'ok': True, 'match': {'event_key': j.key}}))
            self.assertEqual(register_on_web(j, Path(td), run=ok)['event_key'], j.key)
            bad = lambda *a, **k: Done(2, json.dumps({'ok': False, 'error': 'Unauthorized'}))
            with self.assertRaisesRegex(RuntimeError, 'Unauthorized'):
                register_on_web(j, Path(td), run=bad)
            def slow(*a, **k):
                raise subprocess.TimeoutExpired('x', 40)
            with self.assertRaisesRegex(RuntimeError, '40 sekunder'):
                register_on_web(j, Path(td), run=slow)

    def test_missing_engine_folder(self):
        with tempfile.TemporaryDirectory() as td:
            j = sample(Path(td), scanner_path=str(Path(td) / 'finnes-ikke'))
            with self.assertRaisesRegex(RuntimeError, 'Motormappen'):
                register_on_web(j, Path(td), run=lambda *a, **k: Done(0, '{}'))

    def test_clean_checkout_link(self):
        from app.gui import clean_checkout
        base = 'https://billett.rbk.no/checkout/6aaceecebfe408c38e1712dd'
        for raw in (base + '/', base + '?utm_source=x', base + '#top', ' ' + base.replace('https', 'http') + ' '):
            self.assertEqual(clean_checkout(raw), base)


if __name__ == '__main__':
    unittest.main()
