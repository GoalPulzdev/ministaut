"""Verified stadium profiles, using the existing Lerkendal seat reference."""
from __future__ import annotations
from dataclasses import dataclass,asdict
import json
from pathlib import Path

@dataclass(frozen=True)
class StadiumProfile:
    id: str
    version: int
    provider: str
    sections: dict[str,int]
    anchors: dict
    verified: bool = False
    def validate(self):
        if not self.id or self.version < 1 or not self.provider: raise ValueError("Invalid profile identity")
        if not self.sections or any(not isinstance(v,int) or isinstance(v,bool) or v<=0 for v in self.sections.values()):
            raise ValueError("Section capacities must be positive integers")
        if len(self.sections)!=len(set(self.sections)):raise ValueError("Duplicate sections")
        if not isinstance(self.anchors,dict):raise ValueError("Invalid anchors")
        if self.verified and set(self.sections)-set(self.anchors):
            raise ValueError("A verified profile requires anchors for every section")
        return self
    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data).validate()
    def save(self,path):
        self.validate()
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self),ensure_ascii=False,indent=2),encoding="utf-8")
        temp.replace(path)

def candidate_from_reference(stadium_json,anchors_json,profile_id="lerkendal"):
    """Import real Lerkendal references without asserting that other venues have 60 fields."""
    data=json.loads(Path(stadium_json).read_text(encoding="utf-8"))
    anchors=json.loads(Path(anchors_json).read_text(encoding="utf-8"))
    sections=data["seat_sections"]
    return StadiumProfile(profile_id,1,"vivenu",sections,anchors,False).validate()

def validate_measurement(profile,measurements):
    """Fail closed: one reading for each expected section, exactly."""
    profile.validate()
    if not profile.verified:return False,"Profile not approved"
    if set(measurements)!=set(profile.sections):return False,"Incomplete or unexpected sections"
    for key,value in measurements.items():
        if type(value) is not int or not 0<=value<=profile.sections[key]:return False,"Invalid available seats"
    return True,""
