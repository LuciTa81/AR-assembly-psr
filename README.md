# AR-Assisted Procedure Step Recognition for Industrial Enclosure Assembly

An end-to-end graduation project for **AR-based assembly guidance**, focused on **procedure step recognition (PSR)** for a fixed-sequence industrial enclosure assembly task.

The system uses a **Quest 3 client**, a **Python inference server**, and a **part-evidence belief filter (PEBF)** to estimate the current assembly step from visual evidence and provide real-time AR guidance.

---

## 1. Project Overview

This project targets a **single fixed workcell** and a **single assembly object**:

- **Object**: Commercial industrial enclosure + dummy PCB module
- **Platform**: Quest 3 (main), school PC server (runtime), home PC with RTX 5090 (training)
- **Core pipeline**: 
  1. Session recording
  2. ArUco-based workspace alignment
  3. ROI extraction
  4. ROI micro-state classification
  5. PEBF-based step reasoning
  6. AR guidance + warning + logging

### Why this project matters

Instead of trying to solve full action recognition in a complex factory environment, this project focuses on a **controlled yet meaningful industrial assembly scenario**.
It aims to demonstrate that a lightweight, explainable, and deployable system can:

- guide novice operators,
- reduce step omission,
- log assembly sessions,
- and provide a practical path toward connected-worker and digital-twin extensions.

---

## 2. Scope

### In scope

- One fixed workcell
- One commercial enclosure assembly task
- Quest 3 AR interface
- Offline recording and replay pipeline
- ROI-based visual inference
- Proposed **PEBF** step reasoning engine
- Baseline comparison (**FSM**, **HMM**)
- Quantitative evaluation
- Session logging and replay

### Out of scope

- Robot control
- Full factory digital twin
- Multi-product generalization
- Humanoid learning
- Omniverse-first pipeline
- Ultra-low-latency RTP/UDP streaming
- VITURE Beast as primary platform

---

## 3. Assembly Task Definition

### Main States

| ID | Name |
|---|---|
| S0 | Idle_Open_Empty |
| S1 | PCB_Placed |
| S2 | Lid_Closed_Aligned |
| S3 | Screw_A_Done |
| S4 | Screw_B_Done |
| S5 | Screw_C_Done |
| S6 | Screw_D_Done |
| S7 | Finish |

### Error Flags

| ID | Name |
|---|---|
| E1 | PCB_Missing |
| E2 | Lid_Misaligned |
| E3 | Wrong_Order |
| E4 | Step_Not_Confirmed |

### ROI Classes

**PCB ROI**
- `empty`
- `wrong_pose`
- `correct_pose`
- `occluded`

**Lid ROI**
- `open`
- `misaligned`
- `aligned`

**Screw ROI**
- `empty`
- `progress`
- `done`

---

## 4. System Architecture

### Hardware Layer

- **Quest 3**
  - passthrough / camera input
  - AR guidance UI
  - session control and local logging
- **School PC (GTX 1660)**
  - ONNX Runtime inference
  - WebSocket server
  - latency benchmark
- **Home PC (RTX 5090)**
  - model training
  - ablation studies
  - visualization
  - ONNX export
- **Physical Workcell**
  - industrial enclosure + dummy PCB
  - 4 ArUco markers
  - matte single-color mat

### Software Layer

- **Unity (Quest 3 client)**
- **Python inference server**
- **OpenCV ArUco alignment + top-view warp**
- **ROI CNN classifiers**
- **PEBF step engine**
- **Evaluation and replay tools**

---

## 5. Repository Structure

