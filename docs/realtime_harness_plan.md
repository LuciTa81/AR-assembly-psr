# Realtime Harness Plan

This document defines the first realtime runtime for the AR-assisted procedure step recognition project.

## Gate 1 MVP

The first gate intentionally avoids MediaPipe and final HMM tuning. YOLO is now included as a non-blocking evidence cache for screw transitions, because ROI-only screw gates were too sensitive to hands or arms passing over a screw ROI.

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
-> optional RealtimeYoloAnalyzer
-> OnlineStateFilter
-> OverlayHttpServer
-> RealtimeLogger
```

## Current Gate Status

Implemented realtime gates:

1. S0 -> S1: `box_present_score` crosses the configured threshold.
2. S1 -> S2: `lid_closed_score` crosses the configured threshold.
3. S2 -> S6: screw A/B/C/D evidence is checked in order. Screw transitions use ROI done score and ROI-delta events, and the Viture ArUco configs additionally require YOLO driver-tip proximity evidence for the current target screw. This prevents hand or arm motion near screw ROIs from immediately advancing the sequence.

YOLO details:

- Model file: `models/yolo/driver_standard_model/best-3.pt`
- Classes: `driver`, `handle`, `screw`
- Runtime mode: asynchronous cache, evaluated every few frames
- Overlay diagnostics: YOLO age, driver visibility, and current target tool score

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

1. Tune YOLO target score thresholds on the real workspace.
2. Tune lid transition confidence after repeated Viture camera tests.
3. Display target highlights on the original camera frame.
4. Add a replay tool that plots realtime state logs against manually labeled ground truth.
5. Revisit MediaPipe only as a secondary hand/tool association signal after YOLO is stable.
