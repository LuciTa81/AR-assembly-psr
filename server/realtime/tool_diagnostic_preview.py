"""Read-only, in-memory tool diagnostics; never changes recognition evidence."""

from collections import OrderedDict

import cv2
import numpy as np


def project_point(homography, point):
    try:
        point = np.asarray([*point, 1.], dtype=float)
        projected = np.linalg.solve(homography, point)
        if not np.isfinite(projected).all() or abs(projected[2]) < 1e-8:
            return None
        pixel = projected[:2] / projected[2]
        return pixel.tolist() if np.isfinite(pixel).all() else None
    except (ValueError, TypeError, np.linalg.LinAlgError):
        return None


def text(image, value, x, y, width=620, color=(230, 230, 230)):
    scale = .62
    size = cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0]
    if size > width:
        scale *= width / size
    cv2.putText(image, value, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def panel(image):
    canvas = np.zeros((360, 640, 3), np.uint8)
    height, width = image.shape[:2]
    scale = min(640 / width, 360 / height)
    w, h = max(1, round(width * scale)), max(1, round(height * scale))
    x, y = (640 - w) // 2, (360 - h) // 2
    canvas[y:y+h, x:x+w] = cv2.resize(image, (w, h))
    return canvas


def draw_point(image, point, label, color):
    if point is None or not (0 <= point[0] < image.shape[1] and 0 <= point[1] < image.shape[0]):
        return
    x, y = np.rint(point).astype(int)
    cv2.circle(image, (x, y), 14, color, 3)
    cv2.drawMarker(image, (x, y), color, cv2.MARKER_CROSS, 12, 2)
    text(image, label, max(0, min(x + 18, image.shape[1] - 150)), max(20, y), color=color)


class ToolDiagnosticPreview:
    def __init__(self, centers, buffer_size=16):
        self.centers = dict(centers)
        self.buffer_size = max(1, int(buffer_size))
        self.frames = OrderedDict()

    def remember(self, packet, homography):
        # YOLO is asynchronous: its coordinates must stay on its own source frame.
        self.frames[packet.frame_id] = (packet.frame.copy(),
            None if homography is None else homography.copy())
        while len(self.frames) > self.buffer_size:
            self.frames.popitem(last=False)

    def render(self, packet, marker, result, estimate, gate):
        self.remember(packet, marker.homography)
        current = packet.frame.copy()
        if marker.marker_ok:
            for name, center in self.centers.items():
                draw_point(current, project_point(marker.homography, center), "ROI " + name.upper(), (40, 220, 40))
        observation = np.zeros_like(current)
        info = dict(observation_frame=None, preview_reason=result.reason,
                    targets={}, tip=None, detections=0, engage_ms=0, release_ms=0)
        source = self.frames.get(result.frame_id)
        valid = marker.marker_ok and result.evidence_valid and 0 < result.frame_id <= packet.frame_id
        if valid and source is not None:
            observation, h = source[0].copy(), source[1]
            info.update(observation_frame=result.frame_id, preview_reason="ok")
            for name, center in self.centers.items():
                point = project_point(h, center)
                if point is not None:
                    info["targets"][name] = point
                    draw_point(observation, point, "ROI " + name.upper(), (40, 220, 40))
            for detection in result.detections:
                coords = [detection.get(k, float("nan")) for k in ("x1", "y1", "x2", "y2")]
                if not np.isfinite(coords).all():
                    continue
                x1, y1, x2, y2 = np.rint(coords).astype(int)
                x1, x2 = np.clip([x1, x2], 0, observation.shape[1] - 1)
                y1, y2 = np.clip([y1, y2], 0, observation.shape[0] - 1)
                cv2.rectangle(observation, (x1, y1), (x2, y2), (255, 220, 30), 2)
                text(observation, f"{detection['class']} {detection['confidence']:.2f}", x1, max(20, y1-8), color=(255, 220, 30))
                info["detections"] += 1
            f = result.features
            if f.get("tool_tip_source") in (1, 2) and f.get("tool_tip_x", -1) >= 0 and f.get("tool_tip_y", -1) >= 0:
                info["tip"] = project_point(h, (f["tool_tip_x"], f["tool_tip_y"]))
                draw_point(observation, info["tip"], "TIP", (230, 40, 230))
            if gate is not None:
                for key, started in (("engage_ms", gate.started_at), ("release_ms", gate.release_at)):
                    if started is not None:
                        info[key] = max(0, result.timestamp_ms - started)
        elif valid:
            info["preview_reason"] = "source_frame_missing"
        elif not marker.marker_ok:
            info["preview_reason"] = "marker_not_stable"

        canvas = np.zeros((544, 1280, 3), np.uint8)
        canvas[100:460, :640] = panel(current)
        canvas[100:460, 640:] = panel(observation)
        phase = estimate.guidance.phase if estimate.guidance else "LEGACY"
        reason = estimate.guidance.reason if estimate.guidance else ""
        text(canvas, f"LIVE #{packet.frame_id} | {estimate.state} | {phase}", 12, 25)
        text(canvas, f"Markers: {marker.marker_count} {marker.marker_status} | quality {marker.warp_quality:.2f}", 12, 53)
        text(canvas, "Green: configured ROI targets (camera diagnostic only)", 12, 81)
        text(canvas, f"YOLO #{result.frame_id} | age {packet.timestamp_ms-result.timestamp_ms}ms | {info['preview_reason']}", 652, 25)
        if info["observation_frame"] is not None:
            text(canvas, f"Driver count: {result.features.get('driver_count', 0):.0f} | source frame, not live frame", 652, 53)
            text(canvas, "Cyan: detector boxes | Magenta: estimated tip", 652, 81)
        else:
            text(canvas, "No usable observation. Hidden boxes do not mean no driver.", 652, 53)
        scores = " | ".join(f"{n.upper()} {max(result.features.get('tool_score_'+n, 0), result.features.get('tip_screw_score_'+n, 0)):.2f}" for n in "abcd")
        text(canvas, scores if info["observation_frame"] is not None else "Tool scores: unavailable", 12, 484)
        text(canvas, f"Hold {info['engage_ms']}ms | Release {info['release_ms']}ms | {reason or phase}", 652, 484)
        text(canvas, estimate.next_action, 12, 515, width=1250)
        text(canvas, "LOCAL DIAGNOSTIC | NO IMAGE SAVING", 12, 538, width=1250, color=(150, 150, 150))
        return canvas, info
