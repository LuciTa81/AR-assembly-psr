import json
import unittest
import cv2
import numpy as np
import marker_observation_audit as audit
import pose_replay_compare as replay
import corner_size_compare as corner


class MarkerAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
        cls.workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
        fixture=json.loads((replay.ASSETS/'pose-fixtures.json').read_bytes())[0]
        cls.detections={int(k):np.array(v) for k,v in fixture['detections'].items()}
        cls.pose,_=replay.baseline(cls.detections,cls.workspace,cls.camera)
        cls.geometry=corner.corners_for(70,{k:{'radians':0.} for k in cls.detections},cls.workspace)

    def test_exact_square_has_negligible_residual(self):
        for key,quad in self.detections.items():
            value=audit.measure(quad,key,self.pose,self.geometry,self.workspace,self.camera)
            self.assertLess(value['center_error_px'],.001)
            self.assertLess(value['corner_rms_px'],.001)
            self.assertLess(value['shape_rms_px'],.001)
            np.testing.assert_allclose(value['inferred_edge_lengths_mm'],70,atol=.001)

    def test_translation_and_shape_are_separated(self):
        key=4
        quad=cv2.projectPoints(self.geometry[key],self.pose.rvec,self.pose.tvec,self.camera.matrix,self.camera.distortion)[0].reshape(4,2)
        moved=quad+[3.,-4.]
        value=audit.measure(moved,key,self.pose,self.geometry,self.workspace,self.camera)
        self.assertAlmostEqual(5.,value['corner_rms_px'],places=8)
        self.assertLess(value['shape_rms_px'],1e-8)
        np.testing.assert_allclose(value['common_offset_px'],[3.,-4.],atol=1e-8)
        moved[0]+=[5.,0.]
        changed=audit.measure(moved,key,self.pose,self.geometry,self.workspace,self.camera)
        self.assertGreater(changed['shape_rms_px'],1.)

    def test_summary_and_no_fit_overlap(self):
        report=json.loads((replay.ROOT/'pose-comparison/marker-audit.json').read_bytes())
        prior=json.loads((replay.ROOT/'pose-comparison/corner-size-report.json').read_bytes())
        self.assertEqual(40,len(report['used_frames']))
        self.assertLess(prior['cutoff_ms'],min(report['used_frames']))
        for side in ('69','70'):
            self.assertEqual(200,len(report['records'][side]))
            self.assertEqual(report['summaries'][side],audit.summarize(report['records'][side]))
            self.assertNotIn('3',report['summaries'][side])
            self.assertEqual(40,sum(report['worst_shape_counts'][side].values()))


if __name__=='__main__':
    unittest.main()
