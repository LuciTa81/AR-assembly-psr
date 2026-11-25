# Android 인터넷 관제 송신기 결과

검증일: 2026-11-23. Android 후보 구현 및 로컬 JVM 검증 완료. 후속 단계에서 Fold7 후보 설치와 카메라 없는 계측 테스트 4개까지 통과했다. 실제 기기 연결 코드 승인은 대기 중이며 카메라/외부 배포는 실행하지 않았다.

## 변경 범위

- `app/src/main/java/com/lucita/beastgate/RemoteSupervisorLink.java`: 기존 native dark UI에 LAN과 독립된 기본 OFF 토글, 서버 주소/기기 이름/명시적 동의, 8자리 코드와 만료 시각 표시.
- `RemoteSupervisorSampler.java`: main looper에서 기존 snapshot supplier만 읽는다. 실행 중 최대 4Hz, idle 1Hz, ready 이전에는 읽지 않는다.
- `RemoteSupervisorTransport.java`: HTTP 등록/승인 조회, 인증 후 ready 대기, protocol-1 wrapper, 최신 snapshot 한 칸, 재연결 및 종료 정책.
- `RemoteSupervisorPolicy.java`: HTTPS origin 검증, debug loopback HTTP 예외, 이름/재시도/샘플링 정책.
- `RemoteSupervisorCredentials.java`: worker의 Android Keystore AES-256-GCM 저장. endpoint를 AAD에 묶어 다른 endpoint로 토큰을 보내지 않는다. 평문 토큰을 preferences에 저장하지 않는다.
- `MainActivity.java`: 필드, 생성자 연결, `onStop` close, `onDestroy` dispose만 추가. 기존 snapshot/AR/카메라/LAN 동작은 수정하지 않았다.
- `app/build.gradle`: 고정 OkHttp 의존성 및 JVM 테스트 의존성.
- `app/src/debug/AndroidManifest.xml`, `app/src/debug/res/xml/remote_supervisor_network_security.xml`: debug에서만 localhost/127.0.0.1 cleartext 허용. release merged manifest에는 이 설정이 없다.
- JVM 테스트 2개 클래스, instrumented 테스트 2개 클래스, 본 문서.

`internet-supervisor/**`, 기존 SupervisorLink/State/Server, 보정/수학/좌표/임계값/타이밍/상태 의미는 변경하지 않았다. `.env.local`은 읽지 않았다. 커밋/푸시 없음.

## 계약과 수명주기

- `POST /pairing/request`: `{name}`만 보낸다. 이름은 trim 후 1~64자. 연결/코드 요청 전에 사용자 동의를 받는다.
- `POST /pairing/poll`: body 길이 0, `Authorization: Bearer <poll_token>` 사용. 정상 조회 간격 2000ms. 실패 후 재조회도 최소 2000ms이며 같은 poll secret을 사용한다.
- 코드 승인 대기에는 monotonic 12시간 상한을 둔다(2026-11-24 사용자 요청). 서버 만료 시각이 더 이르면 줄이고, 늘어나도 상한을 늘리지 않는다. 승인 응답의 `expires_ms`는 기기 credential 만료로 별도 처리한다.
- `/ws`의 첫 메시지는 `{role:"publisher",token}`. `{type:"ready"}` 이전 상태 전송 없음. 재접속 중 `stream_id`와 증가하는 `seq`를 유지한다. 새 사용자 ON은 새 stream이다.
- `protocol`, `stream_id`, `seq`, `sent_at_ms`, `state` wrapper. 기존 snapshot JSON의 의미는 그대로 유지한다. 메시지는 최대 16KiB, HTTP 응답은 최대 2KiB.
- worker 예약 작업은 현재 연결 세대당 1개. snapshot은 atomic latest 한 칸이며 callback별 작업 큐를 쌓지 않는다. WebSocket outbound queue가 비어야 다음 상태를 넣고, 5초 이상 정체되면 연결을 버리고 재접속한다. 중단 중 snapshot 재생 없음.
- 재시도는 지수 backoff+jitter, 1~30초. HTTP 401/403/410 또는 4401의 `Reauthenticate` 이외 사유는 중단하고 재등록을 요구한다. 정확히 `4401 Reauthenticate`만 재인증 연결을 허용한다. 다른 인증/정책 거절도 무한 재시도하지 않는다.
- 인증 DB 일시 장애의 `1013 Authentication unavailable`은 기존 credential을 보존하고 재접속한다. 재등록 API를 호출하지 않으며 새 연결에서도 ready 전에는 상태를 보내지 않는다.
- OFF/onStop는 현재 세대를 즉시 무효화하고 HTTP/WebSocket/예약 작업/sampler를 중단한다. 늦은 callback은 이전 세대에만 남는다. 자동 ON, background service, 카메라 제어 없음. onDestroy에서 worker/client를 dispose한다.
- 표준 TLS 검증 유지. redirect 및 숨은 HTTP connection retry 비활성화. 토큰은 URL/로그/UI에 노출하지 않는다. 기존 `allowBackup=false` 유지.

