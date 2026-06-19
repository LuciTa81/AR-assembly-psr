from __future__ import annotations

STATES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6"]

STATE_LABELS = {
    "S0": "Empty workspace",
    "S1": "Box placed",
    "S2": "Lid closed",
    "S3": "Screw A engagement observed",
    "S4": "Screw B engagement observed",
    "S5": "Screw C engagement observed",
    "S6": "Screw D engagement observed",
}

NEXT_ACTIONS = {
    "S0": "Place the enclosure box",
    "S1": "Close the lid",
    "S2": "Fasten screw A",
    "S3": "Fasten screw B",
    "S4": "Fasten screw C",
    "S5": "Fasten screw D",
    "S6": "Confirm assembly sequence completion",
}

TARGETS = {
    "S0": "box",
    "S1": "lid",
    "S2": "screw_a",
    "S3": "screw_b",
    "S4": "screw_c",
    "S5": "screw_d",
    "S6": "complete",
}

