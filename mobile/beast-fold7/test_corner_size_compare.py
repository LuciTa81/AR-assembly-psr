import json
import unittest
import numpy as np
import corner_size_compare as corner
import pose_replay_compare as replay


class CornerSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
        cls.workspace=replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
        cls.report=json.loads((replay.ROOT/'pose-comparison/corner-size-report.json').read_bytes())

    def test_hypothesis_keeps_centers_and_exact_assumed_side(self):
        orientations={int(k):v for k,v in self.report['orientations'].items()}
        for side in (69,70):
            world=corner.corners_for(side,orientations,self.workspace)
            self.assertNotIn(3,world)
            for key,quad in world.items():
                np.testing.assert_allclose(quad.mean(axis=0),self.workspace.markers[key],atol=1e-10)
                np.testing.assert_allclose(np.linalg.norm(np.roll(quad,-1,axis=0)-quad,axis=1),side,atol=1e-10)

    def test_known_synthetic_orientation_and_projection(self):
        fixture=json.loads((replay.ASSETS/'pose-fixtures.json').read_bytes())[0]
        row={'detections':{int(k):np.array(v) for k,v in fixture['detections'].items()}}
        orientation=corner.fit_orientations([row],self.workspace,self.camera)
        for value in orientation.values():
            self.assertAlmostEqual(0.,value['degrees'],places=3)
        pose,reason=corner.corner_pose(row['detections'],corner.corners_for(70,orientation,self.workspace),self.camera)
        self.assertEqual('tracking',reason)
        reference,_=replay.baseline(row['detections'],self.workspace,self.camera)
        np.testing.assert_allclose(pose.tvec,reference.tvec,atol=.01)
        np.testing.assert_allclose(pose.rvec,reference.rvec,atol=.0001)

    def test_split_and_report_arithmetic(self):
        fit=self.report['fit_frames'];evaluation=self.report['evaluation_frames']
        self.assertEqual(8,len(fit));self.assertEqual(110,len(evaluation))
        self.assertLess(max(fit),min(evaluation))
        for side in ('69','70'):
            records=self.report['records'][side];summary=self.report['summaries'][side]
            self.assertEqual(summary['full'],replay.summary(records['full']))
            for missing in ('4','5'):
                self.assertEqual(summary['masked'][missing],replay.summary([r for r in records['masked'] if r['removed']==int(missing)]))
        self.assertEqual(self.report['size_change_summary'],replay.summary(self.report['size_changes']))

    def test_incomplete_input_not_promoted(self):
        self.assertEqual((None,'fewer_than_four'),corner.corner_pose({}, {}, self.camera))
        self.assertEqual((None,'orientation_unknown'),corner.corner_pose({k:np.zeros((4,2)) for k in (0,1,2,3)}, {}, self.camera))


if __name__=='__main__':
    unittest.main()
