from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from server.realtime.state_definitions import NEXT_ACTIONS, STATE_LABELS, STATES, TARGETS
from server.realtime.guidance_timing import GuidanceTiming, TimedEvidenceGate
from server.realtime.schemas import AssemblyGuidance


@dataclass
class StateEstimate:
    state: str
    label: str
    next_action: str
    target: str
    confidence: float
    held_reason: str = ""
    transition_event: str = ""
    guidance: Optional[AssemblyGuidance] = None


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
        guidance_policy: str = "legacy_frames",
        timing: Optional[dict] = None,
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
        self.last_observation_id = -1
        if guidance_policy not in {"legacy_frames", "timed_v1"}:
            raise ValueError(f"unknown guidance policy: {guidance_policy}")
        if self.state_index > self.max_state_index:
            raise ValueError("initial state exceeds max state")
        if guidance_policy == "timed_v1" and self.dummy_auto_advance_frames:
            raise ValueError("timed_v1 cannot use dummy auto advance")
        self.timed_gate = TimedEvidenceGate(GuidanceTiming(**(timing or {}))) if guidance_policy == "timed_v1" else None
        self.ack_until_ms, self.ack_text = 0, ""
        self._hold_recheck = False

    @classmethod
    def from_config(cls, config):
        return cls(**{key: config[key] for key in (
            "initial_state", "min_confidence", "min_dwell_frames", "dummy_auto_advance_frames",
            "max_state", "guidance_policy", "timing") if key in config})

    def _timed_update(self, frame_id, marker_ok, features, *, timestamp_ms, observation_id,
                      observation_timestamp_ms, evidence_valid, roi_valid):
        had_progress = self.timed_gate.started_at is not None or self.timed_gate._suspended is not None
        decision = self.timed_gate.evaluate(self.state_index, frame_id, timestamp_ms, marker_ok,
            features, observation_id=observation_id, observation_timestamp_ms=observation_timestamp_ms,
            evidence_valid=evidence_valid, roi_valid=roi_valid, min_confidence=self.min_confidence)
        transition = ""
        phase = decision.phase
        if phase == "PAUSED":
            self.ack_until_ms, self.ack_text = 0, ""
        elif decision.advance and self.state_index < self.max_state_index:
            previous = STATES[self.state_index]
            self.state_index += 1
            transition = f"{previous}->{STATES[self.state_index]}"
            self.last_transition_frame = frame_id
            self.ack_text = (STATE_LABELS[STATES[self.state_index]] if self.state_index <= 2
                             else f"Screw {'ABCD'[self.state_index - 3]} interaction observed")
            self.ack_until_ms = timestamp_ms + self.timed_gate.timing.ack_ms
            self.timed_gate.reset_step(after_frame=frame_id)
            phase = "AWAITING_CONFIRMATION" if self.state_index == 6 else "GUIDING"
        remaining = max(0, self.ack_until_ms - timestamp_ms) if type(timestamp_ms) is int else 0
        state = STATES[self.state_index]
        action = NEXT_ACTIONS[state]
        if phase == "OBSERVING":
            action = ("Checking box placement" if self.state_index == 0 else "Checking lid closure"
                      if self.state_index == 1 else f"Tool at screw {'ABCD'[self.state_index - 2]}")
        elif phase == "OBSERVED":
            action = f"When finished, move driver clear of screw {'ABCD'[self.state_index - 2]}"
        elif phase == "PAUSED":
            action = {
                "marker_not_stable": "Tracking paused. Keep the workspace markers visible.",
                "tool_not_visible": "Tool not visible. Keep the driver in view.",
                "multiple_tool_candidates": "Multiple tool candidates. Recheck the target with one driver.",
                "tool_position_unknown": "Tool position unclear. Keep the driver in view.",
            }.get(decision.reason, "Recognition paused. Waiting for fresh evidence.")
        hold_progress, hold_remaining = self._hold_feedback(had_progress, phase, transition, timestamp_ms)
        if hold_progress == 'checkpoint' and phase == 'PAUSED':
            action += (f' HOLD kept. Recheck screw {"ABCD"[self.state_index - 2]} '
                       'with one driver; no repeated HOLD required.')
        return StateEstimate(state, STATE_LABELS[state], action, TARGETS[state],
            decision.confidence, decision.reason, transition,
            AssemblyGuidance(phase=phase, reason=decision.reason,
                acknowledgement=self.ack_text if remaining else "",
                acknowledgement_remaining_ms=remaining,
                hold_progress=hold_progress, hold_remaining_ms=hold_remaining))

    def _hold_feedback(self, had_progress, phase, transition, timestamp_ms):
        # Read-only UX metadata; it never feeds back into evidence timing or transitions.
        gate = self.timed_gate
        if transition or not 2 <= self.state_index <= 5 or phase in ('OBSERVING', 'OBSERVED'):
            self._hold_recheck = False
            return 'none', 0
        if gate._suspended is not None:
            source_time, _, armed = gate._suspended
            remaining = gate._resume_budget(armed) - (timestamp_ms - source_time) if type(timestamp_ms) is int else 0
            if remaining > 0:
                return 'retained', remaining
            self._hold_recheck = True
        elif had_progress and gate.started_at is None:
            self._hold_recheck = True
        if gate.completed_hold:
            return 'checkpoint', 0
        return ('recheck' if self._hold_recheck else 'none'), 0

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
                require_yolo = bool(features.get("require_yolo_for_screw", 0))
                yolo_score = max(
                    float(features.get(f"tool_score_{screw}", 0.0)),
                    float(features.get(f"tip_screw_score_{screw}", 0.0)),
                )
                yolo_threshold = float(features.get(f"yolo_tool_score_threshold_{screw}", features.get("yolo_tool_score_threshold", 0.35)))
                other_yolo_scores = [
                    max(
                        float(features.get(f"tool_score_{other}", 0.0)),
                        float(features.get(f"tip_screw_score_{other}", 0.0)),
                    )
                    for other in ["a", "b", "c", "d"]
                    if other != screw
                ]
                max_other_yolo = max(other_yolo_scores, default=0.0)
                dominance_ratio = float(features.get("yolo_target_dominance_ratio", 0.0))
                dominance_ok = dominance_ratio <= 0.0 or yolo_score >= max_other_yolo * dominance_ratio
                yolo_ok = yolo_score >= yolo_threshold and dominance_ok
                if require_yolo and not yolo_ok:
                    self.candidate_counts[screw] = 0
                    return None
                if (delta >= delta_threshold and score >= event_min_score) or yolo_ok:
                    self.event_latches[screw] = max(1, hold_frames)
                active_event = self.event_latches.get(screw, 0) > 0
                if active_event:
                    self.event_latches[screw] = self.event_latches.get(screw, 0) - 1
                score_ok = score >= threshold or (require_yolo and yolo_ok)
                if score_ok and (active_event or not require_delta):
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
        roi_confidence = min(1.0, score + 2.0 * delta)
        yolo_score = max(
            float(features.get(f"tool_score_{screw}", 0.0)),
            float(features.get(f"tip_screw_score_{screw}", 0.0)),
        )
        if bool(features.get("require_yolo_for_screw", 0)) and yolo_score > 0.0:
            yolo_confidence = min(1.0, 0.55 + 0.45 * yolo_score)
            return max(roi_confidence, yolo_confidence)
        return roi_confidence

    def _required_confidence(self, candidate: int, features: Dict[str, float]) -> float:
        if candidate == 1:
            return float(features.get("box_min_confidence", self.min_confidence))
        if candidate == 2:
            return float(features.get("lid_min_confidence", self.min_confidence))
        if 3 <= candidate <= 6:
            return float(features.get("screw_min_confidence", self.min_confidence))
        return self.min_confidence

    def update(
        self, frame_id: int, marker_ok: bool, features: Optional[Dict[str, float]] = None,
        *, observation_id: Optional[int] = None, evidence_valid: bool = True,
        timestamp_ms: Optional[int] = None, observation_timestamp_ms: Optional[int] = None,
        roi_valid: bool = False,
    ) -> StateEstimate:
        features = features or {}
        if self.timed_gate is not None:
            return self._timed_update(frame_id, marker_ok, features, timestamp_ms=timestamp_ms,
                observation_id=observation_id, observation_timestamp_ms=observation_timestamp_ms,
                evidence_valid=evidence_valid, roi_valid=roi_valid)
        held_reason = ""
        transition_event = ""
        output_confidence = float(features.get("confidence", 0.55))
        needs_yolo = (
            2 <= self.state_index <= 5 and self.dummy_auto_advance_frames <= 0
            and bool(features.get("require_yolo_for_screw", 0))
        )
        invalid_evidence = needs_yolo and (
            not evidence_valid or observation_id is None
            or observation_id < 0 or observation_id > frame_id
        )

        if not marker_ok or invalid_evidence:
            self.event_latches.clear()
            self.candidate_counts.clear()
            self.frames_in_state = 0
            held_reason = "marker_not_stable" if not marker_ok else "invalid_observation"
            output_confidence = min(output_confidence, 0.40)
        elif needs_yolo and observation_id <= self.last_observation_id:
            held_reason = "duplicate_observation"
        else:
            if needs_yolo:
                self.last_observation_id = observation_id
            self.frames_in_state += 1
            candidate = self._candidate_state(frame_id, features)
            if candidate == 1:
                raw = float(features.get("box_present_score", 0.80))
                smooth = float(features.get("box_present_score_smooth", raw))
                confidence = max(raw, smooth)
            elif candidate == 2:
                raw = float(features.get("lid_closed_score", 0.80))
                smooth = float(features.get("lid_closed_score_smooth", raw))
                confidence = max(raw, smooth)
            elif candidate is not None and 3 <= candidate <= 6:
                screw = {3: "a", 4: "b", 5: "c", 6: "d"}[candidate]
                confidence = self._screw_confidence(screw, features)
            else:
                confidence = float(features.get("confidence", 0.80 if candidate is not None else 0.55))
            output_confidence = confidence
            required_confidence = self._required_confidence(candidate, features) if candidate is not None else self.min_confidence
            if candidate is not None and self.frames_in_state >= self.min_dwell_frames and confidence >= required_confidence:
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
