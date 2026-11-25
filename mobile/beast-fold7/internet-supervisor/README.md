# AR Assembly Internet Supervisor

현재 범위: **로컬 중계/기록 + Next.js 관제 + GitHub 로그인 + 기기 연결 코드 + Fold7 실제 idle 수신/정상 재시작 후 자동 재연결**. 실기 연결은 USB reverse 기반이다. EC2 전용 환경을 준비 중이며 실제 외부망 관제, Vercel 배포와 영상 전송은 아직 완료하지 않았다. 기존 보관본/보정/NOVA는 유지한다. 최신 배포 상태는 `deploy/README.md`에 기록한다.

2026-11-23 기반 검증: 자동 테스트 49개, TypeScript 검사, Next.js production build, 합성 7단계 전달/기록 통과. 실행 중인 Next.js BFF에서도 비로그인/다른 계정/만료/Origin 차단, 로그아웃 후 이전 세션 거절, 기본 NextAuth 로그아웃을 확인했다. 이 검사는 격리된 서명 세션을 쓰며 실제 OAuth 승인과 구분한다. 실제 GitHub 사용자 승인 후 새 로그인 요청으로 OAuth 콜백과 관제 진입도 확인했다. 처음 요청은 임시 State 쿠키가 없어 거절됐으며, 검증을 우회하지 않고 새 로그인으로 해결했다. 새 기기 연결 검증 결과는 `../docs/INTERNET_PAIRING_RESULTS.md`에 별도로 기록한다. 실제 폰 업로드/외부망 관제는 아직 미검증이다.

독립 검토에서 기본 로그아웃 실패 처리와 인증 중인 폰 연결에 영향을 주는 viewer 폐기 경합을 재현해 회귀 테스트로 수정했다. 기존 기반 구현의 보관본 151개 파일 해시 불일치 0개, 의존성 audit 알려진 취약점 0개는 앞선 기반 검증 시점의 결과이며 새 웹 패키지 audit 결과를 뜻하지 않는다.

## 로컬 웹 로그인

`web/.env.example`을 기준으로 `web/.env.local`에 GitHub OAuth ID/Secret을 넣는다. 비밀값은 출력하거나 커밋하지 않는다. OAuth 앱의 홈페이지는 `http://localhost:3000`, callback은 `http://localhost:3000/api/auth/callback/github`이다. 허용 계정은 변경 가능한 닉네임 대신 `OWNER_GITHUB_ID` 숫자로 검사한다. 요청 scope는 `read:user`이며 저장소 권한은 요청하지 않는다.

중계 서버와 웹 서버를 각각 실행한다:

```powershell
node scripts/local-relay.ts
# 다른 터미널, web 디렉터리에서:
node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3000
```

`local-relay.ts`는 `.local/database-v2-20261124`의 PGlite를 이용하는 로컬 개발 전용이다. 원래 DB와 복구용 복사본은 보존한다. 공개 운영의 PostgreSQL/TLS 검증을 대신하지 않는다. 가짜 기기를 자동 생성하지 않으며, 아직 폰이 등록되지 않았으면 빈 기기 목록이 정상이다. 개발 서버를 켠 상태에서 `node scripts/check-local-auth.ts`로 BFF 보호 경로를 검사할 수 있다. 별도 서명 테스트 세션만 생성/폐기하며 실제 사용자 세션은 바꾸지 않는다.

`node scripts/check-local-pairing.ts`는 로컬 웹과 중계 서버를 대상으로 합성 기기를 등록하고 7단계 전달·기록·폐기를 확인한다. 목록에 `[합성 시험] 연결 검증`이라는 폐기된 시험 항목을 남긴다. 실제 폰 연결이나 카메라 시험을 뜻하지 않는다.

## 기기 연결

휴대폰에서 인터넷 관제의 서버 주소를 지정하고 코드를 요청한다. 웹의 **기기·설정 → 새 기기 연결**에 코드를 입력해 기기 이름을 확인한 뒤 승인한다. 휴대폰은 별도의 임의 비밀값으로 승인을 확인하고 기기 전용 자격증명을 받는다. 웹 브라우저에는 폰의 인증값을 전달하지 않는다. 실제 서버 주소와 HTTPS 인증서가 준비되기 전에는 인터넷에서 사용할 수 없다.

- 연결 코드: 8자리, 12시간 만료, 한 번 승인. 같은 승인 결과는 원래 폰만 만료 전까지 재수신할 수 있다. 사용자 요청으로 늘린 값이며 코드가 노출될 수 있는 시간도 길어지므로 공유하지 않는다.
- 폰: POST `/pairing/request`의 `{name}`, POST `/pairing/poll`의 Bearer poll token. poll은 빈 body만 받는다.
- Next.js 서버: POST `/pairing/lookup`의 `{code}`, POST `/pairing/approve`의 `{code,request_id}`. Service key와 유효한 viewer session이 모두 필요하다.
- DB는 코드·poll token·기기 인증값의 해시만 보관한다. 기기 token은 service key와 poll hash에서 HMAC으로 도출하며, 키 교체 시 진행 중인 연결 요청은 새로 시작해야 한다.
- 대기 요청 128개, 요청 body 2KiB, IP당 분당 신규 요청 5회·조회/승인 10회·poll 60회. 프록시 뒤에서 실제 IP 신뢰 경계를 검증하기 전 공개 배포하지 않는다.

