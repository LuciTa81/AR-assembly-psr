# 위치 계산 거부 원인 분리 (2026-10-07)

## 범위와 결론

카메라/Unity를 실행하지 않고 기존 저장 사진, 수치 좌표와 로그로 조사했다.
새 보정, 마커 이동, 인식 임계값 조정, 사진/영상 저장, 외부 전송은 없다.

마커 네 개 중 세 개의 중심이 일직선에 놓이는 일부 조합에서
현재 IPPE 방식의 homography 계산을 지지하는 독립 제약이 부족해진다.
이전 코드는 이 경우도 `No physical workspace pose above the mat`로만 보고했다.
이 문구만으로 카메라가 실제로 매트 아래에 있다고 판단해서는 안 된다.

이번 변경은 구조적인 실패를 미리 거부하고 실패 종류/마커 ID를 남기는 보강이다.
새 좌표 계산기를 도입하거나 표시 유효 시간을 늘린 것이 아니며,
깜빡임 감소나 실물 정합 개선을 새로 검증한 결과는 아니다.

## 실제 저장 자료에서 재현

- 사진: `C:/Users/fresh/Downloads/Beast_View_Retry_20261006_fd277ffc/workspace-view.png`
- SHA-256: `7734b85be9fe73592fb3100bb119dd63218d628be990dd3dc6a4f6ab3cc73dea`
- 작업대: `beast-workspace-comfort-layout-20261006-v1`
- OpenCV: 4.14.0.
- 마커 0, 1, 2는 모두 Y=285mm로 일직선에 있다.
- 저장 사진에서 검출된 미등록 ID 17은 계산에서 제외한다.

| 계산에 사용한 ID | 기존 결과 | 수정 후 결과 |
| --- | --- | --- |
| 0,1,2,4,5 | tracking, RMS 2.5756px | 동일 |
| 0,1,2,4 | No physical workspace pose | IPPE 배치 제약 부족으로 명시적 거부 |
| 0,1,2,5 | No physical workspace pose | IPPE 배치 제약 부족으로 명시적 거부 |
| 0,1,4,5 | tracking, RMS 2.7959px | 동일 |
| 0,2,4,5 | tracking, RMS 1.6991px | 동일 |
| 1,2,4,5 | tracking, RMS 1.5855px | 동일 |

정상 네 마커 조합까지 일괄적으로 다섯 개를 요구하도록 바꾸지 않았다.
다섯 개 중 세 개가 일직선인 경우도 남은 두 개로 제약이 충분하면 그대로 통과한다.
위 RMS는 기존 계산 결과의 회귀 비교이며 실제 나사 정합 오차의 정답값은 아니다.

## 마지막 착용 로그와의 관계

`viture_aruco_rt_20261006_215103_9c13d797a2da`의 프레임 12269~12467 전체 199개:

- tracking 163개.
- 물리 pose 없음으로 보고된 거부 18개: 모두 마커 네 개.
- 마커 부족 거부 15개.
- 재투영 오차 거부 3개.

이것은 앞선 HTTP 표본 154개 집계와 다르게 전체 프레임 로그 집계다.
당시 로그에는 보인 ID 목록이 없으므로 18개 모두가 같은 배치 문제였다고 확정하지 않는다.
다음 실행부터 `presentation_diagnostics.marker_ids`가 결과/상태 로그에 함께 남는다.

## 수정 내용

1. `workspace_projection.require_ippe_support`: 정규화한 마커 중심으로
   identity homography의 독립 제약 수를 검사한다. 기존 평면 분포 검사는 유지한다.
   rank tolerance는 정규화 좌표에서 수치적 퇴화를 구분하는 값이며 재투영 오차 한도가 아니다.
2. 초기 solver 결과 없음, nonfinite 후보만 반환, 유한하지만 물리 조건 불충족을
   서로 다른 오류 문구로 구분한다. 어느 경우에도 새 좌표를 제공하지 않는다.
3. `presentation_bridge`가 실제 관측한 알려진 마커 ID를 진단 로그에 보존한다.
4. 기존 150ms 만료, 3px RMS/5px 최대 오차, 모호성 거부, 매트 위 카메라 조건은 유지한다.

합성 장면에서는 기하 제약이 충분한 조합에서도 IPPE가 NaN을 반환하는 수치 사례가 있었다.
따라서 배치 검사 통과를 추적 성공으로 간주하지 않는다.
일부 퇴화 조합에서 기존 solver/refinement가 우연히 값을 반환하는 경우도 있었으므로,
그 조합은 이제 solver 호출 전에 명시적으로 거부한다.

