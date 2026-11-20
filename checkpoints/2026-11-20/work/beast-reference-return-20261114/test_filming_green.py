import tempfile
import unittest
from pathlib import Path

from run_neutral_d_server import ROOT
from server.realtime.guidance_timing import GuidanceTiming
from filming_green import FilmingGreenGate
from server.realtime.online_state_filter import OnlineStateFilter
from server.realtime.assembly_session import AssemblySession


class FilmingGreenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / 'player.log'
        self.clock = 10.0
        self.gate = FilmingGreenGate(GuidanceTiming(), log_path=self.log, clock=lambda: self.clock)

    def cue(self, state='S2', tone='Release', cue='MOVE CLEAR'):
        with self.log.open('a', encoding='utf-8') as out:
            out.write(f'[SBS TEXT] state={state} cue={cue} action_ko=test tone={tone} text_retained=False\n')

    def tick(self, state=2):
        return self.gate.evaluate(state, int(self.clock * 1000), int(self.clock * 1000), False, {},
                                  observation_id=None, observation_timestamp_ms=None,
                                  evidence_valid=False, roi_valid=False, min_confidence=.75)

    def test_green_waits_two_seconds_despite_missing_tracking(self):
        self.cue()
        self.assertFalse(self.tick().advance)
        self.clock = 11.999
        self.assertFalse(self.tick().advance)
        self.clock = 12.0
        result = self.tick()
        self.assertTrue(result.advance)
        self.assertEqual(result.reason, 'filming_green_timer')

    def test_no_green_never_advances(self):
        self.cue(tone='Working', cue='WORKING')
        self.tick()
        self.clock = 100
        self.assertFalse(self.tick().advance)

    def test_next_screw_requires_new_green(self):
        self.cue()
        self.tick()
        self.clock = 12
        self.assertTrue(self.tick().advance)
        self.gate.reset_step(after_frame=12000)
        self.clock = 20
        self.assertFalse(self.tick(3).advance)
        self.cue('S3')
        self.tick(3)
        self.clock = 22
        self.assertTrue(self.tick(3).advance)

    def test_wrong_stage_and_final_check_do_not_arm(self):
        self.cue('S5')
        self.tick()
        self.clock = 20
        self.assertFalse(self.tick().advance)
        self.cue('S6')
        self.tick(6)
        self.clock = 30
        self.assertFalse(self.tick(6).advance)

    def test_repeat_green_does_not_restart_timer(self):
        self.cue()
        self.tick()
        self.clock = 11
        self.cue()
        self.tick()
        self.clock = 12
        self.assertTrue(self.tick().advance)

    def test_move_clear_with_attention_does_not_arm_each_screw(self):
        for index in range(2, 6):
            with self.subTest(state=index):
                self.cue(f'S{index}', tone='Attention')
                self.assertFalse(self.tick(index).advance)
                self.clock += 1.999
                self.assertFalse(self.tick(index).advance)
                self.clock += .002
                self.assertFalse(self.tick(index).advance)
                self.cue(f'S{index}', tone='Release')
                self.assertFalse(self.tick(index).advance)
                self.clock += 2.01
                self.assertTrue(self.tick(index).advance)
                self.gate.reset_step(after_frame=int(self.clock * 1000))
                self.clock += 1

    def test_full_flow_keeps_manual_setup_and_final_confirmation(self):
        state_filter = OnlineStateFilter(initial_state='S2', guidance_policy='timed_v1')
        state_filter.timed_gate = self.gate
        session = AssemblySession('filming-test', state_filter)

        def update(tracking=True):
            stamp = int(self.clock * 1000)
            return session.update(dict(frame_id=stamp, timestamp_ms=stamp, marker_ok=tracking,
                                       features={}, evidence_valid=False), True)

        self.assertEqual(update().state, 'S0')
        for expected in ('S1', 'S2'):
            session.request('filming-test', session.metadata()['revision'])
            self.clock += .1
            self.assertEqual(update().state, expected)
        for index in range(2, 6):
            self.cue(f'S{index}')
            self.assertEqual(update(False).state, f'S{index}')
            self.clock += 2
            result = update(False)
            self.assertEqual(result.state, f'S{index + 1}')
            self.assertEqual(result.transition_event, f'S{index}->S{index + 1}')
        self.assertFalse(session.metadata()['completed'])
        self.assertEqual(update(False).guidance.phase, 'AWAITING_CONFIRMATION')
        session.request('filming-test', session.metadata()['revision'])
        self.assertEqual(update(False).guidance.phase, 'COMPLETED')


if __name__ == '__main__':
    unittest.main()
