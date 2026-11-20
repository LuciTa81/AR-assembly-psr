# Beast 공식 SDK 도입 사전 확인 (2026-10-07)

최신 상태: Unity XR SDK 0.9.0 정적 검토에 이어 Windows Glasses SDK 2.4.0도 수령했다.
Beast 장치의 설정 조회와 정상 종료를 확인했다. 이후 같은 Native/SBS/0DoF 조건에서
IMU 시작을 시도했으나 USB_EXEC(-3)으로 실패했다. 기존 앱에는 통합하지 않았다.
아래 최초 조사, Unity 패키지 검토, Windows 실조회 및 IMU 시험을 시간 순으로 구분한다.

## 범위와 결과

목표는 공식 Windows SDK의 이용 가능 여부를 확인하고, 가능하면 안경 설정을 읽는 것이다.
기존 인식, Unity 출력, 보정값을 교체하는 작업은 아니다.

- 공개 문서, 실제 다운로드 신청 화면, 현재 프로젝트 코드를 확인했다.
- 기존 `beast_device_check`로 Windows 장치 목록만 읽었다. Beast UVC 및 VITURE 제어 인터페이스 후보가 존재한다.
- 장치 목록의 후보 수는 물리적 안경 대수가 아니다. 하나의 장치가 여러 인터페이스로 나타날 수 있다.
- SDK 파일은 아직 없다. 공식 다운로드는 이메일 신청과 라이선스 동의 후 링크를 받는 방식이다. 신청을 대신 제출하거나 약관에 동의하지 않았다.
- 따라서 SDK의 실제 버전, DLL, 헤더, 초기화 부작용, 설정 조회 성공 여부는 미검증이다.
- 카메라, Unity, IMU 스트리밍을 시작하지 않았다. 화면 모드 및 보정값을 변경하지 않았다.

## SDK 구분

| 대상 | 공식 문서에서 확인한 범위 | 이번 프로젝트 판단 |
| --- | --- | --- |
| VITURE XR SDK for Unity | v0.7.0 문서의 실행 환경은 Android + Pro Neckband. Marker Tracking은 OpenCV ArUco 기반이며 마커 ID, 사전, 실제 길이를 등록한다. | 노트북용 Unity 앱에 그대로 붙여 실행할 수 있다고 판단하면 안 된다. 설계 참고용이다. |
| VITURE XR Glasses SDK | Windows x86_64 C API와 Beast 지원. 장치 설정, IMU, UVC 카메라 API가 있다. | 별도 읽기 전용 도구로 검증할 후보이다. |