## 의존성 선택

Maven Central metadata/POM/AAR를 실제 조회했다. 최신 안정 버전은 `5.5.1`이나 Android AAR가 `minCompileSdk=37`을 요구하여 현재 SDK 36/AGP 8.11.1에서 AAR 검사에 실패했다. `5.4.0` AAR의 `minCompileSdk=36`을 확인하고 `com.squareup.okhttp3:okhttp:5.4.0`으로 고정했다. SDK/AGP/Kotlin BOM은 변경하지 않았다. 테스트용 MockWebServer/okhttp-tls도 5.4.0이다.

참고: [Maven metadata](https://repo.maven.apache.org/maven2/com/squareup/okhttp3/okhttp/maven-metadata.xml), [5.4.0 Android AAR](https://repo.maven.apache.org/maven2/com/squareup/okhttp3/okhttp-android/5.4.0/okhttp-android-5.4.0.aar), [공식 변경 이력](https://lysine.dev/okhttp/changelogs/changelog/).

주의: 공식 5.5.1 변경 이력에는 손상된 eMudhra intermediate 인증서 차단이 포함되어 있다. Google Play Services 기기는 자동 업데이트 대상이라고 명시하지만 이 Fold7의 실제 보안 업데이트 상태는 확인하지 않았다. 운영 전 기기 보안 업데이트 확인 및 SDK 37/최신 OkHttp 업그레이드를 별도 검토해야 한다. 커스텀 trust-all 또는 인증서 검증 우회로 해결하지 않았다.

## 테스트 증거

테스트 파일을 먼저 추가하고 `RemoteSupervisorPolicy`/`RemoteSupervisorTransport` 부재로 컴파일 RED를 확인한 뒤 구현했다. 추가 만료 경계 테스트는 실제 assertion RED를 확인했다: `Long.MIN_VALUE` 만료 시각의 뺄셈 overflow로 CODE가 표시되던 문제를 재현하고, 만료 시각 비교를 먼저 수행하도록 수정한 뒤 GREEN을 확인했다.

최종 Gradle 실행: exit 0, `BUILD SUCCESSFUL in 54s`.

```powershell
$env:JAVA_HOME='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/jdk/jdk-21.0.12.1+1'
$env:ANDROID_HOME='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/android-sdk'
$env:ANDROID_USER_HOME=Join-Path $PWD '.android'
$env:GRADLE_USER_HOME='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/gradle-cache'
& "$env:GRADLE_USER_HOME/wrapper/dists/gradle-8.14.1-bin/baw1sv0jfoi8rxs14qo3h49cs/gradle-8.14.1/bin/gradle.bat" --no-daemon :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug :app:processReleaseMainManifest
```

실행 위치: `C:/Users/fresh/Documents/Codex/Beast-Fold7-Gate`. 기존 `build.ps1`의 SDK/JDK 경로를 그대로 사용했다.

| 검증 | 결과 |
| --- | --- |
| JVM `RemoteSupervisorPolicyTest` | 5 tests, 0 failures/errors |
| JVM `RemoteSupervisorTransportTest` | 17 tests, 0 failures/errors |
| Debug 후보 APK | 빌드 성공 |
| AndroidTest APK | 빌드 성공, Fold7 실기 4 tests 통과 |
| `lintDebug` | errors 0, warnings 20 |
| Release merged manifest | debug cleartext 설정 없음, backup false 유지 |

JVM 범위: HTTPS/loopback URL, 이름, backoff 범위/jitter, 4401 사유, 샘플링 정책, 실제 HTTP 요청/빈 poll body/Bearer 헤더/2초 간격, 승인 응답 유실 후 같은 secret 재시도, endpoint 토큰 격리, ready gating, 최신 상태 wrapper, 재접속 순번, 폐기/만료/401 중단, 늦은 응답/OFF/재시작/dispose, redirect 거부, 자체 서명 TLS 거부, 응답 크기 제한, 5분 monotonic 상한 및 음수 만료 overflow.

독립 리뷰 후 `authenticationUnavailableKeepsCredentialAndReconnectsWithoutPairing` JVM 회귀 테스트 1개를 추가했다. 첫 publisher 인증 직후 ready 없이 `1013 Authentication unavailable`로 닫고, 저장 credential 동일 객체 유지, 동일 token 재인증, HTTP 요청이 `/ws` 2개뿐임, PAIRING/CODE/PAIR_REQUIRED/ERROR 미발생, 두 번째 ready 이후 상태 전송을 확인한다. 기존 Android 운영 로직이 이미 1013을 재시도하므로 운영 코드는 변경하지 않았다. 이 테스트 단독 실행은 exit 0 (`BUILD SUCCESSFUL in 22s`), 이어 위 전체 명령으로 JVM 합계 22/22 및 빌드/lint를 재검증했다. 후보/계측 APK SHA256은 아래 값과 동일하다.

TLS 테스트는 IPv4로 바인딩된 서버를 `127.0.0.1`로 지정했다. `localhost` IPv6 fallback의 연결 거절을 인증서 실패와 혼동하지 않도록 했고 실제 `SSLException`을 확인한다. 인증서 신뢰 완화는 테스트 client에도 없다.

instrumented 테스트 4개는 Keystore round-trip/endpoint AAD 변조/평문 비저장/비추출 키, main-thread 저장소 I/O 거절, main-thread idle sampler 및 종료, not-ready supplier 차단을 다룬다. 후속 설치 단계에서 실제 Fold7(SM-F966N)에서 실행하여 `OK (4 tests)`, 3.128초를 확인했다. 테스트 전용 Keystore namespace를 사용하며 실제 관제 인증값이나 보정을 변경하지 않는다.

## Fold7 설치 및 카메라 없는 검증

- 위 SHA256 후보와 계측 APK를 `adb install -r`로 설치했다. 두 설치 모두 `Success`이며 앱 데이터는 유지했다.
- `RemoteSupervisorCredentialsTest,RemoteSupervisorSamplerTest` 두 클래스만 실행했다. 카메라/AR 시작 테스트는 포함하지 않았다.
- 정상 `MAIN/LAUNCHER` 진입으로 앱을 열었다. `작업 시작`은 누르지 않았다.
- `adb reverse tcp:8787 tcp:8787`을 설정했다. 폰의 `http://127.0.0.1:8787`은 이번 로컬 개발 검증에만 사용하는 임시 경로이며, 외부망 서비스 주소가 아니다.
- 웹은 실제 GitHub 로그인 상태의 `기기·설정` 화면이다. 실제 Fold7 연결 코드 요청/승인은 사용자 입력 대기 중이다.

보고서: `app/build/reports/tests/testDebugUnitTest/index.html`, `app/build/test-results/testDebugUnitTest/TEST-*.xml`, `app/build/reports/lint-results-debug.html` 및 `.xml`. 경고에는 native Switch 권고, 문자열 리소스화, 기존/새 의존성 업데이트 권고 등이 있다. Gradle의 기존 deprecated 기능 및 사용자 홈 Android analytics 설정 접근 경고도 남아 있으나 빌드 실패는 없다.

## 산출물과 보존

아래 표는 2026-11-23 산출물이다. 2026-11-24의 15분 후보 및 이후 12시간 후보 검증은 `INTERNET_PAIRING_RESULTS.md`의 후속 절에 기록했다. 기존 보관 APK는 변경하지 않았다.

| 파일 | Bytes | SHA256 |
| --- | ---: | --- |
| `app/build/outputs/apk/debug/app-debug.apk` | 102938496 | `B240BBBB4F36ABBBE32E06F3B3C8DB96F9EF2E7E481B23CF6D535BA990761197` |
| `app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk` | 5530721 | `A5D9D30F7F18D4791357FC05FC00A772B42B806B205F5C8CF50FBAE79A050FAA` |
| 보존 `baseline/pre-internet-sender-20261123/accepted.apk` | 92321268 | `338C5E1843B3A126583A98D62496AACA78B15A98BC1F1E0E7B4565F2E0EDE0F0` |

- 동결 manifest: v1 90개 + standalone 61개 = 151개, SHA256 불일치 0.
- 작업 전/후 pre-internet checkpoint 전체 75개 파일 비교: 불일치 0.
- checkpoint의 기존 `app/src` 70개와 현재 비교: `MainActivity.java`의 최소 연결 훅만 변경. 기존 LAN, AR, 보정 assets, 205/205 좌표 및 모든 timing 파일은 hash 동일.

## 미검증과 계약 질문

실제 Fold7 UI/접근성/회전, 물리 네트워크 전환/혼잡/지연/배터리, 실기 AR 성능은 미검증이다. Android Keystore와 sampler는 위 카메라 없는 실기 테스트 범위만 확인했다. 실제 Node relay로 승인받은 폰은 아직 구동하지 않았다. 로컬 JVM transport 검증과 상위 작업의 합성 relay/BFF 검증은 실기 인터넷 관제 완료를 뜻하지 않는다. 현재 구현을 막는 계약 질문은 없다.
