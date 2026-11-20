from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from copy import deepcopy
from contextlib import ExitStack

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

from server.realtime.harness_check import check_runtime, validate_config


def parse_args():
    parser = argparse.ArgumentParser(description="Run the realtime AR PSR harness.")
    parser.add_argument("--config", default="configs/realtime_v1.yaml")
    parser.add_argument("--weights", default=None)
    parser.add_argument("--guidance-mode", choices=["auto", "operator", "hybrid"], default=None)
    parser.add_argument("--screw-auto-trial", action="store_true",
                        help="Opt-in metric tool trial: start at A, default end at B")
    parser.add_argument("--screw-auto-end-state", choices=["S3", "S6"], default=None,
                        help="Trial end: S3/B (default) or S6/final confirmation after A-D")
    parser.add_argument('--screw-resume-ms', type=int, default=None,
                        help='Opt-in bounded same-target recovery grace, 0 (baseline) to 1000ms')
    parser.add_argument('--completed-hold-resume-ms', type=int, default=None,
                        help='Opt-in completed-HOLD recovery with fresh withdrawal, 0 to 3000ms')
    parser.add_argument('--source-recovery-boundary', action='store_true',
                        help='Opt-in: source-local tool failures preserve newer in-flight evidence')
    parser.add_argument("--presentation-config", type=Path, default=None,
                        help="Local camera/workspace profiles for continuous candidate presentation")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument('--nested-driver-dedup', action='store_true',
                        help='Opt-in metric trial: merge matching nested shaft-tip candidates')
    parser.add_argument("--validate-filter", action="store_true")
    parser.add_argument("--source", choices=["dummy", "camera", "session"], default=None)
    parser.add_argument("--session", default=None)
    parser.add_argument("--camera-index", type=int, default=None)
    parser.add_argument("--camera-backend", choices=["any", "dshow", "msmf"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--max-frames", type=int, default=0, help="0 means run until Ctrl+C.")
    parser.add_argument("--stop-file", type=Path, default=None, help="Owned launcher shutdown signal")
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--diagnostic-preview", action="store_true", help="Show local tool diagnostics without saving preview images.")
    parser.add_argument("--dummy-auto-advance", type=int, default=None, help="Advance one state every N frames in dummy mode. 0 disables.")
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("config must be a mapping")
    return data


def make_session_id(prefix: str = "rt") -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:12]}"


def make_filter_input(packet, marker, roi, yolo, features):
    return {
        "frame_id": packet.frame_id, "timestamp_ms": packet.timestamp_ms,
        "marker_ok": marker.marker_ok, "features": features,
        "observation_id": yolo.frame_id, "observation_timestamp_ms": yolo.timestamp_ms,
        "evidence_valid": yolo.evidence_valid,
        "roi_valid": roi.enabled and roi.reason == "ok" and marker.marker_ok,
    }


def make_guidance_message(packet, marker, estimate, *, session_id, legacy_action=None, **diagnostics):
    from server.realtime.schemas import OverlayMessage
    return OverlayMessage(
        session_id=session_id, frame_id=packet.frame_id, timestamp_ms=packet.timestamp_ms,
        source=packet.source, system_status="RUNNING", marker_status=marker.marker_status,
        marker_count=marker.marker_count, warp_quality=round(marker.warp_quality, 4),
        current_state=estimate.state, current_label=estimate.label, target=estimate.target,
        next_action=estimate.next_action if estimate.guidance is not None or legacy_action is None else legacy_action,
        confidence=round(estimate.confidence, 4), held_reason=estimate.held_reason,
        guidance=estimate.guidance, **diagnostics)


def record_and_publish(logger, overlay, packet, result_row: dict, message: dict, previous_state: str,
                       display_frame=None) -> None:
    logger.log_result(result_row)
    if result_row.get("transition_event"):
        logger.log_event(
            timestamp_ms=packet.timestamp_ms, event="STATE_TRANSITION",
            from_state=previous_state, to_state=result_row["state"],
            reason=result_row["transition_event"], confidence=message["confidence"],
        )
        logger.flush_transition()
    overlay.update(message, packet.frame if display_frame is None else display_frame)
    logger.log_overlay(message)


REPO_ROOT = Path(__file__).resolve().parents[2]


