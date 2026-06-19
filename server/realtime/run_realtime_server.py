from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

if __package__ is None or __package__ == "":
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

from server.realtime.aruco_tracker import ArUcoRealtimeTracker
from server.realtime.frame_source import FrameSourceConfig, create_frame_source
from server.realtime.online_state_filter import OnlineStateFilter
from server.realtime.overlay_http_server import OverlayHttpServer
from server.realtime.realtime_logger import RealtimeLogger
from server.realtime.roi_realtime import RoiRealtimeAnalyzer
from server.realtime.schemas import OverlayMessage, WarningMessage
from server.realtime.yolo_realtime import RealtimeYoloAnalyzer


def parse_args():
    parser = argparse.ArgumentParser(description="Run the realtime AR PSR harness.")
    parser.add_argument("--config", default="configs/realtime_v1.yaml")
    parser.add_argument("--source", choices=["dummy", "camera", "session"], default=None)
    parser.add_argument("--session", default=None)
    parser.add_argument("--camera-index", type=int, default=None)
    parser.add_argument("--camera-backend", choices=["any", "dshow", "msmf"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--max-frames", type=int, default=0, help="0 means run until Ctrl+C.")
    parser.add_argument("--save-frames", action="store_true")
    parser.add_argument("--dummy-auto-advance", type=int, default=None, help="Advance one state every N frames in dummy mode. 0 disables.")
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def make_session_id(prefix: str = "rt") -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)

    source_cfg = config.get("source", {})
    source_type = args.source or source_cfg.get("type", "dummy")
    session_path = args.session or source_cfg.get("session_path", "")
    camera_index = args.camera_index if args.camera_index is not None else int(source_cfg.get("camera_index", 0))
    camera_backend = args.camera_backend or source_cfg.get("camera_backend", "dshow")
    frame_source = create_frame_source(
        FrameSourceConfig(
            source_type=source_type,
            camera_index=camera_index,
            camera_backend=camera_backend,
            session_path=session_path,
            width=int(source_cfg.get("width", 1280)),
            height=int(source_cfg.get("height", 720)),
            replay_fps=float(source_cfg.get("replay_fps", 5.0)),
            dummy_fps=float(source_cfg.get("dummy_fps", 10.0)),
        )
    )

    overlay_cfg = config.get("overlay", {})
    host = args.host or overlay_cfg.get("host", "127.0.0.1")
    port = int(args.port or overlay_cfg.get("port", 8765))
    web_root = overlay_cfg.get("web_root", "web_overlay")
    overlay = OverlayHttpServer(host=host, port=port, web_root=web_root)
    overlay.start()

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
    dummy_auto = args.dummy_auto_advance
    if dummy_auto is None:
        dummy_auto = int(filter_cfg.get("dummy_auto_advance_frames", 0))
    state_filter = OnlineStateFilter(
        initial_state=filter_cfg.get("initial_state", "S0"),
        min_confidence=float(filter_cfg.get("min_confidence", 0.75)),
        min_dwell_frames=int(filter_cfg.get("min_dwell_frames", 3)),
        dummy_auto_advance_frames=int(dummy_auto),
        max_state=filter_cfg.get("max_state", "S6"),
    )

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
    )
    if yolo_cfg.get("enabled", False):
        print(f"[INFO] yolo={yolo.reason}")

    log_cfg = config.get("logging", {})
    session_id = make_session_id(str(log_cfg.get("session_prefix", "rt")))
    logger = RealtimeLogger(
        output_root=log_cfg.get("output_root", "outputs/realtime_sessions"),
        session_id=session_id,
        config=config,
        save_frames=bool(args.save_frames or log_cfg.get("save_frames", False)),
        save_frame_every=int(log_cfg.get("save_frame_every", 10)),
    )

    print(f"[INFO] realtime harness started")
    print(f"[INFO] source={source_type}")
    print(f"[INFO] overlay={overlay.url}")
    print(f"[INFO] session_id={session_id}")
    print(f"[INFO] log_dir={logger.session_dir}")
    print("[INFO] press Ctrl+C to stop")

    last_loop_ts = time.perf_counter()
    prev_state = "S0"
    processed = 0

    try:
        for packet in frame_source:
            loop_start = time.perf_counter()
            processed += 1
            fps = 1.0 / max(1e-6, loop_start - last_loop_ts)
            last_loop_ts = loop_start

            t0 = time.perf_counter()
            marker = aruco.process(packet.frame)
            t1 = time.perf_counter()
            roi_result = roi_analyzer.process(packet.frame, marker.homography)
            t_roi = time.perf_counter()
            yolo.submit(packet.frame_id, packet.frame, marker.homography)
            yolo_result = yolo.get_result(packet.frame_id)

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
            estimate = state_filter.update(packet.frame_id, marker.marker_ok, features=features)
            t2 = time.perf_counter()

            msg = OverlayMessage(
                session_id=session_id,
                frame_id=packet.frame_id,
                timestamp_ms=packet.timestamp_ms,
                source=packet.source,
                system_status="RUNNING",
                marker_status=marker.marker_status,
                marker_count=marker.marker_count,
                warp_quality=round(marker.warp_quality, 4),
                current_state=estimate.state,
                current_label=estimate.label,
                next_action=estimate.next_action,
                target=estimate.target,
                confidence=round(estimate.confidence, 4),
                held_reason=estimate.held_reason,
                warning=warning,
                fps=round(fps, 2),
                latency_ms=int((time.perf_counter() - loop_start) * 1000),
                queue_lag_ms=max(0, int(loop_start * 1000) - packet.timestamp_ms),
                yolo_age_ms=yolo_result.age_frames(packet.frame_id),
                extra={
                    "transition_event": estimate.transition_event,
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
            overlay.update(msg_dict, packet.frame)
            t3 = time.perf_counter()

            logger.log_frame(packet, packet.frame)
            logger.log_latency(
                {
                    "frame_id": packet.frame_id,
                    "fps": round(fps, 3),
                    "queue_lag_ms": msg.queue_lag_ms,
                    "latency_capture_ms": 0,
                    "latency_aruco_ms": int((t1 - t0) * 1000),
                    "latency_roi_ms": int((t_roi - t1) * 1000),
                    "latency_filter_ms": int((t2 - t_roi) * 1000),
                    "latency_overlay_ms": int((t3 - t2) * 1000),
                    "total_latency_ms": int((time.perf_counter() - loop_start) * 1000),
                }
            )
            logger.log_result(
                {
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
                }
            )
            logger.log_overlay(msg_dict)

            if estimate.transition_event:
                logger.log_event(
                    timestamp_ms=packet.timestamp_ms,
                    event="STATE_TRANSITION",
                    from_state=prev_state,
                    to_state=estimate.state,
                    reason=estimate.transition_event,
                    confidence=estimate.confidence,
                )
                prev_state = estimate.state
            if warning is not None:
                logger.log_event(
                    timestamp_ms=packet.timestamp_ms,
                    event="WARNING",
                    reason=warning.code,
                    confidence=estimate.confidence,
                )

            if processed % 30 == 0:
                print(json.dumps({"frame": packet.frame_id, "fps": round(fps, 2), "state": estimate.state, "marker": marker.marker_status}, ensure_ascii=False))
            if args.max_frames and processed >= args.max_frames:
                break
    except KeyboardInterrupt:
        print("\n[INFO] stopping")
    finally:
        frame_source.close()
        yolo.close()
        logger.close()
        overlay.stop()
        print(f"[DONE] saved realtime session: {logger.session_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
