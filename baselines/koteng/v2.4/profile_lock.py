"""Read-only safety lock for a user-confirmed Koteng seat-map calibration.

This is a SHA256 *accidental change guard*, NOT a signature, access control,
or proof of sellability.  Keeps recorded section/geometry assumptions stable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def lock_payload(profile: dict, anchors: dict, event: str) -> dict:
    if profile.get('venue_id') != 'koteng_arena' or anchors.get('venue_id') != 'koteng_arena':
        raise ValueError('Profil og ankere må begge tilhøre Koteng Arena')
    if event not in profile.get('event_configs', {}):
        raise ValueError('Kampen finnes ikke i den låste Koteng-profilen')
    if anchors.get('training_event_key') != event:
        raise ValueError('Ankerfilen er kalibrert for feil arrangement')
    if anchors.get('profile_version_at_training') != profile.get('profile_version'):
        raise ValueError('Ankerfilens profilversjon stemmer ikke med gjeldende profil')
    if set(anchors.get('points', {})) != set(profile.get('reference_sections', {})):
        raise ValueError('Ankerfilens områder stemmer ikke med seksjonsprofilen')
    return {
        'venue_id': profile['venue_id'],
        'profile_version': profile['profile_version'],
        'event_key': event,
        'reference_sections': profile['reference_sections'],
        'standing_sections': profile.get('standing_sections', []),
        'event_config': profile['event_configs'][event],
        'reference_snapshot': profile.get('reference_snapshot'),
        'local_seated_profile_approved': profile.get('local_seated_profile_approved'),
        'map_full_coverage_verified': profile.get('map_full_coverage_verified'),
        'training_event_key': anchors['training_event_key'],
        'profile_version_at_training': anchors['profile_version_at_training'],
        'reference_viewport': anchors['reference_viewport'],
        'reference_map_region': anchors['reference_map_region'],
        'reference_page_zoom': anchors['reference_page_zoom'],
        'points': anchors['points'],
    }


def digest_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def verify_profile_lock(profile: dict, anchors: dict, event: str) -> str:
    lock = profile.get('local_profile_lock')
    if not isinstance(lock, dict) or lock.get('state') != 'LOCKED':
        raise ValueError('Mangler låst Koteng-profil. Ingen telling godkjennes.')
    if lock.get('event_key') != event:
        raise ValueError('Låsen er knyttet til en annen kamp: opprett ny kampkalibrering separat')
    expected = lock.get('sha256')
    actual = digest_payload(lock_payload(profile, anchors, event))
    if not isinstance(expected,str) or expected != actual:
        raise ValueError('STOPP: Låst seksjonsprofil eller ankerpunkter er endret. '
                         'Gjenopprett godkjent V1.8; ikke overskriv de låste punktene.')
    if profile.get('public_export_enabled',False) or profile.get('approved',False):
        raise ValueError('Låst lokalprofil kan ikke slå på offentlig publisering.')
    return actual


def load_verified_lock(profile: dict, anchor_path: Path, event: str) -> tuple[dict,str]:
    path = Path(anchor_path)
    if not path.is_file():
        raise ValueError('Låste ankerpunkter mangler. Kopier dem fra fungerende V1.8, ikke lær opp på nytt.')
    anchors = json.loads(path.read_text(encoding='utf-8'))
    return anchors, verify_profile_lock(profile, anchors, event)


def main() -> int:
    root = Path(__file__).resolve().parent
    profile = json.loads((root/'koteng_profile.json').read_text('utf-8'))
    event = next(iter(profile['event_configs']))
    try:
        _, digest = load_verified_lock(profile, root/'ankerpunkter_koteng.json', event)
    except (ValueError, OSError, KeyError) as exc:
        print('STOPP - PROFILEN ER IKKE LÅST KORREKT:', exc)
        return 2
    print('KOTENG-PROFIL LÅST OG KONTROLLERT')
    print('Kamp:', event)
    print('Profil:', profile['profile_version'])
    print('Felt:', ', '.join(profile['reference_sections']))
    print('Referansesnapshot: 424 observerte ledige - IKKE et aktuelt tall')
    print('SHA256:', digest)
    print('Kun lokal telling - Supabase/offentlig publisering AV')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
