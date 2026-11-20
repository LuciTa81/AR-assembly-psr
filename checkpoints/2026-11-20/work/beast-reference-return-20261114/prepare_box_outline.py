"""Offline geometric check only: read saved images, never open a camera."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.root))
    from server.realtime.workspace_live_preview import load_profiles
    from server.realtime.workspace_projection import estimate_pose

    presentation = json.loads((args.root / 'outputs/demo/presentation.json').read_text(encoding='utf-8-sig'))
    camera, workspace, metadata = load_profiles(Path(presentation['camera_profile']), Path(presentation['workspace_profile']))
    screws = np.array([workspace.targets[name] for name in 'ABCD'])
    center = screws[:, :2].mean(axis=0)
    x = screws[1, :2] - screws[0, :2] + screws[3, :2] - screws[2, :2]
    y = screws[0, :2] - screws[2, :2] + screws[1, :2] - screws[3, :2]
    u = x + np.array([y[1], -y[0]])
    u /= np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    xy = np.array([center + 62 * (sx * u + sy * v) for sx, sy in [(-1, 1), (1, 1), (1, -1), (-1, -1)]])
    vertices = np.vstack([np.column_stack([xy, np.full(4, z)]) for z in [60., 0.]])
    args.output.mkdir(parents=True, exist_ok=True)
    profile = dict(schema_version='beast_box_outline_trial_v1', candidate_only=True,
        camera_profile_sha256=metadata['camera_profile_sha256'], workspace_profile_sha256=metadata['workspace_profile_sha256'],
        vertices_mm=vertices.reshape(-1).tolist(),
        provenance=dict(exterior_mm=[124, 124, 60], measurement='User approximate square upper and bottom 124mm; prior approximate closed height 60mm',
            positioning='Center and orientation from unchanged A-D workspace points',
            assumptions=['Straight eight-corner reference; rounded corners not modeled',
                         'Top rim uses approximate 60mm plane shared with screw target; exact rim height unmeasured',
                         'Bottom square equals top per user estimate; hidden corners not directly observed'],
            activation_status='not_activated', optical_validation=False))
    (args.output / 'box-outline-124mm.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')

    # Approximate visible edge intersections, manually read from the original images.
    # These are independent image checks, not fitting targets or millimetre ground truth.
    checks = {
        1: [[583,319],[776,313],[803,469],[573,474],[791,529],[582,530]],
        49: [[655,372],[845,369],[879,532],[647,534],[866,591],[653,590]],
        145: [[594,462],[782,453],[818,619],[586,628],[810,678],[595,686]],
    }
    reports = []
    projection = json.loads((args.output.parent / 'candidate-ABCD-joint-unverified.json').read_text(encoding='utf-8-sig'))
    for frame_id, manual in checks.items():
        directory = args.saved / f'frame-{frame_id:06d}'
        record = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
        detections = {int(k): np.array(corners) for k, corners in record['detected_corners_px'].items()}
        pose = estimate_pose(detections, workspace, camera, camera.image_size)
        pixels = cv2.projectPoints(vertices, pose.rvec, pose.tvec, camera.matrix, camera.distortion)[0].reshape(-1, 2)
        image = cv2.imread(str(directory / 'raw.png'))
        if image is None or (image.shape[1], image.shape[0]) != tuple(camera.image_size):
            raise ValueError('Saved image is missing or does not match calibration')
        # Thin lower edges, stronger top rim. This is a camera-view diagnostic, not an optical capture.
        for i in range(4):
            j = (i + 1) % 4
            for p, q, color, width in [(i+4,j+4,(160,110,70),1),(i,i+4,(190,160,80),1),(i,j,(80,230,110),2)]:
                cv2.line(image, tuple(np.rint(pixels[p]).astype(int)), tuple(np.rint(pixels[q]).astype(int)), color, width, cv2.LINE_AA)
        cv2.putText(image, '124 x 124 x 60 mm | OFFLINE BOX REFERENCE', (20,30), cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2)
        path = args.output / f'camera-reference-{frame_id:06d}.png'
        if not cv2.imwrite(str(path), image):
            raise OSError('Could not save diagnostic image')
        checked = pixels[[0,1,2,3,6,7]]
        errors = np.linalg.norm(checked-np.array(manual), axis=1)
        xyz = vertices @ cv2.Rodrigues(pose.rvec)[0].T + pose.tvec.reshape(1,3)
        eyes = {}
        for eye in ['left','right']:
            homogeneous = np.column_stack([xyz,np.ones(len(xyz))]) @ np.array(projection[eye+'_projection']).reshape(3,4).T
            eyes[eye] = (homogeneous[:,:2]/homogeneous[:,2:]).tolist()
        reports.append(dict(frame_id=frame_id, source=str(directory/'raw.png'),
            source_sha256=hashlib.sha256((directory/'raw.png').read_bytes()).hexdigest(),
            pose_rms_px=pose.rms_px, rvec=pose.rvec.reshape(3).tolist(), tvec_mm=pose.tvec.reshape(3).tolist(),
            camera_xyz_mm=xyz.tolist(), camera_pixels=pixels.tolist(), eye_pixels=eyes,
            approximate_manual_edge_pixels=manual, approximate_edge_error_px=errors.tolist(),
            mean_edge_error_px=float(errors.mean()), max_edge_error_px=float(errors.max())))
    report = dict(scope='Saved camera images only; not eye alignment or exact exterior validation',
        active_workspace_hash=metadata['workspace_profile_sha256'], geometry_profile=str(args.output/'box-outline-124mm.json'),
        eye_projection=str(args.output.parent/'candidate-ABCD-joint-unverified.json'), records=reports)
    (args.output/'saved-image-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps([dict(frame=r['frame_id'],pose_rms_px=r['pose_rms_px'],mean_edge_px=r['mean_edge_error_px'],max_edge_px=r['max_edge_error_px']) for r in reports]))


if __name__ == '__main__':
    main()
