# 렌더링 상세 및 아이콘 출처

작성일: 2026-11-26. 기존 v4를 유지하고 v5를 별도로 생성했습니다. 앱·보정·서버는 수정하지 않았습니다.

## 렌더링 코드 대조

- `app/src/main/java/com/lucita/beastgate/EyeProjection.java`: 좌우 3x4 행렬, 프로필 해시, 양의 깊이, 좌표 범위 검사.
- `app/src/main/java/com/lucita/beastgate/StereoOverlayView.java`: 3840x1080 출력 조건, 각 눈의 clip/translate, Canvas 안내, 500ms 관측 유효 시간.
- `app/src/main/java/com/lucita/beastgate/MainActivity.java`: Presentation과 FrameLayout, StereoOverlayView 아래층, PartPreviewView 위층.
- `app/src/main/java/com/lucita/beastgate/PartPreviewView.java`: 로컬 WebView, 네트워크 차단, 작업별 부품 선택.
- `app/src/main/assets/parts/parts.js`: Three.js PerspectiveCamera, 눈별 viewport/scissor, 부품과 테두리 렌더링.

R1–R6는 코드의 책임을 설명하기 위한 단계 구분입니다. 하나의 직렬 함수 호출 순서나 새로운 구현을 뜻하지 않습니다. Android Presentation은 레이어의 호스트로 먼저 만들어지며, R6에서는 그 외부 화면 출력 역할을 나타냈습니다.

## 이번에 공식 사이트에서 확인한 아이콘

- VITURE: https://www.viture.com/beast
- VITURE 사이트 아이콘: https://www.viture.com/beast/icon.png?icon.168eb4f7.png
- ONNX Runtime 로고 안내: https://onnxruntime.ai/docs/reference/citing.html
- ONNX Runtime 밝은 배경용 공식 아이콘: https://onnxruntime.ai/images/logos/onnxruntime/ORT_icon_for_light_bg.svg
- Android Presentation 참고: https://developer.android.com/reference/android/app/Presentation

기존 Android, OpenCV, Python, Unity, Three.js, GitHub 등의 로고는 Devicon의 식별용 자산을 유지했습니다. AWS EC2/S3는 awslabs 아키텍처 아이콘입니다. 구체적인 브랜드가 없는 좌표 변환, 유효성 검사, 상태 전이 등에는 Lucide 기능 아이콘을 사용했습니다. 모든 기능에 임의의 기술 로고를 붙이지 않았습니다. 기존 아이콘 원본 URL은 상위 `icons/sources.json`, 추가 공식 아이콘 URL은 `icons/official-render-sources.json`에 있습니다.

MediaPipe/HMM은 통합 설계안이며 현재 APK 미적용이라는 표기를 유지했습니다. 실제 구현이 완료되었다는 증빙으로 사용하면 안 됩니다.

## 검사

35개 모듈, 38개 연결선. 선 교차·박스 관통 0건. 브라우저에서 측정한 박스 내부 글자 168개에 대해 넘침·화살표 겹침 0건. 전체 이미지와 렌더링 상세 이미지 시각 확인.
