import unittest
import numpy as np
import test_session_corner_replay as fixtures
from learned_corner_tracker import LearnedCornerTracker,MultiWindowCorners


class LearnedCornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SessionCornerTests.setUpClass()
        cls.data=fixtures.SessionCornerTests

    def initialized(self):
        d=self.data;t=LearnedCornerTracker(d.workspace,d.camera)
        for i in range(8):
            p,_=t.update(i*500,d.detections)
            np.testing.assert_array_equal(p.tvec,d.reference.tvec)
        return t

    def test_left_right_and_four_markers(self):
        d=self.data
        for ids in ((0,1,4),(1,2,5),(0,1,2,4),(0,1,2,5)):
            t=self.initialized()
            p,why=t.update(4000,{k:d.detections[k] for k in ids})
            self.assertIsNotNone(p,why)
            np.testing.assert_allclose(p.tvec,d.reference.tvec,atol=.01)

    def test_cold_start_expiry_and_no_partial_renewal(self):
        d=self.data;subset={k:d.detections[k] for k in (0,1,4)}
        t=LearnedCornerTracker(d.workspace,d.camera)
        self.assertIsNone(t.update(0,subset)[0])
        t=self.initialized()
        self.assertIsNotNone(t.update(33000,subset)[0])
        self.assertIsNone(t.update(33501,subset)[0])

    def test_bad_observation_and_clock_fail_closed(self):
        d=self.data;t=self.initialized()
        subset={k:d.detections[k].copy() for k in (0,1,4)}
        subset[0][0]+=100
        self.assertIsNone(t.update(4000,subset)[0])
        self.assertIsNone(t.update(3999,d.detections)[0])
        self.assertIsNone(t.update(5000,{k:d.detections[k] for k in (0,1,4)})[0])

    def test_collinear_three_and_unknown_id_are_rejected(self):
        d=self.data;t=self.initialized()
        self.assertIsNone(t.update(4000,{k:d.detections[k] for k in (0,1,2)})[0])
        bad={k:d.detections[k] for k in (0,1,4)};bad[49]=bad.pop(4)
        self.assertIsNone(t.update(4100,bad)[0])

    def test_multi_window_uses_same_expiry_and_actual_observations(self):
        d=self.data;t=MultiWindowCorners(d.workspace,d.camera)
        for i in range(8):t.update(i*500,d.detections)
        subset={k:d.detections[k] for k in (1,2,5)}
        self.assertIsNotNone(t.update(4000,subset)[0])
        self.assertIsNone(t.update(33501,subset)[0])

    def test_one_different_five_marker_set_does_not_erase_learned_marker(self):
        d=self.data;t=MultiWindowCorners(d.workspace,d.camera)
        for i in range(8):
            ids=(0,2,3,4,5) if i==0 else (0,1,2,4,5)
            self.assertIsNotNone(t.update(i*500,{k:d.detections[k] for k in ids})[0])
        for n,ids in enumerate(((0,1,2,4),(0,1,2,5))):
            p,why=t.update(4000+n*100,{k:d.detections[k] for k in ids})
            self.assertIsNotNone(p,why)

    def test_alternating_five_marker_sets_keep_four_samples_per_marker(self):
        d=self.data;t=LearnedCornerTracker(d.workspace,d.camera)
        for i in range(8):
            ids=(0,2,3,4,5) if i%2==0 else (0,1,2,4,5)
            t.update(i*500,{k:d.detections[k] for k in ids})
        p,why=t.update(4000,{k:d.detections[k] for k in (0,1,2,4)})
        self.assertIsNotNone(p,why)

    def test_underobserved_marker_is_not_invented(self):
        d=self.data;t=LearnedCornerTracker(d.workspace,d.camera)
        for i in range(8):
            ids=(0,1,2,4,5) if i==0 else (0,2,3,4,5)
            t.update(i*500,{k:d.detections[k] for k in ids})
        self.assertIsNone(t.update(4000,{k:d.detections[k] for k in (0,1,2,4)})[0])


if __name__=='__main__':unittest.main()
