import unittest
from unittest.mock import patch
import cv2
import numpy as np
import test_session_corner_replay as fixtures
import pose_replay_compare as replay
from tracking_continuity import ReferenceBank, FlowBridge


class ContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SessionCornerTests.setUpClass()
        cls.data=fixtures.SessionCornerTests

    def image(self):
        gray=np.zeros((720,1280),np.uint8)
        rng=np.random.default_rng(48)
        for quad in self.data.detections.values():
            texture=rng.integers(30,225,(64,64),dtype=np.uint8)
            texture=cv2.GaussianBlur(texture,(3,3),0)
            h=cv2.getPerspectiveTransform(np.float32([[0,0],[63,0],[63,63],[0,63]]),quad.astype(np.float32))
            patch=cv2.warpPerspective(texture,h,(1280,720))
            gray=np.maximum(gray,patch)
        return gray

    def test_bank_bounded_expiring_and_full_pose_unchanged(self):
        d=self.data;t=ReferenceBank(d.workspace,d.camera)
        for i in range(12):
            p,_=t.update(i*600,d.detections)
            np.testing.assert_array_equal(p.tvec,d.reference.tvec)
        self.assertLessEqual(len(t.references),6)
        self.assertIsNotNone(t.update(7000,{k:d.detections[k] for k in (0,1,4)})[0])
        self.assertIsNone(t.update(40000,{k:d.detections[k] for k in (0,1,4)})[0])
        self.assertIsNone(t.update(100,{k:d.detections[k] for k in (0,1,4)})[0])

    def test_flow_uses_new_image_motion_not_a_frozen_pose(self):
        d=self.data;gray=self.image();flow=FlowBridge(d.workspace,d.camera)
        flow.seed(0,gray,d.reference,d.detections)
        shifted=cv2.warpAffine(gray,np.float32([[1,0,4],[0,1,-3]]),(1280,720))
        pose,detail=flow.update(150,shifted,{})
        self.assertIsNotNone(pose,detail)
        delta=replay.target_deltas(d.reference,pose,d.workspace,d.camera)
        self.assertGreater(delta['max_target_delta_px'],2)
        self.assertLess(delta['max_target_delta_px'],8)
        self.assertEqual(0,flow.seed_ms)
        self.assertIsNone(flow.update(501,shifted,{})[0])

    def test_blank_or_unrelated_scene_cannot_extend_visibility(self):
        d=self.data;gray=self.image()
        for current in (np.zeros_like(gray),np.random.default_rng(49).integers(0,255,gray.shape,dtype=np.uint8)):
            flow=FlowBridge(d.workspace,d.camera);flow.seed(0,gray,d.reference,d.detections)
            self.assertIsNone(flow.update(100,current,{})[0])

    def test_flow_without_seed_bad_time_and_resolution_fail_closed(self):
        d=self.data;gray=self.image();flow=FlowBridge(d.workspace,d.camera)
        self.assertIsNone(flow.update(100,gray,{})[0])
        flow.seed(100,gray,d.reference,d.detections)
        self.assertIsNone(flow.update(50,gray,{})[0])
        flow.seed(100,gray,d.reference,d.detections)
        self.assertIsNone(flow.update(150,gray[:360],{})[0])

    def test_missing_native_flow_result_is_rejected(self):
        d=self.data;gray=self.image();flow=FlowBridge(d.workspace,d.camera)
        flow.seed(0,gray,d.reference,d.detections)
        with patch('tracking_continuity.cv2.calcOpticalFlowPyrLK',return_value=(None,None,None)):
            self.assertIsNone(flow.update(100,gray,{})[0])


if __name__=='__main__':unittest.main()
