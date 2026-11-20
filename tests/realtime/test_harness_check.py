from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from server.realtime import run_realtime_server as runtime


ROOT = Path(__file__).resolve().parents[2]


def doctor():
    from server.realtime.harness_check import check_runtime
    return check_runtime


def test_effective_config_preserves_overrides_and_resolves_repo_paths(monkeypatch, tmp_path):
    base = {"source": {"type": "dummy"}, "logging": {"save_frames": False}}
    before = copy.deepcopy(base)
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(source="camera", camera_index=3, port=0,
                              weights="models/example.pt", save_frames=True)
    actual = runtime.build_effective_config(base, args)
    assert actual["source"]["camera_index"] == 3
    assert actual["source"]["type"] == "camera"
    assert actual["overlay"]["port"] == 0
    assert actual["yolo"]["weights"] == str(ROOT / "models/example.pt")
    assert actual["logging"]["save_frames"] is True
    assert base == before


def test_missing_weights_not_ready():
    config = {"yolo": {"enabled": True, "weights": "not-a-real-model.pt"},
              "roi": {"layout": "missing.yaml"}}
    report = doctor()(config, source="camera", session_path=None)
    assert report["ready"] is False
    assert any(c["name"] == "yolo.weights" and c["status"] == "missing"
               for c in report["checks"])


def test_missing_dependency_reported(monkeypatch):
    from server.realtime import harness_check
    original = harness_check.importlib.import_module
    def missing(name):
        if name == "cv2":
            raise ImportError("test missing cv2")
        return original(name)
    monkeypatch.setattr(harness_check.importlib, "import_module", missing)
    report = doctor()({}, source="dummy", session_path=None)
    assert report["ready"] is False
    assert any(c["name"] == "dependency.cv2" and c["status"] == "missing"
               for c in report["checks"])


def test_feature_replay_does_not_require_camera_or_yolo(monkeypatch, tmp_path):
    from server.realtime import harness_check
    original = harness_check.importlib.import_module
    def forbid_vision(name):
        if name in {"cv2", "ultralytics", "torch"}:
            raise AssertionError("feature replay must not import vision")
        return original(name)
    monkeypatch.setattr(harness_check.importlib, "import_module", forbid_vision)
    (tmp_path / "results.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "config_used.yaml").write_text("{}\n", encoding="utf-8")
    report = doctor()({"yolo": {"enabled": True}}, source="features", session_path=tmp_path)
    assert report["ready"] is True


def test_doctor_does_not_open_camera(monkeypatch):
    cv2 = pytest.importorskip("cv2", exc_type=ImportError)
    def forbidden(*args):
        raise AssertionError("doctor must not capture")
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    report = doctor()({}, source="camera", session_path=None)
    assert report["ready"] is True
    assert any(c["name"] == "camera.capture" and c["status"] == "not_tested"
               for c in report["checks"])


@pytest.mark.parametrize("config", [
    {"source": []}, {"source": {"replay_fps": 0}},
    {"state_filter": {"initial_state": "S9"}},
    {"yolo": {"enabled": "false"}},
])
def test_invalid_configuration_is_not_ready(config):
    with pytest.raises(ValueError):
        effective = runtime.build_effective_config(config, argparse.Namespace())
        doctor()(effective, source="dummy", session_path=None)


def test_startup_failure_opens_no_runtime_resources(monkeypatch, tmp_path):
    config = tmp_path / "missing-model.yaml"
    config.write_text("source:\n  type: camera\nyolo:\n  enabled: true\n  weights: nonexistent.pt\n")
    monkeypatch.setattr(sys, "argv", ["runtime", "--config", str(config)])
    def forbidden(*args, **kwargs):
        raise AssertionError("resource opened before preflight completed")
    monkeypatch.setattr(runtime, "run_session", forbidden)
    assert runtime.main() == 1


def test_launcher_doctor_from_other_directory(tmp_path):
    (tmp_path / "results.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "config_used.yaml").write_text("{}\n", encoding="utf-8")
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(ROOT / "scripts/run_beast_harness.ps1"), "-Mode", "doctor",
         "-PythonExe", sys.executable, "-Config", "configs/realtime_v1.yaml",
         "-ValidateFilter", "-Session", str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ready"] is True


def test_malformed_yaml_is_a_configuration_error(monkeypatch, tmp_path):
    config = tmp_path / "broken.yaml"
    config.write_text("source: [\n")
    monkeypatch.setattr(sys, "argv", ["runtime", "--config", str(config), "--doctor"])
    assert runtime.main() == 2


def test_missing_config_parser_is_reported(monkeypatch):
    def missing(path):
        raise ImportError("yaml not installed")
    monkeypatch.setattr(runtime, "load_config", missing)
    monkeypatch.setattr(sys, "argv", ["runtime", "--doctor"])
    assert runtime.main() == 1


@pytest.mark.parametrize("kind", ["empty", "feature_only", "missing_image"])
def test_image_replay_preflight_rejects_sessions_without_recorded_images(monkeypatch, tmp_path, kind):
    from types import SimpleNamespace
    from server.realtime import harness_check
    monkeypatch.setattr(harness_check.importlib, "import_module",
                        lambda name: SimpleNamespace(__version__="test"))
    if kind == "feature_only":
        (tmp_path / "results.jsonl").write_text("{}\n")
    elif kind == "missing_image":
        (tmp_path / "frames.csv").write_text("frame_id,path\n1,missing.jpg\n")
    report = doctor()({}, source="session", session_path=tmp_path)
    assert report["ready"] is False
    assert any(c["name"] == "session.frames" and c["status"] == "missing"
               for c in report["checks"])


def test_image_replay_preflight_checks_paths_without_decoding(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from server.realtime import harness_check
    monkeypatch.setattr(harness_check.importlib, "import_module",
                        lambda name: SimpleNamespace(__version__="test"))
    (tmp_path / "one.jpg").write_bytes(b"not decoded during preflight")
    report = doctor()({}, source="session", session_path=tmp_path)
    assert report["ready"] is True
    assert any(c["name"] == "session.decode" and c["status"] == "not_tested"
               for c in report["checks"])
