"""Re-analyze only saved photographs. This script never opens a camera."""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    sys.path.insert(0, args.repo)
    from server.realtime.aruco_tracker import ArUcoRealtimeTracker
    from server.realtime.tool_diagnostic_preview import draw_point, project_point
    from server.realtime.yolo_realtime import RealtimeYoloAnalyzer

    root = Path(__file__).resolve().parent
    sessions = list((root / "session").glob("photo_check_*"))
    if len(sessions) != 1:
        raise ValueError("Expected exactly one captured session")
    session = sessions[0]
    config = yaml.safe_load((session / "config_used.yaml").read_text(encoding="utf-8"))
    records = {r["frame_id"]: r for r in map(json.loads, (session / "results.jsonl").read_text(encoding="utf-8").splitlines())}
    a, y = config["aruco"], config["yolo"]
    tracker = ArUcoRealtimeTracker(enabled=True, layout_path=a["layout"],
        min_markers=a["min_markers"], min_quality=a["min_quality"],
        detect_scale=a["detect_scale"], use_previous_h=False)
    analyzer = RealtimeYoloAnalyzer(enabled=True, weights=y["weights"],
        layout_path=config["roi"]["layout"], conf=y["conf"], imgsz=y["imgsz"],
        workspace_width=y["workspace_width"], workspace_height=y["workspace_height"],
        tool_score_radius=y["tool_score_radius"], tool_score_softness=y["tool_score_softness"])
    output = root / "annotated"
    output.mkdir(exist_ok=True)
    report, thumbnails = [], []

    def label(canvas, value, line):
        cv2.putText(canvas, value, (16, 27 + line * 28), cv2.FONT_HERSHEY_SIMPLEX,
                    .63, (235, 235, 235), 1, cv2.LINE_AA)

    try:
        if not analyzer.available:
            raise RuntimeError(analyzer.reason)
        for path in sorted((session / "frames").glob("*.jpg")):
            frame_id = int(path.stem)
            frame = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError(f"Cannot decode {path}")
            marker = tracker.process(frame)
            corners, ids = tracker._detect(frame)
            # Identity is used only to obtain raw boxes when alignment is invalid.
            # All derived coordinates/scores are discarded for those photographs.
            h = marker.homography if marker.marker_ok else np.eye(3)
            result = analyzer._process(frame_id, frame, h)
            features = result.features if marker.marker_ok else None
            annotated = frame.copy()
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(annotated, corners, ids)
            targets, tip = {}, None
            if marker.marker_ok:
                for name, center in analyzer.centers.items():
                    point = project_point(h, center)
                    targets[name] = point
                    draw_point(annotated, point, "ROI " + name.upper(), (40, 220, 40))
                if features.get("tool_tip_source") in (1, 2):
                    tip = project_point(h, (features["tool_tip_x"], features["tool_tip_y"]))
                    draw_point(annotated, tip, "TIP", (230, 40, 230))
            for det in result.detections:
                x1, y1, x2, y2 = [round(det[k]) for k in ("x1", "y1", "x2", "y2")]
                color = (255, 220, 30)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated, f"{det['class']} {det['confidence']:.2f}",
                    (max(0, x1), max(20, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2, cv2.LINE_AA)
            live = records[frame_id]
            height, width = frame.shape[:2]
            canvas = np.zeros((height + 168, width, 3), np.uint8)
            canvas[140:140 + height] = annotated
            label(canvas, f"PHOTO #{frame_id} | OFFLINE REANALYSIS of this JPEG (not the live async YOLO result)", 0)
            label(canvas, f"Photo markers {marker.marker_count} | quality {marker.warp_quality:.2f} | alignment {marker.marker_status}", 1)
            counts = {c: sum(d["class"] == c for d in result.detections) for c in ("driver", "handle", "screw")}
            label(canvas, "Photo detections: " + " | ".join(f"{k} {v}" for k, v in counts.items()), 2)
            label(canvas, f"LIVE log: {live['state']} | markers {live['marker_count']} | YOLO {live['yolo_reason']} source #{live['yolo_frame_id']}", 3)
            label(canvas, "Green: configured ROI | Cyan: detections | Magenta: estimated tip (not measured tool contact)", 4)
            cv2.putText(canvas, "Coordinates are from the existing 2D workspace model, not eye/display calibration.",
                (16, height + 159), cv2.FONT_HERSHEY_SIMPLEX, .57, (220, 220, 220), 1, cv2.LINE_AA)
            target = output / (path.stem + "_annotated.png")
            ok, encoded = cv2.imencode(".png", canvas)
            if not ok:
                raise OSError("PNG encoding failed")
            target.write_bytes(encoded.tobytes())
            thumbnails.append(cv2.resize(canvas, (640, 444)))
            report.append(dict(frame_id=frame_id, raw=str(path), annotated=str(target),
                detected_marker_ids=[] if ids is None else ids.flatten().tolist(),
                marker_ok=marker.marker_ok, quality=marker.warp_quality, targets=targets,
                estimated_tip=tip, detections=result.detections, features=features,
                live_state=live["state"], live_yolo_reason=live["yolo_reason"],
                live_yolo_source_frame=live["yolo_frame_id"]))
        if not thumbnails:
            raise ValueError("No photographs captured")
        rows = (len(thumbnails) + 2) // 3
        sheet = np.zeros((rows * 444, 1920, 3), np.uint8)
        for i, thumb in enumerate(thumbnails):
            sheet[(i // 3)*444:(i // 3 + 1)*444, (i % 3)*640:(i % 3 + 1)*640] = thumb
        ok, encoded = cv2.imencode(".png", sheet)
        if not ok:
            raise OSError("Contact sheet encoding failed")
        (root / "00_contact_sheet.png").write_bytes(encoded.tobytes())
        (root / "photo_analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps([dict(frame=r["frame_id"], markers=r["detected_marker_ids"],
            marker_ok=r["marker_ok"], quality=r["quality"],
            detections=[(d["class"], round(d["confidence"], 3)) for d in r["detections"]],
            live_state=r["live_state"], live_yolo_reason=r["live_yolo_reason"]) for r in report], indent=2))
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
