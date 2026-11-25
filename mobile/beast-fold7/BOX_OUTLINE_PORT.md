# Physical enclosure outline candidate

## Scope

- Preserve the accepted APK/source snapshot at `baseline/verified-part-preview-20261121` (53 files plus SHA256 manifest). APK SHA256: A173A10909DFA2EC793473C100FE3575CF9E73E99B56151F66A42FEE285E4B1A.
- Port frozen Unity `BoxOutlineProfile` geometry and the matching `rounded-box-124mm.json` without recalibrating A-D.
- 124 mm square, closed height 60 mm (existing approximation), lid height 10 mm, body height 50 mm. Rounded joins 3 mm are display approximations.
- Preparation box: body only, level 2. Preparation lid: lid prism only, level 3. A-D: lid prism only, level 2. Inspection: whole assembly, level 2. Stop: clear.
- Use current accepted WorkspaceTracker rotation/translation and unchanged EyeProjection for each point, then the existing native SBS Canvas layer. No camera-image compositing and no extra 3D engine for projected lines.
- Opt-in `box_outline` intent flag; previous `part_preview` mode remains available without the outline.
- Require valid pose, five markers, finite pose and both-eye in-bounds projection. Hide entire outline on rejected geometry or age over 500 ms. No changes to tracking gates, calibration, timers, ring colors or completion rules.

## Verification plan

1. Test stage selection, vertex counts/heights, profile binding and malformed inputs.
2. Compare geometry and projected coordinates with an independent replay of the frozen Unity formulas.
3. Test native canvas pixels in both eye halves, freshness, wrong display size, clear and unchanged green acknowledgement behavior.
4. Build/lint, Android regression suite, inspect synthetic replay screenshots; install only after passing.
5. User wearing trial remains required. No camera/photos/video started automatically.

## Implemented and verified (2026-11-21)

- `BoxOutline.java` loads a byte-for-byte copy of the frozen profile, binds its camera/workspace hashes, validates rectangular geometry, and generates stage-specific strokes (20/20/20/32).
- `MainActivity` enables this only with `--ez box_outline true`, also enabling the existing part preview/full preparation flow. Invalid outline initialization blocks starting. No tracking, optical fit, assembly timing or tool evidence changes.
- `StereoOverlayView` draws independent left/right paths behind existing text/rings, levels 2/3 at RGB (77,133,119)/(112,194,173), width 3/4 px. Invalid, future or >500ms-old poses hide the outline. Stop clears it; outline rendering cannot acknowledge the green cue.
- `generate_box_outline_fixtures.ps1` compiles the original frozen C# geometry with transport stubs. Fixture comparisons match each unique stroke rather than array order, because C# sorts equal-level strokes unstably. The initial order-based comparison failed; correcting this comparison required no geometry change.
- Build and lint passed (existing dependency/manifest-removal warnings remain). All 34 Android tests passed, including seven new outline tests and all 27 prior tests. Evidence: `box-outline-tests-device.txt`.
- Every reference world vertex matches within 1e-9 mm; independent eye-matrix projection comparison within 1e-7 px. Stored pose replay verifies the transform produces exactly the existing A-D camera coordinates within 1e-9 mm. These are implementation equivalence checks, not measured real-world alignment accuracy.
- Inspected synthetic native Canvas renders for body, lid, screw stage and inspection in `box-outline-native-qa-v2/`. No camera imagery was used or saved.
- Reverified all 53 checkpoint files against the manifest and the three live calibration assets against the checkpoint.
- Installed candidate and opened it at 03:32 KST. `BOX_OUTLINE_READY`, `TRACKER_READY` and `YOLO_READY` verified. No Beast display reported at launch; camera remains off. Physical alignment/comfort test pending.

## Restore / candidate selection

Current candidate: launch `com.lucita.beastgate/.MainActivity` with `--ez box_outline true`.
Previous behavior in the candidate APK: fresh launch with `--ez part_preview true` and no `box_outline` flag.
Exact rollback: reinstall `baseline/verified-part-preview-20261121/verified.apk` with `adb install -r`; then launch with `--ez part_preview true`. Do not uninstall or change calibration. Build source snapshot is in the same directory; external SDK/JDK/Gradle caches remain at their existing toolchain paths.

## First physical trial

2026-11-21 03:33 KST; user confirmed unchanged wearing/settings. Full SBS 3840x1080 and PARTS_READY verified. User started at 03:33:48.238; camera opened at 03:33:49.761. Body -> lid at 03:34:00.086, lid -> A at 03:34:06.501. Each stage produced 20 projected strokes; brief body-stage invalid observations hid the outline. Captured numeric log `box-outline-live-20261121-0333.txt`, then force-stopped the app after reaching A and verified no PID. No photos/video recorded.

User reported possible slight misalignment ("살짝 안맞게 된거 같지..?"). Do not promote as optically verified. Await which edges/direction and whether the unchanged A ring also looked offset; no calibration or geometry adjustment made in response yet.

Follow-up: user localized the possible mismatch to the lid near A, but did not see/compare the A ring. Direction and depth remain unknown. Next proposed trial: unchanged candidate, observe A ring and lid together for about 20 seconds after preparation, without driver interaction. Compare the ring with the screw head and the outline with the exterior lid edges; those references intentionally do not coincide. No offset adjustment justified yet.

Second trial: Full SBS and candidate readiness verified at 03:36:40 KST. User started the unchanged full-flow app. Body -> lid at 03:37:04.080, lid -> A at 03:37:10.744. Intended A observation window was 20 seconds, but tool evidence near A armed the existing flow and A -> B occurred at 03:37:24.276 (green timer 3015 ms). Monitor stopped the app immediately on detecting this transition; PID absence verified. A was available for about 13.5 seconds, not the full 20. Numeric log: `box-outline-A-compare-20261121-0336.txt`. No image/video recording or calibration changes. Whether the tool was actually near A and whether the comparison was sufficient remain user-observed questions; do not infer them from the detector output.

User feedback: A ring was generally aligned; lid outline was also roughly aligned. No geometry/calibration change requested. User instead requested a small translucent sphere appearance for the active screw, now tracked separately in `SPHERE_MARKER_RESULTS.md`. This qualitative feedback is not a measured accuracy claim.