출처: [Unity SDK](https://www.viture.com/developer/unity-sdk/unity),
[Glasses SDK](https://www.viture.com/developer/glasses-sdk/glasses).
온라인 문서와 실제 배포 패키지의 기능 일치는 수령 후 확인해야 한다.

## 기존 코드와 비교

| 기존 파일 | 확인한 구현 | SDK와의 관계 |
| --- | --- | --- |
| `server/realtime/beast_device_check.py` | 공식 USB 식별자를 이용한 Windows 장치 열거 | 이미 있는 기능. 별도 장치 검색기를 중복 구현하지 않는다. |
| `server/realtime/workspace_projection.py` | 왜곡 보정 후 마커 대각선 교점으로 중심을 구하고, 측정된 중심 좌표로 IPPE/LM 자세 추정 | 우리도 이미 ArUco 기반 위치 추정을 한다. 단순히 Marker Tracking이라는 이름을 추가한다고 정합이 해결되지는 않는다. |
| `client_unity/Assets/Scripts/CandidateProjection.cs` | 카메라 좌표를 눈별 후보 투영행렬로 변환하고 SBS 표시 범위를 검사 | 현재 어려운 눈/화면 정합 단계. SDK 제공 보정값으로 대체 가능한지는 공개 API만으로 확인되지 않는다. |
| `client_unity/Assets/Scripts/SbsGuidancePresenter.cs` | 단계 안내와 후보 위치 표시를 결합 | 당장은 유지한다. Neckband용 XR Origin으로 교체하지 않는다. |

현재 자세 추정은 마커 네 개 이상의 중심점에 의존한다. 마커 한 개의 네 모서리를
실측 사각형과 대응시키는 방식과는 조건이 다르다. 향후 모서리 기반 보드 추정을
비교할 수 있지만 마커의 정확한 크기와 방향이 필요하고, 기존 기하 검사를 단순히
완화하는 변경은 아니다. 공식 샘플의 구체적인 추정 구현은 아직 확인하지 못했다.

## 패키지 수령 후 최소 실행 순서

1. 사용자가 [개발자 페이지](https://www.viture.com/developer)의 Glasses SDK 신청을 완료하고 ZIP 또는 공식 링크를 제공한다. SDK 원본은 OneDrive와 Git 밖에 둔다.
2. 패키지 버전, 라이선스, Windows 샘플 및 헤더를 확인한다. 먼저 샘플의 자동 설정 변경과 외부 통신 여부를 살핀다. 원본 샘플을 무조건 실행하지 않는다.
3. 기존 장치 열거 결과로 대상을 식별한다. 초기화와 종료를 보장하는 독립 프로세스에서 모드, DoF, 화면 크기/거리 설정을 읽는다. SDK의 수치와 단위를 확인하기 전에는 `4.5m` 등으로 임의 해석하지 않는다.
4. 조회 실패, 미지원, 초기화 대기는 각각 표시한다. 설정 변경, recenter, 카메라 시작, IMU 시작, 통계 전송 API는 호출하지 않는다. 초기화 자체가 이 조건을 보장하지 못하면 실행 전에 중단하고 이유를 보고한다.
5. 실제 조회 결과가 있으면 보정 세트의 화면 설정 기록과 비교한다. 성공하기 전에는 기존 수동 설정 확인을 대체하지 않는다.

공개 문서상 native mode와 bypass는 별개이므로, 조회 편의를 위해 모드를 바꾸지 않는다.
카메라 입력 경로도 이번 범위에서 변경하지 않는다. 입력 해상도가 바뀌면 기존 카메라
보정과의 일치 여부부터 다시 검증해야 한다.

## 정합에 대한 결론

Windows SDK는 설정을 정확히 기록하고 향후 센서 진단을 보강할 여지가 있다.
그러나 현재 공개 API에서는 개인별 눈-카메라 변환이나 눈별 광학 투영값을 가져오는
경로를 확인하지 못했다. SDK 설치만으로 정합 정확도나 깜빡임 개선을 약속할 수 없다.
패키지에서도 찾지 못하면 제조사에 해당 값의 제공 여부와 Windows 지원 범위를 문의한다.
IMU 보강은 시간축 및 좌표계 검증을 거친 별도 단계이며 지금 바로 센서 융합을 추가하지 않는다.

## 라이선스와 검증 한계

[SDK License Agreement](https://www.viture.com/viture-sdk-license-agreement)는 SDK 공개 재배포와
벤치마크 결과의 외부 공개 등에 제한을 둔다. SDK 파일이나 헤더를 공개 저장소에 넣지 않고,
SDK 관련 실험 결과를 발표/배포하기 전 해당 조건을 확인한다. 이 기록은 공개 문서 검토와
기존 Windows 장치 열거 결과이며 SDK 벤치마크가 아니다.

기술 문서는 통계 보고를 opt-in으로 설명하지만 약관에는 opt-out 수집 표현이 있다.
실제 패키지의 기본 동작과 비활성화 방법을 확인하기 전 외부 전송이 없다고 보장하지 않는다.
이번 조사에서는 SDK 바이너리를 실행하지 않았고 사용자 영상이나 보정 자료를 외부로 보내지 않았다.

## 후속: Unity SDK 0.9.0 수령 및 정적 검토

사용자 제공 파일: `C:/Users/fresh/Downloads/VITURE_XR_SDK_for_Unity.zip`.
크기 14,090,731 bytes, ZIP 항목 292개. `com.viture.xr/package.json`의 버전은
0.9.0이고 동봉 CHANGELOG의 해당 릴리스 날짜는 2026-08-20이다.
이는 앞서 읽은 온라인 문서의 0.7.0과 다르므로, 패키지 판단에는 실제 내용을 우선했다.
SHA-256: `08b48f67cb89cb8a689bf2e9d43ca8a1b902a60f31f7512fa9d5c91ad6baaf14`.

확인 범위는 package/README/LICENSE/CHANGELOG, 빌드 플랫폼 설정, 제공된 C# 래퍼,
Marker Tracking 시각화 샘플과 API 선언이다. 바이너리 실행이나 역분석은 하지 않았다.

- README의 하드웨어 요구사항은 Pro Neckband이고, 빌드 대상 선언은 Android다.
- Runtime 어셈블리 대상은 Android와 Editor다. Editor 포함은 Windows 실장치 실행 지원을 뜻하지 않는다.
- 네이티브 배포물은 Android AAR이며, ZIP에는 Windows DLL이 없다.
- 마커 검출은 Android 네이티브 호출에 의존한다. Editor에서는 실제 검출 결과를 제공하지 않는다.
- Windows용 설정 조회 시험에 필요한 Glasses SDK와는 다른 패키지다.
- 검토한 공개 C# API에서 개인별 눈-카메라 변환이나 눈별 광학 투영 보정값을 얻는 경로는 확인하지 못했다.
  View Share의 alignment는 별도 장치 사이의 좌표계 정렬이며, 개인 눈별 정합과 혼동하지 않는다.

참고할 설계는 추적과 시각화 분리, ID별 오브젝트 재사용, 검출 시각 관리와 유실 처리다.
기존 코드와 겹치는 부분은 유지한다. 샘플의 유실 처리 조건을 복사하여 오래된 위치를
계속 표시하거나, 좌표계 변환을 의미 확인 없이 옮기지는 않는다.
실제 마커 길이의 네이티브 처리와 반환 자세의 기준 좌표계는 추가 확인 대상이다.

결론: 이 패키지를 기존 Windows Unity 프로젝트에 설치하거나 플랫폼 제한을 바꾸지 않는다.
다운로드 원본은 그대로 두고 압축 내용만 읽었다. SDK 소스/바이너리를 프로젝트에 복사하지 않았다.
카메라, Unity, IMU를 실행하지 않았고 화면 설정 및 보정값도 변경하지 않았다.
런타임 테스트나 정합 성능 검증을 했다는 뜻은 아니다.

다음은 별도 Windows Glasses SDK가 제공되면 기존 읽기 전용 조회 계획을 이어가는 것이다.
그 전에는 기존 정합 수집 경로의 시간 연결 진단을 보강하는 로드맵을 유지한다.

## 후속: Windows SDK 2.4.0 실제 설정 조회 성공

사용자 제공 파일: `C:/Users/fresh/Downloads/VITURE_XR_Glasses_SDK_for_Windows_x86_64.zip`.
크기 33,050,868 bytes, SHA-256
`3317198e3e6f0bbe29025d4cecfc9078d869f9cda9ef7f529a140a006b38b8d3`.
버전 헤더와 DLL의 런타임 버전 반환값이 모두 2.4.0이었다.

동봉 데모에는 표시 모드, DoF와 recenter 변경 경로가 있어 실행하지 않았다.
SDK는 Git/OneDrive 밖 `%LOCALAPPDATA%/ARAssembly/beast-mvp/sdk/`에 별도로 풀었다.
디렉터리 밖으로 나가는 압축 항목이 없음을 확인했고, 기존 파일을 덮어쓰지 않았다.
DLL은 Authenticode 서명이 없으며 파일 해시는 이 패키지 식별용이지 제조사 서명 검증은 아니다.

별도의 일회성 Python/ctypes 도구로 장치 열거에서 확인한 PID를 검증했다.
SDK가 PID 0x1211을 Beast/Gen2로 식별하고 native 기능 지원을 반환한 경우에만
create/initialize/start 후 조회했다. 통계 보고, 카메라, IMU, 표시 설정 변경 API는 호출하지 않았다.
안경 착용이나 사용자 원 정렬은 필요하지 않았다.

| 조회 항목 | 두 차례 공통 원값 | SDK 헤더에 따른 해석 |
| --- | --- | --- |
| mode | 1 | native mode. bypass와 다름 |
| dof | 0 | 0DoF |
| display_mode | 55 (0x37) | Full SBS 3840x1080 60Hz |
| display_size | 3 | Extra Large |
| display_distance | 7 | 내부 거리 설정값. 미터 단위 환산 미확인 |
| side_mode | 0 | 비활성 |

거리 원값 7을 사용자 보고 4.5m와 자동으로 동일시하지 않는다. 동봉 헤더/문서에서
코드-미터 대응표를 확인하지 못했다. 설정 지문으로 원값을 비교하는 것은 가능하다.

- 모든 조회가 비음수 결과를 반환했고 두 번의 결과가 일치했다.
- initialize/start/stop/shutdown은 모두 성공 코드 0, destroy 완료, 프로세스 정상 종료였다.
- 조회 전후 Windows 화면 영역 목록이 동일했고, 카메라/작업대 보정 파일 SHA-256도 동일했다.
- 개인별 눈-카메라 변환이나 눈별 광학 투영값을 조회하는 API는 제공 헤더에서 확인하지 못했다.
- 통계 모듈 문서/헤더는 명시적 초기화가 필요한 opt-in이라고 설명하며 이번에는 호출하지 않았다.
  별도 패킷 감시는 하지 않았으므로 DLL의 모든 내부 통신을 독립 검증했다고 주장하지 않는다.

원본 숫자 기록과 일회성 진단 도구:
`%LOCALAPPDATA%/ARAssembly/beast-mvp/sdk/probes/settings-readonly-20261007-01.json`,
`%LOCALAPPDATA%/ARAssembly/beast-mvp/sdk/probes/beast_settings_spike.py`.
두 파일과 SDK 자체는 저장소 밖에 있고 제품 런타임에 연결하지 않았다.

이번 결과는 Windows에서 실제 안경 설정을 읽을 수 있다는 기능 확인이다.
정합 정확도, IMU 품질, 카메라 타임스탬프 또는 마커 추적 성능의 검증이 아니다.
최소 도입 후보는 보정 세트에 이 설정 지문을 기록하고 변경을 발견하는 것이다.
그 외에는 기존 좌표/시간 진단 보강과 A 자동 정합 검증 순서를 유지한다.

## 후속: 화면 설정을 유지한 IMU 수신 시험

사용자가 승인한 범위는 현재 Full SBS/0DoF 설정에서 IMU가 실제로 들어오는지 확인하는
일회성 시험이다. 수신이 되면 최대 5초 숫자만 수집하고 종료하도록 했다. 모드 변경,
카메라, Unity 실행, 기존 투영/보정값 활성화와 센서 융합은 포함하지 않았다.

- SDK 2.4.0의 제품 능력 조회는 Beast의 pose 모드에서 60~1000Hz 항목을 지원한다고 반환했다.
  이 결과는 현재 연결 모드에서 실제 수신이 가능하다는 보장이 아니다.
- 최소 주파수 60Hz로 `xr_device_provider_open_imu`를 한 번 호출했다.
- initialize, callback 등록, start는 성공했으나 IMU 시작은 `-3`이었다.
  동봉 헤더의 명칭은 `VITURE_GLASSES_ERROR_USB_EXEC`이며 USB 읽기/쓰기 실행 오류를 뜻한다.
- 콜백/샘플은 0개였다. 시작 실패로 5초 수집 구간에 진입하지 않고 종료했다.
  따라서 IMU와 마커 자세의 비교, 센서 시각/좌표계 검증은 수행할 수 없었다.
- stop/shutdown은 모두 0, destroy 완료, 자식 프로세스 정상 종료였고 타임아웃은 없었다.
  프로세스 종료 코드 0은 진단 절차 종료를 뜻하며 IMU 수신 성공을 뜻하지 않는다.
- 전후 설정은 mode=1, dof=0, display_mode=55, display_size=3,
  display_distance=7, side_mode=0으로 같았다. Windows 화면 영역과
  카메라/작업대 보정 파일 SHA-256도 변하지 않았다.

동봉 `demo-source/glasses-demo-src.zip`의 `glasses-demo/main.cpp`를 다시 확인했다.
샘플은 Beast의 host IMU 경로에서 Bypass 모드와 해당 모드의 표시 형식을 설정한 후
IMU를 연다. Native 경로에서는 host IMU를 열지 않는다. 이 차이는 원인 후보이나,
이번 한 번의 `-3`만으로 Native 모드의 모든 IMU 기능이 불가능하다고 확정하지 않는다.
펌웨어/USB 상태, 주파수별 차이, raw IMU는 검증하지 않았다.

현재 보정은 Native 화면 크기/거리 설정에서 수집됐다. Bypass 전환은 표시 조건을
바꿀 수 있어 자동으로 시도하지 않았다. 이후 필요하면 기존 값을 기록하고 복구를
확인하는 별도 장치 시험으로 다루며, 기존 보정값의 호환성을 가정하지 않는다.

원본 결과: `%LOCALAPPDATA%/ARAssembly/beast-mvp/sdk/probes/imu-native-20261007-01.json`.
임시 도구: 같은 폴더의 `beast_imu_spike.py`. 도구의 import/숫자 요약 검사와
장치를 열지 않는 info-only 검사를 통과한 뒤 실제 시작 요청을 실행했다.
이 도구와 SDK는 저장소 밖에 둔다. 카메라 영상 저장이나 외부 업로드 코드는 없고
SDK 통계 API도 호출하지 않았다. 바이너리의 전체 네트워크 동작은 독립 검증하지 않았다.

결정: IMU를 당장 필수 의존성으로 추가하지 않는다. 확인된 설정 조회는 향후 보정
조건 기록에 활용할 수 있다. 우선 기존 마커 관측과 Enter 시점의 좌표/시간 연결을
기록해 정합 오차 원인을 나누고 A 자동 정합을 검증한다. IMU 보강은 수신과
카메라 시간축/좌표계 일치를 확인한 뒤 결정한다.

## 후속: Default 설정 뒤 모드 재조회

사용자가 Default로 바꾼 뒤 실제 SDK 값을 두 번 읽었다. 두 결과 모두 mode=1,
dof=0, display_mode=49(0x31), display_size=3, display_distance=7, side_mode=0이었다.
이는 Native/0DoF/일반 2D 1920x1080 60Hz이며 Bypass(mode=0)가 아니다.
따라서 Bypass IMU 시험은 실행하지 않았고 표시 설정도 변경하지 않았다.
설정 조회 프로세스는 stop/shutdown 성공 후 정상 종료했다.

IMU는 회전/가속도 센서이며 Marker Tracking 자체가 아니다. 공식 Unity Marker Tracking은
ArUco 기반이지만 수령한 패키지의 실행 경로는 Android/Neckband다. Windows에서
Bypass를 선택한다고 해당 패키지가 실행되는 것은 아니다. 기존 마커 자세 계산과
Unity SBS 투영 경로를 유지하고 눈별 정합 진단으로 돌아간다.
