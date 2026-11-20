"""Camera-only review of three saved frames. No camera, fitting or profile writes."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


# Unmarked 1280x720 photos; B/C are estimated upper hole centers, not screw heads.
# A/D use the prior visual labels from the same photos, not independent repeats.
LABELS = {
    15: [(434, 404), (592, 393), (426, 517), (610, 500)],
    51: [(430, 423), (588, 416), (437, 538), (623, 523)],
    99: [(467, 458), (620, 441), (481, 570), (660, 544)],
}


def read(path):
    return json.loads(Path(path).read_bytes())


def main(config, capture, out):
    from server.realtime.workspace_projection import CameraModel

    active, session = read(config), read(capture / "session.json")
    camera_file = Path(active["camera_profile"])
    workspace_file = Path(active["workspace_profile"])
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(camera_file) == session["camera_profile_sha256"]
    active_workspace = read(workspace_file)
    assert active_workspace["marker_centers_mm"] == session["workspace_profile"]["marker_centers_mm"]
    camera = CameraModel.from_profile(read(camera_file))
    sheet = np.full((490, 752, 3), 246, np.uint8)
    black = (32, 32, 32)
    def title(s, x, y, size=.52):
        cv2.putText(sheet, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, black, 1, cv2.LINE_AA)
    title("Camera pixels only | cross: visual estimate   ring: active projection", 10, 22)
    for j, s in enumerate(("A / head", "B / hole", "C / hole", "D / head")):
        title(s, 112 + 163*j, 55)
    rows = []
    for i, (frame, labels) in enumerate(LABELS.items()):
        folder = capture / f"frame-{frame:06d}"
        pose = read(folder / "report.json")
        assert pose["frame_id"] == frame and pose["status"] == "tracking"
        def project(workspace):
            targets = np.array([workspace["targets_mm"][k] for k in "ABCD"], dtype=float)
            return cv2.projectPoints(targets, np.asarray(pose["rvec"]), np.asarray(pose["tvec_mm"]),
                                     camera.matrix, camera.distortion)[0].reshape(4, 2)
        np.testing.assert_allclose(project(session["workspace_profile"]),
                                   [pose["targets"][k]["pixel"] for k in "ABCD"], atol=1e-6, rtol=0)
        projected = project(active_workspace)
        raw = folder / "raw.png"
        image = cv2.imdecode(np.frombuffer(raw.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        assert image.shape[:2] == (720, 1280)
        title(f"#{frame}", 10, 120 + i*143)
        for j, (key, xy, uv) in enumerate(zip("ABCD", labels, projected)):
            dx, dy = uv - xy
            rows.append(dict(frame=frame, raw_sha256=sha(raw), target=key, visual_px=xy,
                             active_px=uv.tolist(), dx=float(dx), dy=float(dy), distance=float(np.hypot(dx,dy))))
            x,y = xy
            patch = cv2.resize(image[y-18:y+19,x-22:x+23], (135,111), interpolation=cv2.INTER_NEAREST)
            center = (67, 55)
            p = tuple(np.round(center + 3*(uv-xy)).astype(int))
            cv2.circle(patch, p, 8, (255,225,25), 1, cv2.LINE_AA)
            cv2.drawMarker(patch, center, (40,180,255), cv2.MARKER_CROSS, 11, 1)
            x0,y0 = 100+j*163, 66+i*143
            sheet[y0:y0+111,x0:x0+135] = patch
            title(f"dx {dx:+.1f}   dy {dy:+.1f}", x0, y0+129, .41)
    metrics = {k: np.round(np.mean([[r["dx"], r["dy"], r["distance"]] for r in rows if r["target"]==k],axis=0),2).tolist() for k in "ABCD"}
    report = dict(source=str(capture), camera_sha256=sha(camera_file), active_workspace_sha256=sha(workspace_file),
                  saved_workspace_sha256=session["workspace_profile_sha256"], units="camera pixels, +y down",
                  label_caveat="Visual estimates, about +/-5px per axis; B/C empty hole rim estimates are less certain. Not eye coordinates or depth.",
                  rows=rows, mean_dx_dy_distance=metrics)
    (out / "camera-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ok, encoded = cv2.imencode(".png", sheet)
    assert ok
    (out / "camera-check.png").write_bytes(encoded.tobytes())
    print(json.dumps(metrics))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    main(args.config, args.capture, Path(__file__).resolve().parent)
