"""Camera-free regression checks for the offline comparison, not Android runtime tests."""
import json
import unittest
import numpy as np
import pose_replay_compare as replay


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
        cls.workspace = replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
        eye = json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
        cls.eye = [np.array(eye[k]).reshape(3, 4) for k in ('left_projection','right_projection')]
        cls.rows = replay.load_rows(replay.ROOT/'pose-live-device.txt')
        cls.full = next(r['detections'] for r in cls.rows if r['valid'] and r['count']==5)

    def test_identity_has_zero_delta_including_both_eyes(self):
        pose, _ = replay.baseline(self.full, self.workspace, self.camera)
        values = replay.comparison(pose, pose, self.workspace, self.camera, self.eye)
        for key in ('max_target_delta_px','max_target_delta_mm','max_eye_delta_px'):
            self.assertAlmostEqual(0., values[key])
        self.assertTrue(values['preserved'])

    def test_normal_path_is_numerically_unchanged(self):
        for row in self.rows:
            original, _ = replay.baseline(row['detections'], self.workspace, self.camera)
            if original is None:
                continue
            alternative, reason, attempted = replay.candidate(row['detections'], self.workspace, self.camera)
            self.assertFalse(attempted)
            self.assertEqual('tracking', reason)
            np.testing.assert_array_equal(original.rvec, alternative.rvec)
            np.testing.assert_array_equal(original.tvec, alternative.tvec)

    def test_three_markers_never_trigger_fallback(self):
        subset = dict(list(self.full.items())[:3])
        pose, _, attempted = replay.candidate(subset, self.workspace, self.camera)
        self.assertIsNone(pose)
        self.assertFalse(attempted)

    def test_recorded_acceptance_matches_android(self):
        self.assertEqual(129, len(self.rows))
        for row in self.rows:
            pose, _ = replay.baseline(row['detections'], self.workspace, self.camera)
            self.assertEqual(row['valid'], pose is not None)

    def test_quality_failure_is_not_bypassed(self):
        row = next(r for r in self.rows if r['reason']=='reprojection_limit')
        pose, _, attempted = replay.candidate(row['detections'], self.workspace, self.camera)
        self.assertIsNone(pose)
        self.assertFalse(attempted)

    def test_report_counts_and_maxima_recompute(self):
        report = json.loads((replay.ROOT/'pose-comparison/report.json').read_bytes())
        for section in ('masked','historical_temporal'):
            records = report[section]['records']
            self.assertEqual(report[section]['summary'], replay.summary(records))
            for removed, expected in report[section]['by_removed'].items():
                self.assertEqual(expected, replay.summary([r for r in records if r['removed']==int(removed)]))
        unsafe = [r for r in report['masked']['records'] if r['fallback'] and r['comparison'] and not r['comparison']['preserved']]
        self.assertTrue(unsafe, 'Candidate acceptance must not be mistaken for location preservation')


if __name__ == '__main__':
    unittest.main()
