# C3.1: mixed visible-marker history regression

## Observed failure

The first C3 wearer test reported that covering one marker immediately hid the
target. The saved numeric log contains 118 pose frames: 30 `tracking`, 8
`learned_corners`, 39 `invalid_corner_ids`, 24 `need_three_markers`, 9
`map_expired`, and 8 `corner_pose_uncertain`.

The full-marker observations alternated between sets such as `0,2,3,4,5` and
`0,1,2,4,5`. C3 intersected IDs across every retained full-marker sample. One
different set could remove marker 1 from a learned map despite multiple later
observations. Four-marker observations containing that ID were then rejected.
This is a reproduced software defect, not solely an RMS threshold issue.

Evidence is preserved in `.local/c3-first-wearer-20261125.txt` and
`.local/c3-first-wearer-poses-20261125.txt`. No new image/video was saved.

## Narrow correction

- Consider the union of observed IDs, but require four real observations per ID.
- Build each marker's median and even/odd validation maps from its own samples.
- Require support for every currently visible marker; do not invent missing data.
- Expire each marker using its own last full-marker observation (30 seconds).
- Report insufficient per-marker support as `map_marker_warmup`.
- Log map readiness and observation counts under `BeastCornerMap`.

The 8/4-sample windows, minimum three noncollinear markers, geometry/ambiguity
checks, 3px/3mm agreement tests, and legacy detector fallback remain unchanged.
No optical-flow bridge or frozen-pose display was added.

## Verification

- Alternating five-marker sets reproduced the defect before the correction.
- Python suite: 44 passed.
- JVM suite: 41 passed, zero failures/errors.
- Candidate build and lint passed; lint has zero errors and 22 warnings.
- Fold7 Android instrumentation: **11 tests passed**, runner 11.149 seconds.
  Includes mixed-five-marker regression and rejection of an ID observed only once.
- Instrumentation log: `.local/c31-device-validation-20261125.txt`.
- Candidate and test APK installed successfully via wireless ADB.
- Existing v1 package was not updated. No camera or network recording was started
  by the verification run.

Candidate: `releases/AR-Assembly-Tracking-C3.1-20261125.apk`

SHA256: `EE7F286E30EDAEC6DC1ED884D3554839FD5BB0A0288626EFF213450B30EA175C`

## Replay and remaining limits

`scripts/replay-first-c3-wearer.py` replays returned pose observations, which may
already contain legacy-detector fallback corners. It is not an exact replay of
the raw precise-detector input/history and has no physical target ground truth.

In that diagnostic replay, C3.1 returned 50/118 poses; 19 of the 39 frames logged
as `invalid_corner_ids` returned a pose. The remaining frames still encounter
geometric consistency, insufficient detection, or warmup checks. These figures
do not establish physical accuracy or prove that the wearer symptom is solved.
Report: `pose-comparison/c31-first-wearer-replay.json`.

An offline-only model grouped by full visible-ID set returned 40/118, including
11/39 affected frames. It was rejected for this APK. Its Python experimental
class/report remain available; it was not ported to Android.

Calibration hashes rechecked unchanged:

| Asset | SHA256 |
| --- | --- |
| camera-profile.json | 25F025BC5C2F71E4C83E6645E5CDC742BDA81CD75D30C55FF7E5ACA99924872E |
| workspace-profile.json | 5D4F4C6610AF3264E0583EB64B038B3D66B12A9FC4844849D21D4F770D5C7ACC |
| eye-projection.json | 1127D29FB5022D005373D12EB0A8886FABAFA53C852AC4BB3FD281CCD10904F3 |

## Next wearer check (not yet completed)

Open explicit `pose_probe` with target D; user starts the 30-second test.
Keep the usual five visible markers for 5-8 seconds, cover only one lower marker
for about 5 seconds, then uncover it. Preserve camera pose and workspace layout.
Compare D alignment as well as visibility, and inspect real marker count, map
readiness, rejection reason, and eye/display bounds. No tightening, calibration
adjustment, photos, video, or server recording is required.

At handoff the phone was charging at 11% and no Beast external display was
connected. Reconnect and confirm Full SBS before starting; do not start camera
automatically.

## C3.1 착용 재시험 결과 (2026-11-25 21:32~21:33 KST)

- 사용자가 직접 시험 시작. Full SBS 3840x1080, 30초 후 자동 종료.
- 카메라 수신 566프레임 중 숫자 진단 130개를 기록했다. 아래 수치는
  전체 카메라 프레임이나 독립 시험 횟수가 아니라 분석 관측 수다.
- 로그: `.local/c31-wearer-20261125-213349.txt`.
- 새 사진/영상 녹화, 서버 저장, 보정 변경은 하지 않았다.

| 실제 검출 개수 | 양안 표시 조건 통과 / 관측 수 | 숨김 사유 |
| --- | ---: | --- |
| 5개 | 41 / 41 | 없음 |
| 4개 | 37 / 37 | 없음 |
| 3개 | 22 / 25 | 초기 지도 준비 1개, 위치 일치 검사 거부 2개 |
| 0~2개 | 0 / 27 | 최소 검출 개수 미달, 대부분 초기 구도 준비 구간 |

4개 조합 `0,1,2,5`는 24/24, `0,1,2,4`는 11/11,
`0,2,4,5`는 2/2 표시 조건을 통과했다. `invalid_corner_ids`는 0건이다.

3개 조합 `0,1,4`는 17/17, `1,2,5`는 4/4, `0,2,4`는 1/1 통과했다.
반면 `0,2,5`는 2/2가 `corner_pose_uncertain`으로 거부됐다.
각 조합의 의도적 가림 여부/지속 시간까지 확인한 시험은 아니다.

안정적인 다섯 마커 구간이 시작된 21:32:53.104 이후 숨김은 세 구간이다.

| 숨김 로그 시각 | 복귀 로그 시각 | 분석 프레임 시각 차이 | 사유 |
| --- | --- | ---: | --- |
| 21:32:57.818 | 21:32:58.212 | 407ms | 3개에서 위치 일치 검사 거부 |
| 21:33:11.646 | 21:33:11.880 | 249ms | 검출 2개 |
| 21:33:12.946 | 21:33:13.196 | 253ms | 검출 1개 |

이 시간은 숫자 로그 사이의 간격이며 실제 디스플레이 소등 시간을 직접
측정한 값은 아니다. 로그만으로 실제 나사와의 절대 정확도를 알 수 없다.

착용자 확인: **"유지됐고 위치도 대체로 맞았어"**.

판정: D 원의 단일 마커 가림 시험은 첫 실사용 통과로 기록한다. 일부 3개
검출 조합에서도 표시를 확인했지만, 모든 조합/장시간/전체 A~D를 검증한
것은 아니다. v1 교체나 전 조합 개선 완료로 판정하지 않는다.
다음 검증은 같은 보정에서 좌우 가림/복귀를 반복하고 A~D 위치를 비교하는
것이다. 남은 짧은 탈락은 별도 개선 대상으로 유지한다.

## 후속 전체 안내 시험

전체 안내에서는 진단과 다른 5마커 조건이 남아 가림 시 숨김이 재현됐다.
위의 통과 판정은 D 진단 모드에만 해당한다. 원인, C3.2 연결 수정과 회귀
시험은 `PARTIAL_TRACKING_C32_20261125.md`에 기록했다. C3.1을 전체 안내
가림 대응 완료본으로 사용하지 않는다.
