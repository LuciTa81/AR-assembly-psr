"""Local checkerboard capture and offline intrinsics estimation; never auto-activate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

SCHEMA = "beast_camera_capture_v1"
WINDOW = "Beast calibration | C: confirm camera | SPACE: save | Q: finish"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]


def write_json(path: Path, value: dict, *, exclusive: bool = True) -> None:
    payload = json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    else:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)


def checkerboard_object_points(columns: int, rows: int, square_mm: float) -> np.ndarray:
    if any(type(v) is not int or not 3 <= v <= 50 for v in (columns, rows)):
        raise ValueError("Inner corner counts must be integers between 3 and 50")
    if not math.isfinite(square_mm) or square_mm <= 0:
        raise ValueError("Measured square size must be finite and positive")
    result = np.zeros((columns * rows, 3), np.float32)
    result[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2) * square_mm
    return result


def validate_size(size) -> tuple[int, int]:
    if len(size) != 2 or any(type(v) is not int or v < 2 for v in size):
        raise ValueError("Invalid image resolution")
    return tuple(size)


def detect_checkerboard(image: np.ndarray, pattern_size: tuple[int, int]) -> np.ndarray | None:
    checkerboard_object_points(*pattern_size, 1.)
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.size == 0
            or image.ndim not in (2, 3) or (image.ndim == 3 and image.shape[2] != 3)):
        raise ValueError("Expected a nonempty uint8 gray/BGR image")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    found, corners = cv2.findChessboardCornersSB(gray, pattern_size, flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
    return corners.reshape(-1, 2) if found else None


class CaptureSession:
    def __init__(self, root: Path, *, camera_index: int, backend: str, image_size: tuple[int, int],
                 pattern_size: tuple[int, int], square_mm: float, inventory: dict):
        checkerboard_object_points(*pattern_size, square_mm)
        validate_size(image_size)
        self.directory = root / ("beast-calibration-" + stamp())
        self.directory.mkdir(parents=True, exist_ok=False)
        self.manifest = {
            "schema_version": SCHEMA, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "preview", "opencv_version": cv2.__version__,
            "image_size": list(image_size),
            "target": {"inner_corners": list(pattern_size), "square_mm": square_mm},
            "camera": {"index": camera_index, "backend": backend, "requested_size": list(image_size),
                       "identity_confirmation": "unconfirmed", "inventory": inventory},
            "images": [],
        }
        self._persist()

    def _persist(self):
        write_json(self.directory / "manifest.json", self.manifest, exclusive=False)

    def validate_frame(self, image):
        if tuple(image.shape[1::-1]) != tuple(self.manifest["image_size"]):
            raise ValueError(f"Camera resolution {image.shape[1::-1]} differs from requested {self.manifest['image_size']}")

    def confirm_preview(self):
        self.manifest["camera"]["identity_confirmation"] = "user_preview"
        self.manifest["status"] = "collecting"
        self._persist()

    def save(self, image, *, frame_id: int) -> dict:
        if self.manifest["camera"]["identity_confirmation"] != "user_preview":
            raise ValueError("Please confirm the Beast camera preview first (C)")
        self.validate_frame(image)
        corners = detect_checkerboard(image, tuple(self.manifest["target"]["inner_corners"]))
        if corners is None:
            raise ValueError("Full checkerboard not detected; hold still, keep all edges visible")
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("PNG encoding failed")
        payload = encoded.tobytes()
        digest = hashlib.sha256(payload).hexdigest()
        if any(row["sha256"] == digest for row in self.manifest["images"]):
            raise ValueError("Exact duplicate image; change board position or tilt")
        filename = f"view-{len(self.manifest['images']) + 1:03d}.png"
        with (self.directory / filename).open("xb") as stream:
            stream.write(payload)
        row = {"image_path": filename, "sha256": digest, "frame_id": frame_id,
               "saved_at_utc": datetime.now(timezone.utc).isoformat(),
               "inner_corners_detected": len(corners)}
        self.manifest["images"].append(row)
        self._persist()
        return row

    def close(self, status: str):
        self.manifest["status"] = status
        self._persist()


def calibrate_views(views: list[np.ndarray], image_size: tuple[int, int],
                    pattern_size: tuple[int, int], square_mm: float) -> dict:
    width, height = validate_size(image_size)
    objects = checkerboard_object_points(*pattern_size, square_mm)
    if len(views) < 15:
        raise ValueError("At least 15 usable distinct views required (12 fit, 3 hold-out minimum)")
    points = []
    seen = set()
    for view in views:
        array = np.asarray(view, np.float32)
        if (array.shape != (len(objects), 2) or not np.isfinite(array).all()
                or (array < 0).any() or (array[:, 0] >= width).any() or (array[:, 1] >= height).any()):
            raise ValueError("Invalid/non-finite or out-of-image corner coordinates")
        digest = hashlib.sha256(array.tobytes()).hexdigest()
        if digest in seen:
            raise ValueError("Exact duplicate corner views cannot calibrate a camera")
        seen.add(digest)
        points.append(array)
    fit_indices = [i for i in range(len(points)) if i % 5 != 4]
    holdout_indices = [i for i in range(len(points)) if i % 5 == 4]
    fit_rms, matrix, distortion, rotations, translations = cv2.calibrateCamera(
        [objects] * len(fit_indices), [points[i] for i in fit_indices], (width, height), None, None)
    if (not np.isfinite(fit_rms) or not np.isfinite(matrix).all() or not np.isfinite(distortion).all()
            or matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or not 0 <= matrix[0, 2] < width
            or not 0 <= matrix[1, 2] < height):
        raise ValueError("Calibration returned invalid intrinsics; recapture varied tilted views")
    pose_by_index = dict(zip(fit_indices, zip(rotations, translations)))
    reports, holdout_squared, normals, areas = [], [], [], []
    for i, observed in enumerate(points):
        if i in pose_by_index:
            rotation, translation = pose_by_index[i]
        else:
            success, rotation, translation = cv2.solvePnP(objects, observed, matrix, distortion)
            if not success:
                raise ValueError(f"Could not fit held-out pose for view {i}")
        projected, _ = cv2.projectPoints(objects, rotation, translation, matrix, distortion)
        squared = np.sum((projected.reshape(-1, 2) - observed) ** 2, axis=1)
        if not np.isfinite(squared).all() or not np.isfinite(translation).all() or translation[2, 0] <= 0:
            raise ValueError(f"Invalid pose or projection for view {i}")
        if i in holdout_indices:
            holdout_squared.extend(squared.tolist())
        normal = cv2.Rodrigues(rotation)[0][:, 2]
        normals.append(normal)
        columns, _ = pattern_size
        areas.append(abs(cv2.contourArea(observed[[0, columns - 1, -1, -columns]])))
        reports.append({"view_index": i, "split": "fit" if i in fit_indices else "holdout",
                        "rms_px": float(np.sqrt(squared.mean()))})
    centers = np.array([view.mean(axis=0) for view in points]) / [width, height]
    span = np.ptp(centers, axis=0)
    normal_spread = max(math.degrees(math.acos(float(np.clip(abs(np.dot(a, b)), 0, 1))))
                        for a in normals for b in normals)
    area_ratio = max(areas) / max(min(areas), 1e-9)
    warnings = []
    if min(span) < .2:
        warnings.append("Limited view-center coverage; capture views near different image edges")
    if normal_spread < 15:
        warnings.append("Limited board tilt diversity; collect visibly different tilts")
    if area_ratio < 1.5:
        warnings.append("Limited distance/scale diversity; collect near and far views")
    return {
        "schema_version": "beast_camera_intrinsics_candidate_v1", "status": "candidate",
        "display_alignment_verified": False, "image_size": [width, height],
        "camera_matrix": matrix.tolist(), "distortion_coefficients": distortion.reshape(-1).tolist(),
        "distortion_model": "opencv_pinhole_k1_k2_p1_p2_k3", "square_mm": square_mm,
        "fit_indices": fit_indices, "holdout_indices": holdout_indices,
        "fit_rms_px": float(fit_rms), "holdout_rms_px": float(np.sqrt(np.mean(holdout_squared))),
        "per_view": reports,
        "coverage": {"center_span_fraction": span.tolist(), "area_ratio": area_ratio,
                     "max_normal_difference_degrees": normal_spread},
        "warnings": warnings,
        "validation_scope": "Held-out K/distortion; each held-out pose is fitted from its own corners. Not physical mm or eye alignment validation.",
    }


def solve_session(directory: Path) -> Path:
    directory = directory.resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA or manifest["camera"]["identity_confirmation"] != "user_preview":
        raise ValueError("Not a confirmed camera calibration capture")
    pattern = tuple(manifest["target"]["inner_corners"])
    size = validate_size(manifest["image_size"])
    square_mm = manifest["target"]["square_mm"]
    checkerboard_object_points(*pattern, square_mm)
    token = stamp()
    report = {"status": "analysing", "accepted_images": [], "rejected_images": []}
    views, hashes = [], set()
    for row in manifest["images"]:
        name = row.get("image_path", "")
        try:
            path = (directory / name).resolve()
            if not path.is_relative_to(directory) or path == directory:
                raise ValueError("Image path outside capture directory")
            payload = path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if digest != row.get("sha256"):
                raise ValueError("Image hash mismatch")
            if digest in hashes:
                raise ValueError("Duplicate image hash")
            image = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Unreadable image")
            if image.shape[1::-1] != size:
                raise ValueError("Mixed image resolution")
            corners = detect_checkerboard(image, pattern)
            if corners is None:
                raise ValueError("Full checkerboard not detected")
            views.append(corners)
            hashes.add(digest)
            report["accepted_images"].append({"image_path": name, "sha256": digest})
        except (OSError, ValueError, cv2.error) as exc:
            report["rejected_images"].append({"image_path": name, "reason": str(exc)})
    try:
        candidate = calibrate_views(views, size, pattern, square_mm)
        candidate.update({"profile_id": "beast-camera-" + token, "source_capture": str(directory),
                          "camera": manifest["camera"], "target": manifest["target"],
                          "opencv_version": cv2.__version__, "images": report["accepted_images"],
                          "rejected_images": report["rejected_images"]})
        path = directory / ("candidate-" + token + ".json")
        write_json(path, candidate)
        report.update({"status": "candidate", "candidate_file": path.name})
    except (ValueError, cv2.error) as exc:
        report.update({"status": "failed", "reason": str(exc)})
        raise ValueError(str(exc)) from exc
    finally:
        write_json(directory / ("analysis-" + token + ".json"), report)
    return path


def device_inventory() -> dict:
    from server.realtime.beast_device_check import inspect_devices, read_windows_devices
    try:
        return inspect_devices(read_windows_devices())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"scope": "unavailable", "error": str(exc)}


def capture(args) -> Path:
    inventory = device_inventory()
    camera = cv2.VideoCapture(args.camera_index, {"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}[args.backend])
    session = None
    status = "cancelled"
    try:
        if not camera.isOpened():
            raise RuntimeError(f"Cannot open camera index {args.camera_index}")
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        session = CaptureSession(args.out_root, camera_index=args.camera_index, backend=args.backend,
                                 image_size=(args.width, args.height), pattern_size=(args.columns, args.rows),
                                 square_mm=args.square_mm, inventory=inventory)
        session.manifest["camera"].update({"fps_property": camera.get(cv2.CAP_PROP_FPS),
                                          "fourcc_property": camera.get(cv2.CAP_PROP_FOURCC)})
        session._persist()
        print(f"[SESSION] {session.directory}", flush=True)
        print("[KEYS] C confirms Beast preview; SPACE saves a view; Q/Esc finishes. No automatic photo saving.", flush=True)
        cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW, 1120, 700)
        start, failures, frame_id = time.monotonic(), 0, 0
        message = "Confirm Beast camera preview with C"
        while time.monotonic() - start < args.duration_seconds:
            ok, frame = camera.read()
            if not ok or frame is None:
                failures += 1
                if failures >= 10:
                    raise RuntimeError("Camera read failed 10 times; check connection or another camera app")
                if cv2.waitKey(50) & 0xFF in (ord("q"), 27):
                    break
                continue
            failures = 0
            frame_id += 1
            session.validate_frame(frame)
            preview = cv2.copyMakeBorder(frame, 65, 0, 0, 0, cv2.BORDER_CONSTANT, value=(20, 20, 20))
            count = len(session.manifest["images"])
            cv2.putText(preview, f"Saved {count}/{args.max_views} | {message}", (15, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, .55, (220, 240, 220), 1, cv2.LINE_AA)
            cv2.putText(preview, "9 x 6 inner corners | Change tilt / distance / position between views", (15, 51),
                        cv2.FONT_HERSHEY_SIMPLEX, .5, (190, 190, 190), 1, cv2.LINE_AA)
            cv2.imshow(WINDOW, preview)
            key = cv2.waitKey(20) & 0xFF
            if key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key in (ord("c"), ord("C")):
                session.confirm_preview()
                message = "Confirmed | Hold still, then SPACE"
                print("[CONFIRMED] User identified the Beast preview", flush=True)
            elif key == 32:
                try:
                    row = session.save(frame, frame_id=frame_id)
                    message = f"Saved {row['image_path']} | Change angle before next view"
                    print(f"[SAVED] {len(session.manifest['images'])}/{args.max_views} {row['image_path']}", flush=True)
                except ValueError as exc:
                    message = str(exc)
                    print(f"[NOT SAVED] {message}", flush=True)
            if len(session.manifest["images"]) >= args.max_views:
                break
        status = "captured" if len(session.manifest["images"]) >= 15 else "insufficient_views"
        print(f"[DONE] {status}: {len(session.manifest['images'])} views. Solve separately; no live profile changed.", flush=True)
        return session.directory
    except BaseException:
        status = "interrupted_or_failed"
        raise
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if session is not None:
            session.close(status)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    live = commands.add_parser("capture")
    live.add_argument("--camera-index", type=int, required=True)
    live.add_argument("--backend", choices=("dshow", "msmf"), default="dshow")
    live.add_argument("--width", type=int, default=1280)
    live.add_argument("--height", type=int, default=720)
    live.add_argument("--columns", type=int, default=9)
    live.add_argument("--rows", type=int, default=6)
    live.add_argument("--square-mm", type=float, required=True, help="Measured side length, not an assumed printer scale")
    live.add_argument("--max-views", type=int, default=25)
    live.add_argument("--duration-seconds", type=float, default=900.)
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "ARAssembly/beast-mvp/camera_calibration"
    live.add_argument("--out-root", type=Path, default=root)
    offline = commands.add_parser("solve")
    offline.add_argument("--session", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "capture":
        checkerboard_object_points(args.columns, args.rows, args.square_mm)
        validate_size((args.width, args.height))
        if args.camera_index < 0 or not 15 <= args.max_views <= 100 or not 0 < args.duration_seconds <= 3600:
            parser.error("Use nonnegative camera index, 15-100 views and 0 < duration <= 3600 seconds")
    return args


def main() -> int:
    args = parse_args()
    try:
        path = capture(args) if args.command == "capture" else solve_session(args.session)
        print(f"[OUTPUT] {path}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, cv2.error) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