```text
.
├── README.md
├── .gitignore
├── docs/
│   ├── project_charter.md
│   ├── state_definition.md
│   ├── risk_register.md
│   ├── wbs.md
│   ├── gantt.md
│   ├── uml_usecase.md
│   ├── uml_component.md
│   ├── uml_sequence.md
│   ├── uml_state.md
│   ├── cocomo_fp.md
│   ├── qa_plan.md
│   └── experiment_log.md
├── client_unity/
│   └── Assets/
│       └── Scripts/
│           ├── Core/
│           │   └── SessionController.cs
│           ├── Camera/
│           │   └── CameraCapture.cs
│           ├── Network/
│           │   └── WsClient.cs
│           ├── AR/
│           │   └── OverlayController.cs
│           └── Logging/
│               └── LocalLogger.cs
├── server/
│   ├── app/
│   │   └── main.py
│   ├── vision/
│   │   ├── marker_pose.py
│   │   ├── warp.py
│   │   ├── roi_defs.py
│   │   └── roi_cropper.py
│   ├── models/
│   │   ├── roi_cnn.py
│   │   ├── infer_onnx.py
│   │   └── export_onnx.py
│   ├── state/
│   │   ├── fsm_baseline.py
│   │   ├── hmm_baseline.py
│   │   └── pebf.py
│   ├── tools/
│   │   ├── label_intervals.py
│   │   ├── label_roi.py
│   │   ├── build_dataset.py
│   │   ├── evaluate.py
│   │   ├── visualize_timeline.py
│   │   └── benchmark_latency.py
│   └── pipelines/
│       ├── offline_replay.py
│       └── online_pipeline.py
├── data/
│   ├── sessions/
│   ├── annotations/
│   ├── roi_patches/
│   └── splits/
├── experiments/
└── tests/
```

---

## 6. Development Roadmap

### Phase 0 — Scope Freeze
- finalize task object, states, errors, and repo structure

### Phase 1 — Recording & Replay
- implement Quest 3 session recording
- build Python replay tool

### Phase 2 — Marker Alignment & ROI Extraction
- ArUco detection
- homography / top-view warp
- fixed ROI extraction

### Phase 3 — Dataset & Labeling
- pilot data collection
- interval labeling
- ROI labeling
- train/val/test split

### Phase 4 — Baselines
- FSM baseline
- HMM baseline

### Phase 5 — Proposed Method
- ROI classifiers
- PEBF implementation
- ablation studies

### Phase 6 — AR Integration & Runtime
- Unity ↔ server communication
- overlay for current step / next step / warnings
- ONNX runtime optimization on GTX 1660

### Phase 7 — Evaluation & Final Packaging
- same-subject / cross-subject evaluation
- latency benchmark
- QA and documentation

---

## 7. Proposed Method: PEBF

The proposed **Part-Evidence Belief Filter (PEBF)** does not rely on full action recognition.
Instead, it integrates:

- ROI-level visual evidence,
- contradiction penalties,
- persistence bonuses,
- and dwell-time constraints

to estimate the current assembly step robustly.

### Motivation

A fixed-sequence enclosure assembly task is better modeled by **state progression** than by frame-wise action classification.
PEBF is designed to be:

- lightweight,
- explainable,
- data-efficient,
- and compatible with real-time deployment.

---

## 8. Evaluation Plan

### Core Metrics

- Step Macro-F1
- Completion Accuracy
- Wrong-Order Recall
- Step_Not_Confirmed Precision / Recall
- End-to-End Latency
- FPS

### Additional Analysis

- same-subject vs cross-subject
- lighting split
- ablation on persistence / contradiction / dwell-time
- 10-minute runtime stability test

---

## 9. Quick Start (Planned)

### 1) Create Python environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Run offline replay

```bash
python server/pipelines/offline_replay.py
```

### 3) Run inference server

```bash
python server/app/main.py
```

### 4) Open Unity client
- start session
- calibrate workspace
- stream frames or replay session
- display step guidance on Quest 3

---

## 10. Current Status

This repository is being reorganized from an earlier vision/classification codebase into a dedicated graduation project structure for AR-based industrial assembly monitoring.

Planned milestones include:
- clean repo structure,
- reproducible session logging,
- ROI-based inference,
- and a polished final demo package.

---

## 11. Notes for Reviewers

This project intentionally prioritizes:
- **clarity over unnecessary complexity**,
- **step reasoning over generic action recognition**,
- and **deployable engineering over overly broad claims**.

The goal is not to solve all of Physical AI, but to build a disciplined, working, and well-evaluated PoC that can later grow into a connected-worker / digital-twin pipeline.
