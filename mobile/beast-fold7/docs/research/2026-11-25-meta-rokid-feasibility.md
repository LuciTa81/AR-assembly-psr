# Meta Ray-Ban Display / Rokid Glasses 이식 조사

조사 기준: 2026-11-25. 공개 공식 문서와 현재 로컬 소스 대조. SDK 설치·빌드, 대상 안경 실험, 계정 등록, 메일 발송, 배포는 하지 않았다.

## 1. 결론

**현재 시스템의 인식·작업 흐름·웹 관제를 재사용한 스마트 안경 버전은 개발할 근거가 충분하다. 다만 Beast의 정밀 양안 오버레이를 그대로 복제하는 과제는 아니다.**

첫 제품 범위는 `안경 카메라 → Fold7에서 인식 → 안경에 현재 작업 안내 → 본인 웹에서 상태·영상 확인`으로 권한다. 녹화·다운로드는 기존 후보 구현의 실서비스 검증을 별도로 통과해야 한다.

구현 수준을 구분한다.

| 수준 | 실제 의미 | 이번 권고 |
| --- | --- | --- |
| HUD 작업 안내 | 시야의 일정한 영역에 다음 행동·대상 나사 그림 표시 | 첫 이식 목표 |
| 영상 위 표시 | 폰·웹의 카메라 영상에서 나사 위치에 원 표시 | 인식 검증과 관제에 사용 |
| 현실 정합 AR | 눈으로 보는 실제 나사 위에 오차를 관리하며 표시 | API·광학 조건 확인 후 별도 연구 |
| 양안 입체 AR | 좌우 눈에 다른 투영을 제공하여 깊이 표현 | Meta Display는 동일 방식 불가, Rokid는 미확인 |

카메라 영상에 맞는 원과 실제 눈에 맞는 원은 다르다. 이미지 좌표, 카메라 내부 파라미터, 카메라-눈 관계, 광학 투영, 시간 지연을 각각 다뤄야 한다.

## 2. 기기별 판단

### Meta Ray-Ban Display

