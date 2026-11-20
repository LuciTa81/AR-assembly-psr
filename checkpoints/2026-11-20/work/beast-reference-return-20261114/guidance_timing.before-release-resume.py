from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GuidanceTiming:
    placement_ms: int = 300
    engage_ms: int = 800
    release_ms: int = 400
    max_gap_ms: int = 350
    max_age_ms: int = 800
    ack_ms: int = 1200
    release_score_max: float = 0.15
    resume_grace_ms: int = 0
    completed_hold_resume_ms: int = 0
    source_recovery_boundary: bool = False
    retain_neutral_recovery: bool = False
    release_absence_ms: int = 0
    retain_completed_hold: bool = False

    def __post_init__(self):
        for name in ("placement_ms", "engage_ms", "release_ms", "max_gap_ms", "max_age_ms", "ack_ms"):
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= (3000 if name == "ack_ms" else 10000):
                raise ValueError(f"timing.{name} must be a positive bounded integer in ms")
        if not finite(self.release_score_max) or not 0 <= self.release_score_max < 1:
            raise ValueError("timing.release_score_max must be in [0,1)")
        if type(self.resume_grace_ms) is not int or not 0 <= self.resume_grace_ms <= 1000:
            raise ValueError('timing.resume_grace_ms must be an integer in 0..1000 ms')
        if type(self.completed_hold_resume_ms) is not int or not 0 <= self.completed_hold_resume_ms <= 3000:
            raise ValueError('timing.completed_hold_resume_ms must be an integer in 0..3000 ms')
        if type(self.source_recovery_boundary) is not bool:
            raise ValueError('timing.source_recovery_boundary must be a boolean')
        if type(self.retain_neutral_recovery) is not bool:
            raise ValueError('timing.retain_neutral_recovery must be a boolean')
        if (type(self.release_absence_ms) is not int
                or self.release_absence_ms != 0 and not 400 <= self.release_absence_ms <= 1000):
            raise ValueError('timing.release_absence_ms must be 0 or an integer in 400..1000 ms')
        if type(self.retain_completed_hold) is not bool:
            raise ValueError('timing.retain_completed_hold must be a boolean')
        if self.retain_completed_hold and not self.completed_hold_resume_ms:
            raise ValueError('completed HOLD checkpoints require bounded direct recovery')


