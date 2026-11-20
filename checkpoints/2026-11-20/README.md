# Pre-Mobile Checkpoint: 2026-11-20

This is an archival checkpoint, not a promotion of every candidate into the default runtime.
The original working trees, successful Windows build, A-D calibration, and launch profiles were left unchanged.

## Contents

- Repository root: the current Beast feature working tree, including Python perception and stage logic, Unity source, supervisor web UI, tests and design documents.
- `work/`: independent experiment runners, calibration analyses, Korean guidance candidates, presentation stability fixes, clipping fixes, and video-generation sources.
- `baseline/`: explicitly referenced camera, workspace and display projection profiles. Historical raw calibration collections remain in the local backup.
- `project/`: project-specific technical notes and scripts outside the Git working tree. Raw diagnostic JSON is excluded from publication.
- `presentation-sources/`: scripts from the user's presentation-source archive. These were preserved, not executed.
- `presentation/`: narration/subtitle and production notes; no PPTX or video binaries.

## Important Versions

- `work/AI-Assembly-Console/profile.json` records the existing desktop launcher bindings.
- `work/beast-reference-return-20261114/candidate-ABCD-joint-unverified.json` is the joint candidate used during the reported A-D distance/side tests. Its original candidate flags are preserved.
- `work/beast-action-guide-20261115/` contains the Korean action-guidance candidate and build source.
- `work/beast-preparation-text-20261116/` contains the later S0/S1 text-retention candidate and separate build source.
- `work/beast-line-clip-20261116/` contains the filming runner and clipping verification scripts.
- `work/beast-pose-continuation-20261116/presentation-rms32.json` records the 3.2 px presentation threshold candidate.
- `baseline/` contains explicitly referenced successful/candidate profiles from otherwise ignored output locations.
- Filming auto-advance remains at the archived 2-second setting. It is a filming-only timer, not a torque/fastening sensor.

## Restore Notes

1. Restore the intended version, not all candidate folders on top of one another.
2. Several historical scripts contain absolute Windows paths. Use the local backup manifest to reconstruct the original paths or deliberately rebind a separate installation.
3. Preserve calibration JSON bytes when comparing their recorded SHA-256 bindings. Do not silently rewrite paths inside calibration files and assume the old hash bindings still match.
4. Reinstall Python/Unity dependencies and obtain the VITURE SDK from the vendor. Dependencies, licensed SDK distributions, and generated Unity caches are not included here.
5. Generate fresh local observation/session credentials. Archived live client-config/token files are deliberately excluded.
6. Successful player binaries, PPT files, images, recordings, and raw session logs are retained in the separate local backup, not published in this branch.

## Pending Work

The requested 3-second auto-advance, box/lid automatic progression, head-locked 3D part preview, Galaxy Z Fold7 / Android 16 port, and phone-to-laptop live supervision have not been implemented by this backup operation.

## Verification Scope

This checkpoint verifies preservation and publication hygiene, not a new hardware acceptance test.
Historical test reports and trial notes describe their own dates and scopes. No camera or glasses session was started while making the checkpoint.
