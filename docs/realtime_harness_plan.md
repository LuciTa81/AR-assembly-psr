# Realtime Harness Plan

This document defines the first realtime runtime for the AR-assisted procedure step recognition project.

## Gate 1 MVP

The first gate intentionally avoids YOLO, MediaPipe, and final HMM tuning.

Required behavior:

1. Read frames from `dummy`, `camera`, or `session` source through the same interface.
2. Serve the current frame to a browser overlay.
3. Serve the current state as JSON.
4. Display FPS, latency, marker status, current state, and next action.
5. Save reproducible logs under `outputs/realtime_sessions/<session_id>/`.

## Runtime Flow

```text
FrameSource
-> optional ArUcoRealtimeTracker
-> optional RoiRealtimeAnalyzer
-> OnlineStateFilter
-> OverlayHttpServer
-> RealtimeLogger
```

## Current Gate Status

Implemented realtime gates:

1. S0 -> S1: `box_present_score` crosses the configured threshold.
2. S1 -> S2: `lid_closed_score` crosses the configured threshold.
3. S2 -> S6: screw A/B/C/D ROI evidence is checked in order. Screw transitions require both a sufficient done score and a recent positive ROI-delta event by default, so already-visible screw-like texture does not immediately advance the whole sequence.

## Run

```powershell
python server/realtime/run_realtime_server.py --source dummy --max-frames 300
```

Open:

```text
http://127.0.0.1:8765
```

For a camera:

```powershell
python server/realtime/run_realtime_server.py --source camera --camera-index 0 --camera-backend dshow
```

For the current Viture/external camera candidate with ArUco enabled:

```powershell
python server/realtime/run_realtime_server.py --config configs/realtime_viture_beast_aruco.yaml
```

For a saved session:

```powershell
python server/realtime/run_realtime_server.py --source session --session data/raw_sessions/session_17
```

## Output Files

```text
outputs/realtime_sessions/<session_id>/
  meta.json
  config_used.yaml
  frames.csv
  latency.csv
  events.csv
  results.jsonl
  overlay_messages.jsonl
```

## Next Gates

1. Tune screw ROI thresholds on the real workspace.
2. Add YOLO as an asynchronous cache, not as a blocking call.
3. Fuse YOLO driver/handle/screw evidence with the screw ROI gate.
4. Display target highlights on the original camera frame.
5. Add a replay tool that plots realtime state logs against manually labeled ground truth.
