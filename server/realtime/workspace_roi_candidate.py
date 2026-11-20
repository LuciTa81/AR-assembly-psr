"""Saved-image metric surface ROI inspection; never activates recognition or a camera."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from .camera_calibration import write_json
from .workspace_live_preview import analyze_frame, load_profiles
from .workspace_projection import finite_array


def _bilinear(quad, u, v):
    return ((1-u)*(1-v))[..., None]*quad[0] + (u*(1-v))[..., None]*quad[1] + \
           (u*v)[..., None]*quad[2] + ((1-u)*v)[..., None]*quad[3]


def roi_quads(workspace, screw_side_mm=18.):
    if not np.isfinite(screw_side_mm) or not 1 <= screw_side_mm <= 40:
        raise ValueError('Screw inspection side must be 1-40 mm')
    if set(workspace.targets) != set('ABCD'):
        raise ValueError('Registered A-D targets required')
    perimeter = finite_array([workspace.targets[k] for k in 'ABDC'], (4, 3), 'lid perimeter')
    if (perimeter[0, 2] <= 0 or np.ptp(perimeter[:, 2]) > .1
            or not cv2.isContourConvex(perimeter[:, :2].astype(np.float32))
            or abs(cv2.contourArea(perimeter[:, :2].astype(np.float32))) < 100):
        raise ValueError('Targets must describe a convex, level lid surface above the mat')
    offsets = np.array([[-1, 1, 0], [1, 1, 0], [1, -1, 0], [-1, -1, 0]]) * screw_side_mm/2
    regions = {'screw_' + name.lower(): workspace.targets[name] + offsets for name in 'ABCD'}
    uv = np.array([[.1, .1], [.9, .1], [.9, .9], [.1, .9]])
    regions['lid_surface'] = _bilinear(perimeter, uv[:, 0], uv[:, 1])
    return regions


def region_definition(workspace):
    return dict(screw_side_mm=18., lid_inset_fraction=.1,
                regions_mm={name: quad.tolist() for name, quad in roi_quads(workspace).items()})


def sample_region(image, camera, state, quad, size=64, *, make_crop=True):
    result = dict(valid=False, reason='', corners_raw_px=[], boundary_raw_px=[], center_raw_px=None)
    if state.get('status') != 'tracking':
        result['reason'] = state.get('reason') or state.get('status', 'Missing pose')
        return result, None
    try:
        if image is None or image.shape[:2][::-1] != camera.image_size:
            raise ValueError('Image resolution differs from camera calibration')
        if type(size) is not int or not 2 <= size <= 256:
            raise ValueError('Inspection crop size must be 2-256 pixels')
        quad = finite_array(quad, (4, 3), 'region quad')
        rvec = finite_array(state.get('rvec'), (3,), 'rvec')
        tvec = finite_array(state.get('tvec_mm'), (3,), 'tvec_mm')
        u, v = np.meshgrid(np.linspace(0, 1, size), np.linspace(0, 1, size))
        world = _bilinear(quad, u, v).reshape(-1, 3)
        if ((cv2.Rodrigues(rvec)[0] @ world.T + tvec[:, None])[2] <= 0).any():
            raise ValueError('Region behind camera')
        pixels = cv2.projectPoints(world, rvec, tvec, camera.matrix, camera.distortion)[0].reshape(size, size, 2)
        if (not np.isfinite(pixels).all() or (pixels < 0).any()
                or (pixels > np.array(camera.image_size)-1).any()):
            raise ValueError('Region is not fully inside the calibrated image')
        corners = pixels[[0, 0, -1, -1], [0, -1, -1, 0]]
        indices = np.unique(np.linspace(0, size-1, 9).astype(int))
        boundary = np.concatenate([pixels[0, indices], pixels[indices, -1],
                                   pixels[-1, indices[::-1]], pixels[indices[::-1], 0]])
        center = cv2.projectPoints(quad.mean(axis=0), rvec, tvec, camera.matrix,
                                  camera.distortion)[0].reshape(2)
        # Direct world-grid sampling preserves lid height and lens distortion.
        crop = None
        if make_crop:
            crop = cv2.remap(image, pixels[:, :, 0].astype(np.float32), pixels[:, :, 1].astype(np.float32),
                             cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        result.update(valid=True, corners_raw_px=corners.tolist(), boundary_raw_px=boundary.tolist(),
                      center_raw_px=center.tolist())
        return result, crop
    except (ValueError, cv2.error) as exc:
        result['reason'] = str(exc)
        return result, None


def project_regions(image, camera, workspace, state):
    reports = {name: sample_region(image, camera, state, quad, make_crop=False)[0]
               for name, quad in roi_quads(workspace).items()}
    valid = sum(r['valid'] for r in reports.values())
    return dict(scope='camera_projection_only', activation_status='not_activated',
                visible=bool(valid), valid_regions=valid, regions=reports)


def draw_regions(visual, reports):
    for name, report in reports.items():
        if not report['valid']:
            continue
        points = np.rint(report['boundary_raw_px']).astype(np.int32)
        color = (255, 210, 0) if name == 'lid_surface' else (50, 235, 60)
        cv2.polylines(visual, [points], True, (20, 20, 20), 4, cv2.LINE_AA)
        cv2.polylines(visual, [points], True, color, 2, cv2.LINE_AA)
        center = tuple(np.rint(report['center_raw_px']).astype(int))
        label = name[-1].upper() if name.startswith('screw_') else 'LID'
        origin = (max(0, min(center[0]+14, visual.shape[1]-50)),
                  max(55, min(center[1]-8, visual.shape[0]-8)))
        cv2.putText(visual, label, origin, cv2.FONT_HERSHEY_SIMPLEX, .6, (20, 20, 20), 4, cv2.LINE_AA)
        cv2.putText(visual, label, origin, cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2, cv2.LINE_AA)


def _save_png(path, image):
    ok, encoded = cv2.imencode('.png', image)
    if not ok:
        raise ValueError('Could not encode inspection image')
    with path.open('xb') as stream:
        stream.write(encoded.tobytes())


def inspect_images(camera_path, workspace_path, images, output, *, screw_side_mm=18., corner_refinement='subpix'):
    camera, workspace, metadata = load_profiles(camera_path, workspace_path)
    regions = roi_quads(workspace, screw_side_mm)
    if not images or corner_refinement not in ('subpix', 'apriltag'):
        raise ValueError('Saved images and a supported detector are required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    candidate = dict(schema_version='beast_saved_roi_candidate_v1', scope='offline_camera_projection_only',
        activation_status='not_activated', physical_accuracy_verified=False, display_alignment_verified=False,
        camera_profile_id=camera.profile_id, camera_profile_sha256=metadata['camera_profile_sha256'],
        workspace_profile_id=workspace.profile_id, workspace_profile_sha256=metadata['workspace_profile_sha256'],
        screw_side_mm=screw_side_mm, lid_inset_fraction=.1, inspection_crop_size=[64, 64],
        corner_refinement=corner_refinement,
        regions_mm={name: quad.tolist() for name, quad in regions.items()},
        limitations=['Provisional region dimensions, not measured screw diameters.',
                    'Inherited target registration, not independently labelled ground truth.',
                    'Old recognition templates are not compatible by assumption.',
                    'No lid/screw state inference or eye alignment validation.'])
    write_json(output / 'candidate.json', candidate)
    summary = dict(scope=candidate['scope'], activation_status='not_activated', images=[])
    for index, source in enumerate(images, 1):
        source = Path(source)
        content = source.read_bytes()
        image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2][::-1] != camera.image_size:
            raise ValueError(f'Invalid image or resolution: {source}')
        state = analyze_frame(image, camera, workspace, corner_refinement=corner_refinement)
        directory = output / f'image-{index:03d}'
        directory.mkdir(exist_ok=False)
        visual, reports = image.copy(), {}
        for name, quad in regions.items():
            report, crop = sample_region(image, camera, state, quad)
            reports[name] = report
            if crop is None:
                continue
            _save_png(directory / (name + '.png'), crop)
        draw_regions(visual, reports)
        valid = sum(r['valid'] for r in reports.values())
        cv2.rectangle(visual, (0, 0), (camera.image_size[0]-1, 38), (0, 0, 0), -1)
        cv2.putText(visual, f'OFFLINE ROI CANDIDATE | {state["status"]} | regions {valid}/5 | NOT ACTIVE',
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
        _save_png(directory / 'preview.png', visual)
        report = dict(source_path=str(source.resolve()), source_sha256=hashlib.sha256(content).hexdigest(),
                      pose=state, regions=reports, scope=candidate['scope'], activation_status='not_activated')
        write_json(directory / 'report.json', report)
        summary['images'].append(dict(directory=directory.name, source=str(source.resolve()),
                                      pose_status=state['status'], valid_regions=valid))
    write_json(output / 'summary.json', summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera-profile', required=True, type=Path)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--images', required=True, nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--screw-side-mm', type=float, default=18.)
    parser.add_argument('--corner-refinement', choices=['subpix', 'apriltag'], default='subpix')
    args = parser.parse_args(argv)
    try:
        result = inspect_images(args.camera_profile, args.workspace, args.images, args.output,
                                screw_side_mm=args.screw_side_mm, corner_refinement=args.corner_refinement)
        print(json.dumps(result), flush=True)
        return 0
    except (OSError, ValueError, KeyError, cv2.error) as exc:
        print(f'[ERROR] {exc}', flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
