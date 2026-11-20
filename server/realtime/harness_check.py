from __future__ import annotations

import importlib
import math
from pathlib import Path

from server.realtime.state_definitions import STATES


def validate_config(config: dict) -> None:
    for section in ("source", "overlay", "aruco", "roi", "yolo", "state_filter", "logging"):
        if not isinstance(config.get(section, {}), dict):
            raise ValueError(f"{section} must be a mapping")
    for section in ("aruco", "roi", "yolo"):
        if not isinstance(config.get(section, {}).get("enabled", False), bool):
            raise ValueError(f"{section}.enabled must be true or false")
    source = config.get("source", {})
    if source.get("type", "dummy") not in {"dummy", "camera", "session"}:
        raise ValueError("source.type must be dummy, camera, or session")
    for key in ("replay_fps", "dummy_fps"):
        value = float(source.get(key, 5))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"source.{key} must be finite and positive")
    state = config.get("state_filter", {})
    from server.realtime.online_state_filter import OnlineStateFilter
    OnlineStateFilter.from_config(state)
    if state.get("initial_state", "S0") not in STATES or state.get("max_state", "S6") not in STATES:
        raise ValueError("state_filter states must be S0-S6")
    if STATES.index(state.get("initial_state", "S0")) > STATES.index(state.get("max_state", "S6")):
        raise ValueError("initial_state exceeds max_state")
    if int(config.get("yolo", {}).get("max_age_ms", 800)) <= 0:
        raise ValueError("yolo.max_age_ms must be positive")
    if type(config.get('yolo', {}).get('nested_driver_dedup', False)) is not bool:
        raise ValueError('yolo.nested_driver_dedup must be true or false')
    if type(config.get('yolo', {}).get('handle_linked_driver', False)) is not bool:
        raise ValueError('yolo.handle_linked_driver must be true or false')
    if not 0 <= int(config.get("overlay", {}).get("port", 8765)) <= 65535:
        raise ValueError("overlay.port must be between 0 and 65535")


def check_runtime(config: dict, *, source: str, session_path: Path | None) -> dict:
    validate_config(config)
    if source not in {"dummy", "camera", "session", "features"}:
        raise ValueError(f"Unknown source: {source}")
    checks = []

    def add(name, status, detail):
        checks.append({"name": name, "status": status, "detail": str(detail)})

    def require_file(name, path):
        p = Path(path) if path else None
        add(name, "ok" if p and p.is_file() else "missing", p or "path not configured")

    dependencies = ["yaml"]
    if source != "features":
        dependencies += ["numpy", "cv2"]
        if config.get("yolo", {}).get("enabled", False):
            dependencies += ["ultralytics"]
    for name in dependencies:
        try:
            module = importlib.import_module(name)
            if name == "cv2" and config.get("aruco", {}).get("enabled") and not hasattr(module, "aruco"):
                raise ImportError("OpenCV ArUco support missing")
            add(f"dependency.{name}", "ok", getattr(module, "__version__", "imported"))
        except (ImportError, OSError) as exc:
            add(f"dependency.{name}", "missing", f"{type(exc).__name__}: {exc}")

    if source == "features":
        require_file("session.results", session_path / "results.jsonl" if session_path else None)
        require_file("session.config_used", session_path / "config_used.yaml" if session_path else None)
    else:
        if source == "session":
            add("session.path", "ok" if session_path and session_path.is_dir() else "missing",
                session_path or "session path not configured")
            if session_path and session_path.is_dir():
                from server.realtime.frame_source import FrameSourceConfig, SessionFrameSource
                try:
                    frames = SessionFrameSource(FrameSourceConfig(
                        source_type="session", session_path=str(session_path),
                        replay_fps=float(config.get("source", {}).get("replay_fps", 5.0)),
                    ))
                    add("session.frames", "ok", f"{len(frames.items)} recorded image paths")
                    add("session.decode", "not_tested", "Images are decoded only during replay")
                except (OSError, ValueError) as exc:
                    add("session.frames", "missing", exc)
        for section, keys in (("aruco", ("layout",)), ("roi", ("layout",)),
                              ("yolo", ("weights",))):
            if config.get(section, {}).get("enabled"):
                for key in keys:
                    require_file(f"{section}.{key}", config[section].get(key))
        if config.get("yolo", {}).get("enabled"):
            if not config.get("screw_auto_trial"):
                require_file("yolo.roi_layout", config.get("roi", {}).get("layout"))
            add("yolo.inference", "not_tested", "Model inference is not part of doctor")
        if config.get("roi", {}).get("enabled"):
            refs = config["roi"].get("refs")
            names = ["box_absent", "box_present", "lid_open", "lid_closed"]
            names += [f"screw_{s}_{status}" for s in "abcd" for status in ("empty", "done")]
            for name in names:
                require_file(f"roi.refs.{name}", Path(refs) / f"{name}.jpg" if refs else None)
        if source == "camera":
            add("camera.capture", "not_tested", "Use check_beast_device.ps1 and probe_cameras.py")
    return {"ready": all(c["status"] != "missing" for c in checks),
            "source": source, "checks": checks}
