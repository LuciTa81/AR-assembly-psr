# Repository Refactor Plan

## Current Uploaded ZIP
The uploaded repository is a clean image-classification repository with:
- a strong README style,
- a flat `models/` folder,
- root-level notebooks,
- and no dedicated docs / client / server split.

## Why it should be refactored for the graduation project
The AR assembly project needs:
- Unity client code,
- Python inference server,
- data/session management,
- documentation,
- baselines and evaluation,
- and runtime deployment code.

## Recommended changes
- move from a flat training-script repo to a system-oriented repo
- separate `client_unity/` and `server/`
- add `docs/`, `experiments/`, and `tests/`
- keep training, inference, evaluation, and runtime separated
- avoid notebooks as the main project interface

## Recommended first commit sequence
1. create new repo skeleton
2. add README + docs
3. implement Quest recording and Python replay
4. add marker / ROI pipeline
5. add baselines
6. add proposed PEBF
7. integrate Unity AR overlays