def build_effective_config(base: dict, args: argparse.Namespace) -> dict:
    config = deepcopy(base)
    validate_config(config)
    for name in ("source", "overlay", "aruco", "roi", "yolo", "state_filter", "logging"):
        config.setdefault(name, {})
    for arg, section, key in (
        ("source", "source", "type"), ("session", "source", "session_path"),
        ("camera_index", "source", "camera_index"), ("camera_backend", "source", "camera_backend"),
        ("host", "overlay", "host"), ("port", "overlay", "port"),
        ("weights", "yolo", "weights"), ("dummy_auto_advance", "state_filter", "dummy_auto_advance_frames"),
    ):
        value = getattr(args, arg, None)
        if value is not None:
            config[section][key] = value
    if getattr(args, "save_frames", False):
        config["logging"]["save_frames"] = True
    if getattr(args, "diagnostic_preview", False) and config["logging"].get("save_frames", False):
        raise ValueError("diagnostic preview requires save_frames=false")
    mode = getattr(args, "guidance_mode", None) or config.get("guidance_mode", "auto")
    if mode not in ("auto", "operator", "hybrid"):
        raise ValueError("Invalid guidance mode")
    config["guidance_mode"] = mode
    config["screw_auto_trial"] = bool(getattr(args, "screw_auto_trial", False))
    if getattr(args, 'nested_driver_dedup', False):
        config['yolo']['nested_driver_dedup'] = True
    if config['yolo'].get('handle_linked_driver', False) and mode != 'hybrid' and not config['screw_auto_trial']:
        raise ValueError('handle_linked_driver requires a metric screw trial or hybrid flow')
    if config['yolo'].get('nested_driver_dedup', False) and mode != 'hybrid' and not config['screw_auto_trial']:
        raise ValueError('Nested driver dedup requires hybrid flow or an isolated screw trial')
    end_state = getattr(args, "screw_auto_end_state", None)
    if end_state is not None and (not config["screw_auto_trial"] or end_state not in ("S3", "S6")):
        raise ValueError("Screw auto end state requires an explicit trial and S3 or S6")
    if mode == 'hybrid' and config['screw_auto_trial']:
        raise ValueError('Choose hybrid assembly flow or the isolated screw trial')
    resume_ms = getattr(args, 'screw_resume_ms', None)
    if resume_ms is not None:
        if type(resume_ms) is not int or not 0 <= resume_ms <= 1000:
            raise ValueError('Screw recovery grace must be an integer in 0..1000 ms')
        if mode != 'hybrid' and not config['screw_auto_trial']:
            raise ValueError('Screw recovery requires hybrid flow or an isolated screw trial')
        config['state_filter'].setdefault('timing', {})['resume_grace_ms'] = resume_ms
    completed_ms = getattr(args, 'completed_hold_resume_ms', None)
    if completed_ms is not None:
        if type(completed_ms) is not int or not 0 <= completed_ms <= 3000:
            raise ValueError('Completed-HOLD recovery must be an integer in 0..3000 ms')
        if mode != 'hybrid' and not config['screw_auto_trial']:
            raise ValueError('Completed-HOLD recovery requires hybrid flow or an isolated screw trial')
        config['state_filter'].setdefault('timing', {})['completed_hold_resume_ms'] = completed_ms
    if getattr(args, 'source_recovery_boundary', False):
        if mode != 'hybrid' and not config['screw_auto_trial']:
            raise ValueError('Source recovery boundary requires hybrid flow or an isolated screw trial')
        config['state_filter'].setdefault('timing', {})['source_recovery_boundary'] = True
    if config["screw_auto_trial"] or mode == 'hybrid':
        if mode not in ("auto", "hybrid") or not getattr(args, "presentation_config", None):
            raise ValueError("Screw auto trial requires auto mode and --presentation-config")
        if config["overlay"].get("host", "127.0.0.1") not in ("127.0.0.1", "localhost"):
            raise ValueError("Screw auto trial requires loopback")
        if config["logging"].get("save_frames", False) or getattr(args, "diagnostic_preview", False):
            raise ValueError("Screw auto trial requires no image saving or legacy diagnostic preview")
        if not config["yolo"].get("enabled", False):
            raise ValueError("Screw auto trial requires YOLO")
        for section in ("aruco", "roi"):
            config[section]["enabled"] = False
        config["state_filter"].update(initial_state="S2", max_state='S6' if mode == 'hybrid' else end_state or "S3",
                                     guidance_policy="timed_v1", dummy_auto_advance_frames=0)
    if mode == "operator":
        if getattr(args, "save_frames", False):
            raise ValueError("Operator demo does not save camera frames")
        config["logging"]["save_frames"] = False
        if config["source"].get("type", "dummy") != "dummy" and not getattr(args, "presentation_config", None):
            raise ValueError("Operator camera/session mode requires --presentation-config")
        if config["overlay"].get("host", "127.0.0.1") not in ("127.0.0.1", "localhost"):
            raise ValueError("Operator mode requires loopback")
        if getattr(args, "diagnostic_preview", False):
            raise ValueError("Operator mode uses the supervisor, not legacy tool diagnostics")
        for section in ("aruco", "roi", "yolo"):
            config[section]["enabled"] = False
        config["state_filter"]["dummy_auto_advance_frames"] = 0
    config["overlay"].setdefault("web_root", "web_overlay")
    config["logging"].setdefault("output_root", "outputs/realtime_sessions")
    for section, key in (
        ("source", "session_path"), ("overlay", "web_root"),
        ("aruco", "layout"), ("roi", "layout"), ("roi", "refs"),
        ("yolo", "weights"), ("logging", "output_root"),
    ):
        value = config[section].get(key)
        if value:
            config[section][key] = str((REPO_ROOT / Path(value).expanduser()).resolve())
    validate_config(config)
    return config


