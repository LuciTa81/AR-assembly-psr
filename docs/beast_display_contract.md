# Beast 눈별 표시 좌표 계약 (R2)

2026-09-28. 소프트웨어 계산/전달 단계이며 **실제 광학 보정이 아니다.**
R3 일반 안내의 합성 SBS 연결까지 구현했으며, 실제 보정 모델 선택/계수 추정은 H1이다.
이 단계에서는 카메라 실행, 안경 착용 시험, 외부 전송을 하지 않는다.
2026-10-06에는 아래 H1 오프라인 후보 계산 도구를 추가했다. 일반 런타임이
지원하는 합성 전용 프로필 및 Unity 계약은 변경하지 않았다.

## 입력과 계산

`server/realtime/display_calibration.py`의 `project_display(profile, target, current_ms)`:

- `target_id`: A/B/C/D. 카메라 영상의 2D 픽셀이 아닌 `camera_xyz_mm`을 입력한다.
- 카메라 좌표는 OpenCV 기준 X 오른쪽, Y 아래, Z 전방, 단위 mm다.
  기존 workspace_projection의 pose에 대해
  `Rodrigues(rvec) @ workspace.targets[target_id] + tvec.reshape(3)`으로 구한다.
- 호출자는 현재 검증을 통과한 pose만 공급해야 한다. 마커 유실 시 과거 pose를
  현재 관측으로 대체하지 않는다. 이 연결은 아직 일반 런타임에 추가하지 않았다.
- 카메라/작업대 profile ID와 SHA-256을 표시 프로필의 바인딩과 비교한다.
- `pose_frame_id`, `pose_timestamp_ms`는 원본 관측의 값이다.
  timestamp는 Python 서버와 같은 perf_counter 시간축의 캡처 반환 시각(ms)이다.
  상태 추론 완료 시각이나 HTTP 요청 시각으로 바꾸면 안 된다.
  기존 monotonic 기록을 연결할 때 같은 시간축이라고 가정하지 말고 변환을 명시해야 한다.

현재 지원하는 프로필은 `beast_display_projection_synthetic_v1` **한 종류뿐**이다.
좌우 각각 3x4 행렬 P에 대해 `q=P@[X,Y,Z,1]`, `pixel=q[:2]/q[2]`로 계산한다.
합성 fixture의 행렬/눈 간 간격/초점 값은 테스트용 수치이며 실제 Beast 사양이 아니다.
실제 수집 후보 5개를 불러오거나 보정 계수로 사용하지 않는다.
H1에서 다른 보정 모델을 선택하더라도 출력 픽셀 계약은 재사용할 수 있다.

### H1: 눈별 후보 계산 (2026-10-06)

`server/realtime/display_fit.py`는 수집된 대응점 중 명시적으로 선택한 관측만
읽어 좌우 3x4 투영행렬 후보를 계산한다. NumPy SVD를 쓰는 정규화 DLT이며,
안경의 광학계를 핀홀 투영으로 근사할 수 있다는 가정 아래의 초기 후보다.
수집한 점에 잘 맞는 것과 미관측 자세의 실물에 잘 맞는 것은 다르다.

입력 manifest 예시:

```json
{
  "schema_version": "beast_display_fit_dataset_v1",
  "points": [
    {"path": "../session/point-001.json", "pose_id": "front", "split": "fit"},
    {"path": "../session/point-003.json", "pose_id": "front", "split": "fit"}
  ]
}
```

`pose_id`는 작업자가 같은 수집 자세로 구분한 그룹이다. 같은 자세를 다시 저장한
파일을 모두 추가하지 않고 눈별 최종 관측 하나를 고른다. 카메라와 눈별 시점이
순차 수집이므로 두 파일의 3D 좌표를 하나로 합치지 않는다. 각 파일에서 실제
저장 대상으로 선택한 눈의 좌표만 사용한다. 함께 들어 있는 반대 눈 좌표를
새로운 관측으로 세지 않는다. 파일 경로는 manifest 기준 상대/절대 경로다.