웹 의존성은 `web` 디렉터리에서 `pnpm install --ignore-workspace --frozen-lockfile`로 설치한다. `web/.env.local`, `.local`, `node_modules`, `.next`는 업로드하지 않는다. 로그인 쿠키는 HTTP-only JWT, 최대 유효 시간 설정은 1시간이며 별도 viewer 세션 폐기로 로그아웃 이후 접근을 거절한다. Next.js만 service key를 가지고 브라우저에는 30초 일회용 구독 티켓만 전달한다. 기본 로그아웃 경로도 relay 폐기 성공 전에는 쿠키를 지우지 않는다.

## 실행과 검증

Node 24.22 이상과 pnpm 사용. Node 내장 TypeScript 실행을 사용하므로 별도 번들러 실행은 필요하지 않다.

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm demo
```

`demo`는 임시 메모리 DB와 loopback 소켓으로 상자/뚜껑/A-D/최종 검사 7단계를 전송하고 종료한다. 카메라/휴대폰/EC2에 접속하지 않으며 실제 기기 시험이 아니다. PGlite는 PostgreSQL 엔진을 사용하는 테스트 의존성이다. TCP PostgreSQL 서버, EC2 권한/네트워크/TLS 검증을 대체하지 않는다.

Windows 번들 런타임에서 pnpm 명령이 PATH에 없다면:

```powershell
$pnpm = Join-Path (Split-Path (Split-Path (Get-Command node).Source)) 'node_modules/pnpm/bin/pnpm.cjs'
node $pnpm test
node $pnpm typecheck
node $pnpm demo
```

## DB 서버에 연결해 실행

`.env.example`의 항목을 서버 환경변수로 설정한 뒤 `node --env-file=.env server/main.ts`로 실행한다. 실제 비밀값을 저장소에 넣지 않는다. localhost:8787만 수신하며 0.0.0.0은 거절한다. 실제 공개 운영은 TLS reverse proxy, 로그인/기기 등록, 로그아웃 시 권한 폐기까지 검증한 뒤 진행해야 한다.

- Node `pg` pool 4개 연결, 연결 제한 3초, statement 제한 3초, query 제한 4초.
- 시작 시 `schema.sql`의 새 테이블을 생성한다. 기존 NOVA DB가 아닌 AR 전용 DB/계정만 사용한다.
- `SERVICE_KEY`: 32바이트 난수의 64자리 hex. 오직 Next.js 서버용이며 브라우저/폰에 전달하지 않는다.
- `OWNER_GITHUB_ID`: Next.js OAuth 로그인에서 허용할 숫자 ID. relay는 서비스 키로 인증한 Next.js 서버 요청만 받는다.
- 기기 자격증명은 로그인한 소유자가 연결 코드를 승인해야 발급한다. `Store.provision()`은 격리된 테스트에서만 사용한다. 공개 회원가입은 없다.

## 프로토콜

### 로컬 시험 서버

- 시작: `node scripts/local-relay.ts`. `.local/database-v2-20261124`를 사용하며 원래 `.local/database`와 복구용 복사본은 보존한다.
- 종료: `node scripts/stop-local-relay.ts`. localhost 전용 경로에서 기존 서비스 키를 확인하고 WebSocket/저장 대기 작업/DB를 정상 종료한 뒤 잠금 해제를 확인한다. 키는 출력하지 않는다.
- `Stop-Process`로 강제 종료하거나 같은 DB를 다른 프로세스에서 열지 않는다. `.local/relay.lock`이 있거나 포트가 사용 중이면 DB를 열기 전에 실패한다. 잠금이 남았다고 자동 삭제하지 않는다.
- `/health` 200은 버전 적용이나 DB 복구의 증거가 아니다. 설정 변경 후 실제 코드 만료시간과 정상 종료 후 데이터 재열기를 검증한다.

`/ws`는 첫 JSON 메시지로 `{role:"publisher"|"observer", token:"..."}` 인증한다. publisher는 기기 토큰, observer는 서버에서 발급한 30초 일회용 티켓을 사용한다. 인증 전 상태 전송 없음, 5초 후 닫힘. observer는 허용된 Origin이 있어야 하며 읽기만 가능하다. 자격증명 원문은 DB에 보관하지 않는다.

상태 업로드: `protocol:1`, `stream_id`, 단조 증가 `seq`, `sent_at_ms`, Android schema 1의 `state`. `state.updated_ms`는 Android monotonic 시간이지 Unix 시각이 아니다. 최신 상태/순서 경계는 메모리에 있으며 서버 재시작 후 초기화된다. DB는 기록을 보존한다.

관제 수신: `type:"state"`, `status:waiting|live|stale|offline`, `snapshot`, `received_at_ms`, `history_status:ok|pending|error`. stale/offline의 snapshot은 마지막 수신값이며 현재 안내로 표시하면 안 된다. `history_status:ok`는 현재 저장 처리 상태이지 과거 공백이 없다는 보증이 아니다. 이력의 gap 이벤트를 별도로 보여줘야 한다.

서버 전용 REST (Bearer SERVICE_KEY, 브라우저 Origin 요청은 거절):
- GET `/devices`: 본인 소유 기기의 ID/이름/폐기 상태만 반환.
- POST `/viewers/:id/revoke`: 해당 관제 세션의 티켓과 연결을 폐기. 폰은 계속 동작.
- POST `/devices/:id/ticket`: 본인 소유 기기의 구독 티켓 발급.
- GET `/devices/:id/history`: 최신 이벤트 240개. 원본 상태 포함, 시간 내림차순.
- POST `/devices/:id/revoke`: 기기 자격증명 폐기 및 활성 연결 종료.
- GET `/health`: 기기 정보 없이 프로세스 liveness만 반환. DB 정상 보증 아님.

Next.js는 모든 기기 조회/티켓/폐기 요청에 `X-Viewer-Session`을 전달한다. relay는 폐기된 viewer의 읽기 API도 거절하며 세션을 다시 활성화하지 않는다.

## 제한과 보안 경계

- payload 16KiB, 인증 메시지 포함 소켓당 초당 10개, 소켓 최대 32개/IP당 8개.
- HTTP 연결 최대 64개, 관리 API IP당 분당 120회. 프록시 배포 시 trusted proxy/IP 정책을 따로 검증한다.
- `TRUSTED_PROXY=127.0.0.1`을 명시한 경우에만 단일 loopback 프록시의 `X-Real-IP`를 사용한다. 누락/복수/유효하지 않은 IP 또는 비-loopback peer는 거절한다. 미설정이면 헤더를 무시한다. nginx는 반드시 해당 헤더를 실제 peer 주소로 덮어써야 하며 HTTP/WS 모두 같은 정책이다. 현재 자동 테스트는 통과했고 운영 nginx 경유 검증은 별도다.
- 64개 기기의 메모리 상태, 기기당 폐기된 stream 1024개, DB 대기 작업 32개, 소켓 송신 버퍼 64KiB 한도.
- 3초 수신 중단은 stale, 연결 종료는 offline. 재연결 후 공백을 기록하며 건너뛴 단계 완료를 만들지 않는다.
- 느린 관제 연결은 종료하고 최신 상태로 재연결하도록 한다. 서버는 과거 프레임 큐를 재생하지 않는다.
- 기기 토큰 30일, 접속 티켓 30초, 활성 소켓 최대 15분. 폰/웹 adapter에서 갱신/재인증 처리 필요.
- 연결 코드 승인은 같은 SQL 안에서 viewer 행을 잠가 로그아웃과 직렬화한다. 인증 DB의 일시 오류는 WS1013으로 재시도하며, 실제 폐기/만료 WS4401과 구분해 정상 폰 토큰을 지우지 않는다.
- 데이터 보존 자동 삭제/운영 백업은 아직 활성화하지 않았다. 실서비스 전 저장 공간 및 보존 정책을 적용해야 한다.
- DB 대기 한도로 이벤트가 누락되면 현재 snapshot은 계속 전달하되 이력 오류를 유지한다. 대기 큐가 비면 최신 상태의 gap 기록을 한 번 시도하며, 실패하면 이후 새 상태에서 다시 시도한다. 조용히 전체 기록이 완전한 것처럼 표시하지 않는다.
- Android sender/Keystore는 후보 코드와 실기 시험을 구분한다. 웹/폰의 외부망 시험, HTTPS 설정을 마치기 전 완성된 인터넷 서비스로 보고하지 않는다.

## 구조와 참고

- `shared/protocol.ts`: 실제 Android snapshot 형식 검증.
- `server/store.ts`, `schema.sql`: 소유권, 기기 토큰, 접속 티켓, 중복 없는 기록.
- `server/relay.ts`: 상태 전달, 인증 제한, 순서/공백/지연/권한 폐기.
- `server/pairing.ts`, `pairing-http.ts`: 단기 코드, 승인, 재수신 가능한 폰 인증 발급.
- `server/config.ts`, `main.ts`: fail-closed 설정과 PostgreSQL 실행 경로.
- `tests/`: 실제 loopback HTTP/WebSocket과 PostgreSQL 엔진 테스트.

SafeOps의 API/화면/기록 분리와 연결 지연 처리, sentientsys-web의 인증 출처 제한을 참고했다. 회사 코드/데이터/비밀값은 복사하지 않았다. 확인한 SafeOps 관제는 기본 5초 폴링이며 본 relay의 WebSocket 구현과는 다르다.

계획/상태: `../docs/superpowers/plans/2026-11-23-relay-foundation.md`.
