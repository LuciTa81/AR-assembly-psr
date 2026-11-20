"""Regression for the local 2026-10-06 open/closed lid score separation.

These samples are not a general accuracy benchmark; independent live checks
are still required after changes to the camera, lighting or workspace.
"""
from pathlib import Path

import yaml

from server.realtime.online_state_filter import OnlineStateFilter


ROOT = Path(__file__).resolve().parents[2]


def test_configured_lid_gate_rejects_measured_open_and_accepts_measured_closed():
    config = yaml.safe_load((ROOT / "configs/realtime_viture_beast_aruco.yaml").read_text(encoding="utf-8"))
    settings = dict(config["state_filter"], initial_state="S1")
    state_filter = OnlineStateFilter.from_config(settings)
    assert settings["timing"]["placement_ms"] == 300
    features = {
        "lid_threshold": config["roi"]["lid_threshold"],
        "lid_min_confidence": settings["lid_min_confidence"],
    }
    frame = 0

    def tick(t, score, marker_ok=True):
        nonlocal frame
        frame += 1
        return state_filter.update(
            frame, marker_ok, dict(features, lid_closed_score=score),
            timestamp_ms=t, roi_valid=marker_ok,
        )

    # The highest measured open score must not advance, however long it persists.
    for t in range(1000, 3001, 100):
        result = tick(t, 0.47942502574958695)
        assert result.state == "S1"
        assert not result.transition_event

    # Use the lowest measured closed score, not the more favorable average.
    for t in (3100, 3200, 3300):
        assert tick(t, 0.5097538764536259).state == "S1"
    assert tick(3400, 0.5097538764536259, marker_ok=False).state == "S1"
    for t in (3500, 3600, 3700):
        assert tick(t, 0.5097538764536259).state == "S1"
    result = tick(3800, 0.5097538764536259)
    assert result.state == "S2"
    assert result.target == "screw_a"
    assert result.transition_event == "S1->S2"
