import itertools
import unittest
import numpy as np
import cv2
import test_session_corner_replay as fixtures
import corner_bridge_replay as bridge
import session_corner_replay as corners


class CornerBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SessionCornerTests.setUpClass()
        cls.data = fixtures.SessionCornerTests

    def tracker(self):
        return bridge.CornerBridge(self.data.workspace, self.data.camera)

    def test_cold_partial_rejected_and_full_baseline_unchanged(self):
        t = self.tracker()
        partial = dict(list(self.data.detections.items())[:3])
        self.assertIsNone(t.update(0, partial)[0])
        pose, _ = t.update(10, self.data.detections)
        np.testing.assert_array_equal(pose.tvec, self.data.reference.tvec)

    def test_all_synthetic_subsets_follow_moving_camera(self):
        d = self.data
        geometry = corners.fit_reference([{'detections': d.detections}], d.workspace, d.camera)
        r = d.reference.rvec + np.array([[.015], [-.02], [.01]])
        v = d.reference.tvec + np.array([[4.], [-3.], [8.]])
        moved = {k: cv2.projectPoints(q, r, v, d.camera.matrix, d.camera.distortion)[0].reshape(4, 2)
                 for k, q in geometry.items()}
        for count in (3, 4):
            for ids in itertools.combinations(sorted(moved), count):
                with self.subTest(ids=ids):
                    t = self.tracker()
                    t.update(0, d.detections)
                    pose, detail = t.update(100, {k: moved[k] for k in ids})
                    self.assertIsNotNone(pose, detail)
                    np.testing.assert_allclose(pose.tvec, v, atol=.05)

    def test_expiry_loss_unknown_bad_corners_and_clock_reset(self):
        d = self.data.detections
        partial = dict(list(d.items())[:3])
        for time, observation in [(3001, partial), (1, {}), (1, dict(list(d.items())[:2])),
                                  (-1, partial), (1, {49: next(iter(d.values())), **partial})]:
            t = self.tracker()
            t.update(0, d)
            self.assertIsNone(t.update(time, observation)[0])
        t = self.tracker()
        t.update(0, d)
        self.assertIsNotNone(t.update(1000, partial)[0])
        self.assertEqual(0, t.anchor_ms)
        self.assertIsNone(t.update(3001, partial)[0])

    def test_outlier_rejected_without_moving_anchor(self):
        d = self.data.detections
        t = self.tracker()
        t.update(0, d)
        partial = {k: v.copy() for k, v in list(d.items())[:3]}
        partial[next(iter(partial))] += [60, -40]
        self.assertIsNone(t.update(100, partial)[0])
        self.assertEqual(0, t.anchor_ms)

    def test_conservative_three_separates_right_occlusion_from_top_row(self):
        d=self.data
        t=bridge.CornerBridge(d.workspace,d.camera,max_age_ms=30000,conservative_three=True)
        t.update(0,d.detections)
        self.assertIsNotNone(t.update(100,{k:d.detections[k] for k in (0,1,4)})[0])
        self.assertIsNone(t.update(200,{k:d.detections[k] for k in (0,1,2)})[0])
        self.assertIsNotNone(t.update(29999,{k:d.detections[k] for k in (0,1,4)})[0])
        self.assertEqual(0,t.anchor_ms)
        self.assertIsNone(t.update(30001,{k:d.detections[k] for k in (0,1,4)})[0])

    def test_hidden_on_loss_but_fresh_observation_can_reacquire_before_expiry(self):
        d=self.data
        t=bridge.CornerBridge(d.workspace,d.camera,max_age_ms=30000,conservative_three=True,retain_reference_on_loss=True)
        t.update(0,d.detections)
        self.assertIsNone(t.update(500,{})[0])
        self.assertIsNone(t.update(1000,dict(list(d.detections.items())[:2]))[0])
        self.assertIsNotNone(t.update(1500,{k:d.detections[k] for k in (0,1,4)})[0])
        self.assertEqual(0,t.anchor_ms)
        self.assertIsNone(t.update(30001,{k:d.detections[k] for k in (0,1,4)})[0])


if __name__ == '__main__':
    unittest.main()
