# Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Quest 3 camera integration is delayed | Medium | High | Prioritize offline recording/replay first; use fallback capture if needed |
| R2 | ROI alignment is unstable | Medium | High | Adjust ArUco placement, improve warp pipeline, add calibration if necessary |
| R3 | Label ambiguity reduces model quality | High | High | Write labeling guideline before large-scale annotation; run pilot labeling first |
| R4 | GTX 1660 runtime is too slow | Medium | Medium | Keep classifiers lightweight, use ONNX Runtime, frame skipping, async processing |
| R5 | Error cases are underrepresented | High | Medium | Intentionally record error sessions instead of only successful ones |
| R6 | Schedule slips during exam periods | Medium | High | Use reduced-development weeks and defer non-core items |
| R7 | Final demo is unstable | Medium | High | Prepare replay-based fallback demo and regression test set |
| R8 | Scope creep from extra features | High | High | Keep VITURE, RTP/UDP, and synthetic data as optional stretch goals |
