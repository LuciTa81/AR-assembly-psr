# Observation freshness clock diagnosis (2026-10-30)

## Scope and plan

First step of the approved stabilization roadmap: remove avoidable freshness
measurement error without changing the 150 ms limit or holding stale geometry.
No camera, Unity, SDK settings, exposure or calibration activation in this step.

Local Python 3.12.14 reports `time.monotonic` using GetTickCount64 with 15.625 ms
resolution. `time.perf_counter` uses QueryPerformanceCounter with reported
0.0001 ms resolution. The existing FrameSource already uses perf_counter.

A camera-free clock sampling experiment found intervals measuring 142.714 to
149.302 ms with perf_counter but 156 ms with monotonic. These are examples of
possible early expiry, not measurements of the recorded camera frames.
The 24 stale events in capture-05 cannot be retrospectively corrected: that
recording contains only the coarse timestamps. Real processing delay remains.

Implementation plan:
1. Reproduce early expiry and mixed clock epochs with deterministic tests.
2. Use perf_counter consistently in workspace_live_preview,
   display_observation_server and presentation_bridge. Preserve the original
   FramePacket timestamp instead of converting to a coarse clock.
3. Label new session/trace clock provenance, preserving historical files and
   existing field names. Update synthetic test sources to the same clock.
4. Run focused and full Python tests. Record results and limits below.

Completion means the observation path uses one precise monotonic clock, valid
146 ms samples remain valid, and samples older than 150 ms or in the future
remain rejected. It does not mean live flicker or optical alignment is solved.

No timestamp may be refreshed when analysis finishes or an HTTP request arrives.
Unity continues receiving age_ms, not host absolute counter values. The old
received_at_monotonic field name remains descriptive: perf_counter is monotonic
here, but its epoch must never be mixed with historical GetTickCount64 values.

Reference: [Python 3.12 time](https://docs.python.org/3.12/library/time.html#time.perf_counter).

## Implementation and verification

- Three new regression tests failed before the fix: worker receive timestamp,
  HTTP observation age, and bridge source-clock preservation.
- Camera receipt, analysis, observation HTTP and preview now use perf_counter.
  The bridge preserves FramePacket.timestamp_ms rather than translating epochs.
- New session metadata and pose traces identify the timestamp clock. Historical
  records are unchanged. Existing field names and Unity age_ms remain compatible.
- Focused tests: 114 passed. Full Python suite: 537 passed, no skips or errors
  (41.871 seconds). The first full run hit sandbox filesystem permissions; the
  authorized rerun completed and produced the JUnit report below.
- Independent read-only code review found no concrete defect in the changed scope.
- Replaying all 145 capture-05 records with their original recorded ages reproduced
  waiting=1, tracking=105, stale=24 and pose_rejected=15, with zero mismatches.
  This checks unchanged decisions, not a reduction in historical stale events.
- A second 0.65-second clock-only sample reproduced 143.162-149.055 ms precise
  intervals measured as 156 ms by the coarse clock. Overlapping sampling windows
  are not independent trials and are not a camera failure rate.

Evidence is in `C:/Users/fresh/Downloads/AR_Beast_Diagnostics_20261030/`:
- `freshness-clock-analysis.json`: clock metadata and historical replay.
- `freshness-clock-full-tests.xml`: complete Python suite results.

No camera or Unity was started, no new images were captured, and the 150 ms
freshness limit, pose-quality gates, detector defaults and calibration profiles
were not changed. Live flicker improvement and optical alignment remain unverified.
Clock resolution does not bound camera, transport or rendering latency.

## Next step

After a fresh readiness confirmation, use one short live comparison to check
display continuity with the same detector and physical setup. If genuine stale
frames remain, separate capture intervals from analysis time before any tuning.
Then reconcile current workspace coordinates with recognition warp/ROI references;
do not expand eye calibration or activate the unvalidated corner solver yet.
