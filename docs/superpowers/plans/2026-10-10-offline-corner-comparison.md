# Offline Corner Comparison Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this bounded, approved offline extension.

**Goal:** 착용 시험 없이 기존 사진의 모서리 방향 후보와 동일 trace 비교를 준비한다.

**Architecture:** 기존 중심 solver/report는 보존한다. 별도 CLI가 사진에서 이미 추출한
수치 fixture와 명시적인 약 70mm 가정으로 미검증 후보를 만들고 두 solver를 같은 기록에 적용한다.
후보는 보고서 안에만 포함하며 실제 프로필/Unity/실시간 호출부에 연결하지 않는다.

**Tech Stack:** 기존 Python, NumPy, OpenCV, pytest. 새 의존성 없음.

**Spec:** `docs/beast_tracking_corner_readiness_20261010.md`의 최소 후속 순서.

## Constraints

- 카메라, Unity, 외부 영상 전송, 새 서버, 커밋/푸시 없음.
- 출력은 새 파일만 허용. 원본 프로필/trace/사진은 읽기 전용.
- 3px RMS/5px 최대 오차와 모호성 검사 유지. 비교를 통과시키려고 조정하지 않는다.
- reference 사진으로 얻은 방향과 약 70mm 변 길이는 실측이 아니다.
- 마커 3의 방향은 이 사진에 없으므로 생성하지 않는다.
- 카메라 자세의 프레임 간 변화에는 사용자 움직임이 포함된다. 이를 흔들림/광학 정확도라고 부르지 않는다.

## Tasks

- [x] `tests/realtime/test_corner_tracking_report.py`: 합성 정답, 서로 다른 마커 회전,
  프로필 불일치, 누락/0개/미등록 관측, 카메라 금지, 출력 덮어쓰기 금지를 먼저 검사한다.
- [x] `server/realtime/corner_tracking_report.py`: `reference_candidate`, `compare_trace`,
  CLI를 구현한다. 기존 `tracking_report.selected_rows/numeric_evidence`와 solver를 재사용한다.
  전체 분모/수치 관측 분모, 마커 조합별 결과, 양쪽 통과 시 좌표 차이를 분리한다.
- [x] 동일 저장 trace 비교를 실행하고 한계/다음 실측 준비를 기존 readiness 문서에 기록한다.
- [x] `docs/beast_overlay_ux_next_20261010.md`: 공식 UX 자료와 연구 초록을 근거로
  기존 카메라 화살표/둘레선, Unity A REF 상태를 구분하고 후속 순서를 정리한다.
- [x] 대상 및 전체 pytest, 독립 리뷰, 결과 확인. live 검증 완료를 주장하지 않는다.

## Review Focus

- 사진/fixture와 제공 프로필의 좌표·왜곡·해상도 불일치.
- 검출 순서를 화면 왼쪽 위로 재정렬하거나 반사된 방향을 정상으로 만드는 오류.
- 0개/누락 관측을 통과 분모에서 제거해 과장하는 결과.
- stale 관측을 source analysis가 정상이라는 이유로 표시 가능으로 보고하는 오류.
- 기준 사진 자체의 재적합 결과 또는 두 계산 간 차이를 독립 정확도로 해석하는 오류.

## Execution Record

- 새 API에 대한 18개 실패를 확인한 후 구현했다. 개선/손실 분리 집계 검사도
  실패를 확인한 뒤 추가했다. 미등록/불완전 입력 검사까지 새 테스트 19개 통과.
- 기존 report/projection 포함 대상 123개 통과.
- Ruling: 별도 활성화 가능한 보정 파일 대신 비교 JSON 안에 후보를 포함한다.
  실측되지 않은 후보를 live 프로필로 혼용할 가능성과 새 파일 로더를 줄인다.
- 같은 기록 2,973행에서 기준 102/후보 1,240 통과. 기준만 통과 76도 명시하고 채택을 보류했다.
- 독립 리뷰는 중요한 결함 없음. 실제 기록 재계산의 공통 필드도 일치했다.
- 전체 pytest는 두 번 모두 522 통과/기존 Tk 초기화 1 실패. 단독 및 관련 48개는 통과.
  원인 미확정으로 readiness 문서에 남겼다. 전체 green 완료로 간주하지 않는다.
- 카메라/Unity/실측은 실행하지 않았다. UX는 기존 기능 대조와 출처 있는 설계 메모만 작성했다.
