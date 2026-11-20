# A 현재 착용 양안 기준점 시도

2026-10-31. 새 A 작업대 후보를 사용했다. 사진·영상 저장과 외부 전송은 없으며 숫자 관측과 Unity 로그만 남겼다.

- 사용자 확인: Full SBS / 0DoF / Extra Large / 4.5m / 같은 도수 렌즈 / 확장 모드.
- Windows와 Unity에서 Beast 3840 x 1080 출력을 확인했다.
- 기존 양안 모델은 착용 조건과 독립 검증에 불확실성이 있어 활성화하지 않았다. 새 setup_id로 한 자세만 수동 수집하려 했다.
- 관측/표시 연결 Python 검사: 95 passed in 21.95s. 이번에는 새 Player 빌드를 하지 않았다.

## 실행 경로 문제와 재시도

첫 세션 `08abefe7b5d5423d88ea3878440e4c88`은 다운로드 경로를 Unity 수집기가 거부했다. 원인은 기존 `IsLocalCollectionPath` 허용 경로 규칙이다. 카메라 서버를 중단했고 숫자 trace/summary를 보존했다. Unity 초기화 실패와 카메라 추적 실패를 혼동하지 않는다.

규칙을 완화하지 않고 기존 AppData 전용 수집 폴더로 재시도했다. 정상 수집 세션은 `f53c4d2e3561419ba731e6b18f728d2c`이며 원본 위치는 `C:/Users/fresh/AppData/Local/ARAssembly/beast-mvp/display_correspondence/f53c4d2e3561419ba731e6b18f728d2c`다. 앱 가상화로 실제 로그에는 Packages/OpenAI.Codex.../LocalCache/Local 경로가 표시된다.

## 결과

- Unity 정렬 창 정상 표시. 사용자가 원과 TRACKING을 확인하고 조절 중이라고 답했다.
- 숫자 관측 2,968개: tracking 2,083, pose_rejected 885. 조절·화면 확인 중 관측이 섞여 있어 정지 안정성 검증으로 해석하지 않는다.
- 단안 파일 15개만 저장됐다. 왼눈 5개, 오른눈 10개이며 동일 위치 반복 저장을 독립 보정점으로 세지 않는다.
- 양안 `pair_v2` 파일은 0개. 이후 좌우 위치를 다시 조절했으나 최종 양안 저장 전에 시간제한으로 끝났다. 사용자가 미완료라고 보고했다.
- 마지막 로그 위치: 왼눈 (860,432), 오른눈 (640,422). `resume-position-only.json`에 화면 복원용으로만 보존했다. 이 위치에 과거 카메라 관측을 붙여 보정점을 만들지 않는다.
- `summary.json`은 deadline 종료, Unity도 deadline_or_display_changed로 종료했다. 종료 직전 연결 오류는 서버 종료와 겹쳤으므로 마커 인식 실패로 집계하지 않는다.
- 카메라/Unity 프로세스 종료 확인. 기존 프로필과 자동 투영은 변경하지 않았다.

다음에는 사용자 준비 확인 후 마지막 화면 위치를 복원하고 눈별 저장, 3으로 양안 확인, 최종 Enter 순으로 마무리한다. 재착용/OSD 변경 시 setup_id를 새로 부여한다. 한 자세의 PAIR SAVED도 전체 자동 정합 완료를 의미하지 않는다.
