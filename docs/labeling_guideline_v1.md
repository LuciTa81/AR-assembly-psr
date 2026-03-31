# Labeling Guideline v1

## 목적
본 문서는 AR 기반 산업용 인클로저 조립 세션에 대해
- step interval label
- ROI state label
을 일관되게 부여하기 위한 기준을 정의한다.

---

## 1. 전체 step state 정의

### S0 Idle_Open_Empty
- 인클로저가 비어 있음
- PCB가 올바르게 장착되지 않음
- 뚜껑이 닫히지 않음
- 조립 시작 전 상태

### S1 PCB_Placed
- PCB 더미 모듈이 인클로저 내부에 놓여 있음
- 방향이 올바르거나 이후 lid close로 넘어갈 준비가 된 상태
- 아직 lid는 닫히지 않음

### S2 Lid_Closed_Aligned
- 뚜껑이 닫힘
- lid 정렬 상태가 aligned로 판단됨
- 나사 체결은 아직 완료되지 않음

### S3 Screw_A_Done
- Screw A 위치가 done 상태
- B, C, D는 done이 아닐 수 있음

### S4 Screw_B_Done
- Screw A, B가 순서대로 완료된 상태

### S5 Screw_C_Done
- Screw A, B, C가 순서대로 완료된 상태

### S6 Screw_D_Done
- Screw A, B, C, D가 모두 완료된 상태

### S7 Finish
- 최종 조립 완료 상태
- 기본 기준:
  - 마지막 나사 완료 후 전체 조립 상태가 안정적으로 유지됨
  - 최소 1초 이상 추가 변동 없음
- 초기 버전에서는 `S6`와 `S7`을 엄격히 분리하기 어렵다면
  평가 시 하나로 합쳐 분석할 수 있음

---

## 2. 오류 정의

### E1 PCB_Missing
- PCB가 삽입되지 않은 상태에서 다음 단계 진행 시도

### E2 Lid_Misaligned
- 뚜껑이 닫혀 보이지만 aligned 기준을 만족하지 않음

### E3 Wrong_Order
- 정의된 순서를 따르지 않음
- 예:
  - lid close 전에 screw 단계 시도
  - screw B를 screw A보다 먼저 완료 처리
  - PCB 미삽입 상태에서 lid close 시도

### E4 Step_Not_Confirmed
- 시스템이 다음 step 완료를 확신할 근거가 충분하지 않음
- 주의:
  - E1, E2, E3처럼 물리적 공정 오류라기보다
    시스템 경고/미확인 플래그에 가깝다

---

## 3. ROI label 정의

### 3.1 PCB ROI

#### empty
- PCB가 ROI 안에 보이지 않음

#### wrong_pose
- PCB가 ROI 안에 있으나 방향/위치가 올바르지 않음

#### correct_pose
- PCB가 ROI 안에서 올바른 방향과 위치로 장착됨

#### occluded
- 손/도구/가림으로 인해 판단 불가

---

### 3.2 Lid ROI

#### open
- 뚜껑이 열려 있음

#### misaligned
- 닫힌 것처럼 보이지만 기준 정렬선과 맞지 않음

#### aligned
- 뚜껑이 정상 정렬 상태로 닫힘

---

### 3.3 Screw ROI

#### empty
- 나사가 없거나 체결 시작 전 상태

#### progress
- 체결 진행 중으로 보임
- 예:
  - 나사가 부분 삽입 상태
  - 드라이버 접촉 중
  - 완전 체결로 보기 애매한 중간 상태

#### done
- 해당 screw 위치가 완료 상태로 안정적으로 보임

---

## 4. interval labeling 원칙

- 각 프레임에 대해 단일 대표 step state를 부여한다.
- 상태 전이는 가능한 한 실제 조립 이벤트 직후부터 반영한다.
- 경계가 애매한 경우:
  - step interval은 보수적으로 이전 상태를 더 길게 유지한다.
- 손/도구로 일부 가려져도 문맥상 확실하면 직전/직후 상태를 참고할 수 있다.
- 판단 불가가 길게 지속되면 `E4 Step_Not_Confirmed` 검토

---

## 5. screw done 판정 기준

초기 기준:
- 해당 screw ROI가 `done` 형태로 보임
- 최소 2개 이상의 연속 프레임에서 동일하게 유지됨

주의:
- 한 프레임만 보고 done 처리하지 않는다.
- `progress`와 `done` 경계가 모호하면 `progress` 우선

---

## 6. finish 판정 기준

초기 기준:
- 마지막 screw 완료 후
- 전체 조립 상태가 안정적으로 유지되고
- 최소 1초 이상 추가 동작이 없음

필요 시 이후 데이터셋 구축 단계에서
`S6`와 `S7`을 병합할 수 있다.

---

## 7. 라벨링 우선순위

애매할 때 우선순위:

1. 명확한 물리 상태
2. 정렬 여부
3. 연속 프레임 문맥
4. 보수적 판정

즉, 애매하면 과감하게 다음 단계로 넘기지 않는다.

---

## 8. 판단 불가 처리

다음 경우는 판정 불가 또는 보수적 처리:
- 손으로 ROI 대부분 가림
- motion blur가 심함
- screw 상태가 한 프레임만 잠깐 보임
- lid 정렬선이 거의 보이지 않음

이 경우:
- ROI label은 `occluded` 또는 이전 안정 상태 유지
- step state는 보수적으로 유지

---

## 9. 현재 버전 주의사항

- 본 가이드는 실물 박스 도착 전 작성한 v1 초안이다.
- 실제 촬영 후 다음 항목은 수정 가능:
  - PCB correct_pose 기준
  - lid aligned 기준
  - screw progress/done 기준
  - finish 정의
