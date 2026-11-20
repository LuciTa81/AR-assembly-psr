# Viture / External Camera Probe - 2026-06-19

## Summary

The realtime harness can currently see two camera inputs through OpenCV with the DirectShow backend.

| Index | Result | Observed View | Note |
| :--- | :--- | :--- | :--- |
| `0` | OK | Laptop-facing webcam view | Shows the user's face / laptop direction |
| `1` | OK | Desk/cable-facing external view | Candidate for Viture Beast or externally connected camera |
| `2` to `8` | Not opened | None | No additional cameras found |

Probe command:

```powershell
.\.venv_rt\Scripts\python.exe server\realtime\probe_cameras.py --max-index 8 --backend dshow --save-preview
```

Do not run multiple camera probes in parallel. Windows camera backends can lock or fail when two processes try to read the same device.

Realtime harness smoke test with index `1`:

```powershell
.\.venv_rt\Scripts\python.exe server\realtime\run_realtime_server.py --source camera --camera-index 1 --camera-backend dshow --max-frames 30 --port 8878
```

Result:

```text
[INFO] source=camera
[INFO] overlay=http://127.0.0.1:8878
{"frame": 30, "fps": 10.38, "state": "S0", "marker": "DISABLED"}
[DONE] saved realtime session: outputs\realtime_sessions\rt_20260619_193512
```

## Next

Use `configs/realtime_viture_beast_display_camera.yaml` for the next camera-facing harness run:

```powershell
.\.venv_rt\Scripts\python.exe server\realtime\run_realtime_server.py --config configs\realtime_viture_beast_display_camera.yaml
```

Open the overlay:

```text
http://127.0.0.1:8765
```

If camera indices change after reconnecting devices, run the probe again.
