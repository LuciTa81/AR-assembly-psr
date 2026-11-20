from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


SPATIAL_POSE_BUDGET_MS = 150


def pose_age_ms(timestamp_ms: int, current_ms: int) -> int:
    if (type(timestamp_ms) is not int or type(current_ms) is not int
            or not 0 < timestamp_ms <= current_ms < 2**63):
        return -1
    return current_ms - timestamp_ms


@dataclass
class SpatialGuidance:
    schema_version: str = "beast_spatial_guidance_v1"
    display_profile_id: str = ""
    camera_profile_id: str = ""
    workspace_profile_id: str = ""
    camera_profile_sha256: str = ""
    workspace_profile_sha256: str = ""
    calibration_status: str = "synthetic"
    display_alignment_verified: bool = False
    coordinate_convention: str = "eye_local_pixels_top_left"
    channel_order: str = "left_half_left_eye_right_half_right_eye"
    display_mode: str = "full_sbs"
    eye_width: int = 1920
    eye_height: int = 1080
    target_id: str = ""
    pose_frame_id: int = -1
    pose_timestamp_ms: int = -1
    pose_age_ms: int = -1
    target_visible: bool = False
    reason: str = "no_pose"
    left_pixel: Optional[list[float]] = None
    right_pixel: Optional[list[float]] = None


def now_ms(perf_counter) -> int:
    return int(perf_counter() * 1000)


@dataclass
class WarningMessage:
    code: str
    message: str


@dataclass(frozen=True)
class AssemblyGuidance:
    schema_version: str = "assembly_guidance_v1"
    phase: str = "GUIDING"
    reason: str = ""
    acknowledgement: str = ""
    acknowledgement_remaining_ms: int = 0
    hold_progress: str = "none"
    hold_remaining_ms: int = 0


@dataclass
class FramePacket:
    frame_id: int
    timestamp_ms: int
    source: str
    frame: Any
    source_path: str = ""
    source_frame_id: Optional[int] = None
    source_timestamp_ms: Optional[int] = None


@dataclass
class OverlayMessage:
    schema_version: str = "realtime_v1"
    session_id: str = ""
    frame_id: int = 0
    timestamp_ms: int = 0
    source: str = "unknown"
    system_status: str = "STARTING"
    marker_status: str = "DISABLED"
    marker_count: int = 0
    warp_quality: float = 0.0
    current_state: str = "S0"
    current_label: str = "Empty workspace"
    next_action: str = "Place the enclosure box"
    target: str = "box"
    confidence: float = 0.0
    held_reason: str = ""
    warning: Optional[WarningMessage] = None
    fps: float = 0.0
    latency_ms: int = 0
    queue_lag_ms: int = 0
    yolo_age_ms: int = -1
    extra: Dict[str, Any] = field(default_factory=dict)
    spatial: Optional[SpatialGuidance] = None
    guidance: Optional[AssemblyGuidance] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.warning is None:
            data["warning"] = None
        return data

