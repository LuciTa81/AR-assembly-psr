# Decision Log

## Marker layout v2 direction

Current 4-corner ArUco warp is unstable under natural Quest 3 head movement.
Future version should use 6 ArUco markers and estimate homography from all visible marker corners using cv2.findHomography + RANSAC.

Keep:
- warped output size: 800x600
- ROI cropper structure
- YOLO raw pipeline
- MediaPipe raw pipeline
- HMM input structure

Change:
- marker layout config
- warp_session.py / marker_pose.py homography estimation
- roi_layout may need minor recalibration after new warp
