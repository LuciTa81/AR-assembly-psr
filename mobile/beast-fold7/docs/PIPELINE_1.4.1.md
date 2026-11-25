# AR Assembly 1.4.1 파이프라인

기준: 2026-11-24 설치 APK 1.4.1, EC2 release 20261124-03, Vercel production dpl_Fm1dMTVkZH4wtdSju55aqr8KrJZt.

## 핵심 구조

Beast 카메라 -> USB-C -> Fold7 입력 프레임 -> 로컬 AR 처리 / 선택적 인터넷 영상 전송으로 분기한다. AR 결과는 Android 외부 디스플레이로 Beast에 출력한다. 인터넷 관제 서버가 AR 좌표나 다음 단계를 계산하는 구조가 아니다.

### 폰 로컬 AR 경로

1. MainActivity: UVC 카메라 NV21 1280x720 입력. 분석 분기는 최소 200ms 간격, 처리 중 프레임은 추가 적재하지 않는다.
2. WorkspaceTracker: OpenCV ArUco DICT_4X4_50 검출, 마커 중심점 기반 IPPE 자세 후보 평가, LM 재최적화. RMS <=3.2px, 최대 오차 <=5px 등 품질 조건. PnP 추정에는 최소 4개가 필요하지만 현재 안내/도구 증거 경로는 마커 5개 이상을 추가 요구한다.
3. YoloDetector: 로컬 ONNX Runtime 도구 검출, 입력 640x384. ToolEvidence는 동일 분석 프레임의 자세로 도구 끝을 나사 평면에 투영하고 목표별 근접 점수를 계산한다.
4. PreparationGuide: 유효한 추적/표시 시간을 누적해 상자 7초, 뚜껑 6초 안내. 물체 배치나 닫힘 자동 검증은 아니다.
5. AssemblyProbe: 유효 근접 증거 누적 800ms 후 진행 확보. 확보 이후 4000ms가 지나고 근접 증거가 유효하면 RELEASE로 전환한다. 실제 초록 안내가 그려진 시점을 acknowledgeGreen으로 받고 3000ms 후 다음 목표로 진행한다. 체결 토크나 조임 품질은 검증하지 않는다.
6. EyeProjection: 기존 보정 JSON의 좌/우 3x4 투영행렬로 카메라 XYZ를 눈별 픽셀로 변환한다. 카메라/작업대 프로파일 해시를 검증한다. 양쪽 중 표시 범위 밖 좌표가 있으면 해당 투영은 거부한다.
7. BoxOutline + StereoOverlayView: 단계별 몸체/뚜껑 윤곽, 네 나사 표시, 현재 대상 색상, 한국어 행동 안내를 렌더링한다. PartPreviewView는 로컬 Three.js/WebView로 오른쪽 위 부품 예시를 별도로 표시하며 위치/단계 증거를 공급하지 않는다.
8. Android Presentation: 좌/우 각 1920x1080, Full SBS 3840x1080으로 Beast 외부 화면 출력. 노트북에서 가져온 보정은 유지하지만 현재 Android 실행 경로에 Unity 런타임은 없다.

### 인터넷 상태 경로

RemoteSupervisorSampler -> RemoteSupervisorTransport -> TLS/WSS /ws -> EC2 Nginx -> Node relay -> 관제 브라우저.

작업 중 250ms, 대기 중 1000ms 간격으로 상태를 추출한다. 서버는 형식/인증/기기 소유권/순서를 검증하고 웹에 전달한다. PostgreSQL에는 기기 등록, 티켓, 의미 있는 작업 상태 변화 등을 저장한다. 프레임을 DB에 저장하지 않는다.

### 인터넷 영상 경로

동일 카메라 프레임 -> RemoteVideoEncoder -> Android MediaCodec 하드웨어 H.264 -> 별도 TLS/WSS /video -> EC2 relay -> 관제 브라우저 WebCodecs/Canvas.

AR 분석 주기와 별개다. 720p, 30fps, 2Mbps 목표이며 실제 입력이 느리면 목표 속도를 보장하지 못한다. 서버는 영상을 디코딩/추론/녹화하지 않는다. WebRTC가 아니라 WSS/TCP 전송이다. 프레임 누락과 지연 시 큐를 제한하고 키프레임에서 복구한다. 지원되는 브라우저에서는 초기 지연을 줄이기 위해 소프트웨어 디코더를 우선한다.

영상 공유는 폰의 별도 동의와 웹 영상 표시 켜기가 필요하다. 음성 전송/영상 저장은 없다. 관제에는 카메라 시점이 나오며 Beast 양안 AR 렌더가 자동 합성되는 것은 아니다. 화면에 FPS 숫자는 표시하지 않는다.

### 로그인과 웹

GitHub OAuth -> Vercel Next.js 로그인/BFF -> EC2 기기/기록 API 및 일회용 관제 티켓.

로그인 허용은 본인 계정으로 제한한다. 티켓 발급 후 브라우저의 상태/영상 WSS는 EC2에 직접 연결한다. Vercel을 영상 중계 서버로 사용하지 않는다. 폰과 관제는 서로 다른 인터넷 회선에서도 연결하도록 구성했다. 노트북은 브라우저 관제자로만 필요하며 AR 실행 엔진이 아니다.

## 검증 범위

- 기존 AR 좌표/단계 안내: 이전 실기 사용자 확인 있음. 새 영상 병행 조건의 재검증은 별도.
- 최신 서버 82개, Android 37개 자동 테스트 통과. 웹 빌드 통과.
- 로컬 합성 H.264 재생 및 운영 TLS/WSS 합성 패킷 전달 확인.
- 합성 브라우저 내부 측정은 24fps. 실제 Beast/Fold7 성능 결과가 아니며 30fps 달성으로 표현하지 않는다.
- 남은 항목: 실제 카메라 영상 재생, AR 병행 성능/발열, 네트워크 변경/장시간 반복 시연.

## 도면 표기 원칙

현재 실행 경로에는 Python 서버, Unity 앱, MediaPipe, HMM/Viterbi를 넣지 않는다. 이들은 예전 노트북 아키텍처와 혼동하지 않도록 별도 역사 문서에서 다룬다. 프레임률/렌더링 주기/분석 주기는 서로 다른 지표다.
