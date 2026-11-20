"""Filming-only transition timer driven by this run's actual Unity release cue."""
import re
import time
from dataclasses import replace
from pathlib import Path

from server.realtime.guidance_timing import EvidenceDecision, TimedEvidenceGate


class FilmingGreenGate(TimedEvidenceGate):
    def __init__(self, timing, *, log_path, clock=time.monotonic):
        self.log_path = Path(log_path)
        self.clock = clock
        self.offset = 0
        self.pending = b''
        self.green_at = None
        self.green_state = None
        super().__init__(timing)

    def _read_green(self, state_index):
        try:
            with self.log_path.open('rb') as source:
                source.seek(self.offset)
                chunk = source.read()
                self.offset = source.tell()
        except OSError:
            return False
        lines = (self.pending + chunk).split(b'\n')
        self.pending = lines.pop()
        pattern = (rb'\[SBS TEXT\] state=S' + str(state_index).encode()
                   + rb' .*\btone=Release\b')
        return any(re.search(pattern, line) for line in lines)

    def evaluate(self, state_index, frame_id, timestamp_ms, marker_ok, features, **kwargs):
        decision = super().evaluate(state_index, frame_id, timestamp_ms, marker_ok, features, **kwargs)
        green = self._read_green(state_index)
        if not 2 <= state_index <= 5:
            return decision
        if self.green_state != state_index:
            self.green_at = None
            self.green_state = state_index
        if green and self.green_at is None:
            self.green_at = self.clock()
            print(f'[FILMING TIMER] state=S{state_index} release_cue_seen=true delay_ms=2000 fastening_verified=false', flush=True)
        if self.green_at is not None and self.clock() - self.green_at >= 2.0:
            print(f'[FILMING TIMER] S{state_index}->S{state_index + 1} reason=filming_green_timer fastening_verified=false', flush=True)
            return EvidenceDecision('GUIDING', 'filming_green_timer', True, 0.0)
        # A logical release cue alone does not prove green was rendered.
        return replace(decision, advance=False)
