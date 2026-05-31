# AR-Assisted Assembly Step Recognition

This repository contains an end-to-end pipeline for **procedure step recognition (PSR)** in a fixed-sequence industrial enclosure assembly task.

The project is currently organized around two tracks:

1. **Machine-learning team project**
   - Offline HMM-based step recognition for recorded assembly sessions.
   - Current priority: improve and document `session_17` performance.

2. **Graduation project**
   - Real-time AR assembly guidance using a wearable display and a Python inference server.
   - This track is kept as the long-term direction, but real-time integration is not the current focus.

The latest verified offline pipeline uses ArUco-based workspace warping, YOLO detections, ROI evidence, ROI delta, MediaPipe auxiliary features, FSM smoothing, and HMM temporal reasoning.

---

## 1. Project Overview

The target task is a controlled industrial enclosure assembly sequence.

| Item | Description |
| :--- | :--- |
| Task | Industrial enclosure assembly |
| Sequence | Empty workspace -> box placed -> lid closed -> four screws completed |
| Current dataset | `session_17` frame sequence |
| Current best method | HMM v2 with continuous evidence features |
| Real-time target | AR guidance through Quest 3 / wearable display |

The project intentionally focuses on a controlled workcell instead of broad action recognition. This makes the system easier to evaluate, explain, and later deploy as a real-time AR guidance prototype.

---

## 2. Current Focus: HMM v2 Session17

The current reproducible result is the offline **HMM v2 pipeline** for `session_17`.

### 2.1 State Definition

| State | Meaning |
| :--- | :--- |
| `S0` | Empty workspace / no box |
| `S1` | Box placed |
| `S2` | Lid closed |
| `S3` | Screw A done |
| `S4` | Screw B done |
| `S5` | Screw C done |
| `S6` | Screw D done |

### 2.2 Feature Sources

| Source | Role |
| :--- | :--- |
| ArUco markers | Workspace calibration and top-view warp |
| YOLO 3-class model | Detects `driver`, `handle`, and `screw` |
| ROI templates | Measures state-specific visual evidence |
| ROI delta | Measures local visual change around screw ROIs |
| MediaPipe | Auxiliary hand/index signal, not the main decision source |
| Continuous proximity scores | Replaces hard 0/1 tool/index evidence with smooth scores |
| FSM / HMM | Applies temporal consistency and ordered step progression |

The offline pipeline still uses `labels/labels_segments.csv` for evaluation. In a later real-time version, this file will not be used at runtime; online state filtering will replace it.

---

## 3. Result Summary

Best verified `session_17` result:

| Model | Accuracy | Macro-F1 |
| :--- | ---: | ---: |
| Framewise v2 | 88.24% | 89.52% |
| FSM v2 | 91.60% | 93.23% |
| HMM v2 | **94.12%** | **94.85%** |

Additional notes:

- `S0` was correctly detected for all 7 frames.
- The remaining HMM errors are short boundary delays between neighboring states.
- Full plots and mismatch CSVs are stored in `docs/assets/session17_hmm_v2/`.

See:

- `docs/session17_hmm_v2_status.md`
- `docs/assets/session17_hmm_v2/timeline_best_role3.png`
- `docs/assets/session17_hmm_v2/s0_zoom_best_role3.png`

---

## 4. Data and Model Setup

Large runtime files are not stored in this repository.

Place the required session data and model weights at the following paths:

```text
data/raw_sessions/session_17/
models/yolo/driver_standard_model/best-3.pt
```

Expected YOLO classes:

```text
driver
handle
screw
```

The current HMM pipeline assumes the `best-3.pt` 3-class detector trained by the team.

---

## 5. Repository Structure

```text
.
├── client_unity/                  # Unity / AR client prototype
├── configs/                       # Marker and ROI layout configs
├── data/                          # Ignored local session data
├── docs/                          # Project docs and session17 result reports
│   └── assets/session17_hmm_v2/    # Best result plots and CSV summaries
├── labels/
│   └── labels_segments.csv         # Offline GT segments for evaluation
├── models/                        # Ignored local model weights
├── refs/
│   └── roi_templates_v2/           # Warped ROI templates used by v2 pipeline
├── scripts/                       # PowerShell runners for setup and evaluation
├── server/
│   ├── app/                        # Server entry points
│   ├── state/                      # FSM / HMM / state reasoning code
│   ├── tools/                      # Utility tools, including ArUco marker generation
│   └── vision/                     # Warp, YOLO, MediaPipe, ROI feature extraction
└── tests/
```

The existing ArUco marker generation utilities are preserved because they are still useful for the later AR pipeline.

---

## 6. Quick Start

### 6.1 Environment Setup

Use Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
py -3.11 -m venv .venv_mp
.\.venv_mp\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\server\requirements.txt
```

You can also use the helper script:

```powershell
.\scripts\setup_env_v2.ps1
```

### 6.2 Run the Full Session17 Pipeline

```powershell
.\scripts\run_session17_full_then_best_hmm.ps1 -Clean
.\scripts\run_session17_best_role3_hmm.ps1
```

Main outputs:

```text
outputs/hmm_v2/session_17_state_predictions_v2_best_role3.csv
outputs/hmm_v2/session_17_state_metrics_v2_best_role3.csv
outputs/hmm_v2/session_17_state_timeline_v2_best_role3.png
```

### 6.3 Run HMM Only After Features Already Exist

```powershell
.\scripts\run_hmm_v2_only.ps1
```

---

## 7. HMM v2 Best Configuration

The current best `session_17` configuration uses smooth continuous evidence and a relatively fast transition setting.

| Parameter | Value |
| :--- | ---: |
| `tool_score_radius` | `90` |
| `tool_score_softness` | `45` |
| `index_score_radius` | `100` |
| `index_score_softness` | `30` |
| `index_weight` | `0.0` |
| `roi_weight` | `0.10` |
| `roi_delta_weight` | `0.12` |
| `roi_delta_scale` | `0.20` |
| `roi_delta_window` | `3` |
| `screw_detect_weight` | `0.55` |
| `self_prob` | `0.76` |
| `next_prob` | `0.24` |
| `smooth_window` | `2` |

These values are tuned for the current low-FPS `session_17` sequence. They should be retuned if the capture rate or camera setup changes.

---

## 8. Graduation Project Track

The long-term AR system is still part of the repository direction.

Planned runtime flow:

```text
Camera / wearable input
-> ArUco calibration
-> top-view warp
-> visual evidence extraction
-> online state filter
-> AR guidance overlay
```

For real-time deployment, the following parts still need work:

- collect higher-FPS sessions,
- remove dependency on `labels_segments.csv` at runtime,
- retune temporal transition parameters,
- optimize latency,
- connect the Python server with the AR client,
- design the operator-facing guidance UI.

---

## 9. Future Work

- Collect denser sessions, ideally around 5 FPS or higher.
- Retune HMM transition probabilities for higher frame rates.
- Evaluate generalization on new sessions and new operators.
- Compare HMM, FSM, and the planned PEBF-style online filter.
- Improve MediaPipe usage as a stable auxiliary signal instead of a primary signal.
- Add a clean real-time inference path for the graduation project.

---

## 10. Notes

This repository should currently be treated as:

- a strong offline HMM baseline for the machine-learning team project,
- a documented starting point for later real-time AR assembly guidance,
- and a workspace that keeps experimental HMM work separate from the graduation-project AR track.
