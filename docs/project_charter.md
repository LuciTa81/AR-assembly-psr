# Project Charter

## 1. Project Title
AR-Assisted Procedure Step Recognition for Industrial Enclosure Assembly

## 2. Objective
Build a Quest 3 based AR system that recognizes the current assembly step of a commercial industrial enclosure task and provides current-step guidance, next-step hints, warnings, and session logs.

## 3. Scope
- Single fixed workcell
- Single target object
- 8 assembly states
- 4 error flags
- ROI-based visual inference
- PEBF-based step reasoning
- Quest 3 AR overlay
- Offline recording/replay
- Runtime deployment on GTX 1660

## 4. Deliverables
- Session recording pipeline
- Replay and labeling tools
- ROI extraction pipeline
- FSM and HMM baselines
- ROI classifiers
- PEBF engine
- Unity AR client
- Evaluation report
- UML / WBS / QA documentation

## 5. Success Criteria
- Session recording and replay work reliably
- ROI extraction is stable
- Proposed method outperforms or is clearly justified against baselines
- Current step / next step / warning can be rendered in AR
- Quantitative evaluation and documentation are complete
