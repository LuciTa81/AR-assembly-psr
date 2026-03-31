# Session Schema

## 목적
Quest 3에서 저장한 조립 세션을
- 재생
- 검증
- 라벨링
- ROI 추출
- 학습 데이터셋 생성
에 공통으로 사용할 수 있도록 세션 저장 형식을 고정한다.

---

## 폴더 구조

```text
sessions/
  session_YYYYMMDD_HHMMSS/
    meta.json
    frames.csv
    frames/
      000001.jpg
      000002.jpg
      000003.jpg
```

예시:

```text
sessions/
  session_20260331_113750/
    meta.json
    frames.csv
    frames/
      000001.jpg
      000002.jpg
      000003.jpg
```

---

## 세션 ID 규칙

- 형식: `session_YYYYMMDD_HHMMSS`
- 예시: `session_20260331_113750`

규칙:
- 같은 세션 폴더 안에는 하나의 연속 촬영 세션만 저장한다.
- 세션 ID는 로컬 시간 기준 생성한다.

---

## meta.json

세션 전체 메타데이터를 저장한다.

### 필수 필드

- `session_id`
- `device`
- `capture_source`
- `requested_resolution`
- `actual_resolution`
- `capture_interval_sec`
- `image_format`
- `jpg_quality`
- `started_at`
- `stopped_at`
- `app_version`

### 예시

```json
{
  "session_id": "session_20260331_113750",
  "device": "Quest3",
  "capture_source": "passthrough_camera_access",
  "requested_resolution": "use_inspector_setting",
  "actual_resolution": "640x480",
  "capture_interval_sec": 0.5,
  "image_format": "jpg",
  "jpg_quality": 90,
  "started_at": "2026-03-31T11:37:50.1234567+09:00",
  "stopped_at": "2026-03-31T11:38:20.4567890+09:00",
  "app_version": "0.1.0"
}
```

### 필드 설명

- `session_id`: 세션 폴더명과 동일
- `device`: 촬영 장치 이름
- `capture_source`: 입력 소스
- `requested_resolution`: Unity inspector에서 의도한 해상도
- `actual_resolution`: 실제 저장 해상도
- `capture_interval_sec`: 프레임 저장 간격
- `image_format`: 저장 포맷
- `jpg_quality`: JPG 인코딩 품질
- `started_at`: 세션 시작 시각
- `stopped_at`: 세션 종료 시각
- `app_version`: 앱 버전 문자열

---

## frames.csv

프레임 단위 메타데이터를 저장한다.

### 컬럼

- `frame_id`
- `timestamp_iso`
- `timestamp_unix_ms`
- `image_path`
- `width`
- `height`

### 예시

```csv
frame_id,timestamp_iso,timestamp_unix_ms,image_path,width,height
1,2026-03-31T11:37:50.3000000+09:00,1774924670300,frames/000001.jpg,640,480
2,2026-03-31T11:37:50.8000000+09:00,1774924670800,frames/000002.jpg,640,480
3,2026-03-31T11:37:51.3000000+09:00,1774924671300,frames/000003.jpg,640,480
```

### 컬럼 설명

- `frame_id`: 1부터 시작하는 연속 정수
- `timestamp_iso`: ISO-8601 시각 문자열
- `timestamp_unix_ms`: Unix epoch milliseconds
- `image_path`: 세션 폴더 기준 상대 경로
- `width`, `height`: 해당 프레임 실제 해상도

---

## frames/

실제 이미지 프레임을 저장한다.

### 파일명 규칙

- 형식: `000001.jpg`, `000002.jpg`, ...
- 6자리 zero padding 사용

규칙:
- `frames.csv`의 `image_path`와 반드시 일치해야 한다.
- 누락 프레임이 있으면 검증 단계에서 경고한다.

---

## 유효성 규칙

정상 세션은 아래 조건을 만족해야 한다.

1. `meta.json` 존재
2. `frames.csv` 존재
3. `frames/` 폴더 존재
4. `frames.csv` 헤더가 정확함
5. `frame_id`는 1부터 시작하는 연속 정수
6. `image_path`가 실제 파일과 일치함
7. `width`, `height`가 양수
8. 프레임 수가 1개 이상
9. `session_id`와 폴더명이 일치함

---

## 현재 버전 정책

현재는 `v1` 스키마로 운영한다.

향후 변경이 필요하면:
- 새 필드 추가는 허용
- 기존 필드 이름 변경은 지양
- 파이프라인 호환성이 깨지는 변경은 문서에 명시
