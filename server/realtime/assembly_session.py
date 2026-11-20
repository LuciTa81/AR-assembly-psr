"""Manual setup/final check around the unchanged timed screw interaction filter."""
from threading import Lock

from .online_state_filter import StateEstimate
from .schemas import AssemblyGuidance
from .state_definitions import NEXT_ACTIONS, TARGETS


class AssemblySession:
    def __init__(self, session_id, state_filter):
        if state_filter.state_index != 2 or state_filter.max_state_index != 6 or state_filter.timed_gate is None:
            raise ValueError('Assembly flow requires the timed S2-S6 screw filter')
        self.session_id, self.filter = session_id, state_filter
        self._lock = Lock()
        self._index = self._revision = 0
        self._pending = None
        self._completed = False
        self._last_result = ''
        self.last_input = None

    @property
    def requires_tracking(self):
        with self._lock:
            return self._index != 6

    def request(self, session_id, revision):
        with self._lock:
            if (session_id != self.session_id or type(revision) is not int or revision != self._revision
                    or self._pending is not None or self._completed or self._index not in (0, 1, 6)):
                raise ValueError('Confirmation is stale, duplicate, or unavailable during automatic screw steps')
            self._pending = revision

    def metadata(self):
        with self._lock:
            return dict(mode='hybrid', revision=self._revision, pending=self._pending is not None,
                        completed=self._completed, last_result=self._last_result,
                        can_confirm=self._index in (0, 1, 6) and not self._completed)

    def update(self, filter_input, fresh_input):
        with self._lock:
            self.last_input = dict(confirmation_revision=self._pending, fresh_input=bool(fresh_input))
            transition = ''
            if self._pending is not None:
                self._pending = None
                ready = fresh_input and (self._index == 6 or filter_input['marker_ok'])
                self._last_result = 'confirmed' if ready else 'rejected_tracking_or_stale'
                if ready:
                    self._revision += 1
                    transition = 'operator_confirmation'
                    if self._index == 6:
                        self._completed = True
                    else:
                        self._index += 1
                        if self._index == 2:
                            self.filter.timed_gate.reset_step(after_frame=filter_input['frame_id'])
            if 2 <= self._index <= 5:
                item = filter_input if fresh_input else dict(filter_input, marker_ok=False)
                result = self.filter.update(**item)
                new_index = int(result.state[1])
                if new_index != self._index:
                    self._index = new_index
                    self._revision += 1
                if self._index != 6:
                    if transition:
                        result.transition_event = transition
                    return result
                transition = result.transition_event
            state = 'S' + str(self._index)
            phase = 'COMPLETED' if self._completed else 'AWAITING_CONFIRMATION' if self._index == 6 else 'GUIDING'
            action = ('Assembly complete - confirmed by operator' if self._completed
                      else NEXT_ACTIONS[state] + ' | Operator confirmation')
            label = 'Assembly confirmed by operator' if self._completed else {
                0: 'Box placement - operator check', 1: 'Lid closure - operator check',
                6: 'Screw interactions observed - final check',
            }[self._index]
            return StateEstimate(state, label, action, TARGETS[state], 0., transition_event=transition,
                                 guidance=AssemblyGuidance(phase=phase, reason='operator_confirmation'))
