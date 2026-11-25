# 작업 시간과 서버 녹화 복구 · 2026-11-25

## 원인과 변경

- Android 일반 실행에 300초 카메라 종료 제한이 있었다. 600초로 변경했다.
- 운영 서버는 RECORDING_ENABLED=false였다. 새 영상이 없었던 이유이며, 전송만 한 영상을 사후 복구할 수는 없다.
- 사용자 승인에 따라 RECORDING_ENABLED=true, RECORDING_MAX_SECONDS=600으로 변경했다.
- 파일별/사용자 전체 보관 한도는 각각 100,000,000 bytes 그대로다. 기존 2개 영상 20,104,027 bytes를 삭제하지 않았다.
- 녹화의 시간/용량 한도는 AR 종료 명령이 아니다. AR은 별도 앱 시간 제한, 사용자 종료, 최종 확인 완료, 장치 상태에 따라 종료된다.
- 최종 확인 후 10초 자동 종료는 유지한다. 진단 모드의 30/90/300초 제한도 유지한다.
- 녹화에는 폰의 상태 연결, 영상 공유, 서버 저장 동의가 필요하다. 서버를 켰다는 사실만으로 카메라나 새 작업을 시작하지 않는다.
- 저장 영상 메뉴에 서버 녹화 활성 여부를 표시한다. 실시간 관제도 서버 녹화 꺼짐과 폰의 영상/녹화 동의를 구분한다.
- 본인 전용 로그인·권한, 7일 보관, S3/IAM, NOVA, A~D 보정은 변경하지 않았다.

## 검증

- 변경 전 테스트로 5분 종료와 서버 활성 여부 필드 누락, 웹 비활성 안내 누락을 재현했다.
- Android 단위 테스트 41개, APK 빌드, lintDebug 통과. 기존 deprecation/analytics 쓰기 권한 경고는 남아 있다.
- 서버/웹 단위·통합 테스트 123개와 TypeScript 검사, Next.js 빌드 통과.
- Playwright로 서버 녹화 꺼짐/켜짐, 영상 목록, 다운로드·삭제 mock, 실제 합성 AVC 프레임 디코딩, 5개 화면 크기와 기존 UI 동작 검증.
- 서버 읽기 전용 smoke로 활성 상태, 600초, 파일/사용자 100MB, 기존 영상 2개 확인. 새 촬영/녹화는 시작하지 않았다.
- 운영 로그인 페이지 HTTP 200. Vercel READY 및 운영 별칭 갱신 확인.
- Fold7 192.168.200.191:38811에 데이터 유지 업데이트 설치. versionCode=12, versionName=1.4.2 확인.
- eye-projection.json, workspace-profile.json, camera-profile.json SHA256은 변경 전과 동일하다.
- 실제 착용 상태의 5분 경과/10분 종료 및 새 영상 저장 시험은 아직 하지 않았다.

## 배포와 백업

- 앱: app/build/outputs/apk/debug/app-debug.apk (1.4.2)
- 기존 설치 APK: ../.local/before-ten-minute-1.4.1.apk
- 소스 백업: ../.local/before-ten-minute-20261125.tar.gz
- 서버: /opt/ar-assembly/releases/20261125-06-ten-minute
- 이전 서버: /opt/ar-assembly/releases/20261125-05-work-history-idle
- 서버 DB/환경 백업: /var/backups/ar-assembly/pre-ten-minute-20261125T083944Z
- 웹: dpl_jL19VaLF5M5gzimdkQw1w1rAWkux
- 이전 웹: dpl_9ziU7UsvuW7YTfgTgszYPZ7SjWdw
- URL: https://ar-assembly-supervisor.vercel.app

이 문서는 SUPERVISOR_WORKSPACE_20261125.md의 이전 "녹화 꺼짐/Android 미변경" 상태 이후 업데이트다. 복구 시 서비스 코드와 환경만 이전 백업으로 되돌리며 새 영상/DB를 덮어쓰거나 삭제하지 않는다. APK 다운그레이드는 데이터 보존 가능 여부를 확인한 뒤 별도 수행한다.
