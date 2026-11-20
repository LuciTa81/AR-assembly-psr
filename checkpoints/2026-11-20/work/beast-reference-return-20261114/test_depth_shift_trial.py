import json
import unittest

import numpy as np

import depth_shift_trial as trial


class DepthShiftTests(unittest.TestCase):
    def setUp(self):
        self.matrices = np.array([
            [[1400., 0., 960., -44800.], [0., 1300., 540., 0.], [0., 0., 1., 0.]],
            [[1400., 0., 960., 44800.], [0., 1300., 540., 0.], [0., 0., 1., 0.]],
        ])
        self.xyz = np.array([[-50., 30., 350.], [30., 75., 430.], [-15., 10., 530.]])
        self.bias = np.array([[12., 8.], [-5., 4.]])
        points = np.column_stack([self.xyz[:, :2], self.xyz[:, 2]+52., np.ones(3)])
        q = np.einsum('eij,nj->nei', self.matrices, points)
        self.truth = q[:, :, :2] / q[:, :, 2:] + self.bias

    def test_recovers_known_shared_shift_and_eye_bias(self):
        result = trial.fit(self.matrices, self.xyz, self.truth)
        self.assertAlmostEqual(result['shift_mm'], 52., places=4)
        np.testing.assert_allclose(result['bias_px'], self.bias, atol=1e-5)

    def test_result_is_portable_json(self):
        result = trial.fit(self.matrices, self.xyz, self.truth)
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)

    def test_export_is_exactly_equivalent_and_nonmutating(self):
        before = self.matrices.copy()
        exported = trial.shifted_matrices(self.matrices, 52., self.bias)
        np.testing.assert_allclose(trial.predict(exported, self.xyz), self.truth, atol=1e-9)
        np.testing.assert_array_equal(self.matrices, before)

    def test_held_out_pixels_do_not_influence_fit(self):
        first = trial.fit(self.matrices, self.xyz[:2], self.truth[:2])
        changed = self.truth.copy()
        changed[2] += 20.
        second = trial.fit(self.matrices, self.xyz[:2], changed[:2])
        self.assertEqual(first, second)
        np.testing.assert_allclose(trial.predict(self.matrices, self.xyz[2:],
            first['shift_mm'], first['bias_px']), self.truth[2:], atol=1e-5)

    def test_rejects_nonfinite_invalid_shape_and_duplicate_poses(self):
        for xyz in (self.xyz[:1], np.full((3, 3), np.nan), np.repeat(self.xyz[:1], 3, axis=0)):
            with self.subTest(xyz=xyz), self.assertRaises(ValueError):
                trial.fit(self.matrices, xyz, self.truth[:len(xyz)])

    def test_rejects_nonpositive_projection_depth(self):
        with self.assertRaises(ValueError):
            trial.predict(self.matrices, [[0., 0., -1.]])

    def test_constant_bias_reduces_to_zero_shift(self):
        truth = trial.predict(self.matrices, self.xyz) + self.bias
        result = trial.fit(self.matrices, self.xyz, truth)
        self.assertAlmostEqual(result['shift_mm'], 0., places=4)


if __name__ == '__main__':
    unittest.main()
