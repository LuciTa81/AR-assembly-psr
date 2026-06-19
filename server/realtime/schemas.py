from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


def now_ms(perf_counter) -> int:
    return int(perf_counter() * 1000)


@dataclass
class WarningMessage:
    code: str
    message: str


@dataclass
class FramePacket:
    frame_id: int
    timestamp_ms: int
    source: str
    frame: Any
    source_path: str = ""


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

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.warning is None:
            data["warning"] = None
        return data

