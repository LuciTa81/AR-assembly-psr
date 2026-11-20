"""Offline regression checks for the common workspace translation hypothesis."""
import copy
import unittest
import cv2
import numpy as np
from server.realtime.workspace_projection import CameraModel, MetricWorkspace
from compare_workspace_xy import FIT_FRAMES, fit_offset, make_candidate


class WorkspaceXYTests(unittest.TestCase):
    def setUp(self):
        self.camera = CameraModel("test", (1280, 720),
                                  np.array([[800., 0, 640], [0, 800, 360], [0, 0, 1]]), np.zeros(5))
        self.source = dict(schema_version="beast_workspace_metric_v1", profile_id="old",
            units="mm", axes="x_right_y_away_z_up", origin_marker_id=3,
            marker_centers_mm={"3": [0,0,0], "0": [0,285,0], "1": [205,285,0], "5": [330,175,0]},
            targets_mm={"A": [150,150,60], "B": [260,150,60], "C": [150,40,60], "D": [260,40,60]})
        self.workspace = MetricWorkspace.from_dict(self.source)
        self.offset = np.array([2.5, -25., 0.])
        self.observations = {}
        for frame, tvec in zip((*FIT_FRAMES, 109), ([-180.,150,600], [-150.,100,640], [-170.,130,620])):
            rvec = np.array([np.pi, 0., 0.])
            labels = {name: cv2.projectPoints((point+self.offset).reshape(1,3), rvec, np.array(tvec),
                       self.camera.matrix, self.camera.distortion)[0].reshape(2).tolist()
                      for name, point in self.workspace.targets.items()}
            self.observations[frame] = dict(rvec=rvec, tvec_mm=tvec, labels=labels)

    def test_recovers_exact_translation(self):
        np.testing.assert_allclose(fit_offset(self.camera, self.workspace, self.observations),
                                   self.offset, atol=1e-8)

    def test_holdout_does_not_change_fit(self):
        self.observations[109]["labels"] = {k: [0, 0] for k in "ABCD"}
        np.testing.assert_allclose(fit_offset(self.camera, self.workspace, self.observations),
                                   self.offset, atol=1e-8)

    def test_empty_recess_labels_are_not_fitted(self):
        for frame in FIT_FRAMES:
            for name in "BC":
                self.observations[frame]["labels"][name] = [float("nan"), 0]
        np.testing.assert_allclose(fit_offset(self.camera, self.workspace, self.observations),
                                   self.offset, atol=1e-8)

    def test_invalid_fit_label_is_rejected(self):
        self.observations[FIT_FRAMES[0]]["labels"]["A"] = [float("nan"), 0]
        with self.assertRaises(ValueError):
            fit_offset(self.camera, self.workspace, self.observations)

    def test_candidate_keeps_geometry_and_original_untouched(self):
        original = copy.deepcopy(self.source)
        candidate = make_candidate(self.source, self.offset, "parent-hash")
        self.assertEqual(self.source, original)
        self.assertEqual(candidate["marker_centers_mm"], self.source["marker_centers_mm"])
        self.assertEqual(candidate["activation_status"], "not_activated")
        self.assertFalse(candidate["display_alignment_verified"])
        self.assertNotEqual(candidate["profile_id"], self.source["profile_id"])
        a = np.array([self.source["targets_mm"][k] for k in "ABCD"], float)
        b = np.array([candidate["targets_mm"][k] for k in "ABCD"], float)
        np.testing.assert_allclose(b-a, np.tile(self.offset, (4,1)), atol=1e-8)
        np.testing.assert_allclose(b[:,None]-b, a[:,None]-a, atol=1e-8)
        np.testing.assert_array_equal(b[:,2], a[:,2])

    def test_vertical_or_nonfinite_offset_is_rejected(self):
        for value in ([0., 0., 1.], [float("nan"), 0., 0.]):
            with self.assertRaises(ValueError):
                make_candidate(self.source, value, "parent-hash")


if __name__ == "__main__":
    unittest.main()

