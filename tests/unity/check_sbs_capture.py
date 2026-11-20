"""Check Unity's own rendered SBS frames; never capture the desktop or camera."""

import argparse
from pathlib import Path

import cv2
import numpy as np


def check(directory, guidance=False):
    live = {}
    hidden = set()
    checked = 0
    target_regions = np.zeros((432, 1536), dtype=bool)
    regions_by_target = {}
    if guidance:
        from guidance_fixture import build_fixture
        # Restrict color checks to known synthetic targets, not colored action text.
        for snapshot in build_fixture()['snapshots']:
            spatial = snapshot.get('spatial')
            if not spatial or not spatial['target_visible']:
                continue
            region = regions_by_target.setdefault(snapshot['target'][-1], np.zeros_like(target_regions))
            for eye, key in enumerate(('left_pixel', 'right_pixel')):
                x, y = np.rint(np.array(spatial[key]) * .4).astype(int)
                x += eye * 768
                target_regions[y-14:y+15, x-14:x+15] = True
                region[y-14:y+15, x-14:x+15] = True
    else:
        target_regions[140:280, :] = True
    for path in sorted(Path(directory).glob("*.png")):
        if "SBS_" not in path.name or "WAITING_DISPLAY" in path.name or "_none" in path.name:
            continue
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert image is not None and image.shape[:2] == (432, 1536), path.name
        blue, green, red = image.astype(float).transpose(2, 0, 1)
        ready = (blue > 180) & (green > 150) & (red < green * .6)
        observed = (green > 180) & (green > red * 1.5) & (blue > 80) & (blue < green * .9)
        holding = (red > 180) & (green > 120) & (blue < green * .6)
        region = target_regions
        if guidance and '_screw_' in path.stem:
            region = regions_by_target[path.stem.split('_screw_')[1][0]]
        mask = (ready | observed | holding) & region
        assert np.count_nonzero(image.max(axis=2) > 100) > 300, f"Blank UI: {path.name}"
        if guidance and ('_box' in path.stem or '_lid' in path.stem):
            checked += 1
            continue
        guidance_live = ("_screw_" in path.stem and any(
            "SBS_GUIDANCE_" + phase + "_" in path.stem
            for phase in ("GUIDING", "OBSERVING", "OBSERVED")))
        is_live = guidance_live if guidance else "SBS_SYNTHETIC_PREVIEW" in path.name
        if is_live:
            ys, xs = np.nonzero(mask)
            left, right = xs < 768, xs >= 768
            assert left.sum() >= 20 and right.sum() >= 20, f"Missing eye ring: {path.name}"
            lx, rx = xs[left].mean(), xs[right].mean() - 768
            ly, ry = ys[left].mean(), ys[right].mean()
            # Hand-derived relation for the asymmetric R2 synthetic matrices at Z=500mm.
            expected_rx = (908.8 + 1.025 * (lx / .4 - 1008)) * .4
            expected_ry = (539.62 + 1.0125 * (ly / .4 - 540)) * .4
            assert abs(rx - expected_rx) < 2 and abs(ry - expected_ry) < 2, f"Eye mapping: {path.name}"
            assert abs(lx - rx) > 10, f"Duplicated eye coordinates: {path.name}"
            assert xs.min() > 3 and xs.max() < 1533 and not mask[:, 764:772].any(), path.name
            target = path.stem.split("_screw_")[1][0] if guidance else path.stem.rsplit("_", 1)[-1]
            live.setdefault(target, []).append((lx, ly))
        else:
            assert not mask.any(), f"Ring survived failure: {path.name}"
            for reason in ("TRACKING_LOST", "STALE_POSE", "PROFILE_MISMATCH", "INVALID_SPATIAL",
                           "DISCONNECTED", "NO_TARGET", "PAUSED", "AWAITING_CONFIRMATION"):
                if reason in path.name:
                    hidden.add(reason)
        checked += 1
    assert set(live) == set("abcd"), f"Missing targets: {set(live)}"
    if guidance:
        assert np.ptp(np.array([points[0] for points in live.values()])[:, 0]) > 5, "No target movement"
        required_hidden = {"TRACKING_LOST", "PAUSED", "AWAITING_CONFIRMATION", "DISCONNECTED"}
    else:
        assert any(np.ptp(np.array(points)[:, 0]) > 5 for points in live.values() if len(points) > 1), "No ring movement"
        required_hidden = {"TRACKING_LOST", "STALE_POSE", "PROFILE_MISMATCH", "INVALID_SPATIAL", "DISCONNECTED", "NO_TARGET"}
    assert required_hidden <= hidden, hidden
    return {"checked_frames": checked, "targets": sorted(live), "hidden_states": sorted(hidden)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--guidance", action="store_true", help="Check the R4 timed-guidance sequence")
    args = parser.parse_args()
    print(check(args.directory, args.guidance))