```powershell
python -m server.realtime.display_fit --dataset "<dataset.json>" --camera-profile "<camera-candidate.json>" --workspace "<workspace-candidate.json>"
```

- 원본 수집 파일은 수정하지 않고, 카메라/Unity를 켜거나 서버에 전송하지 않는다.
- 프로필 ID/해시, 눈 선택, Full SBS 해상도, 저장 당시 관측 신선도·품질 및
  `camera_xyz = R @ world_xyz + t`의 일치를 확인한다. 마커 개수는 ID 목록과
  같아야 하며, 저장한 카메라 픽셀도 보정값으로 재투영한 결과와 일치해야 한다.
- 동일 관측과 같은 자세의 같은 눈을 중복 계산하지 않는다. 한 자세를 계산용
  `fit`과 확인용 `check` 양쪽에 배정하면 거절한다.
- DLT 계산은 눈별 최소 6개 점부터 가능하다. 같은 평면/직선에 몰리거나 수치적으로
  퇴화한 배치는 계수를 만들지 않는다. 최소 개수 충족은 보정 품질 통과가 아니다.
- 계산용 오차와 확인용 오차를 각각 RMS/max/점별 값으로 기록한다. 확인용 점은
  보정행렬 계산에 사용하지 않는다. 현재 최소 확인 계획은 눈별 2개다.
- 오차 수치를 기록할 뿐 자동 합격 기준으로 사용하지 않는다. `candidate_fitted`도
  수학적 후보가 계산됐다는 뜻이며 광학 정합/깊이/편안함 검증 완료가 아니다.
- `display_fits/fit-<unique>/report.json`에만 결과를 기록한다. 부족할 때는
  `needs_fit_points`, 계수는 null이며 추가 개수를 표시한다. 종료 코드 1은 미완료
  데이터/배치, 2는 입력 오류, 0은 후보 계산 완료를 뜻한다.
- 결과 형식은 `beast_display_fit_review_v1`이고 기존 합성 프로필 로더가 거절한다.
  모든 결과는 `activation_status=not_activated`, `calibration_valid=false`,
  `display_alignment_verified=false`이며 자동으로 실제 안내에 사용하지 않는다.

