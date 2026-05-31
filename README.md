# AR-Assisted Procedure Step Recognition for Industrial Enclosure Assembly

This repository contains an end-to-end pipeline for **AR-based assembly guidance** and **procedure step recognition (PSR)** in a fixed-sequence industrial enclosure assembly task.

The goal is to recognize the current assembly step from camera frames, keep the estimate stable over time, and use that state estimate for AR guidance, warning, replay, and session logging.

The current repository includes a verified offline **HMM v2 evaluation pipeline** for `session_17`. This offline pipeline is used as the current working baseline before moving the same step-recognition logic into a real-time AR runtime.

---

## 1. Project Overview

This project targets a controlled workcell with one assembly object and a fixed order of operations.

| Item | Description |
| :--- | :--- |
| Object | Industrial enclosure box, lid, screws, and screwdriver |
| Task | Place box, close lid, complete four screws in order |
| Workspace | ArUco marker-based calibrated tabletop |
| Main output | Estimated assembly state `S0` to `S6` |
| AR goal | Show current step, next step, warnings, and session feedback |

### Core Pipeline

1. Record or stream camera frames.
2. Detect ArUco markers and align the workspace.
3. Warp frames into a stable top-view coordinate system.
4. Extract visual evidence from fixed ROIs and detected tools.
5. Estimate the current assembly step with FSM / HMM / state filter logic.
6. Send the state to AR guidance UI or offline replay tools.

### Why this approach

Instead of training a broad action-recognition model, the system focuses on **state progression** in a known assembly process.
That makes the pipeline easier to debug, explain, evaluate, and later deploy in a real-time AR setup.

---

## 2. Assembly Task Definition

The current task is modeled as a fixed sequence.

| State | Meaning |
| :--- | :--- |
| `S0` | Empty workspace / no box |
| `S1` | Box placed |
| `S2` | Lid closed |
| `S3` | Screw A done |
| `S4` | Screw B done |
| `S5` | Screw C done |
| `S6` | Screw D done |

The expected state progression is:

```text
S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6
```

The state estimator is designed to prefer this ordered progression while still using visual evidence from the frame.

---

## 3. System Architecture

### Hardware Layer

- **AR client / wearable display**
  - camera input or streamed frames
  - operator-facing guidance overlay
  - session control and local feedback
- **Python inference server**
  - image processing
  - YOLO / MediaPipe / ROI feature extraction
  - state estimation
  - replay and evaluation scripts
- **Physical workcell**
  - industrial enclosure parts
  - screwdriver and screws
  - ArUco markers
  - fixed tabletop or mat

### Software Layer

- **Unity client prototype**
- **Python server and offline replay tools**
- **OpenCV ArUco detection and homography warp**
- **YOLO 3-class detector**
- **ROI template and ROI delta features**
- **MediaPipe auxiliary hand signal**
- **FSM / HMM step reasoning**

---

## 4. Current Vision and State Features

The current `session_17` pipeline combines multiple evidence sources.

| Feature Source | Purpose |
| :--- | :--- |
| ArUco markers | Calibrate and warp the workspace into a stable view |
| ROI templates | Compare key regions such as box/lid/screw positions |
| ROI delta | Detect visual change around screw ROIs |
| YOLO `driver` | Locate screwdriver metal part |
| YOLO `handle` | Stabilize tool detection when the handle is visible |
| YOLO `screw` | Add direct evidence for screw locations |
| MediaPipe | Optional auxiliary hand/index information |
| Continuous scores | Replace hard 0/1 proximity features with smooth values |
| HMM transition | Smooth the state sequence over time |

MediaPipe is intentionally treated as a supporting signal because hand occlusion can make it unstable during screw tightening.

---

## 5. Current Benchmark

The best verified offline result on `session_17` is:

| Model | Accuracy | Macro-F1 |
| :--- | ---: | ---: |
| Framewise v2 | 88.24% | 89.52% |
| FSM v2 | 91.60% | 93.23% |
| HMM v2 | **94.12%** | **94.85%** |

