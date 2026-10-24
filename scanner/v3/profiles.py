"""Versioned stadium learning profiles; no assumptions about field counts."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
import os
import re


@dataclass(frozen=True)
class StadiumProfile:
    id: str
    version: int
    provider: str
    sections: dict[str, int]
    anchors: dict
    verified: bool = False

    def validate(self):
        if not re.fullmatch(r"[a-z0-9_-]{2,50}", self.id):
            raise ValueError("Invalid stadium ID")
        if type(self.version) is not int or self.version < 1 or not self.provider:
            raise ValueError("Invalid stadium profile version/provider")
        if not isinstance(self.sections, dict) or not self.sections:
            raise ValueError("Stadium has no measured fields")
        if any(not isinstance(k, str) or not k.strip() for k in self.sections):
            raise ValueError("Invalid section labels")
        if any(type(v) is not int or v <= 0 for v in self.sections.values()):
            raise ValueError("Section capacities must be positive integers")
        if not isinstance(self.anchors, dict) or set(self.anchors) - set(self.sections):
            raise ValueError("Anchor belongs to unknown section")
        for field, points in self.anchors.items():
            if not isinstance(points, list):
                raise ValueError("Expected a list of hover points for " + field)
            for item in points:
                pair = item.get("ref") if isinstance(item, dict) else item
                if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                    raise ValueError("Invalid hover anchor for " + field)
                if any(type(v) not in (float, int) or not math.isfinite(v) for v in pair):
                    raise ValueError("Invalid hover coordinates for " + field)
        if self.verified and any(not self.anchors.get(k) for k in self.sections):
            raise ValueError("Approved profiles require recorded points for every section")
        return self

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8"))).validate()

    def save(self, path):
        self.validate()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def candidate_from_reference(stadium_json, anchors_json, profile_id="lerkendal"):
    """Import *real* legacy references, always as a draft pending human approval."""
    data = json.loads(Path(stadium_json).read_text(encoding="utf-8"))
    points = json.loads(Path(anchors_json).read_text(encoding="utf-8"))
    seats = data.get("seat_sections", {})
    anchors = points.get("fields", {})
    if not isinstance(anchors, dict):
        raise ValueError("Legacy point file missing fields")
    return StadiumProfile(profile_id, 1, "vivenu", seats, anchors, False).validate()


def validate_measurement(profile, measurements):
    """Never treat a missing field as zero or approve an untrained arena."""
    profile.validate()
    if not profile.verified:
        return False, "Stadium profile not approved"
    if not isinstance(measurements, dict) or set(measurements) != set(profile.sections):
        return False, "Incomplete or unexpected sections"
    for key, value in measurements.items():
        if type(value) is not int or not 0 <= value <= profile.sections[key]:
            return False, "Invalid available count"
    return True, ""