DLT 근거: [Oxford Imaging Geometry](https://robots.ox.ac.uk/~az/tutorials/tutoriala.pdf),
[CMU Geometric Camera Calibration](https://www.cs.cmu.edu/~seitz/course/SIGG99/slides/seitz-calib.pdf).

### 현재 수집 자료의 계산 준비도

새 작업대 배치의 두 세션에서 반복 저장을 제외하고 다음 6개 파일을 선택했다.
manifest는 로컬 `display_fits/datasets/comfort-20261006-review.json`에 있다.

| 자세 | 세션 | 왼눈 | 오른눈 |
| --- | --- | --- | --- |
| 편한 정면 | ba7f017bbd6a4a78be23911ef171cd7d | point-001 | point-003 |
| 약간 오른쪽 | 74510324a63c4ad68d87f2cb48da63fd | point-001 | point-003 |
| 가까운 자세 최종 저장 | 74510324a63c4ad68d87f2cb48da63fd | point-009 | point-008 |

이는 계산 준비도 검토를 위한 선택이며 최종 정합 확인을 대신하지 않는다.
`fit-20261006T085825Z-1b453bf3` 결과는 양쪽 모두 fit 3/check 0,
`needs_fit_points`였다. 계수는 생성하지 않았다. 화면 좌표 범위는 왼눈 가로 118/
세로 22 px, 오른눈 가로 130/세로 34 px로 좁다. 가까운 자세에서 느낀 깊이 차이와
반복 관측 사이의 위치 변동도 해결된 것으로 보지 않는다.

다음 수집 계획은 기존 점들의 착용/표시 설정 일관성을 확인한 뒤 계산용 3자세와
독립 확인용 2자세를 추가하는 것이다. 같은 한 점만 계속 저장하지 않고 화면의
가로·세로 위치와 작업 거리가 달라지게 한다. 같은 평면에 몰리는 경우 더 필요하다.
안경 재착용·화면 거리/크기 변경으로 이전 점이 무효라면 필요한 점을 다시 수집한다.
수집 중에는 0DoF, Full SBS 및 표시 설정을 고정한다.

초기 검증: 새 21개 포함 Python realtime 351개 통과. 알려진 좌우 행렬의 합성 관측으로
계산에 쓰지 않은 위치의 재투영을 확인했고, 부족/퇴화/중복/바인딩 불일치/오래된
관측 거절과 원본 보존을 검사했다. 이후 독립 검토에서 지적한 마커 개수/카메라
픽셀 일관성 검사를 보강했고, 후보 계산 테스트 25개를 재실행해 통과했다.
실안경 자동 추적, Unity 변경, 커밋/푸시는 이번 후보 계산 작업에 포함하지 않았다.

추가 수집: 사용자가 착용/표시 설정을 유지했다고 확인한 뒤 메타데이터만 수집했다.
`7ee46c62a43341fd9179eda83d5c1bdb`의 point-001(왼눈), point-002(오른눈)은
고개를 조금 숙인 `upper-view` 자세이며, 사용자가 두 눈 저장과 편한 겹침을 확인했다.
`comfort-20261006-plus-upper.json`으로 분석한 `fit-20261006T090834Z-9e269bbd`는
양쪽 fit 4/check 0, `needs_fit_points`다. 세로 좌표 범위는 왼눈 238 px,
오른눈 246 px로 늘었지만 계수는 아직 생성하지 않았다. 사진/영상은 저장하지 않았다.
다음 자세 조절은 이 첫 수집의 제한 시간 안에 저장되지 않아 별도 세션으로 재개했다.

### 추가 수집 후 후보 계산 결과

재개 세션 `953627d2a0cd478ba7cd11ae721ba8f7`에서 다음 관측을 선택했다.
사용자는 두 자세 모두 눈별 저장과 편한 양안 겹침을 확인했다.

| 자세 | 왼눈 | 오른눈 | 선택 기준 |
| --- | --- | --- | --- |
| 화면 오른쪽에 A가 보이는 자세 | point-001 | point-003 | 오른눈 반복 저장 중 마지막 하나 |
| 약 10~15 cm 더 먼 자세 | point-005 | point-007 | 눈별 반복 저장 중 마지막 하나 |

`comfort-20261006-six-fit.json`에는 기존 3자세와 새 3자세의 눈별 최종 관측을
합쳐 fit 6/check 0씩 배정했다. 원본 파일과 기존 manifest는 보존했다.
`fit-20261006T091603Z-b77bccc7`은 **전체 rejected_geometry, 활성화하지 않음**이다.

- 왼눈: 수학적 후보는 생성됐고 계산용 RMS 8.14 px/max 13.88 px다.
  독립 확인 자료가 없으므로 실제 정합 합격이 아니다.
- 오른눈: `Points behind fitted eye or invalid projection`으로 거절했다.
  진단용으로 계산한 투영식에서 기존 `closer-final` 관측의 동차 투영 깊이가
  -19.04였다. 다른 다섯 점과 부호가 달라 행렬 전체의 부호 반전으로 해결되지 않는다.
  실제 나사가 눈 뒤에 있거나 사용자의 양안 겹침 확인이 틀렸다는 뜻은 아니다.
- 새 오른눈 반복 저장 후보를 조합한 4가지 경우 모두 같은 유효성 거절이 재현됐다.
  반복 파일 선택 하나의 우연한 문제로 해결되지는 않았다. 원본 선택을 결과에 맞춰
  바꾸거나 검사 조건을 완화하지 않았다.
- 직접적인 거절 원인은 확인했지만 수집 오차, 착용 변화, pose 추정 오차,
  핀홀 근사 및 최소 점 수의 민감도 중 어느 것이 주원인인지는 아직 확정하지 않았다.
  기존 가까운 자세를 우선 재확인할 필요가 있으며, 해당 점을 오류로 단정해 삭제하지 않는다.

다음 단계는 카메라를 끈 상태에서 자료 일관성을 검토하고, 필요하면 가까운 자세를
재측정하여 비교하는 것이다. 유효한 양쪽 후보가 확보된 뒤 계산에 쓰지 않은
별도 자세와 A-D 위치에서 실물 정합을 확인해야 한다. 최소 6개 수집 완료를
자동 추적 완료로 취급하지 않는다. 선/화살표의 실제 SBS 활성화도 아직 보류한다.

재개 수집은 300초 제한으로 종료됐고 Unity도 종료를 확인했다. 사진/영상 저장이나
외부 전송은 하지 않았다. 최종 소프트웨어 검증은 후보 계산 25개를 포함한
Python realtime **355개 통과**이며, 광학 보정 통과를 의미하지 않는다.

## Python에서 Unity로

### 별도 H1 후보 추적 시험 (2026-10-06)

가까운 자세를 재측정한 세션 `3a28023efb7f431584f36c85a7170e24`에서
왼눈 point-006, 오른눈 point-009를 선택했다. 사용자는 최종 양안 겹침이 편하다고
확인했다. 기존 가까운 자세를 대체한 비교 manifest는
`comfort-20261006-near-retest-six-fit.json`이며 원본 자료는 삭제하지 않았다.
`fit-20261006T092415Z-e580f383`에서는 양쪽 모두 양의 투영 깊이를 갖는 후보가
계산됐다. fit RMS는 왼눈 6.53/right 0.46 px, check 0이며 아직 미검증이다.
재측정으로 수학적 거절이 해소됐지만 이전 오류의 물리적 원인이 확정된 것은 아니다.

사용자 승인에 따라 기존 수동 SBS 시험에만 후보 추적 모드를 추가했다.
`display_fit --export-probe`는 기존 report 외에
`beast_candidate_projection_probe_v1` 형식의 `candidate-probe.json`을 만든다.
좌우 3x4 행렬은 Unity JSON 호환을 위해 각각 row-major 12개 숫자로 내보낸다.
유효한 양쪽 후보가 없으면 내보내지 않는다. 일반 안내용 보정 프로필은 아니다.

`run_beast_unity.ps1 -Beast -StereoAlignmentProbe -DisplayObservationConfig <config>
-CandidateProjection <candidate-probe.json> -ProbeSeconds 30`으로 명시적으로 실행한다.
서버는 기존 유한 시간 observation server를 사용하며 카메라 번호는 Beast 0번이다.

- 카메라/작업대 ID와 해시, Full SBS 출력 3840x1080 및 좌우 채널을 확인한다.
- Space로 채널을 확인한 뒤 A의 최신 3D 관측을 눈별로 투영한다.
- 이 모드에서는 방향키 위치 편집과 Enter 저장이 비활성화된다.
- 150 ms 예산에는 관측 나이, 요청 왕복 시간, 수신 후 시간이 포함된다.
  같은 frame으로 유효 시간이 연장되지 않으며 연결 실패 뒤 같은 frame을
  다시 받아도 기존 점을 복구하지 않는다.
- 마커 유실/만료/화면 밖/눈 뒤의 점은 양쪽 원을 숨긴다. 화면 변경과
  시간 만료, Q/Esc는 시험을 종료한다.
- `CANDIDATE`/`UNVERIFIED`를 표시한다. 후보 시험이 기존 synthetic-only
  일반 안내 계약이나 `calibration_valid=false`를 변경하지 않는다.
- 기존 수집과 동일하게 사진/영상을 저장하거나 외부로 전송하지 않는다.

구현 검증: Python realtime 359개, C# NUnit 186개 통과.
Unity Windows 최종 빌드 `build-20261006-183753-191.log` 성공.
실제 후보 파일을 Unity JsonUtility로 읽고 투영/뒤쪽 점/바인딩 불일치를 검사한
`candidate-smoke-20261006.log`도 통과했다. 실안경 정합 판정과 별개다.

독립 검토에서 확인한 실행 제한도 보강했다. 후보 모드는 런처와 실제 Unity
초기화 모두 30초 초과를 거절하며, 3840x1200에는 1080용 후보를 적용하지 않는다.
생략한 후보 시험 시간은 30초로 설정된다. 기존 수동 시험의 300초 상한은 유지한다.

#### 첫 자동 원 시험과 남은 문제

2026-10-06 18:34 KST, `player-20261006-183433-291.log`.
실제 출력은 3840x1080, 후보 화면 제한은 30초였다. 카메라 세션
`cd88635e5004449c8c015f27a7b3e227`은 연결 준비를 포함한 45초로 종료됐다.
좌우 표시 좌표가 새 관측에 따라 갱신됐고, 사용자는
**A 근처에는 대략 맞지만 깜빡임이 매우 심하다**고 보고했다.
광학 정합 정확도/깊이/다른 나사에서의 품질 통과로 해석하지 않는다.

카메라 세션 집계는 tracking 238/pose_rejected 184 프레임이다. 이는 화면 표시율이
아니다. Unity 로그에는 NO POSE, STALE이 반복됐고 서버 종료 후 CONNECTION ERROR도
기록됐다. 사진/영상이나 새 대응점 파일은 저장하지 않았다.

시험 후에는 후보 모드의 조회 간격만 100 ms에서 약 33 ms로 줄였다.
10 Hz 입력/30 ms 처리/20 ms RTT를 가정한 회귀 테스트에서 불필요한 만료 구간이
줄어드는 것을 확인했다. 실제 카메라 성능 측정이나 재착용 시험 결과는 아니다.
150 ms 신선도 예산, 마커 유실 시 숨김, 수동 수집의 조회 간격은 변경하지 않았다.
이 변경 이후 실안경 재시험은 하지 않았다.

다음 우선순위는 (1) 변경된 조회 간격의 실제 효과 확인, (2) 남은 마커/pose 유실
원인과 지연 분리 측정, (3) A 원의 안정성 및 독립 자세 정합 확인이다.
그 뒤에 A-D 연결선과 목표 화살표를 실제 SBS에 확대한다.

기존 `realtime_v1`에 선택적 `spatial` 필드만 추가했다.
없거나 null이면 기존 상태 메시지로 취급한다.
하위 버전은 `beast_spatial_guidance_v1`이다.

| 필드 | 의미 |
| --- | --- |
| display_profile_id, camera/workspace profile ID·SHA256 | 좌표가 계산된 프로필 식별 |
| calibration_status, display_alignment_verified | 현재 반드시 synthetic, false |
| coordinate_convention | eye_local_pixels_top_left |
| display_mode, channel_order | full_sbs, 왼쪽 반쪽=왼눈 / 오른쪽 반쪽=오른눈 |
| eye_width, eye_height | 각 눈 1920x1080, 전체 framebuffer는 3840x1080 |
| target_id | 계산 대상 A-D |
| pose_frame_id, pose_timestamp_ms, pose_age_ms | 상태 프레임과 별개인 원본 위치 관측 |
| left_pixel, right_pixel | 각각 [x,y]. 좌상단 원점, 아래로 +y |
| target_visible, reason | 시험 좌표 표시 가능 여부와 거절 이유 |

**target_visible=true는 실제 안내 허가가 아니다.**
synthetic/미검증 프로필은 실물 안내에 사용하지 않는다.
일반 Unity presenter/receiver/state는 명시적 노트북 합성 시험 설정에서만
눈별 원을 그린다. 실제 보정 프로필 로더는 아직 없으며 일반 실행은 미보정이다.
기존 명시적 중앙 시험 원/수동 SBS 시험은 별개 기능이다.

SBS 렌더링 시에만 오른눈의 x에 eye_width를 더한다. 왼눈 좌표를 오른눈에 복제하지 않는다.
R3 renderer는 IMGUI의 좌상단 원점을 사용하므로 y를 뒤집지 않는다.
한쪽이라도 화면 밖/카메라 뒤/눈 투영면 뒤이면 두 좌표 모두 null로 숨긴다.
화면 가장자리로 clamp하여 다른 물체를 가리키지 않는다.

## 시간과 실패 처리

- /state.json은 원본 pose_timestamp_ms를 기준으로 매 응답마다 pose_age_ms를 다시 계산한다.
  새로운 조립 상태가 같은 pose를 재사용해도 위치의 유효 시간은 연장되지 않는다.
- 0~150ms만 시험 좌표가 유효하다. 초과 시 stale_pose,
  누락/미래/비정상 시각이면 invalid_pose와 함께 좌표를 지운다.
- 상태의 frame_age_ms 및 기존 상태 표시 500ms 예산과 별개다.
- Unity R3는 pose_age_ms + 요청 RTT + 수신 후 경과시간을 적용하고,
  같은 pose 재수신/역순에 대한 클라이언트 이력을 관리한다.
  클라이언트는 150ms 이상이면 숨겨 경계에서 보수적으로 동작한다.
  원시 Python/Unity 시각을 서로 직접 빼지 않는다.
- 나이는 센서 노출이나 실제 눈에 도달하는 광학 지연 측정치가 아니다.
- 다른 거절 이유: profile_mismatch, invalid_target, behind_camera,
  behind_eye, outside_display. 잘못된 프로필 구성 자체는 ValueError다.

## 검증과 재현

공동 수기 기대 fixture: `tests/fixtures/spatial_guidance_v1.json`.
카메라 좌표 [0,0,500]에서 왼눈 [1008,540], 오른눈 [908.8,539.62].
대칭 복사, 단위 오류, Y축 뒤집힘, 원본 pose 나이 유실을 검출한다.

실행 명령(저장소 루트, 프로젝트 Python 환경 사용):

```powershell
python -m pytest -q
dotnet run --project tests/unity/GuidanceTests.csproj -- --noresult
python tests/unity/spatial_contract_fixture.py --output outputs/unity_p1/r2-spatial-python.json
.\scripts\build_beast_unity.ps1
```

실제 Unity JSON 검사는 batchmode/nographics에서
`-executeMethod ARAssembly.SpatialContractSmoke.Run`과
`--spatial-fixture <위 생성 JSON의 절대 경로>`로 실행한다.
이는 디스크의 합성 메타데이터 파싱 검사이며 카메라나 기기 출력 검사가 아니다.
별도 Python 테스트는 실제 loopback /state.json 전송도 검사한다.

R2 당시 검증: pytest 234개, NUnit 94개, Unity JsonUtility smoke 13개 통과.
Unity Windows 빌드 성공: outputs/unity_p1/build-20260928-004345-581.log.
독립 코드 검토에서 R2 범위의 수정 필요 사항은 발견되지 않았다.
R3 렌더/시간 이력, H1 광학 정합, 실제 추적 품질, 기존 범위 밖 변경은 이 판정에 포함하지 않는다.
기존 수집 HTTP/JSON smoke 37개도 재실행해 통과했다.

R3 검증: pytest242, NUnit146, Unity spatial smoke26, 수집 smoke37,
Windows 최종 빌드 및 실제 Player 렌더34장 검사 통과.
실행 방법과 남은 한계는 [R3 안내](beast_sbs_guidance.md)를 참조한다.