def main() -> int:
    args = parse_args()
    try:
        config = build_effective_config(load_config(REPO_ROOT / args.config), args)
        source = "features" if args.validate_filter else config["source"].get("type", "dummy")
        session = config["source"].get("session_path")
        report = check_runtime(config, source=source, session_path=Path(session) if session else None)
        if args.presentation_config:
            from server.realtime.workspace_live_preview import load_profiles
            data = json.loads(args.presentation_config.read_text(encoding="utf-8"))
            camera, _, metadata = load_profiles(Path(data["camera_profile"]), Path(data["workspace_profile"]))
            if config.get("guidance_mode") in ("operator", "hybrid") or config.get("screw_auto_trial"):
                config["source"]["width"], config["source"]["height"] = camera.image_size
            config["presentation"] = {key: metadata[key] for key in
                                      ("camera_profile_sha256", "workspace_profile_sha256")}
            report["checks"].append({"name": "presentation.profiles", "status": "ok",
                                     "detail": "Profiles match; live tracking and eye alignment are not tested"})
        if args.doctor or not report["ready"]:
            print(json.dumps(report, indent=2, ensure_ascii=True))
        if not report["ready"]:
            return 1
        if args.doctor:
            return 0
        if args.validate_filter:
            from server.realtime.realtime_replay import validate_session
            validate_session(Path(session))
            return 0
        with ExitStack() as resources:
            return run_session(config, args, resources)
    except ImportError as exc:
        print(f"[ERROR] Missing or blocked dependency: {exc}", file=sys.stderr)
        return 1
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def run_session(config: dict, args: argparse.Namespace, resources: ExitStack) -> int:
    from server.realtime.aruco_tracker import ArUcoRealtimeTracker
    from server.realtime.frame_source import FrameSourceConfig, create_frame_source
    from server.realtime.online_state_filter import OnlineStateFilter
    from server.realtime.overlay_http_server import OverlayHttpServer
    from server.realtime.realtime_logger import RealtimeLogger
    from server.realtime.roi_realtime import RoiRealtimeAnalyzer
    from server.realtime.schemas import WarningMessage
    from server.realtime.yolo_realtime import RealtimeYoloAnalyzer

    source_cfg = config.get("source", {})
    source_type = source_cfg.get("type", "dummy")
    session_path = source_cfg.get("session_path", "")
    camera_index = args.camera_index if args.camera_index is not None else int(source_cfg.get("camera_index", 0))
    camera_backend = args.camera_backend or source_cfg.get("camera_backend", "dshow")
    frame_source_config = FrameSourceConfig(
        source_type=source_type,
        camera_index=camera_index,
        camera_backend=camera_backend,
        session_path=session_path,
        width=int(source_cfg.get("width", 1280)),
        height=int(source_cfg.get("height", 720)),
        replay_fps=float(source_cfg.get("replay_fps", 5.0)),
        dummy_fps=float(source_cfg.get("dummy_fps", 10.0)),
    )

    overlay_cfg = config.get("overlay", {})
    host = args.host or overlay_cfg.get("host", "127.0.0.1")
    port = int(args.port if args.port is not None else overlay_cfg.get("port", 8765))
    web_root = overlay_cfg.get("web_root", "web_overlay")

    aruco_cfg = config.get("aruco", {})
    aruco = ArUcoRealtimeTracker(
        enabled=bool(aruco_cfg.get("enabled", False)),
        layout_path=aruco_cfg.get("layout", ""),
        min_markers=int(aruco_cfg.get("min_markers", 4)),
        min_quality=float(aruco_cfg.get("min_quality", 0.25)),
        detect_scale=float(aruco_cfg.get("detect_scale", 1.0)),
        use_previous_h=bool(aruco_cfg.get("use_previous_h", True)),
        max_fallback_frames=int(aruco_cfg.get("max_fallback_frames", 5)),
    )

    filter_cfg = config.get("state_filter", {})
    state_filter = OnlineStateFilter.from_config(filter_cfg)

    roi_cfg = config.get("roi", {})
    roi_analyzer = RoiRealtimeAnalyzer(
        enabled=bool(roi_cfg.get("enabled", False)),
        layout_path=roi_cfg.get("layout", ""),
        refs_dir=roi_cfg.get("refs", ""),
        box_threshold=float(roi_cfg.get("box_threshold", 0.50)),
        lid_threshold=float(roi_cfg.get("lid_threshold", 0.52)),
        score_alpha=float(roi_cfg.get("score_alpha", 0.35)),
    )

    yolo_cfg = config.get("yolo", {})
    log_cfg = config.get("logging", {})
    session_id = make_session_id(str(log_cfg.get("session_prefix", "rt")))
    operator = None
    if config.get("guidance_mode") == "operator":
        from server.realtime.operator_session import OperatorSession
        operator = OperatorSession(session_id)
    elif config.get('guidance_mode') == 'hybrid':
        from server.realtime.assembly_session import AssemblySession
        operator = AssemblySession(session_id, state_filter)
    presentation = None
    if getattr(args, 'presentation_config', None):
        if host not in ('127.0.0.1', 'localhost') or args.save_frames or log_cfg.get('save_frames', False):
            raise ValueError('Presentation requires loopback and no frame saving')
        from server.realtime.presentation_bridge import PresentationBridge
        presentation = PresentationBridge(args.presentation_config, session_id)
        resources.callback(presentation.close)
        if operator is not None or config.get("screw_auto_trial"):
            frame_source_config.width, frame_source_config.height = presentation.camera.image_size
        print(f"Presentation client config: {presentation.config_path}", flush=True)
    metric_plane = None
    if config.get("screw_auto_trial") or config.get('guidance_mode') == 'hybrid':
        from server.realtime.yolo_realtime import MetricToolPlane
        if presentation is None:
            raise ValueError("Screw auto trial requires presentation profiles")
        metric_plane = MetricToolPlane(presentation.camera, presentation.workspace)
        end_label = "S6/final confirmation" if config["state_filter"]["max_state"] == "S6" else "S3/B only"
        start_label = 'assembly flow: S0/operator setup' if operator is not None else 'screw-auto trial: S2/A'
        print(f"[INFO] {start_label} -> {end_label}; tool distance unit=mm; no torque verification", flush=True)
    yolo = RealtimeYoloAnalyzer(
        enabled=bool(yolo_cfg.get("enabled", False)),
        weights=yolo_cfg.get("weights", ""),
        layout_path=roi_cfg.get("layout", ""),
        conf=float(yolo_cfg.get("conf", 0.30)),
        imgsz=int(yolo_cfg.get("imgsz", 640)),
        interval_frames=int(yolo_cfg.get("interval_frames", 3)),
        workspace_width=int(yolo_cfg.get("workspace_width", 800)),
        workspace_height=int(yolo_cfg.get("workspace_height", 600)),
        tool_score_radius=float(yolo_cfg.get("tool_score_radius", 90.0)),
        tool_score_softness=float(yolo_cfg.get("tool_score_softness", 45.0)),
        max_age_frames=int(yolo_cfg.get("max_age_frames", 10)),
        session_id=session_id,
        max_age_ms=int(yolo_cfg.get("max_age_ms", 800)),
        metric_plane=metric_plane,
        nested_driver_dedup=yolo_cfg.get('nested_driver_dedup', False),
        handle_linked_driver=yolo_cfg.get('handle_linked_driver', False),
    )
    resources.callback(yolo.close)
    if yolo_cfg.get("enabled", False) and not yolo.available:
        raise RuntimeError(f"YOLO startup failed: {yolo.reason}")

    if presentation is not None:
        import cv2
        # Ultralytics import disables OpenCV threads for DataLoader use. This
        # runner has no DataLoader; configure once before any frames are submitted.
        previous_threads = cv2.getNumThreads()
        cv2.setNumThreads(min(4, max(1, os.cpu_count() or 1)))
        print(f"[INFO] presentation OpenCV threads: {previous_threads} -> {cv2.getNumThreads()}", flush=True)

    preview = preview_window = None
    if getattr(args, "diagnostic_preview", False):
        from server.realtime.tool_diagnostic_preview import ToolDiagnosticPreview
        from server.realtime.workspace_live_preview import PreviewWindow
        preview = ToolDiagnosticPreview(yolo.centers)
        preview_window = PreviewWindow((1280, 544), allow_save=False)
        resources.callback(preview_window.close)
        preview_window.root.title("Beast tool diagnostic | Q: stop | NO IMAGE SAVING")
        preview_window.root.attributes("-topmost", True)

    logger = RealtimeLogger(
        output_root=log_cfg.get("output_root", "outputs/realtime_sessions"),
        session_id=session_id,
        config=config,
        save_frames=bool(args.save_frames or log_cfg.get("save_frames", False)),
        save_frame_every=int(log_cfg.get("save_frame_every", 10)),
    )

    resources.callback(logger.close)
    frame_source = create_frame_source(frame_source_config)
    resources.callback(frame_source.close)
    overlay = OverlayHttpServer(host=host, port=port, web_root=web_root, operator=operator)
    resources.callback(overlay.stop)
    overlay.start()

    print(f"[INFO] realtime harness started")
    print(f"[INFO] source={source_type}")
    print(f"[INFO] overlay={overlay.url}")
    print(f"[INFO] session_id={session_id}")
    print(f"[INFO] log_dir={logger.session_dir}")
    print("[INFO] press Ctrl+C to stop")

    last_loop_ts = time.perf_counter()
    prev_state = 'S0' if config.get('guidance_mode') == 'hybrid' else filter_cfg.get("initial_state", "S0")
    processed = 0
    transition_ack_until_frame = -1
    transition_ack_text = ""
    transition_ack_frames = int(overlay_cfg.get("transition_ack_frames", 10))
    min_valid_yolo_frame = 0

    try:
        for packet in frame_source:
            loop_start = time.perf_counter()
            processed += 1
            fps = 1.0 / max(1e-6, loop_start - last_loop_ts)
            last_loop_ts = loop_start

            t0 = time.perf_counter()
            presentation_frame = presentation_status = None
            marker = aruco.process(packet.frame)
            observation = None
            if operator is not None or metric_plane is not None:
                if presentation is not None:
                    from server.realtime.presentation_bridge import metric_marker
                    observation = presentation.observe(packet)
                    marker = metric_marker(observation, time.perf_counter())
                    if metric_plane is not None:
                        marker.homography = metric_plane.homography(observation, time.perf_counter())
                        marker.homography_source = "metric_screw_plane"
                        marker.marker_ok = marker.marker_ok and marker.homography is not None
                elif source_type == "dummy":
                    from server.realtime.aruco_tracker import ArUcoResult
                    marker = ArUcoResult(False, True, 0, "OK", 0.)
            t1 = time.perf_counter()
            roi_result = roi_analyzer.process(packet.frame, marker.homography)
            t_roi = time.perf_counter()
            if not marker.marker_ok:
                min_valid_yolo_frame = packet.frame_id + 1
            yolo.submit(
                packet.frame_id, packet.frame, marker.homography,
                timestamp_ms=packet.timestamp_ms, marker_ok=marker.marker_ok,
            )
            yolo_result = yolo.get_result(
                packet.frame_id, now_ms=int(time.perf_counter() * 1000),
                min_valid_frame_id=min_valid_yolo_frame,
            )

            warning = None
            if marker.warning_code:
                warning = WarningMessage(code=marker.warning_code, message=marker.warning_message)

            features = dict(roi_result.scores)
            features.update(roi_result.deltas)
            features.update(yolo_result.features)
            features["box_threshold"] = float(roi_cfg.get("box_threshold", 0.50))
            features["lid_threshold"] = float(roi_cfg.get("lid_threshold", 0.52))
            features["box_min_confidence"] = float(filter_cfg.get("box_min_confidence", filter_cfg.get("min_confidence", 0.75)))
            features["lid_min_confidence"] = float(filter_cfg.get("lid_min_confidence", filter_cfg.get("min_confidence", 0.75)))
            features["screw_min_confidence"] = float(filter_cfg.get("screw_min_confidence", filter_cfg.get("min_confidence", 0.75)))
            features["screw_done_threshold"] = float(roi_cfg.get("screw_done_threshold", 0.58))
            features["screw_delta_threshold"] = float(roi_cfg.get("screw_delta_threshold", 0.015))
            features["screw_event_min_score"] = float(roi_cfg.get("screw_event_min_score", 0.45))
            features["screw_event_hold_frames"] = int(roi_cfg.get("screw_event_hold_frames", 12))
            features["screw_confirm_frames"] = int(roi_cfg.get("screw_confirm_frames", 1))
            features["screw_min_dwell_frames"] = int(roi_cfg.get("screw_min_dwell_frames", filter_cfg.get("min_dwell_frames", 3)))
            features["require_yolo_for_screw"] = 1 if bool(yolo_cfg.get("require_for_screw", False)) else 0
            features["yolo_tool_score_threshold"] = float(yolo_cfg.get("tool_score_threshold", 0.35))
            features["yolo_target_dominance_ratio"] = float(yolo_cfg.get("target_dominance_ratio", 0.0))
            for screw in ["a", "b", "c", "d"]:
                for name in [
                    "screw_done_threshold",
                    "screw_delta_threshold",
                    "screw_event_min_score",
                    "screw_event_hold_frames",
                    "screw_confirm_frames",
                    "screw_min_dwell_frames",
                ]:
                    key = f"{name}_{screw}"
                    if key in roi_cfg:
                        features[key] = roi_cfg[key]
                yolo_key = f"tool_score_threshold_{screw}"
                if yolo_key in yolo_cfg:
                    features[f"yolo_tool_score_threshold_{screw}"] = yolo_cfg[yolo_key]
            features["require_screw_delta"] = 1 if bool(roi_cfg.get("require_screw_delta", True)) else 0
            filter_input = make_filter_input(packet, marker, roi_result, yolo_result, features)
            fresh_input = 0 <= time.perf_counter() * 1000 - packet.timestamp_ms < 500
            if config.get('guidance_mode') == 'hybrid':
                estimate = operator.update(filter_input, fresh_input)
            else:
                estimate = (operator.update(marker.marker_ok and fresh_input)
                            if operator is not None else state_filter.update(**filter_input))
            if presentation is not None:
                from server.realtime.presentation_bridge import guided_target
                presentation_frame, presentation_status = presentation.update(
                    packet, target_id=guided_target(estimate, marker.marker_ok), observation=observation)
            diagnostic_image = diagnostic_info = None
            if preview is not None:
                diagnostic_image, diagnostic_info = preview.render(
                    packet, marker, yolo_result, estimate, state_filter.timed_gate)
            t2 = time.perf_counter()
            display_next_action = estimate.next_action
            if estimate.guidance is None and estimate.transition_event and transition_ack_frames > 0:
                transition_ack_until_frame = packet.frame_id + transition_ack_frames
                transition_ack_text = f"Detected: {estimate.label}"
            if packet.frame_id <= transition_ack_until_frame and transition_ack_text:
                display_next_action = transition_ack_text

            msg = make_guidance_message(
                packet, marker, estimate,
                session_id=session_id,
                legacy_action=display_next_action,
                warning=warning,
                fps=round(fps, 2),
                latency_ms=int((time.perf_counter() - loop_start) * 1000),
                queue_lag_ms=max(0, int(loop_start * 1000) - packet.timestamp_ms),
                yolo_age_ms=yolo_result.age_ms(int(time.perf_counter() * 1000)),
                extra={
                    "transition_event": estimate.transition_event,
                    "raw_next_action": estimate.next_action,
                    "homography_source": marker.homography_source,
                    "fallback_age": marker.fallback_age,
                    "roi_reason": roi_result.reason,
                    "yolo_reason": yolo_result.reason,
                    "yolo_frame_id": yolo_result.frame_id,
                    "yolo_latency_ms": yolo_result.latency_ms,
                    **{k: round(v, 4) for k, v in roi_result.scores.items()},
                    **{k: round(v, 4) for k, v in roi_result.deltas.items()},
                    **{k: round(v, 4) for k, v in yolo_result.features.items()},
                },
            )
            msg_dict = msg.to_dict()
            if metric_plane is not None:
                msg_dict['extra']['screw_auto_trial'] = config.get('screw_auto_trial', False)
                msg_dict['extra']['screw_auto_end_state'] = config['state_filter']['max_state']
                msg_dict['extra']['tool_distance_unit'] = 'mm'
            if operator is not None:
                msg_dict['extra']['operator'] = operator.metadata()
            if presentation_status is not None:
                msg_dict['extra']['presentation_overlay'] = 1.0
                msg_dict['extra']['presentation_pose'] = presentation_status['status']
                msg_dict['extra']['presentation_target'] = presentation_status['assembly_overlay']['target_id']
                msg_dict['extra']['presentation_selection'] = 'stage'
                msg_dict['extra']['presentation_diagnostics'] = presentation_status['diagnostics']
            logger.log_frame(packet, packet.frame)
            result_row = {
                    "frame_id": packet.frame_id,
                    "marker_ok": marker.marker_ok,
                    "marker_count": marker.marker_count,
                    "warp_quality": marker.warp_quality,
                    "homography_source": marker.homography_source,
                    "fallback_age": marker.fallback_age,
                    "roi_reason": roi_result.reason,
                    "yolo_reason": yolo_result.reason,
                    "yolo_frame_id": yolo_result.frame_id,
                    "yolo_latency_ms": yolo_result.latency_ms,
                    **{k: round(v, 6) for k, v in roi_result.scores.items()},
                    **{k: round(v, 6) for k, v in roi_result.deltas.items()},
                    **{k: round(v, 6) for k, v in yolo_result.features.items()},
                    "state": estimate.state,
                    "confidence": estimate.confidence,
                    "held_reason": estimate.held_reason,
                    "transition_event": estimate.transition_event,
                    "filter_input": filter_input,
                    "target": estimate.target,
                    "next_action": estimate.next_action,
                    "guidance": asdict(estimate.guidance) if estimate.guidance is not None else None,
                    "guidance_mode": config.get("guidance_mode", "auto"),
                    "operator": operator.metadata() if operator is not None else None,
                }
            publish_start = time.perf_counter()
            if config.get('guidance_mode') == 'hybrid':
                result_row['assembly_input'] = operator.last_input.copy()
            if metric_plane is not None:
                # Numeric camera-pixel boxes belong to yolo_frame_id, not the current frame.
                result_row["yolo_detections"] = yolo_result.detections
            if diagnostic_info is not None:
                result_row["tool_diagnostic"] = diagnostic_info
            if presentation_status is not None:
                result_row["presentation_diagnostics"] = presentation_status['diagnostics']
            if presentation_frame is None:
                record_and_publish(logger, overlay, packet, result_row, msg_dict, prev_state)
            else:
                record_and_publish(logger, overlay, packet, result_row, msg_dict, prev_state,
                                   display_frame=presentation_frame)
            t3 = time.perf_counter()
            prev_state = estimate.state
            logger.log_latency({
                "frame_id": packet.frame_id, "fps": round(fps, 3),
                "queue_lag_ms": msg.queue_lag_ms, "latency_capture_ms": None,
                "latency_aruco_ms": int((t1 - t0) * 1000),
                "latency_roi_ms": int((t_roi - t1) * 1000),
                "latency_filter_ms": int((t2 - t_roi) * 1000),
                "latency_overlay_ms": int((t3 - publish_start) * 1000),
                "total_latency_ms": int((t3 - loop_start) * 1000),
            })
            if warning is not None:
                logger.log_event(
                    timestamp_ms=packet.timestamp_ms,
                    event="WARNING",
                    reason=warning.code,
                    confidence=estimate.confidence,
                )

            if processed % 30 == 0:
                print(json.dumps({"frame": packet.frame_id, "fps": round(fps, 2), "state": estimate.state, "marker": marker.marker_status}, ensure_ascii=False))
            if preview_window is not None:
                preview_window.show(diagnostic_image)
                if preview_window.poll() == "quit":
                    break
            if args.max_frames and processed >= args.max_frames:
                break
            if getattr(args, "stop_file", None) is not None and args.stop_file.exists():
                break
    except KeyboardInterrupt:
        print("\n[INFO] stopping")
    finally:
        print(f"[INFO] session log directory: {logger.session_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
