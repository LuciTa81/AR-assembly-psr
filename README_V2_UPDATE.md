# Vision Assembly PSR v2 업데이트 패키지

이 패키지는 기존 `Vision-assembly-psr`에 6개 ArUco 기반 v2 파이프라인과 HMM v2 실험 코드를 추가한 버전입니다.

## 핵심 변경점

1. **4개 ArUco → 6개 ArUco**
   - ID 0/1/2 = 위쪽 좌/중/우
   - ID 3/4/5 = 아래쪽 좌/중/우
   - 보이는 marker corner 전체로 RANSAC homography를 계산합니다.

2. **calibrated marker layout**
   - `marker_layout_v2.yaml`의 가상 좌표를 그대로 쓰지 않고, 기준 프레임에서 실제 마커 위치를 보정한 layout을 생성합니다.

3. **warp quality 기록**
   - `homography_valid`, `homography_usable`, `marker_count`, `warp_quality`, `homography_source`를 CSV에 저장합니다.

4. **YOLO feature v2**
   - YOLO driver bbox를 homography로 warped 좌표계에 투영합니다.
   - `tool_near_a/b/c/d`, `tool_dist_a/b/c/d`를 생성합니다.
   - 기존 one-hot 문제를 줄이기 위해 multi-hot near를 지원합니다.
   - `--distance-mode polygon|center|tip` 옵션을 제공합니다.

5. **MediaPipe v2**
   - frame당 최대 2개 손을 저장합니다.
   - YOLO driver bbox와 가까운 손을 작업손으로 선택하는 hybrid feature를 생성합니다.
   - handedness가 반대로 잡히는 경우 `--swap-handedness` 옵션을 사용할 수 있습니다.

6. **HMM input v2 / baseline v2**
   - ROI + YOLO + MediaPipe + homography quality를 병합합니다.
   - `tool_near_*_smooth`, `tool_seen_*_cum`, `index_near_*_smooth`를 생성합니다.
   - HMM에서는 YOLO를 완료 상태 자체가 아니라 상태 전이 trigger로 사용합니다.

## 먼저 실행할 것

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_env_v2.ps1
.\scripts\check_package_v2.ps1 -SessionId session_17
```

## 전체 v2 파이프라인 실행

전제:

- `data\raw_sessions\session_17` 세션이 존재해야 합니다.
- `models\yolo\driver_standard_model\best.pt`가 있어야 합니다.
- `configs\roi_layout_v2.yaml`을 현재 warped v2 기준으로 맞춰두어야 합니다.
- `refs\roi_templates_v2`에 reference crop이 있어야 합니다.
- `labels\labels_segments.csv`가 세션 구간 라벨을 포함해야 합니다.

기본 실행:

```powershell
.\scripts\run_session_pipeline_v2.ps1 -SessionId session_17
```

MediaPipe handedness가 좌우 반대로 잡히는 경우:

```powershell
.\scripts\run_session_pipeline_v2.ps1 -SessionId session_17 -SwapHandedness
```

C 단계가 약하게 잡히는 경우 YOLO tip 모드 실험:

```powershell
.\scripts\run_session_pipeline_v2.ps1 -SessionId session_17 -YoloDistanceMode tip -YoloNearThreshold 120
```

HMM만 다시 튜닝:

```powershell
.\scripts\run_hmm_v2_only.ps1 -SessionId session_17 -ToolThreshold 0.35 -IndexWeight 0.0 -SelfProb 0.94 -NextProb 0.06
```

## 현재 알려진 이슈

- ROI template score는 나사 상태 차이가 작아 0.45~0.58 근처에서 움직일 수 있습니다. 따라서 screw ROI는 약한 trend feature로만 쓰는 것을 권장합니다.
- MediaPipe는 양손 작업에서 작업손 분리가 어렵습니다. 기본 HMM 실험에서는 `IndexWeight=0.0`으로 두고, ablation용으로 사용하는 것을 권장합니다.
- 현재 관찰된 병목은 C 작업 구간에서 `tool_near_c`가 충분히 살아나지 않는 문제입니다. 이를 위해 `build_yolo_features.py`에 multi-hot near와 tip mode를 추가했습니다.
