"""Create an isolated A trial profile and replay the three user-labelled photos."""
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from server.realtime.camera_calibration import write_json
from server.realtime.workspace_live_preview import analyze_frame, load_profiles

ROOT = Path(__file__).resolve().parent
PROFILE = Path('C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp')
CAMERA = PROFILE / 'camera_calibration/combined-review-20260927T065914Z-89414bbe/candidate.json'
WORKSPACE = PROFILE / 'workspace_registration/comfort-layout-20261006-v1/workspace-candidate.json'
LABELS = ROOT / 'user-check/run-20261031T003934-ef35c3bc/observations.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result_path = ROOT / 'results/analysis.json'
    result = json.loads(result_path.read_bytes())
    labels = json.loads(LABELS.read_bytes())
    assert labels['status'] == 'completed'
    assert len(labels['observations']) == 3
    for path in (CAMERA, WORKSPACE):
        assert digest(path) == result['input_sha256'][str(path)]
    original = json.loads(WORKSPACE.read_bytes())
    candidate = copy.deepcopy(original)
    assert original['targets_mm']['A'] == result['original_A_mm']
    assert result['hypothesis_A_mm'][2] == 60
    candidate['targets_mm']['A'] = result['hypothesis_A_mm']
    candidate['profile_id'] += '-A-trial-20261031'
    candidate['status'] = 'A_camera_projection_trial_only'
    candidate['target_adjustment'] = {
        'target': 'A', 'parent_profile_path': str(WORKSPACE),
        'parent_profile_sha256': digest(WORKSPACE),
        'frozen_fit_result': str(result_path), 'frozen_fit_sha256': digest(result_path),
        'user_labels': str(LABELS), 'user_labels_sha256': digest(LABELS),
        'original_A_mm': original['targets_mm']['A'],
        'validation': 'Three user-labelled saved photos; no refit, no eye alignment validation',
        'display_binding': 'New workspace ID/hash; existing SBS binding must not be rewritten',
    }
    assert candidate['activation_status'] == 'not_activated'
    assert not candidate['display_alignment_verified']
    assert not candidate['physical_accuracy_verified']
    for key in original:
        if key not in ('targets_mm', 'profile_id', 'status'):
            assert candidate[key] == original[key]
    for target in 'BCD':
        assert candidate['targets_mm'][target] == original['targets_mm'][target]
    output = ROOT / 'camera-trial'
    output.mkdir(exist_ok=False)
    trial = output / 'workspace-A-candidate.json'
    write_json(trial, candidate)
    camera, old, _ = load_profiles(CAMERA, WORKSPACE)
    _, new, _ = load_profiles(CAMERA, trial)
    rows = []
    for entry in labels['observations']:
        assert entry['status'] == 'confirmed'
        source = Path(entry['source'])
        assert digest(source) == entry['source_sha256']
        image = cv2.imdecode(np.frombuffer(source.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        before = analyze_frame(image, camera, old)
        after = analyze_frame(image, camera, new)
        assert before['status'] == after['status'] == 'tracking'
        np.testing.assert_array_equal(before['rvec'], after['rvec'])
        np.testing.assert_array_equal(before['tvec_mm'], after['tvec_mm'])
        for target in 'BCD':
            assert before['targets'][target] == after['targets'][target]
        point = np.array(entry['raw_pixel'])
        rows.append({
            'source': str(source), 'user_pixel': point.tolist(),
            'before_px': before['targets']['A']['pixel'],
            'candidate_px': after['targets']['A']['pixel'],
            'before_distance_px': float(np.linalg.norm(before['targets']['A']['pixel'] - point)),
            'candidate_distance_px': float(np.linalg.norm(after['targets']['A']['pixel'] - point)),
        })
    for path in (CAMERA, WORKSPACE):
        assert digest(path) == result['input_sha256'][str(path)]
    report = dict(activation_status='not_activated', candidate_path=str(trial),
                  candidate_sha256=digest(trial), user_comparison=rows,
                  checks=['source_hashes', 'profiles_unchanged', 'A_only_geometry_change',
                          'new_profile_id', 'same_marker_pose', 'BCD_unchanged', 'camera_access_forbidden'])
    write_json(output / 'preflight.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    with patch.object(cv2, 'VideoCapture', side_effect=AssertionError('Offline only')):
        main()