- 공식 제품은 오른쪽 렌즈의 컬러 600×600 표시다. Beast처럼 두 눈에 다른 화면을 보내는 구성을 그대로 만들 수 없다. 단안에서 입체적으로 그린 부품 그림은 가능성과 별개로, 양안 입체 표시와 구분해야 한다. [공식 제품 사양](https://www.ray-ban.com/usa/electronics/0HX000001-META%20RAY-BAN%20DISPLAY-Black/815820026709)
- 현재 Android DAT 저장소의 최신 공개 변경 기록은 **1.1.0, 2026-11-20**이다. 표시 기능도 있으므로 과거의 “카메라만 되고 화면 API는 없다”는 판단을 적용하면 안 된다. 실험적 기능은 공개 배포에 제약이 있어 첫 버전의 필수 기능에서 제외한다. [버전 기록](https://github.com/meta/meta-wearables-dat-android/blob/main/CHANGELOG.md)
- 한국이 일반 Ray-Ban Meta 지원 국가에 포함되어도 **Display 제품의 지원 국가 목록에는 없다**. 해당 기기의 국내 활성화·개발 계정·실기기 테스트 가능 여부를 구매나 구현 약속보다 먼저 확인해야 한다. 이것만으로 모든 국내 개발이 불가능하다는 결론을 내리지는 않는다. [제품별 지원 국가](https://www.meta.com/help/ai-glasses/4961066940605960/)

**판단:** 공개 SDK의 구체성이 좋아 첫 기술 검증 후보로 적합하다. 다만 국내 사용 조건이 막히면 승인된 환경을 확보할 때까지 모의 테스트로 제한한다. 위치 우회나 비공식 펌웨어는 계획에 넣지 않는다.

### Rokid Glasses

여기서는 **디스플레이 있는 소비자용 Rokid Glasses**를 뜻한다. Style은 화면이 없고, Max·Station·기업용 Glass3는 다른 개발 대상이다. Glasses는 양안 녹색 표시이므로 기존 주황·파랑·초록 표현을 그대로 옮길 수 없다. [공식 모델 비교](https://store.rokid.com/pages/faqs)

공식 개발 안내의 경로 구분은 다음과 같다. [Rokid SDK 포털](https://developerdoc.rokid.com/sdk?lang=en), [한국 공식 개발 안내](https://kr.rokid.com/43)

| 경로 | 확인된 범위 | 우리 프로젝트 판단 |
| --- | --- | --- |
| CXR-L | Hi Rokid 경유 휴대폰 연동, CustomView, 사진·명령 등 | HUD 검증 후보. 연속 카메라 스트림 지원은 확정하지 않음 |
| CXR-M | Android 직접 연결, 실시간 영상·음성, 승인 필요 | 카메라 기반 자동 안내의 우선 문의 대상 |
| CXR-S | 안경 측 앱·하드웨어 연동 | M 경로에서 필요할 때만 추가 |
| AIUI | 에이전트·카드형 경험 | 현재 OpenCV/ONNX 루프의 직접 대체재가 아님 |

CXR-M은 Hi Rokid와 동일 폰에서 동시 사용하지 않는 경로로 안내된다. SDK 제공·배포 라이선스·학술 프로젝트 허용 조건은 먼저 문의해야 한다. 공개 안내의 버전 숫자는 안내 작성 시점 기준이며 최신 바이너리 제공을 보장하지 않는다.

**판단:** 단순 안내는 진입 경로가 있지만, 우리의 연속 영상 처리까지 하려면 SDK 권한과 실제 입출력 계약 확인이 먼저다. “양안”이라는 제품 사양만으로 독립 좌우 렌더링을 가정하면 안 된다.

## 3. Meta에서 실제 사용할 API

다음은 공식 문서의 API 이름이다. 이 프로젝트에서 컴파일 검증한 코드가 아니며, 다운로드 시 버전과 샘플 커밋을 함께 고정해야 한다.

| 용도 | 확인한 API / 구성 | 구현 시 확인 |
| --- | --- | --- |
| 의존성 | `com.meta.wearable:mwdat-core:1.1.0`, `mwdat-camera`, `mwdat-display` | Maven Central. 현재 프로젝트 Kotlin 의존성과 호환 검사 |
| 초기화 | `Wearables.initialize` | Application 초기화, 앱 메타데이터 |
| 앱 등록 | `Wearables.startRegistration`, `registrationState` | `REGISTERED` 전 세션 생성 금지 |
| 카메라 동의 | `Wearables.checkPermissionStatus(Permission.CAMERA)`, `Wearables.RequestPermissionContract()` | 폰 Android 권한과 안경 접근 동의 구분 |
| 연결 세션 | `Wearables.createSession`, `session.start()` | 세션 상태·오류 관찰 |
| 카메라 | `session.addCamera(StreamConfiguration(...))`, `camera.stream.start()` | 프레임 형식·수명·타임스탬프 확인 |
| 프레임 수신 | `camera.stream.videoStream` | 분석은 최신 프레임 중심, 누적 큐 금지 |
| 표시 | `device.isDisplayCapable()`, `session.addDisplay()` | `DisplayState.STARTED` 이후 전송 |
| UI 갱신 | `display.sendContent { ... }` | 상태가 바뀔 때 작은 안내 화면 갱신 |

근거: [설정](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/getting-started/SKILL.md), [등록·권한](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/permissions-registration/SKILL.md), [카메라](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/camera-streaming/SKILL.md), [표시](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/display-access/SKILL.md).

### 영상과 화면의 제약

공식 카메라 가이드의 HIGH는 **720×1280 세로 영상**, 선택 가능한 최고 프레임률은 **30fps**다. 압축 옵션은 HEVC이며 기본 프레임은 YUV로 설명된다. 광고용 촬영 해상도나 화면 주사율을 SDK 수신 성능으로 간주하지 않는다. 세부 plane/stride·회전·촬영 시각은 실제 버퍼와 해당 버전 API로 확인한다. [카메라 가이드](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/camera-streaming/SKILL.md)

표시 API는 UI 트리 전송 방식이다. `sendContent`는 기존 내용을 대체하며 텍스트·이미지·버튼을 제공한다. 이것이 임의의 카메라-눈 투영이나 월드 앵커 API라는 근거는 찾지 못했다. SDK의 전송 성공과 사용자가 실제로 본 시각도 구분한다. [표시 가이드](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/display-access/SKILL.md)

공식 버전 기록에는 로컬 Bitmap 표시와 Display 모의 미리보기가 추가되어 있다. 일반 FAQ의 모의 Display 미지원 안내와 일부 문서가 엇갈리므로 최신 버전 샘플을 기준으로 빌드 확인한다. 모의 화면은 광학 정합 검증을 대신하지 않는다. [버전 기록](https://github.com/meta/meta-wearables-dat-android/blob/main/CHANGELOG.md)

### 웹앱만으로 하면 더 쉬운가?

Meta는 독립 웹앱 경로도 제공한다. 하지만 우리 앱의 Java/OpenCV/ONNX 처리와 외부 카메라 루프를 재사용하려면 **Fold7의 네이티브 앱 + DAT**가 먼저다. 웹 경로는 간단한 안내 시제품에 적합하다는 판단이며, 네이티브와 동일 카메라 접근을 가정하지 않는다. 개발 테스트와 일반 이용자에게 공개하는 배포도 별개다. 공식 FAQ는 발견·공개 제출 경로를 아직 예정으로 안내한다. [개발·배포 FAQ](https://developers.meta.com/wearables/faq/)

## 4. Rokid에서 아직 확정하면 안 되는 것

공개 개요와 공식 연결 문서는 확인했지만, 이번 조사에서 CXR-M/S의 인증된 최신 패키지와 전체 API 계약을 확보하지 못했다. 따라서 `startCameraStream()` 같은 그럴듯한 메서드명을 만들어 계획에 넣지 않는다.

문의 후 받아야 할 것은 다음과 같다.

1. 정확한 Glasses SKU·펌웨어에 맞는 SDK, 변경 기록, 라이선스, Android 예제.
2. 카메라와 자체 안내 화면을 동시에 유지하는 공식 샘플.
3. 연속 영상의 형식·해상도·fps·타임스탬프·카메라 보정 데이터 제공 범위.
4. 화면의 실제 앱 사용 영역, 갱신 제한, 표시 완료 콜백, 임의 픽셀 접근 여부.
5. 좌우 개별 출력과 카메라-눈 관계 제공 여부. 없으면 HUD까지만 진행.
6. Fold7 Android 16, 화면 잠금, Wi-Fi 연결과 모바일 인터넷 병행 조건.
7. 개발 장치 등록·인증·케이블·앱 서명·일반 사용자 배포 절차와 비용.

기업용 Glass3의 공개 예제를 소비자 Glasses에 그대로 적용하지 않는다. 저장소가 공개되어 있어도 SDK 바이너리 재배포·상용 사용 권한까지 자동으로 생기는 것은 아니다.

## 5. 현재 코드 재사용 분석

로컬 프로젝트 기준이다. 아래 비율 대신 모듈별 재사용 단위를 제시한다. 단순 파일 개수로 재사용률을 계산하면 새 보정과 무선 안정화 작업이 가려진다.

| 현재 파일 / 영역 | 재사용 | 필요한 변경 |
| --- | --- | --- |
| `AssemblyProbe.java`, `PreparationGuide.java` | 작업 순서·증거 누적 규칙 | 실제 그리기 콜백에 결합된 시간 기준 분리 |
| `WorkspaceTracker.java` | ArUco·자세 추정 알고리즘 | 고정 1280×720, 새 카메라 K·왜곡·영상 변환 |
| `YoloDetector.java` | ONNX 모델과 추론 흐름 | 고정 letterbox·좌표 역변환 일반화, 새 영상에서 성능 측정 |
| `ToolEvidence.java` | 도구-나사 근접 평가 | 새 카메라와 작업대 프로필로 재검증 |
| `EyeProjection.java` | 계산 접근법 참고 | **Beast 눈별 행렬은 재사용 금지** |
| `BoxOutline.java`, `SphereMarker.java` | 부품·표시 기하 의미 | 출력 장치별 렌더링 별도 |
| `StereoOverlayView.java` | Beast에서 그대로 유지 | Meta/Rokid HUD 렌더러 신규 |
| `PartPreviewView.java` | 모델·부품 그림 자산 | WebView/Three.js 실행 경로를 그대로 이식하지 않음 |
| `MainActivity.java` | 기존 조작 흐름 참고 | UVC·외부 화면·분석·표시 의존성 최소 분리 |
| `RemoteSupervisor*` | 연결·인증·상태 전송 대부분 | 기기 능력·영상 상태를 사실대로 표시 |
| `RemoteVideoEncoder.java`, `AvcPacket.java` | H.264 전송 틀 | 고정 NV21 1280×720 입력의 변환 경계 추가 |
| 인터넷 서버·Next.js·소유권·녹화 코드 | 사업 로직 대부분 | 실제 새 입력 영상의 호환·권한 회귀 테스트 |

Java 소스 위치: [기존 앱 소스](C:/Users/fresh/Documents/Codex/Beast-Fold7-Gate/app/src/main/java/com/lucita/beastgate). 서버 위치: [internet-supervisor](C:/Users/fresh/Documents/Codex/Beast-Fold7-Gate/internet-supervisor).

### 반드시 먼저 고칠 결합 네 가지

**1. 영상 크기와 방향**

현재 YOLO 전처리는 1280×720을 640×384로 맞추고, 결과 좌표를 고정 배율·여백으로 되돌린다. 세로 입력을 가로로 늘리거나 숫자만 바꾸면 도구 위치가 틀어진다. 원본→모델 변환과 역변환을 한 객체로 관리하고 회전·여백·잘림을 테스트한다.

**2. 보정과 기기 능력**

현재 시작 조건과 웹의 나사 표시 상태에 Beast `EyeProjection` 유효성이 연결되어 있다. HUD 기기는 양안 투영 파일이 없어도 영상 분석을 시작할 수 있어야 한다. `추적 가능`, `안경 표시 가능`, `정밀 정합 가능`을 구분한다.

Beast의 205/205 작업대 설정과 A~D 눈별 보정은 그대로 보관한다. 새 기기의 카메라 프로필은 별도로 만들고 실제 측정값을 확인한다. 200/205 측정 이슈를 숨긴 채 새 카메라에 기존 오차를 복제하지 않는다.

**3. 시간의 의미**

현재 상자·뚜껑은 유효한 표시/추적 시간이 7초·6초 누적되면 전환한다. 이는 상자 배치·뚜껑 닫힘의 자동 검출이 아니다. 나사 단계는 작업 안내 지연과 초록 표시 승인 후 3초 전환을 사용한다. 체결 토크·품질 검증과도 다르다.

새 SDK의 콘텐츠 전송 성공을 실제 광학 표시 완료라고 기록하면 안 된다. 세션·대상·화면 revision에 대응하는 승인만 인정하고, 측정 근거를 `SDK_ACCEPTED` 또는 실제 표시 콜백 등으로 구분한다. 표시가 중단되면 유효 안내 시간도 진행하지 않도록 후보 정책을 검증한다.

**4. 스트림 지연**

현재 일부 시각은 콜백 수신 시각이다. 새 SDK의 촬영 시각이 없으면 이미 늦게 도착한 프레임을 신선한 관측으로 착각할 수 있다. 촬영 시각의 의미·단위·시계 기준을 확인하고, 미제공이면 수신 지연 한계를 별도로 측정한다. 포즈와 도구 검출은 같은 프레임을 사용한다.

## 6. 추천 구성

```text
안경: 카메라 + 기기별 HUD
  │ 공식 SDK의 로컬 연결
  ▼
Fold7 AR Assembly
  ├─ 기기 연결 / 프레임 형식 변환
  ├─ OpenCV + ONNX 추론 + 작업 단계 판단
  ├─ Meta HUD 또는 Rokid HUD 출력
  └─ 기존 사용자 인증 + 상태 / 동의한 영상 전송
       │ HTTPS / WSS
       ▼
기존 EC2 relay / DB ── 본인 Next.js 관제
       └─ 별도 승인·검증 후 비공개 녹화 저장 / 다운로드
```

클라우드가 매 프레임 AR 좌표를 계산하게 바꾸지 않는다. 인터넷 상태와 현장 작업 판단을 최대한 분리한다. 다만 SDK 자체의 오프라인 세션 유지 가능성은 별도 실기기 확인 대상이다.

첫 이식에서는 서버의 H.264 1280×720 계약을 유지하는 쪽이 변경 범위가 작다. **분석은 적절한 원본 영상 좌표계**, 관제 전송만 비율을 유지한 1280×720 캔버스로 변환한다. 세로 영상에는 여백이 생기며 억지 확대·잘림은 하지 않는다. 필요할 때만 크기를 명시하는 새 프로토콜 버전을 도입한다.

Meta의 HEVC 프레임을 현재 H.264로 선언하여 전송하면 안 된다. 비압축 프레임 수신 또는 정식 디코드 후 기존 인코더로 연결하는 경로를 측정한다. 압축 스트림을 반복 복사·재인코딩하여 발열이 커지면 먼저 해상도·분석 빈도를 조절한다.

현재 서버도 헤더 검증과 MP4 기록 크기가 고정되어 있어 폰 인코더만 바꾸면 끝나지 않는다. **30fps는 목표/설정값과 실측을 분리하고 60fps는 기본 약속에서 제외한다.**

## 7. 표시 디자인 방향

공통 화면은 `짧은 행동 한 줄 + A~D 배치 그림 + 현재 부품`으로 시작한다. 여러 상태 설명·진단 수치·카메라 영상을 안경에 동시에 넣지 않는다.

| 단계 | Meta 컬러 HUD 제안 | Rokid 단색 HUD 제안 |
| --- | --- | --- |
| 상자 | 몸체 그림 + 상자 배치 행동 | 열린 상자 윤곽 + 같은 행동 |
| 뚜껑 | 뚜껑 그림 + 닫기 행동 | 얇은 뚜껑 윤곽 + 같은 행동 |
| 나사 준비 | A~D 중 대상 강조 + 행동 문구 | 대상의 굵은 원 + 화살표 |
| 작업 중 | 진행 표시 + 한 줄 행동 | 진행 표시 + 짧은 상태어 |
| 단계 전환 | 확인 표시, 다음 대상 준비 | 체크 표시, 다음 대상 준비 |
| 최종 검사 | 조립체 그림 + 사용자 검사 | 조립체 윤곽 + 사용자 검사 |

색은 추가 단서로만 사용한다. 기존 사용자에게 이미 익숙한 문구는 유지하되 렌즈에서 가독성을 직접 확인한다. 부품은 정적인 등각 그림부터 시작하고, 3D 회전은 API와 자원 여유가 확인될 때 추가한다. 현실 위 정합인 것처럼 보이게 연출하지 않는다.

## 8. 계정·권한·사용자 참여

| 구분 | 필요할 것 | 이번에 하지 않는 것 |
| --- | --- | --- |
| Meta | Meta 계정·Meta AI 앱·개발 모드, 개발 포털 앱 등록, 앱 ID/Client Token·콜백 구성, 안경 카메라 동의 | 대신 약관 동의·계정 인증·비밀값 공개 |
| Rokid | Global 계정, 실제 SKU 확인, 선택 SDK 권한과 배포 계약 확인 | 기업 인증 가능 여부 추측, 유료 계약 체결 |
| Android | 연결에 필요한 Bluetooth 권한, SDK가 필요로 하는 근처 기기/네트워크 권한 | 광범위한 위치·파일·마이크 권한 일괄 추가 |
| 장시간 실행 | 적절한 foreground service, 보이는 알림과 종료 동작 | 백그라운드 몰래 촬영 |
| 우리 서비스 | 기존 GitHub 로그인·기기 승인·별도 영상/녹화 동의 | 안경 연결 동의를 클라우드 녹화 동의로 간주 |
| 서버 | 기존 소유권 분리·제한·만료 정책 검증 | 이식 때문에 AWS 관리자 권한 새로 요구 |

Meta 설정·등록 근거: [설정 가이드](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/getting-started/SKILL.md), [권한 가이드](https://github.com/meta/meta-wearables-dat-android/blob/main/plugins/mwdat-android/skills/permissions-registration/SKILL.md).

Android 16에서는 `BLUETOOTH_CONNECT`와 탐색에 필요한 경우 `BLUETOOTH_SCAN`을 구분한다. Wi-Fi 제어 API를 쓰는 경우 `NEARBY_WIFI_DEVICES` 등의 필요성을 확인한다. 위치 권한을 요구하는 일부 Wi-Fi API도 있어 정확한 SDK 호출에 따라 결정한다. [Bluetooth 권한](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions), [Wi-Fi 권한](https://developer.android.com/develop/connectivity/wifi/wifi-permissions)

외부 기기와의 지속 통신에는 서비스 유형·권한을 맞춰야 한다. Meta 공식 예제는 `connectedDevice` foreground service를 사용한다. 현재 앱은 foreground service 권한을 명시적으로 제거하므로 무조건 매니페스트를 합치지 않고 후보별로 분리한다. 마이크 권한은 첫 범위에서 제외한다. [Android 서비스 유형](https://developer.android.com/develop/background-work/services/fgs/service-types), [Meta 예제 Manifest](https://github.com/meta/meta-wearables-dat-android/blob/main/samples/CameraAccess/app/src/main/AndroidManifest.xml)

현재 앱 최소 Android 버전은 36이다. SDK가 더 오래된 Android를 지원하더라도 우리 앱이 자동으로 구형 폰을 지원하는 것은 아니다. 첫 대상은 계속 Fold7 Android 16으로 제한한다.

## 9. 공급사에 보낼 질문 초안

아래는 **발송하지 않은 초안**이다. 사용자 이름·학교·연락처·기기 시리얼은 승인 후 필요한 항목만 넣는다.

### Rokid

제목: Rokid Glasses 기반 대학 조립 안내 프로젝트의 CXR SDK 접근 문의

프로젝트는 Fold7(Android 16)에서 작업대 영상을 OpenCV/ONNX로 처리하여 나사별 안내를 안경에 표시하고, 사용자가 동의한 영상만 자체 관제에 전송하는 구조입니다. 음성 수집은 하지 않습니다.

확인을 요청드립니다: 소비자 Glasses에서 연속 영상과 CustomView 동시 실행에 맞는 SDK, 학술 POC 승인 절차와 비용, 프레임 사양과 시간 정보, 표시 갱신/좌우 개별 출력 지원, Hi Rokid와의 공존 방식, 모바일 인터넷 병행, 배포·장치 등록·개발 케이블 조건, 자체 서버 영상 전송 및 제한된 보관의 허용 조건.

### Meta

확인할 항목: 한국에서 Display 실기기와 개발 포털 사용 가능 조건, DAT 1.1.0의 camera+display 동시 실행, 스트림 촬영 시각·카메라 내부 파라미터 제공 여부, 손떨림 보정/영상 잘림 변화, Bitmap 갱신 한도와 실제 표시 완료 콜백, 테스트 배포와 일반 배포의 절차 차이.

## 10. 착수 판단

**권고 순서: Meta 공식 샘플 검증 준비 + Rokid SDK 접근 조건 확인 → 입출력 검증 → 공통 코드 연결 → 신규 카메라 검증 → 웹 영상·녹화 → 안정화.**

국내 사용 조건이나 SDK 승인에서 막히면 그 기기의 구현 약속을 멈추고 다른 기기의 허용된 범위부터 진행한다. 화면만 성공한 결과를 연속 인식까지 성공했다고 보고하지 않는다.

현재 녹화·다중 사용자 기능은 로컬 검증된 후보이며 실제 배포·Fold7/Beast·S3 경로의 남은 검증이 있다. 다음 문서의 상태를 우선한다: [기존 녹화 구현 상태](C:/Users/fresh/Documents/Codex/Beast-Fold7-Gate/docs/MULTIUSER_RECORDINGS.md).

실행 순서와 통과 기준: [개발 로드맵](C:/Users/fresh/Documents/Codex/Beast-Fold7-Gate/docs/superpowers/plans/2026-11-25-multi-glasses-port.md).
