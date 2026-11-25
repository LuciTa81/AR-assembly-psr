# AR Assembly Architecture v2

2026-11-25 전시 버전의 코드 대조 결과를 바탕으로 제작한 시스템 구성도입니다.

## 파일

- `01-AR-Assembly-Architecture.png`: 전체 시스템, 6400 x 3600.
- `02-Cloud-Recording-Pipeline.png`: 인증, 중계, 녹화, 저장 상세, 6400 x 3600.
- `AR-Assembly-Architecture-v2.pdf`: 두 도면을 포함한 PDF.
- 같은 이름의 `.svg`: 아이콘이 내장된 편집·확대용 원본.
- `*-preview.png`: 미리보기 이미지.
- `validation.json`: 화살표 교차와 노드 관통 검사.
- `visual-validation.json`: 브라우저 글자 크기 측정 기반 넘침·화살표 겹침 검사.

## 표현 범위

실선은 현재 동작 경로입니다. Python과 Unity는 기존 개발·검증 기반으로 별도 표기했습니다. MediaPipe와 HMM·Viterbi는 현재 Android 앱에 적용된 기능이 아니며 점선의 확장 설계 영역으로 구분했습니다. NumPy 로고를 현재 Android 좌표 연산 모듈에 붙이지 않고 일반 좌표 아이콘을 사용했습니다.

목표 인코딩 프레임률 30fps와 확인된 녹화 파일의 실측 평균 약 6.7fps는 서로 다릅니다. 웹 카메라 영상에는 안경의 양안 오버레이가 합성되지 않습니다. 기계적 체결 토크를 측정한다는 의미로 해석하면 안 됩니다.

## 아이콘 출처

- [Devicon](https://github.com/devicons/devicon): Python, Unity, OpenCV, Android, GitHub, Chrome, PostgreSQL, Next.js, Node.js, nginx, Three.js 로고.
- [Simple Icons](https://github.com/simple-icons/simple-icons): MediaPipe, ONNX, Ultralytics, Vercel 로고.
- [AWS Icons for PlantUML](https://github.com/awslabs/aws-icons-for-plantuml): EC2와 Amazon S3 아키텍처 아이콘.
- [Lucide](https://github.com/lucide-icons/lucide): 카메라, 좌표, 안경, 상태 전이, 네트워크, 다운로드 등의 기능 아이콘.

로고는 해당 기술을 식별하기 위해 사용했으며 공급자의 인증·후원을 의미하지 않습니다. 상세 원본 URL은 상위 `icons/sources.json`에 기록되어 있습니다.