@dataclass(frozen=True)
class EvidenceDecision:
    phase: str = "GUIDING"
    reason: str = ""
    advance: bool = False
    confidence: float = 0.0


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class TimedEvidenceGate:
    """Evidence timing only; OnlineStateFilter owns and changes the assembly step."""

    def __init__(self, timing: GuidanceTiming):
        self.timing = timing
        self.last_frame = self.last_frame_time = -1
        self.last_observation = self.last_observation_time = -1
        self.recovery_after_frame = -1
        self.reset_step()

    def reset_step(self, *, after_frame=None):
        self.started_at = self.release_at = None
        self._release_clear_at = self._release_absent_at = None
        self.armed = False
        self.completed_hold = False
        self._resumed_hold = False
        self._progress_time = -1
        self._suspended = None
        self.decision = EvidenceDecision()
        if after_frame is not None:
            self.recovery_after_frame = max(self.recovery_after_frame, after_frame)

    def _resume_budget(self, armed):
        return (self.timing.completed_hold_resume_ms if armed and self.timing.completed_hold_resume_ms
                else self.timing.resume_grace_ms)

    def _checkpoint_payload_error(self, features, state_index, min_confidence):
        # Missing tips use finite -1 sentinels; corrupt values are not visual ambiguity.
        source = features.get('tool_tip_source', 0)
        count = features.get('driver_count')
        if (not finite(count) or count < 0 or count != int(count)
                or not finite(features.get('driver_visible')) or features['driver_visible'] not in (0, 1)
                or not finite(source) or source not in (0, 1, 2)
                or not all(finite(features.get(k)) for k in ('tool_tip_x', 'tool_tip_y'))):
            return 'tool_position_unknown'
        for name in 'abcd':
            distance = features.get(f'tool_dist_{name}')
            if (not all(finite(features.get(k)) and 0 <= features[k] <= 1
                        for k in (f'tool_score_{name}', f'tip_screw_score_{name}'))
                    or not finite(distance) or distance < 0 and not (source == 0 and distance == -1)):
                return 'tool_position_unknown'
        name = 'abcd'[state_index - 2]
        threshold = features.get(f'yolo_tool_score_threshold_{name}', features.get('yolo_tool_score_threshold', .35))
        dominance = features.get('yolo_target_dominance_ratio', 1.)
        required = features.get('screw_min_confidence', min_confidence)
        if (not finite(threshold) or not self.timing.release_score_max < threshold <= 1
                or not finite(dominance) or dominance < 0
                or not finite(required) or not 0 <= required <= 1):
            return 'invalid_threshold'
        return ''

    def _pause(self, reason, frame_id=None, *, recoverable=False, preserve_checkpoint=False):
        checkpoint = self.completed_hold if recoverable or preserve_checkpoint else False
        saved = self._suspended if recoverable else None
        if recoverable and saved is None and self.started_at is not None:
            saved = (self._progress_time, self._progress_time - self.started_at, self.armed)
        self.reset_step()
        self.completed_hold = checkpoint
        budget = self._resume_budget(saved[2]) if saved is not None else 0
        if (budget and saved[0] > 0 and 0 <= self.last_frame_time - saved[0] <= budget):
            self._suspended = saved
        if type(frame_id) is int:
            self.recovery_after_frame = max(self.recovery_after_frame, frame_id)
        self.decision = EvidenceDecision("PAUSED", reason)
        return self.decision

    def evaluate(self, state_index, frame_id, timestamp_ms, marker_ok, features, *,
                 observation_id, observation_timestamp_ms, evidence_valid, roi_valid,
                 min_confidence):
        if (type(frame_id) is not int or frame_id < 1 or type(timestamp_ms) is not int
                or timestamp_ms <= 0 or frame_id <= self.last_frame
                or timestamp_ms <= self.last_frame_time):
            return self._pause("invalid_frame", frame_id)
        frame_gap = timestamp_ms - self.last_frame_time
        self.last_frame, self.last_frame_time = frame_id, timestamp_ms
        if frame_gap > self.timing.max_gap_ms:
            if self._release_absent_at is not None:
                self._pause('observation_gap', recoverable=True)
            self._release_clear_at = self._release_absent_at = None
        if not marker_ok:
            return self._pause("marker_not_stable", frame_id, recoverable=2 <= state_index <= 5)
        if state_index == 6:
            self.decision = EvidenceDecision("AWAITING_CONFIRMATION")
            return self.decision
        if state_index < 2:
            if not roi_valid:
                return self._pause("invalid_roi", frame_id)
            if frame_gap > self.timing.max_gap_ms:
                self.reset_step()
            prefix = "box" if state_index == 0 else "lid"
            score = features.get("box_present_score" if state_index == 0 else "lid_closed_score")
            threshold = features.get(prefix + "_threshold", 0.50 if state_index == 0 else 0.52)
            required = features.get(prefix + "_min_confidence", min_confidence)
            if not all(finite(v) and 0 <= v <= 1 for v in (score, threshold, required)):
                return self._pause("invalid_roi", frame_id)
            if score < max(threshold, required):
                self.reset_step()
                return self.decision
            if self.started_at is None:
                self.started_at = timestamp_ms
            self.decision = EvidenceDecision("OBSERVING", confidence=score,
                advance=timestamp_ms - self.started_at >= self.timing.placement_ms)
            return self.decision

        # Waiting for an in-flight pre-boundary result must not move the boundary.
        if type(observation_id) is int and 0 < observation_id <= self.recovery_after_frame:
            return self._pause("invalid_observation", recoverable=True)
        if self.completed_hold and evidence_valid:
            error = self._checkpoint_payload_error(features, state_index, min_confidence)
            if error:
                return self._pause(error, frame_id)
        if (not evidence_valid or type(observation_id) is not int
                or not 0 < observation_id <= frame_id
                or type(observation_timestamp_ms) is not int
                or not 0 < observation_timestamp_ms <= timestamp_ms
                or timestamp_ms - observation_timestamp_ms > self.timing.max_age_ms):
            missing_result = (not evidence_valid
                and (observation_id is None or type(observation_id) is int and 0 <= observation_id <= frame_id)
                and (observation_timestamp_ms is None or type(observation_timestamp_ms) is int
                     and 0 <= observation_timestamp_ms <= timestamp_ms))
            stale_result = (evidence_valid and type(observation_id) is int
                and 0 < observation_id <= frame_id and type(observation_timestamp_ms) is int
                and 0 < observation_timestamp_ms < timestamp_ms
                and timestamp_ms - observation_timestamp_ms > self.timing.max_age_ms
                and (observation_id > self.last_observation and observation_timestamp_ms > self.last_observation_time
                     or observation_id == self.last_observation and observation_timestamp_ms == self.last_observation_time))
            return self._pause("invalid_observation", frame_id, recoverable=missing_result,
                               preserve_checkpoint=stale_result)
        # Source-local failures must not invalidate newer in-flight captures.
        recovery_frame = observation_id if self.timing.source_recovery_boundary else frame_id
        if observation_id <= self.last_observation:
            if (observation_id != self.last_observation
                    or observation_timestamp_ms != self.last_observation_time):
                return self._pause("invalid_observation", frame_id)
            if timestamp_ms - observation_timestamp_ms > self.timing.max_gap_ms:
                return self._pause("observation_gap", recovery_frame, recoverable=True)
            return self.decision
        if observation_timestamp_ms <= self.last_observation_time:
            return self._pause("invalid_observation", frame_id)
        gap = observation_timestamp_ms - self.last_observation_time
        self.last_observation, self.last_observation_time = observation_id, observation_timestamp_ms
        if gap > self.timing.max_gap_ms:
            self._pause('observation_gap', recoverable=True)
        scores = []
        if features.get("driver_visible") != 1 or features.get("driver_count") != 1:
            missing_tool = features.get('driver_visible') == 0 and features.get('driver_count') == 0
            # Only a completed, fresh negative detection after visible clearance counts.
            # Workspace-scoped driver_count=0 alone can hide a shaft or visible handle.
            if (self.timing.release_absence_ms and self.armed and self._release_clear_at is not None
                    and all(finite(features.get(k)) and features[k] == 0 for k in (
                        'driver_visible', 'driver_count', 'driver_count_raw', 'handle_visible', 'handle_count'))
                    and timestamp_ms - observation_timestamp_ms <= self.timing.max_gap_ms
                    and observation_timestamp_ms - self._release_clear_at
                        <= self.timing.max_gap_ms + self.timing.release_absence_ms):
                if (self._release_absent_at is None
                        and observation_timestamp_ms - self._release_clear_at <= self.timing.max_gap_ms):
                    self._release_absent_at = observation_timestamp_ms
                if self._release_absent_at is not None:
                    self.release_at = None
                    self.decision = EvidenceDecision("OBSERVED",
                        advance=observation_timestamp_ms - self._release_absent_at >= self.timing.release_absence_ms)
                    return self.decision
            multiple = (features.get('nested_driver_dedup') == 1
                and finite(features.get('driver_count')) and features['driver_count'] > 1)
            ambiguous = (features.get('driver_visible') == 1
                and finite(features.get('driver_count')) and features['driver_count'] > 1)
            return self._pause('multiple_tool_candidates' if multiple else 'tool_not_visible',
                               recovery_frame, recoverable=missing_tool, preserve_checkpoint=ambiguous)
        if self._release_absent_at is not None:
            # Reappearance must pass the original HOLD recovery rules and deadline.
            self._pause('tool_not_visible', recoverable=True)
        self._release_absent_at = self._release_clear_at = None
        if (features.get("tool_tip_source") not in (1, 2)
                or not all(finite(features.get(k)) and features[k] >= 0 for k in ("tool_tip_x", "tool_tip_y"))):
            missing_tip = (features.get('tool_tip_source') == 0
                and all(finite(features.get(k)) for k in ('tool_tip_x', 'tool_tip_y')))
            outside_tip = (features.get('tool_tip_source') in (1, 2)
                and all(finite(features.get(k)) for k in ('tool_tip_x', 'tool_tip_y')))
            return self._pause("tool_position_unknown", recovery_frame, recoverable=missing_tip,
                               preserve_checkpoint=outside_tip)
        for name in "abcd":
            values = [features.get(f"tool_score_{name}"), features.get(f"tip_screw_score_{name}")]
            distance = features.get(f"tool_dist_{name}")
            if (not all(finite(v) and 0 <= v <= 1 for v in values)
                    or not finite(distance) or distance < 0):
                return self._pause("tool_position_unknown", frame_id)
            scores.append(max(values))
        index = state_index - 2
        score = scores[index]
        name = "abcd"[index]
        threshold = features.get(f"yolo_tool_score_threshold_{name}", features.get("yolo_tool_score_threshold", 0.35))
        dominance = features.get("yolo_target_dominance_ratio", 1.0)
        required = features.get("screw_min_confidence", min_confidence)
        if (not finite(threshold) or not self.timing.release_score_max < threshold <= 1
                or not finite(dominance) or dominance < 0
                or not finite(required) or not 0 <= required <= 1):
            return self._pause("invalid_threshold", frame_id)
        other = max(scores[:index] + scores[index + 1:])
        confidence = min(1.0, 0.55 + 0.45 * score)
        near = score >= threshold and score > other and score >= other * max(1.0, dominance) and confidence >= required
        far = score <= self.timing.release_score_max
        if self.completed_hold and not near and other > self.timing.release_score_max:
            return self._pause('tool_position_unknown', recovery_frame, preserve_checkpoint=True)
        if self._suspended is not None:
            source_time, elapsed, armed = self._suspended
            # Neutral recovery is neither new work nor withdrawal; keep its original deadline.
            if (self.timing.retain_neutral_recovery
                    and self.timing.release_score_max < score < threshold
                    and other <= self.timing.release_score_max
                    and 0 <= timestamp_ms - source_time <= self._resume_budget(armed)):
                return self._pause('tool_position_unknown', recoverable=True)
            clear = far and other <= self.timing.release_score_max
            release_recovery = armed and self.timing.completed_hold_resume_ms and clear
            # Completed HOLD may recover away; withdrawal still starts at this new source.
            if (near or release_recovery) and 0 <= timestamp_ms - source_time <= self._resume_budget(armed):
                self.started_at = observation_timestamp_ms - elapsed
                self.armed = armed
                self._resumed_hold = bool(armed and self.timing.completed_hold_resume_ms)
            self._suspended = None
        if self._resumed_hold and not near and other > self.timing.release_score_max:
            self.reset_step()
            self.decision = EvidenceDecision('GUIDING', confidence=confidence)
            return self.decision
        self._progress_time = observation_timestamp_ms
        # Historical HOLD completion is not permission to advance after a blind gap.
        # A fresh near-current-target observation reauthorizes it without another HOLD.
        if self.completed_hold and not self.armed:
            if not near or timestamp_ms - observation_timestamp_ms > self.timing.max_gap_ms:
                return self._pause('tool_position_unknown', recoverable=True)
            self.started_at = observation_timestamp_ms - self.timing.engage_ms
            self.armed = self._resumed_hold = True
            self.decision = EvidenceDecision('OBSERVED', confidence=confidence)
            return self.decision
        if not self.armed:
            if not near:
                self.started_at = None
                self.decision = EvidenceDecision("GUIDING", confidence=confidence)
                return self.decision
            if self.started_at is None:
                self.started_at = observation_timestamp_ms
            self.armed = observation_timestamp_ms - self.started_at >= self.timing.engage_ms
            self.completed_hold = self.timing.retain_completed_hold and self.armed
            self.decision = EvidenceDecision("OBSERVED" if self.armed else "OBSERVING", confidence=confidence)
            return self.decision
        if not far:
            self.release_at = None
        elif self.release_at is None:
            self.release_at = observation_timestamp_ms
        if self.timing.release_absence_ms and far and other <= self.timing.release_score_max:
            self._release_clear_at = observation_timestamp_ms
        self.decision = EvidenceDecision("OBSERVED", confidence=confidence,
            advance=far and observation_timestamp_ms - self.release_at >= self.timing.release_ms)
        return self.decision
