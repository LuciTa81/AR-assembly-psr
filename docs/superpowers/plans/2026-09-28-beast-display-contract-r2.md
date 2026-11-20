# R2 Display Coordinate Contract

Status: complete (software only), 2026-09-28. User approved continuing the software-first roadmap.

Goal: calculate and exchange separate eye-local coordinates without camera capture,
device activation, optical calibration fitting, or automatic guidance.
Parent: 2026-09-27-beast-software-first-roadmap.md, stage R2.

## Decisions

- Keep realtime_v1; add optional spatial with beast_spatial_guidance_v1.
- Input is a target A-D in OpenCV camera coordinates (X right, Y down,
  Z forward, mm), camera/workspace ID + SHA256, pose frame ID and original
  Python perf_counter timestamp_ms. Invalid tracking must not supply a target.
- Use two independently specified 3x4 projection matrices ONLY in an explicitly
  synthetic profile. This is a math/transport fixture, not Beast optics or a
  decision about the H1 calibration model. Do not load real candidate points.
- Output uses eye-local top-left pixel coordinates, Full SBS left/right order,
  per-eye 1920x1080, profile binding, original pose identity, age, visibility and reason.
  calibration_status=synthetic and display_alignment_verified=false are mandatory.
- target_visible means geometrically drawable for a synthetic test, NOT real
  guidance permission. No renderer or normal runtime is connected in R2.
- Recalculate pose age at each HTTP read from the original pose timestamp,
  independent of the state timestamp. Hide both coordinates past 150ms.
  RTT/local elapsed and duplicate/reorder client history belong to R3.
- Invalid configuration raises ValueError. Invalid individual targets return a
  hidden payload with null eye coordinates; never clamp coordinates onto an edge.

## Tasks

- [x] 1. Python synthetic projection and typed optional payload, failing tests first.
  Files: server/realtime/display_calibration.py, schemas.py,
  tests/realtime/test_display_calibration.py, tests/fixtures/spatial_guidance_v1.json.
  Cover asymmetric eyes, axis/unit/depth, invalid input/binding, stale/future clock,
  no synthetic-to-verified promotion, fixture equality and strict JSON.
- [x] 2. HTTP nested-payload isolation and pose freshness, failing tests first.
  Files: overlay_http_server.py, tests/realtime/test_overlay_http_server.py.
  Cover independent pose/state ages, repeated reads, no mutation/refresh,
  absent payload compatibility, actual loopback HTTP.
- [x] 3. Unity DTO and shared fixture parsing; ordinary rendering unchanged.
  Files: GuidanceSnapshot.cs, tests/unity/SpatialContractTests.cs, GuidanceTests.csproj,
  client_unity/Assets/Editor/SpatialContractSmoke.cs, docs/beast_display_contract.md.
  Verify the same Python-produced contract in NUnit and actual Unity JsonUtility.
- [x] 4. Full Python/NUnit tests, Unity smoke/build, one scoped independent review.
  Keep pre-existing dirty work. No commit/push/deploy; retain ledger for continuation.

Verification: full pytest 234 passed; NUnit 94 passed; actual Unity spatial
JsonUtility smoke 13 passed; existing correspondence HTTP/JSON smoke 37 passed;
Windows build passed. Independent scoped review found no actionable defects.
The reviewer independently reran 51 focused Python tests and reported 46
additional in-memory checks; these are not counted as permanent suite tests.

## Completion

Known synthetic results agree across Python and Unity; invalid/expired geometry
does not remain visible. Record separately that H1 optical validation and R3
render integration remain outstanding. No hardware test is required in this stage.

## Review Focus

Check original pose timestamp vs newer state timestamp, nested mutation, hidden
failure coordinates, eye-local conventions, synthetic provenance, missing JSON
fields/defaults, and backward compatibility. Do not expand into unrelated dirty
work, H1 fitting, R3 rendering, or production infrastructure.
