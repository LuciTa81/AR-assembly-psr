"""Inspect a saved camera image against a measured workspace; no runtime activation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from server.vision.calibrate_marker_layout_v2 import detect_markers
from .camera_calibration import stamp, write_json
from .workspace_projection import CameraModel, MetricWorkspace, WorkspacePose, estimate_pose, project_targets, pixel_to_plane


def local_root() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "ARAssembly/beast-mvp/workspace_registration"


def inspect_image(image_path: Path, camera_profile_path: Path, workspace_path: Path,
                  output_root: Path) -> Path:
    paths = [Path(p) for p in (image_path, camera_profile_path, workspace_path)]
    raw, camera_bytes, workspace_bytes = [p.read_bytes() for p in paths]
    camera_data = json.loads(camera_bytes)
    workspace_data = json.loads(workspace_bytes)
    camera = CameraModel.from_profile(camera_data)
    workspace = MetricWorkspace.from_dict(workspace_data)
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None or tuple(image.shape[1::-1]) != camera.image_size:
        raise ValueError("Image cannot decode or resolution differs from camera profile")

    mapping, corners, ids = detect_markers(image, 1.0)
    report = {
        "schema_version": "beast_workspace_inspection_v1",
        "scope": "offline_camera_projection_only",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_image": str(paths[0].resolve()), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "camera_profile_id": camera.profile_id,
        "camera_profile_sha256": hashlib.sha256(camera_bytes).hexdigest(),
        "workspace_profile_id": workspace.profile_id,
        "workspace_profile_sha256": hashlib.sha256(workspace_bytes).hexdigest(),
        "image_size": list(camera.image_size), "opencv_version": cv2.__version__,
        "detected_ids": sorted(mapping),
        "marker_corners_raw_px": {str(key): value.tolist() for key, value in mapping.items()},
        "target_registration": "provided_not_physically_verified" if workspace.targets else "not_registered",
        "activation_status": "not_activated", "display_alignment_verified": False,
        "physical_accuracy_verified": False, "pose": None, "targets": {},
        "diagnostic_limits": {"rms_undistorted_px": 3., "max_error_undistorted_px": 5.,
                              "ambiguity_gap_px": .25},
    }
    visual = image.copy()
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(visual, corners, ids)
    try:
        known_ids = [int(key) for key in ids.flatten() if int(key) in workspace.markers] if ids is not None else []
        if len(known_ids) != len(set(known_ids)):
            raise ValueError("duplicate known marker ID in image")
        pose = estimate_pose(mapping, workspace, camera, image.shape[1::-1])
        report["status"] = "pose_estimated"
        report["reason"] = ""
        report["pose"] = {
            "rvec": pose.rvec.reshape(3).tolist(), "tvec_mm": pose.tvec.reshape(3).tolist(),
            "camera_position_workspace_mm": pose.camera_position_mm.tolist(),
            "marker_ids": pose.marker_ids,
            "observed_centers_undistorted_px": pose.observed_centers_px.tolist(),
            "projected_centers_undistorted_px": pose.projected_centers_px.tolist(),
            "rms_undistorted_px": pose.rms_px, "max_error_undistorted_px": pose.max_error_px,
        }
        report["targets"] = project_targets(pose, workspace, camera)
        centers = np.array([workspace.markers[key] for key in pose.marker_ids])
        projected = cv2.projectPoints(centers, pose.rvec, pose.tvec, camera.matrix, camera.distortion)[0].reshape(-1, 2)
        for pixel in projected:
            if np.isfinite(pixel).all():
                cv2.drawMarker(visual, tuple(np.rint(pixel).astype(int)), (0, 220, 255), cv2.MARKER_CROSS, 14, 2)
        for name, target in report["targets"].items():
            if target["visible"]:
                point = tuple(np.rint(target["pixel"]).astype(int))
                cv2.circle(visual, point, 12, (30, 230, 30), 2)
                cv2.putText(visual, name, (point[0] + 15, point[1]), cv2.FONT_HERSHEY_SIMPLEX, .7, (30, 230, 30), 2)
        message = f"CAMERA POSE: RMS {pose.rms_px:.2f}px | " + ("TARGETS PROVIDED" if workspace.targets else "TARGETS NOT REGISTERED")
    except ValueError as exc:
        report["status"] = "pose_rejected"
        report["reason"] = str(exc)
        message = "POSE REJECTED: " + str(exc)
    cv2.rectangle(visual, (0, 0), (image.shape[1], 42), (0, 0, 0), -1)
    cv2.putText(visual, message, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1)

    directory = Path(output_root) / ("projection-" + stamp())
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "camera-profile.json", camera_data)
    write_json(directory / "workspace-profile.json", workspace_data)
    ok, encoded = cv2.imencode(".png", visual)
    if not ok:
        raise RuntimeError("Diagnostic PNG encoding failed")
    with (directory / "diagnostic.png").open("xb") as stream:
        stream.write(encoded.tobytes())
    write_json(directory / "report.json", report)
    return directory



def register_target_points(clicks: dict, pick_height_mm: float, target_height_mm: float,
                           pose: WorkspacePose, camera: CameraModel, *,
                           square_mm=110., tolerance_mm=10.) -> dict:
    if set(clicks) != set("ABCD"):
        raise ValueError("Click exactly A, B, C, D")
    numbers = np.array([pick_height_mm, target_height_mm, square_mm, tolerance_mm], float)
    if not np.isfinite(numbers).all() or (numbers[:2] < 0).any() or (numbers[2:] <= 0).any():
        raise ValueError("Heights and measured square dimensions must be finite and valid")
    points = {name: pixel_to_plane(clicks[name], pick_height_mm, pose, camera) for name in "ABCD"}
    if not (max(points["A"][0], points["C"][0]) < min(points["B"][0], points["D"][0])
            and min(points["A"][1], points["B"][1]) > max(points["C"][1], points["D"][1])):
        raise ValueError("Target labels must match workspace left/right and far/near rows")
    polygon = np.array([points[name][:2] for name in "ABDC"], np.float32)
    if not cv2.isContourConvex(polygon) or cv2.contourArea(polygon, oriented=True) >= 0:
        raise ValueError("Target order must be A far-left, B far-right, C near-left, D near-right")
    for first, second, expected in [("A", "B", square_mm), ("B", "D", square_mm),
                                    ("D", "C", square_mm), ("C", "A", square_mm),
                                    ("A", "D", square_mm * np.sqrt(2)), ("B", "C", square_mm * np.sqrt(2))]:
        measured = np.linalg.norm(points[first][:2] - points[second][:2])
        if abs(measured - expected) > tolerance_mm:
            raise ValueError(f"Clicked square disagrees with measured spacing: {first}-{second}={measured:.1f}mm")
    # Retain observed XY instead of forcing a perfect square and hiding discrepancies.
    return {name: [float(point[0]), float(point[1]), float(target_height_mm)] for name, point in points.items()}


def collect_target_clicks(image: np.ndarray) -> dict | None:
    window = "Beast screw registration | A B C D | Enter: confirm | Backspace: undo | Q: cancel"
    names = ["A", "B", "C", "D"]
    locations = ["far-left", "far-right", "near-left", "near-right"]
    points = []
    height, width = image.shape[:2]

    def clicked(event, x, y, _flags, _data):
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4 and 0 <= x < width and 0 <= y < height:
            points.append([x, y])
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    try:
        cv2.setMouseCallback(window, clicked)
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            visual = image.copy()
            for index, point in enumerate(points):
                cv2.circle(visual, tuple(point), 10, (0, 230, 255), 2)
                cv2.putText(visual, names[index], (point[0] + 12, point[1]), cv2.FONT_HERSHEY_SIMPLEX, .65, (0, 230, 255), 2)
            message = f"Select {names[len(points)]}: {locations[len(points)]}" if len(points) < 4 else "A B C D selected"
            cv2.rectangle(visual, (0, 0), (width, 40), (0, 0, 0), -1)
            cv2.putText(visual, message, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, .7, (255, 255, 255), 1)
            cv2.imshow(window, visual)
            key = cv2.waitKey(30) & 0xFF
            if key in (ord("q"), 27):
                return None
            if key == 13 and len(points) == 4:
                return dict(zip(names, points))
            if key in (8, 127) and points:
                points.pop()
            if key == ord("r"):
                points.clear()
            if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1:
                return None
        return None
    finally:
        try:
            cv2.destroyWindow(window)
        except cv2.error:
            pass


def pick_workspace_targets(image_path: Path, camera_profile_path: Path, workspace_path: Path,
                           output_root: Path, *, pick_height_mm: float, target_height_mm: float) -> Path | None:
    heights = np.array([pick_height_mm, target_height_mm], float)
    if not np.isfinite(heights).all() or (heights < 0).any():
        raise ValueError("Explicit finite, nonnegative head and target heights are required")
    directory = inspect_image(image_path, camera_profile_path, workspace_path, output_root)
    report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    if report["pose"] is None:
        raise ValueError(report["reason"])
    source = Path(image_path).read_bytes()
    if hashlib.sha256(source).hexdigest() != report["source_sha256"]:
        raise ValueError("Source image changed after pose estimation")
    image = cv2.imdecode(np.frombuffer(source, np.uint8), cv2.IMREAD_COLOR)
    camera = CameraModel.from_profile(json.loads((directory / "camera-profile.json").read_text(encoding="utf-8")))
    data = json.loads((directory / "workspace-profile.json").read_text(encoding="utf-8"))
    p = report["pose"]
    pose = WorkspacePose(np.array(p["rvec"]).reshape(3, 1), np.array(p["tvec_mm"]).reshape(3, 1),
                         np.array(p["camera_position_workspace_mm"]), p["marker_ids"],
                         np.array(p["observed_centers_undistorted_px"]), np.array(p["projected_centers_undistorted_px"]),
                         p["rms_undistorted_px"], p["max_error_undistorted_px"])
    clicks = collect_target_clicks(image)
    if clicks is None:
        return None
    data["targets_mm"] = register_target_points(clicks, pick_height_mm, target_height_mm, pose, camera)
    data["profile_id"] += "-targets-" + stamp()
    data["status"] = "target_candidate_pending_validation"
    data["activation_status"] = "not_activated"
    data["display_alignment_verified"] = False
    data["target_registration"] = {
        "method": "user_clicks_intersect_measured_height_plane",
        "source_image": report["source_image"], "source_image_sha256": report["source_sha256"],
        "clicks_raw_px": clicks, "picked_head_height_mm": pick_height_mm, "target_height_mm": target_height_mm,
        "expected_square_mm": 110., "spacing_tolerance_mm": 10.,
        "camera_profile_id": camera.profile_id, "camera_profile_sha256": report["camera_profile_sha256"],
        "marker_layout_sha256": report["workspace_profile_sha256"],
        "validation": "Spacing sanity check only; held-out physical target checks and eye alignment remain pending",
    }
    candidate = directory / "target-candidate.json"
    write_json(candidate, data)
    return candidate



def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline metric workspace pose inspection; never activates runtime/Unity.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--camera-profile", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--out-root", type=Path)
    parser.add_argument("--pick-targets", action="store_true")
    parser.add_argument("--pick-height-mm", type=float)
    parser.add_argument("--target-height-mm", type=float)
    args = parser.parse_args(argv)
    try:
        if args.pick_targets:
            if args.pick_height_mm is None or args.target_height_mm is None:
                raise ValueError("--pick-targets requires --pick-height-mm and --target-height-mm")
            candidate = pick_workspace_targets(args.image, args.camera_profile, args.workspace,
                                               args.out_root or local_root(), pick_height_mm=args.pick_height_mm,
                                               target_height_mm=args.target_height_mm)
            print(json.dumps({"status": "candidate_saved" if candidate else "cancelled",
                              "candidate": str(candidate.resolve()) if candidate else None}, indent=2))
            return 0 if candidate else 1
        directory = inspect_image(args.image, args.camera_profile, args.workspace, args.out_root or local_root())
        report = json.loads((directory / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, cv2.error) as exc:
        print(f"[ERROR] {exc}")
        return 2
    print(json.dumps({"directory": str(directory.resolve()), "status": report["status"],
                      "reason": report["reason"], "pose": report["pose"],
                      "target_registration": report["target_registration"]}, indent=2))
    return 0 if report["status"] == "pose_estimated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
