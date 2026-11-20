import copy
import importlib
import unittest

import numpy as np


def sample():
    return dict(schema_version='beast_tracked_alignment_diagnostic_v1',
        candidate_only=True, calibration_valid=False, display_alignment_verified=False,
        binocular_confirmed_by_user=True, rendered_view='Both', setup_id='same-fit',
        coordinate_convention='eye_local_pixels_top_left',
        channel_order='left_half_left_eye_right_half_right_eye',
        output_width=3840, output_height=1080, candidate_sha256='candidate',
        conservative_age_ms=100.,
        observation=dict(status='tracking', target_id='A', session_id='s', frame_id=1,
            camera_profile_sha256='camera', workspace_profile_sha256='workspace',
            camera_xyz_mm=[12., 30., 400.]),
        left_base_px=[900., 500.], right_base_px=[800., 500.],
        left_offset_px=[4., 6.], right_offset_px=[-2., 3.],
        left_final_px=[904., 506.], right_final_px=[798., 503.])


class RecordTests(unittest.TestCase):
    def validate(self, record):
        module = importlib.import_module('shared_ab_review')
        return module.validate_record(record, setup='same-fit', target='A',
            camera_hash='camera', workspace_hash='workspace', candidate_hash='candidate')

    def test_absolute_final_pixels_not_offsets(self):
        xyz, pixels = self.validate(sample())
        np.testing.assert_array_equal(xyz, [12, 30, 400])
        np.testing.assert_array_equal(pixels, [[904, 506], [798, 503]])

    def test_free_position_needs_no_requested_world_position(self):
        record = sample()
        record['observation']['camera_xyz_mm'] = [-57.31, 92.46, 473.27]
        xyz, _ = self.validate(record)
        np.testing.assert_array_equal(xyz, [-57.31, 92.46, 473.27])

    def test_rejects_mixed_wearing_profiles_and_channel_order(self):
        for key, value in [('setup_id', 'different'), ('candidate_sha256', 'different'),
                           ('channel_order', 'swapped'), ('output_width', 1920),
                           ('coordinate_convention', 'normalized')]:
            record = sample()
            record[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(record)
        for key in ('camera_profile_sha256', 'workspace_profile_sha256', 'target_id'):
            record = sample()
            record['observation'][key] = 'different'
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(record)

    def test_rejects_stale_unconfirmed_and_partial_pair(self):
        for key, value in [('conservative_age_ms', 151), ('conservative_age_ms', -1),
                           ('conservative_age_ms', float('nan')),
                           ('binocular_confirmed_by_user', False), ('rendered_view', 'Left')]:
            record = sample()
            record[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate(record)

    def test_rejects_wrong_pixel_reconstruction_and_nonfinite_geometry(self):
        record = sample()
        record['left_final_px'][0] += 1
        with self.assertRaises(ValueError):
            self.validate(record)
        for xyz in ([1, 2, 0], [1, float('nan'), 400], [1, 2]):
            record = sample()
            record['observation']['camera_xyz_mm'] = xyz
            with self.assertRaises(ValueError):
                self.validate(record)

    def test_input_record_is_not_modified(self):
        record = sample()
        original = copy.deepcopy(record)
        self.validate(record)
        self.assertEqual(record, original)

    def test_duplicate_pose_groups_rejected(self):
        module = importlib.import_module('shared_ab_review')
        with self.assertRaises(ValueError):
            module.check_groups(['A_middle', 'A_middle'], [sample(), sample()])
        with self.assertRaises(ValueError):
            module.check_groups(['A_middle', 'A_near'], [sample(), sample()])

    def test_unadjusted_targets_are_reported_separately(self):
        module = importlib.import_module('shared_ab_review')
        record = sample()
        record['observation']['camera_targets'] = [
            dict(target_id='C', camera_xyz_mm=[-10., 160., 400.]),
            dict(target_id='D', camera_xyz_mm=[10., 160., 400.])]
        before = copy.deepcopy(record)
        result = module.unobserved_target_coverage([record], [[12., 30., 400.]])
        self.assertEqual(result['outside_observed_vertical_range'], 2)
        self.assertFalse(result['these_are_calibration_observations'])
        self.assertEqual(record, before)

    def test_nonpositive_unobserved_target_depth_rejected(self):
        module = importlib.import_module('shared_ab_review')
        record = sample()
        record['observation']['camera_targets'] = [dict(target_id='C', camera_xyz_mm=[1, 2, -1])]
        with self.assertRaises(ValueError):
            module.unobserved_target_coverage([record], [[12., 30., 400.]])


if __name__ == '__main__':
    unittest.main()
