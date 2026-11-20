import importlib
import importlib.util
import unittest

import numpy as np


class InverseDepthTests(unittest.TestCase):
    def model(self):
        self.assertIsNotNone(importlib.util.find_spec('compare_b_poses'),
                             'B offline comparison is not implemented')
        return importlib.import_module('compare_b_poses')

    def test_known_inverse_depth_relation(self):
        z = np.array([350., 500.])
        slope = np.array([[10000., 2000.], [8000., -3000.]])
        bias = np.array([[2., 3.], [4., 5.]])
        offsets = slope[None] / z[:, None, None] + bias
        value, extrapolated = self.model().inverse_depth(z, offsets, 420.)
        np.testing.assert_allclose(value, slope/420. + bias, atol=1e-12)
        self.assertFalse(extrapolated)

    def test_endpoint_and_reversed_training_order(self):
        values = np.arange(8).reshape(2, 2, 2)
        a, extra = self.model().inverse_depth([350., 500.], values, 350.)
        b, reverse_extra = self.model().inverse_depth([500., 350.], values[::-1], 350.)
        np.testing.assert_array_equal(a, values[0])
        np.testing.assert_array_equal(a, b)
        self.assertFalse(extra or reverse_extra)

    def test_extrapolation_is_explicit_diagnostic_only(self):
        _, extra = self.model().inverse_depth([350., 500.], np.zeros((2, 2, 2)), 600.)
        self.assertTrue(extra)

    def test_rejects_invalid_or_duplicate_depths(self):
        model = self.model()
        for z, query in (([350., 350.], 400.), ([0., 500.], 400.),
                         ([350., np.nan], 400.), ([350., 500.], -1.),
                         ([350.], 400.), ([350., 500.], np.inf)):
            with self.subTest(z=z, query=query), self.assertRaises(ValueError):
                model.inverse_depth(z, np.zeros((2, 2, 2)), query)

    def test_rejects_invalid_offsets(self):
        model = self.model()
        for values in (np.zeros((2, 4)), np.full((2, 2, 2), np.nan)):
            with self.assertRaises(ValueError):
                model.inverse_depth([350., 500.], values, 420.)

    def test_withheld_pixels_are_not_inputs(self):
        z = [350., 420., 500.]
        values = np.arange(12.).reshape(3, 2, 2)
        a, _ = self.model().inverse_depth(np.array(z)[[0, 2]], values[[0, 2]], z[1])
        values[1] += 10000.
        b, _ = self.model().inverse_depth(np.array(z)[[0, 2]], values[[0, 2]], z[1])
        np.testing.assert_array_equal(a, b)


if __name__ == '__main__':
    unittest.main()
