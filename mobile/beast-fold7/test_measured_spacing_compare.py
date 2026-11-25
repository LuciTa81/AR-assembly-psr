import json
import unittest
import cv2
import numpy as np
import pose_replay_compare as replay
import corner_size_compare as corner
import measured_spacing_compare as spacing


class MeasuredSpacingTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((replay.ASSETS/'workspace-profile.json').read_bytes())
        self.camera=replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))

    def test_only_top_row_x_changes_without_mutating_source(self):
        before=json.dumps(self.raw,sort_keys=True)
        updated=spacing.measured_profile(self.raw)
        self.assertEqual(before,json.dumps(self.raw,sort_keys=True))
        centers=updated['marker_centers_mm']
        self.assertEqual(200,centers['1'][0]-centers['0'][0])
        self.assertEqual(205,centers['2'][0]-centers['1'][0])
        for key in ('0','3','4','5'):
            self.assertEqual(self.raw['marker_centers_mm'][key],centers[key])
        for key in self.raw:
            if key!='marker_centers_mm':self.assertEqual(self.raw[key],updated[key])

    def test_known_synthetic_pose_with_measured_geometry(self):
        original=replay.MetricWorkspace.from_dict(self.raw)
        updated=replay.MetricWorkspace.from_dict(spacing.measured_profile(self.raw))
        sample=json.loads((replay.ASSETS/'pose-fixtures.json').read_bytes())[0]
        reference,_=replay.baseline({int(k):np.array(v) for k,v in sample['detections'].items()},original,self.camera)
        world=corner.corners_for(69,{k:{'radians':0.} for k in (0,1,2,4,5)},updated)
        detections={k:cv2.projectPoints(q,reference.rvec,reference.tvec,self.camera.matrix,self.camera.distortion)[0].reshape(4,2) for k,q in world.items()}
        full,reason=replay.baseline(detections,updated,self.camera)
        self.assertEqual('tracking',reason)
        np.testing.assert_allclose(reference.tvec,full.tvec,atol=.01)
        for missing in (4,5):
            subset={k:v for k,v in detections.items() if k!=missing}
            self.assertIsNone(replay.baseline(subset,updated,self.camera)[0])
            pose,reason=corner.corner_pose(subset,world,self.camera)
            self.assertEqual('tracking',reason)
            np.testing.assert_allclose(reference.tvec,pose.tvec,atol=.01)
            np.testing.assert_allclose(reference.rvec,pose.rvec,atol=.0001)

    def test_capture_has_complete_pairs_and_increasing_timestamps(self):
        rows=spacing.capture_rows()
        self.assertEqual(46,len(rows))
        self.assertTrue(all(b['frame_ms']>a['frame_ms'] for a,b in zip(rows,rows[1:])))
        self.assertEqual(1,len({r['session'] for r in rows}))

    def test_report_counts_and_summaries(self):
        report=json.loads((replay.ROOT/'pose-comparison/measured-spacing-report.json').read_bytes())
        self.assertFalse(report['live_enabled'])
        self.assertEqual([],report['baseline_mismatches'])
        self.assertEqual(18,report['reference_frames'])
        for name,group in report['records'].items():
            summary=report['summaries'][name]
            self.assertEqual(46,len(group['actual']))
            self.assertEqual(24,summary['geometry_rejects'])
            self.assertEqual(replay.summary(group['full']),summary['full'])
            for missing in (4,5):
                rows=[r for r in group['masked'] if r['removed']==missing]
                self.assertEqual(18,len(rows))
                self.assertEqual(replay.summary(rows),summary['masked'][str(missing)]['versus_frozen'])


if __name__=='__main__':unittest.main()
