"""Explicit operator confirmations; no automatic recognition claims."""
from threading import Lock

from .online_state_filter import StateEstimate
from .schemas import AssemblyGuidance
from .state_definitions import NEXT_ACTIONS, TARGETS


class OperatorSession:
    requires_tracking = True

    def __init__(self, session_id):
        self.session_id = session_id
        self._lock = Lock()
        self._revision = 0
        self._pending = False
        self._last_result = ""

    def request(self, session_id, revision):
        with self._lock:
            if (session_id != self.session_id or type(revision) is not int
                    or revision != self._revision or self._pending or self._revision >= 7):
                raise ValueError("Confirmation is duplicate, stale, or already completed")
            self._pending = True

    def metadata(self):
        with self._lock:
            return dict(mode="operator", revision=self._revision, pending=self._pending,
                        completed=self._revision == 7, last_result=self._last_result)

    def update(self, tracking_ok):
        with self._lock:
            transition = ""
            if self._pending:
                self._pending = False
                self._last_result = "confirmed" if tracking_ok else "rejected_tracking"
                if tracking_ok:
                    self._revision += 1
                    transition = "operator_confirmation"
            index = min(self._revision, 6)
            state = "S" + str(index)
            completed = self._revision == 7
            phase = "COMPLETED" if completed else "AWAITING_CONFIRMATION" if index == 6 else "GUIDING"
            labels = ["Ready", "Box placement confirmed", "Lid closure confirmed",
                      "Screw A confirmed", "Screw B confirmed", "Screw C confirmed",
                      "Screw D confirmed"]
            return StateEstimate(
                state=state, label="Operator: " + ("Assembly confirmed" if completed else labels[index]),
                next_action=("Assembly complete - confirmed by operator" if completed
                             else NEXT_ACTIONS[state] + " | Operator confirmation"),
                target=TARGETS[state], confidence=0., transition_event=transition,
                guidance=AssemblyGuidance(phase=phase, reason="operator_confirmation"))
