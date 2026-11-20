"""Metric screw perimeter and target arrow for camera diagnostics, not eye alignment."""

from __future__ import annotations

import cv2
import numpy as np

from .workspace_projection import CameraModel, MetricWorkspace, finite_array


EDGE_COLOR = (210, 190, 70)
TARGET_COLOR = (40, 205, 255)


def world_segments(workspace: MetricWorkspace, target_id: str | None) -> list[dict]:
    if (target_id is not None and target_id not in tuple('ABCD')) or set(workspace.targets) != set('ABCD'):
        raise ValueError('Registered A-D targets and a valid target selection are required')
    segments = [dict(kind='edge', name=pair,
                     points_mm=[workspace.targets[name].tolist() for name in pair])
                for pair in ('AB', 'BD', 'DC', 'CA')]
    if target_id is None:
        return segments
    target = workspace.targets[target_id]
    tip = target + [0, 0, 8]
    segments.append(dict(kind='arrow', name='shaft', points_mm=[(target + [0, 0, 30]).tolist(), tip.tolist()]))
    # Four wings keep the world-up arrow legible from different camera directions.
    for index, offset in enumerate(([6, 0, 16], [-6, 0, 16], [0, 6, 16], [0, -6, 16])):
        segments.append(dict(kind='arrow', name=f'wing-{index}',
                             points_mm=[(target + offset).tolist(), tip.tolist()]))
    return segments


def _clipped_lines(pixels, image_size):
    rounded = np.rint(pixels).astype(np.int32)
    for first, second in zip(rounded[:-1], rounded[1:]):
        visible, start, end = cv2.clipLine((0, 0, *image_size), tuple(map(int, first)), tuple(map(int, second)))
        if visible:
            yield start, end


def project_overlay(state: dict, camera: CameraModel, workspace: MetricWorkspace, target_id: str | None) -> dict:
    geometry = world_segments(workspace, target_id)
    result = dict(scope='camera_projection_only', selection_mode='manual', target_id=target_id,
                  visible=False, target_visible=False, segments=[], targets={}, reason='')
    if state.get('status') != 'tracking':
        result['reason'] = state.get('reason') or state.get('status', 'No pose')
        return result
    try:
        rvec = finite_array(state.get('rvec'), (3,), 'rvec')
        tvec = finite_array(state.get('tvec_mm'), (3,), 'tvec_mm')
        rotation = cv2.Rodrigues(rvec)[0]

        def project(points):
            points = np.asarray(points, dtype=np.float64)
            if ((rotation @ points.T + tvec[:, None])[2] <= 0).any():
                return None
            pixels = cv2.projectPoints(points, rvec, tvec, camera.matrix, camera.distortion)[0].reshape(-1, 2)
            if not np.isfinite(pixels).all() or np.abs(pixels).max() > 1e7:
                raise ValueError('Invalid projected geometry')
            return pixels

        targets, segments = {}, []
        for name, point in workspace.targets.items():
            pixels = project([point])
            visible = pixels is not None and bool((pixels[0] >= 0).all() and (pixels[0] < camera.image_size).all())
            targets[name] = dict(visible=visible, pixel=pixels[0].tolist() if visible else None)
        target_visible = target_id is not None and targets[target_id]['visible']
        for segment in geometry:
            if segment['kind'] == 'arrow' and not target_visible:
                continue
            # Sample straight world edges to preserve lens distortion in the raw image.
            pixels = project(np.linspace(*segment['points_mm'], 9))
            if pixels is not None and any(_clipped_lines(pixels, camera.image_size)):
                segments.append(dict(kind=segment['kind'], name=segment['name'], pixels=pixels.tolist()))
        visible = bool(segments) or any(t['visible'] for t in targets.values())
        result.update(visible=visible, target_visible=target_visible, segments=segments, targets=targets,
                      reason='' if target_visible or target_id is None else 'Selected screw outside camera view')
    except (ValueError, cv2.error) as exc:
        result['reason'] = str(exc)
    return result


def draw_overlay(image: np.ndarray, overlay: dict) -> None:
    """Draw only this frame's projected primitives into the caller's image copy."""
    if not overlay['visible']:
        return
    height, width = image.shape[:2]
    for outline in (True, False):
        for segment in overlay['segments']:
            color = TARGET_COLOR if segment['kind'] == 'arrow' else EDGE_COLOR
            thickness = 3 if segment['kind'] == 'arrow' else 2
            if outline:
                color, thickness = (20, 20, 20), thickness + 2
            for start, end in _clipped_lines(segment['pixels'], (width, height)):
                cv2.line(image, start, end, color, thickness, cv2.LINE_AA)
    for name, target in overlay['targets'].items():
        if not target['visible']:
            continue
        selected = name == overlay['target_id']
        color, radius = (TARGET_COLOR, 16) if selected else (EDGE_COLOR, 10)
        point = tuple(map(int, np.rint(target['pixel'])))
        cv2.circle(image, point, radius, (20, 20, 20), 4, cv2.LINE_AA)
        cv2.circle(image, point, radius, color, 2, cv2.LINE_AA)
        x = min(point[0] + radius + 5, width - 24)
        y = max(62, min(point[1] + 5, height - 8))
        cv2.putText(image, name, (x, y), cv2.FONT_HERSHEY_SIMPLEX, .6, (20, 20, 20), 4, cv2.LINE_AA)
        cv2.putText(image, name, (x, y), cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2, cv2.LINE_AA)
