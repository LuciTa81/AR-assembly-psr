from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from server.realtime.state_definitions import NEXT_ACTIONS, STATE_LABELS, STATES, TARGETS


@dataclass
class StateEstimate:
    state: str
    label: str
    next_action: str
    target: str
    confidence: float
    held_reason: str = ""
    transition_event: str = ""


class OnlineStateFilter:
    """Small causal state filter for the first realtime harness.

    The initial implementation is intentionally conservative. It can run in
    dummy mode without vision features, and it refuses to advance while marker
    quality is not OK. Later phases can replace _candidate_state with ROI/YOLO
    evidence without changing the overlay/logger interface.
    """

    def __init__(
        self,
        initial_state: str = "S0",
        min_confidence: float = 0.75,
        min_dwell_frames: int = 3,
        dummy_auto_advance_frames: int = 0,
    ):
        if initial_state not in STATES:
            raise ValueError(f"unknown initial state: {initial_state}")
        self.state_index = STATES.index(initial_state)
        self.min_confidence = float(min_confidence)
        self.min_dwell_frames = int(min_dwell_frames)
        self.dummy_auto_advance_frames = int(dummy_auto_advance_frames)
        self.frames_in_state = 0
        self.last_transition_frame = 0

    def _candidate_state(self, frame_id: int, features: Dict[str, float]) -> Optional[int]:
        if self.dummy_auto_advance_frames <= 0:
            if self.state_index == 0 and float(features.get("box_present_score", 0.0)) >= float(features.get("box_threshold", 0.50)):
                return 1
            if self.state_index == 1 and float(features.get("lid_closed_score", 0.0)) >= float(features.get("lid_threshold", 0.52)):
                return 2
            return None
        if self.state_index >= len(STATES) - 1:
            return None
        if self.frames_in_state >= self.dummy_auto_advance_frames:
            return self.state_index + 1
        return None

    def update(self, frame_id: int, marker_ok: bool, features: Optional[Dict[str, float]] = None) -> StateEstimate:
        features = features or {}
        self.frames_in_state += 1
        held_reason = ""
        transition_event = ""
        output_confidence = float(features.get("confidence", 0.55))

        if not marker_ok:
            held_reason = "marker_not_stable"
            output_confidence = min(output_confidence, 0.40)
        else:
            candidate = self._candidate_state(frame_id, features)
            if candidate == 1:
                confidence = float(features.get("box_present_score", 0.80))
            elif candidate == 2:
                confidence = float(features.get("lid_closed_score", 0.80))
            else:
                confidence = float(features.get("confidence", 0.80 if candidate is not None else 0.55))
            output_confidence = confidence
            if candidate is not None and self.frames_in_state >= self.min_dwell_frames and confidence >= self.min_confidence:
                prev = STATES[self.state_index]
                self.state_index = candidate
                self.frames_in_state = 0
                self.last_transition_frame = frame_id
                transition_event = f"{prev}->{STATES[self.state_index]}"
            elif candidate is not None:
                held_reason = "low_confidence_or_dwell"
            else:
                held_reason = "no_transition_candidate"

        state = STATES[self.state_index]
        return StateEstimate(
            state=state,
            label=STATE_LABELS[state],
            next_action=NEXT_ACTIONS[state],
            target=TARGETS[state],
            confidence=output_confidence,
            held_reason=held_reason,
            transition_event=transition_event,
        )
