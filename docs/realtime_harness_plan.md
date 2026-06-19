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
-> OnlineStateFilter
-> OverlayHttpServer
-> RealtimeLogger
```

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

1. Enable ArUco and verify marker loss does not crash the runtime.
2. Add realtime ROI scores and ROI delta.
3. Replace dummy state movement with causal online belief updates.
4. Add YOLO as an asynchronous cache, not as a blocking call.
5. Display target highlights on the original camera frame.
