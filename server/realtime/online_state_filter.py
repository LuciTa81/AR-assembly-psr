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
        max_state: str = "S6",
    ):
        if initial_state not in STATES:
            raise ValueError(f"unknown initial state: {initial_state}")
        if max_state not in STATES:
            raise ValueError(f"unknown max state: {max_state}")
        self.state_index = STATES.index(initial_state)
        self.max_state_index = STATES.index(max_state)
        self.min_confidence = float(min_confidence)
        self.min_dwell_frames = int(min_dwell_frames)
        self.dummy_auto_advance_frames = int(dummy_auto_advance_frames)
        self.frames_in_state = 0
        self.last_transition_frame = 0
        self.event_latches: Dict[str, int] = {}
        self.candidate_counts: Dict[str, int] = {}

    def _candidate_state(self, frame_id: int, features: Dict[str, float]) -> Optional[int]:
        if self.dummy_auto_advance_frames <= 0:
            if self.state_index == 0 and float(features.get("box_present_score", 0.0)) >= float(features.get("box_threshold", 0.50)):
                return 1
            if self.state_index == 1 and float(features.get("lid_closed_score", 0.0)) >= float(features.get("lid_threshold", 0.52)):
                return 2
            screw_targets = {
                2: ("a", 3),
                3: ("b", 4),
                4: ("c", 5),
                5: ("d", 6),
            }
            if self.state_index in screw_targets:
                screw, next_index = screw_targets[self.state_index]
                if next_index > self.max_state_index:
                    return None
                raw_score = float(features.get(f"screw_{screw}_done_score", 0.0))
                smooth_score = float(features.get(f"screw_{screw}_done_score_smooth", raw_score))
                score = max(raw_score, smooth_score)
                raw_delta = float(features.get(f"screw_{screw}_done_score_delta", 0.0))
                smooth_delta = float(features.get(f"screw_{screw}_done_score_delta_smooth", raw_delta))
                delta = max(raw_delta, smooth_delta)
                threshold = float(features.get(f"screw_done_threshold_{screw}", features.get("screw_done_threshold", 0.54)))
                delta_threshold = float(features.get(f"screw_delta_threshold_{screw}", features.get("screw_delta_threshold", 0.012)))
                event_min_score = float(features.get(f"screw_event_min_score_{screw}", features.get("screw_event_min_score", 0.43)))
                hold_frames = int(features.get(f"screw_event_hold_frames_{screw}", features.get("screw_event_hold_frames", 12)))
                confirm_frames = int(features.get(f"screw_confirm_frames_{screw}", features.get("screw_confirm_frames", 1)))
                min_dwell_frames = int(features.get(f"screw_min_dwell_frames_{screw}", features.get("screw_min_dwell_frames", self.min_dwell_frames)))
                require_delta = bool(features.get("require_screw_delta", 1))
                if delta >= delta_threshold and score >= event_min_score:
                    self.event_latches[screw] = max(1, hold_frames)
                active_event = self.event_latches.get(screw, 0) > 0
                if active_event:
                    self.event_latches[screw] = self.event_latches.get(screw, 0) - 1
                if score >= threshold and (active_event or not require_delta):
                    self.candidate_counts[screw] = self.candidate_counts.get(screw, 0) + 1
                    if self.frames_in_state >= min_dwell_frames and self.candidate_counts[screw] >= confirm_frames:
                        return next_index
                else:
                    self.candidate_counts[screw] = 0
            return None
        if self.state_index >= len(STATES) - 1:
            return None
        if self.frames_in_state >= self.dummy_auto_advance_frames:
            return self.state_index + 1
        return None

    def _screw_confidence(self, screw: str, features: Dict[str, float]) -> float:
        raw_score = float(features.get(f"screw_{screw}_done_score", 0.0))
        smooth_score = float(features.get(f"screw_{screw}_done_score_smooth", raw_score))
        score = max(raw_score, smooth_score)
        raw_delta = max(0.0, float(features.get(f"screw_{screw}_done_score_delta", 0.0)))
        smooth_delta = max(
            0.0,
            float(
                features.get(
                    f"screw_{screw}_done_score_delta_smooth",
                    raw_delta,
                )
            ),
        )
        delta = max(raw_delta, smooth_delta)
        return min(1.0, score + 2.0 * delta)

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
            elif candidate is not None and 3 <= candidate <= 6:
                screw = {3: "a", 4: "b", 5: "c", 6: "d"}[candidate]
                confidence = self._screw_confidence(screw, features)
            else:
                confidence = float(features.get("confidence", 0.80 if candidate is not None else 0.55))
            output_confidence = confidence
            if candidate is not None and self.frames_in_state >= self.min_dwell_frames and confidence >= self.min_confidence:
                prev = STATES[self.state_index]
                self.state_index = candidate
                self.frames_in_state = 0
                self.last_transition_frame = frame_id
                self.event_latches.clear()
                self.candidate_counts.clear()
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
