import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def fixture_module():
    spec = importlib.util.spec_from_file_location("spatial_fixture", ROOT / "tests/unity/serve_spatial_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("elapsed,step,target", [
    (1., "S2", "A"), (3., "S3", "B"), (5., "S4", "C"), (7., "S5", "D")
])
def test_preview_replays_server_step_and_independent_eye_movement(elapsed, step, target):
    module = fixture_module()
    message = module.make_message(elapsed, 70, 10000, "preview")
    assert message["current_state"] == step
    assert message["spatial"]["target_id"] == target
    assert message["spatial"]["target_visible"]
    assert message["spatial"]["left_pixel"] != message["spatial"]["right_pixel"]
    later = module.make_message(elapsed + .5, 80, 10000, "preview")
    assert message["spatial"]["left_pixel"] != later["spatial"]["left_pixel"]


def test_fixture_has_loss_frozen_pose_profile_fault_missing_age_and_recovery():
    module = fixture_module()
    assert module.make_message(9, 181, 10000, "preview")["marker_status"] == "LOST"
    frozen = module.make_message(13, 261, 10000, "preview")
    next_frame = module.make_message(13.5, 271, 10000, "preview")
    assert frozen["timestamp_ms"] < next_frame["timestamp_ms"]
    assert frozen["spatial"]["pose_frame_id"] == next_frame["spatial"]["pose_frame_id"]
    assert frozen["spatial"]["pose_timestamp_ms"] == next_frame["spatial"]["pose_timestamp_ms"]
    assert next_frame["spatial"]["pose_age_ms"] == 1500
    assert not next_frame["spatial"]["target_visible"]
    assert module.make_message(17, 341, 10000, "preview")["spatial"]["display_profile_id"] == "wrong-profile"
    assert "pose_age_ms" not in module.make_message(19, 381, 10000, "preview")["spatial"]
    assert module.make_message(21, 421, 10000, "preview")["spatial"]["target_visible"]


@pytest.mark.parametrize("args,reason", [
    (["-Beast", "-SpatialPreviewConfig", "missing.json"], "laptop-only"),
    (["-SbsGuidance", "-TestRing"], "Choose only one"),
    (["-SpatialPreviewConfig", "missing.json"], "Preview config not found"),
])
def test_launcher_rejects_invalid_sbs_combinations_without_starting_player(args, reason):
    literals = "'" + str(ROOT / "scripts/run_beast_unity.ps1").replace("'", "''") + "' "
    literals += " ".join(item if item.startswith("-") else "'" + item.replace("'", "''") + "'" for item in args)
    # Never start a real Player even if argument validation regresses.
    command = "function Start-Process { throw 'PLAYER_LAUNCH_BLOCKED' }; & " + literals
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    assert result.returncode != 0
    assert reason in result.stdout + result.stderr