Notes:

- `S0` is correctly detected for all 7 frames.
- Most remaining errors are short delays near state boundaries.
- The current parameters are tuned for the recorded `session_17` frame rate.

Result files:

```text
docs/session17_hmm_v2_status.md
docs/assets/session17_hmm_v2/timeline_best_role3.png
docs/assets/session17_hmm_v2/s0_zoom_best_role3.png
docs/assets/session17_hmm_v2/metrics_best_role3.csv
docs/assets/session17_hmm_v2/mismatches_best_role3.csv
```

---

## 6. Required Files Before Running

Large runtime files are not committed to this repository.

Prepare the following files locally:

```text
data/raw_sessions/session_17/
models/yolo/driver_standard_model/best-3.pt
```

Expected YOLO classes in `best-3.pt`:

```text
driver
handle
screw
```

The repository already includes the lightweight configuration, labels, scripts, and reference templates needed to run the current pipeline.

Important included files:

```text
configs/
labels/labels_segments.csv
refs/roi_templates_v2/
scripts/
server/vision/
server/state/
```

---

## 7. Repository Structure

```text
.
├── client_unity/                  # Unity / AR client prototype
├── configs/                       # Marker layouts and ROI layouts
├── data/                          # Local raw sessions, not tracked
├── docs/                          # Project docs and result reports
│   └── assets/session17_hmm_v2/    # HMM result plots and CSV summaries
├── labels/
│   └── labels_segments.csv         # Offline GT segments for evaluation
├── models/                        # Local model weights, not tracked
├── refs/
│   └── roi_templates_v2/           # Warped ROI templates
├── scripts/                       # PowerShell setup and run scripts
├── server/
│   ├── app/                        # Server entry points
│   ├── state/                      # FSM / HMM / state reasoning
│   ├── tools/                      # Utility tools, including ArUco marker generation
│   └── vision/                     # Warp, YOLO, MediaPipe, ROI features
└── tests/
```

The ArUco marker generation tools are kept because marker-based workspace alignment is still part of the AR pipeline.

---

## 8. Quick Start

### 8.1 Environment Setup

Use Windows PowerShell with Python 3.11:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
py -3.11 -m venv .venv_mp
.\.venv_mp\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\server\requirements.txt
```

Or run the helper script:

```powershell
.\scripts\setup_env_v2.ps1
```

### 8.2 Check Required Package Layout

```powershell
.\scripts\check_package_v2.ps1
```

### 8.3 Run the Full Session17 Pipeline

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

### 8.4 Run HMM Only

If the feature files already exist:

```powershell
.\scripts\run_hmm_v2_only.ps1
```

---

## 9. Current Best HMM Configuration

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

These values should be retuned when the frame rate, camera setup, workspace layout, or object placement changes.

---

## 10. Development Roadmap

### Phase 1: Recording and Replay

- collect assembly sessions
- maintain offline replay scripts
- keep labels and output timelines easy to inspect

### Phase 2: Marker Alignment and ROI Features

- detect ArUco markers
- warp the workspace to a stable top view
- maintain fixed ROI definitions and reference templates

### Phase 3: Object and Tool Evidence

- use YOLO detections for driver, handle, and screw
- use MediaPipe only as an auxiliary signal
- combine ROI and detector evidence into continuous features

### Phase 4: State Reasoning

- compare framewise, FSM, and HMM outputs
- tune transition behavior and state boundary delay
- prepare an online state filter for the AR runtime

### Phase 5: AR Integration

- connect server state output to the Unity client
- display current step, next step, and warnings
- log sessions and replay decisions for review

---

## 11. Notes for Reviewers

This repository is an AR assembly guidance project, with the current offline HMM pipeline serving as the most reproducible step-recognition baseline.

The design priorities are:

- stable workspace alignment,
- interpretable visual evidence,
- ordered step reasoning,
- easy replay and debugging,
- and a clear path toward real-time AR feedback.
