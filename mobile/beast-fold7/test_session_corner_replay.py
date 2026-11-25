import itertools
import json
import unittest
import cv2
import numpy as np
import session_corner_replay as candidate
import pose_replay_compare as replay


class SessionCornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.camera = replay.CameraModel.from_profile(json.loads((replay.ASSETS/'camera-profile.json').read_bytes()))
        cls.workspace = replay.MetricWorkspace.from_dict(json.loads((replay.ASSETS/'workspace-profile.json').read_bytes()))
        fixture = json.loads((replay.ASSETS/'pose-fixtures.json').read_bytes())[0]
        cls.detections = {int(k):np.array(v) for k,v in fixture['detections'].items()}
        cls.reference, _ = replay.baseline(cls.detections, cls.workspace, cls.camera)

    def test_initialization_requires_valid_five_marker_frames(self):
        with self.assertRaises(ValueError):
            candidate.fit_reference([], self.workspace, self.camera)
        subset = dict(list(self.detections.items())[:3])
        with self.assertRaises(ValueError):
            candidate.fit_reference([{'detections':subset}], self.workspace, self.camera)

    def test_all_three_and_four_subsets_recover_known_synthetic_pose(self):
        rows = [{'detections':self.detections}]
        world = candidate.fit_reference(rows, self.workspace, self.camera)
        r = self.reference.rvec + np.array([[.015],[-.02],[.01]])
        t = self.reference.tvec + np.array([[4.],[-3.],[8.]])
        observed = {key:cv2.projectPoints(quad,r,t,self.camera.matrix,self.camera.distortion)[0].reshape(4,2)
                    for key,quad in world.items()}
        for count in (3,4):
            for ids in itertools.combinations(sorted(world),count):
                with self.subTest(ids=ids):
                    pose,reason = candidate.partial_pose({key:observed[key] for key in ids},world,self.camera)
                    self.assertEqual('tracking',reason)
                    np.testing.assert_allclose(pose.tvec,t,atol=.01)
                    np.testing.assert_allclose(cv2.Rodrigues(pose.rvec)[0],cv2.Rodrigues(r)[0],atol=1e-5)

    def test_no_reference_two_markers_unknown_and_bad_quad_rejected(self):
        self.assertIsNone(candidate.partial_pose(self.detections,{},self.camera)[0])
        world = candidate.fit_reference([{'detections':self.detections}],self.workspace,self.camera)
        self.assertIsNone(candidate.partial_pose(dict(list(self.detections.items())[:2]),world,self.camera)[0])
        unknown = dict(list(self.detections.items())[:3]); unknown[49]=unknown.pop(next(iter(unknown)))
        self.assertIsNone(candidate.partial_pose(unknown,world,self.camera)[0])
        bad = {k:v.copy() for k,v in self.detections.items()}
        bad[next(iter(bad))][0]=[float('nan'),0]
        self.assertIsNone(candidate.partial_pose(bad,world,self.camera)[0])

    def test_bad_correspondence_does_not_pass_low_marker_count(self):
        world=candidate.fit_reference([{'detections':self.detections}],self.workspace,self.camera)
        bad={k:v.copy() for k,v in list(self.detections.items())[:3]}
        bad[next(iter(bad))]+=np.array([60.,-40.])
        self.assertIsNone(candidate.partial_pose(bad,world,self.camera)[0])

    def test_recent_reference_expiry_and_no_partial_renewal(self):
        tracker=candidate.RecentReference(self.workspace,self.camera)
        subset=dict(list(self.detections.items())[:3])
        self.assertIsNone(tracker.update(100,subset)[0])
        self.assertIsNotNone(tracker.update(200,self.detections)[0])
        self.assertIsNotNone(tracker.update(3199,subset)[0])
        self.assertIsNone(tracker.update(3201,subset)[0])
        self.assertIsNotNone(tracker.update(3300,self.detections)[0])
        self.assertIsNone(tracker.update(3200,subset)[0])

    def test_full_loss_drops_reference_and_normal_pose_stays_unchanged(self):
        tracker=candidate.RecentReference(self.workspace,self.camera)
        pose,_=tracker.update(100,self.detections)
        np.testing.assert_array_equal(pose.tvec,self.reference.tvec)
        self.assertIsNone(tracker.update(200,{})[0])
        self.assertIsNone(tracker.update(300,dict(list(self.detections.items())[:4]))[0])

    def test_reference_is_not_changed_by_later_partial_observations(self):
        tracker=candidate.RecentReference(self.workspace,self.camera)
        before={k:v.copy() for k,v in self.detections.items()}
        tracker.update(100,self.detections)
        geometry={k:v.copy() for k,v in tracker.geometry.items()}
        tracker.update(200,dict(list(self.detections.items())[:3]))
        self.assertEqual(100,tracker.anchor_ms)
        for key in before:
            np.testing.assert_array_equal(self.detections[key],before[key])
            np.testing.assert_array_equal(tracker.geometry[key],geometry[key])

    def test_report_holds_out_current_and_future_frames(self):
        rows=[{'detections':self.detections} for _ in range(10)]
        raw=json.loads((replay.ASSETS/'eye-projection.json').read_bytes())
        eyes=[np.array(raw[k]).reshape(3,4) for k in ('left_projection','right_projection')]
        report=candidate.evaluate(rows,self.workspace,self.camera,eyes)
        self.assertEqual(list(range(8)),report['fit_indices'])
        self.assertTrue(all(r['index']>=8 for r in report['masked']))
        for count in (3,4):
            records=[r for r in report['masked'] if r['count']==count]
            self.assertEqual(replay.summary(records),report['summary']['masked'][str(count)])


if __name__=='__main__':
    unittest.main()