SQPNP 대체 계산도 오프라인에서 비교했다. 좌표를 반환할 수 있었지만 일부 결과는
다섯 마커 기준 계산과 차이가 있었고 실물 정답이 없다. 다른 solver의 후보/모호성 검증을
끝내지 않았으므로 실행 경로에는 추가하지 않았다.

## 검증

- 원인 구분과 누락된 ID 기록 테스트의 수정 전 실패를 확인한 뒤 구현했다.
- 여섯 마커 중 네 개를 고르는 15개 조합의 기하 제약 검사를 추가했다.
- 실제 사진의 숫자 좌표만 `tests/realtime/fixtures/workspace_pose_comfort.json`에 저장했다.
  이미지나 사용자 모습은 포함하지 않으며 카메라 없이 여섯 가지 부분 조합을 재현한다.
- 정상 조합의 계산 값 유지, 퇴화 조합 거부, solver 결과 없음/NaN 거부를 확인했다.
- 전체 Python 테스트: **392 passed**.
- 카메라/Unity 재실행과 착용 검증은 하지 않았다.

## 보류 이유 UI 연결 (2026-10-07)

위치 추적 진단을 조립 단계 안내와 분리해 표시하도록 연결했다.

- Python 관측 응답과 presentation 진단에 선택 필드 `reason_code`를 추가했다.
  기존 예외 문구의 분류는 서버 한 곳에서 수행하며, 원문 `reason`과
  `analysis_reason`은 그대로 남긴다. 기존 results/overlay 로그에도 코드가 기록된다.
- Unity SBS 하단은 A 고정 참조/UNVERIFIED 표시를 유지하면서 마커 부족, 배치 조건 부족,
  계산 실패, 위치 불확실, 갱신 지연을 짧은 영어로 설명한다.
  기존 visibility gate와 150ms 만료는 바꾸지 않았다.
- 관제 화면은 영상 아래 별도 줄에 같은 원인을 한국어로 표시한다.
  상태 데이터의 capture-to-client age를 사용하며, 서로 다른 frame_id의 진단은 쓰지 않는다.
  연결 끊김/만료 후에는 이전 마커 오류를 현재 원인처럼 표시하지 않는다.
- 카메라 위치 추적 성공은 안경 실물 정합 성공이나 Unity에서 원이 실제로 보인다는 확인이 아니다.
  관제의 정상 문구에도 A 고정 참조와 안경 정합 미검증을 명시했다.
- 오래된 서버의 reason_code 누락이나 알 수 없는 코드는 일반적인 위치 확인 불가로 표시한다.
  조립 단계, 인식 임계값, calibration profile, solver는 바꾸지 않았다.

검증 결과:

- Python 전체 400 passed; C# NUnitLite 208 passed; Node 21 passed.
- Unity Editor 실제 loopback HTTP/JSON/cancel smoke 46 checks 통과.
  `outputs/unity_p1/pose-feedback-smoke-20261007.log`
- Windows Player 빌드 성공.
  `outputs/unity_p1/build-20261007-130319-091.log`
- Playwright 합성 입력: 데스크톱 1440x900/모바일 390x844 각각 8개 상태 통과.
  문구 잘림/영역 겹침/수평 넘침/페이지 오류 없음.
  `outputs/supervisor_pose/browser-report.json` 및 같은 폴더의 PNG.
- 카메라와 Beast Player는 실행하지 않았다. 브라우저 사진은 합성 UI만 포함한다.
  Unity 안경 화면 가독성과 깜빡임 개선을 실측한 결과는 아니다.

## 다음 단계

후속 수치 로그/재생 구현과 실행 검사까지 마쳤다.
현재 상태는 [오프라인 준비 상태와 검증 순서](beast_offline_readiness_20261007.md)에 정리했다.

보류 이유 UI 연결과 모의 검증은 완료했다.
다음에는 저장 숫자 fixture와 로그로 위치 실패/갱신 지연을 다시 분리해,
카메라 없이 재현할 수 있는 안정화 후보를 먼저 검증한다.
실제 착용 검사에서는 원의 정합, 보류 문구 가독성, 깜빡임을 함께 확인한다.
실물 배치 변경이나 solver 교체는 자동 적용하지 않는다.
마커 배치를 바꾸는 경우 작업대 등록과 눈별 정합의 재검증 범위를 먼저 정한다.

## 참고

IPPE의 homography 기반 계산과 대체 PnP 방법의 성격을 확인하는 데
[IPPE 공식 저장소](https://github.com/tobycollins/IPPE)와
[OpenCV PnP 문서](https://docs.opencv.org/4.12.0/d5/d1f/calib3d_solvePnP.html)를 참고했다.
이 문서의 수치와 실패 사례는 현재 로컬 코드 및 저장 자료에서 직접 재현한 결과다.
