"""Koteng's complete numbered-seating inventory, confirmed by the operator.

These are the six and only six seated areas on the stadium's public map.
Ståplass A is a different inventory category and is excluded deliberately.
Any future seatmap/capacity change must be reviewed, not silently accepted.
"""
from __future__ import annotations

EXPECTED_SEATED = {
    "FELT-1": 49,
    "FELT-2": 160,
    "FELT-3": 120,
    "FELT-4": 152,
    "FELT-5": 49,
    "VIP": 71,
}
TOTAL_SEATED = sum(EXPECTED_SEATED.values())  # 601; not the overall stadium capacity
STANDING_AREA = "STÅPLASS A"


def validate_koteng_profile(profile):
    profile.validate()
    if profile.id != "koteng_arena":
        raise ValueError("Wrong arena profile")
    if profile.sections != EXPECTED_SEATED:
        raise ValueError("Koteng's confirmed six field capacities do not match the saved profile")
    if set(profile.anchors) != set(EXPECTED_SEATED) or any(
            not profile.anchors[name] for name in EXPECTED_SEATED):
        raise ValueError("Saved hover points are missing for one or more Koteng sections")
    for field in EXPECTED_SEATED:
        for anchor in profile.anchors[field]:
            if not isinstance(anchor, dict) or anchor.get("coordinate_system") not in (
                "map_normalized", "map_normalized_v2"
            ):
                raise ValueError("Unknown/legacy coordinate system in " + field)
            coordinates = anchor["ref"]
            if any(not 0 <= value <= 1 for value in coordinates):
                raise ValueError("Koteng anchor is outside the training map for " + field)
    return profile
