const { test } = require('node:test');
const assert = require('node:assert/strict');
const { SupervisorState, supervisorFeedback } = require('../../web_overlay/supervisor_state.js');

function frame(progress = 'retained', remaining = 200, phase = 'PAUSED') {
  return { schema_version: 'realtime_v1', session_id: 's', source: 'fixture', frame_id: 1,
    timestamp_ms: 1000, frame_age_ms: 50, system_status: 'RUNNING', marker_status: 'OK',
    current_state: 'S2', current_label: 'Screw A', next_action: 'Waiting for evidence', target: 'screw_a',
    guidance: { schema_version: 'assembly_guidance_v1', phase, reason: 'invalid_observation',
      acknowledgement: '', acknowledgement_remaining_ms: 0, hold_progress: progress, hold_remaining_ms: remaining } };
}

for (const marker of ['OK', 'LOST']) test('retained HOLD expires without renewing on duplicate: ' + marker, () => {
  const state = new SupervisorState(), f = frame(); f.marker_status = marker;
  assert.equal(state.apply(f, 1000, 1050), true);
  assert.equal(state.view(1100).holdProgress, 'retained');
  assert.match(supervisorFeedback(state.view(1100)).title, /보존/);
  assert.equal(supervisorFeedback(state.view(1100)).stage, null);
  assert.equal(state.view(1151).holdProgress, 'none');
  state.apply(f, 1170, 1180);
  assert.equal(state.view(1190).holdProgress, 'none');
  state.disconnect();
  assert.equal(state.view(1200).holdProgress, 'none');
});

test('recheck is local to current target and disappears with new work or session', () => {
  const state = new SupervisorState();
  assert.equal(state.apply(frame('recheck', 0, 'GUIDING'), 1000, 1010), true);
  assert.match(supervisorFeedback(state.view(1020)).title, /A.*재확인/);
  const next = frame('none', 0, 'OBSERVING'); next.frame_id++; next.timestamp_ms++;
  state.apply(next, 1030, 1040);
  assert.equal(state.view(1050).holdProgress, 'none');
  const other = frame('none', 0, 'GUIDING'); other.session_id = 'other';
  state.apply(other, 1060, 1070);
  assert.equal(state.view(1080).holdProgress, 'none');
});

test('invalid HOLD metadata cannot claim retained progress', () => {
  for (const args of [['retained', 0], ['retained', 3001], ['retained', 200, 'OBSERVED'],
    ['recheck', 1], ['recheck', 0, 'OBSERVING'], ['unknown', 0]]) {
    const state = new SupervisorState();
    assert.equal(state.apply(frame(...args), 1000, 1010), false, JSON.stringify(args));
    assert.equal(state.view(1020).holdProgress, 'none');
  }
});

test('duplicate hold metadata mutation is invalid and stale frames cannot claim progress', () => {
  const state = new SupervisorState();
  state.apply(frame(), 1000, 1010);
  assert.equal(state.apply(frame('recheck', 0), 1020, 1030), false);
  assert.equal(state.view(1040).status, 'INVALID_DATA');
  assert.equal(state.view(1040).holdProgress, 'none');
  const fresh = new SupervisorState(); fresh.apply(frame('retained', 2000), 1000, 1010);
  assert.equal(fresh.view(1501).holdProgress, 'none');
});

test('progress feedback preserves the recovery cause and driver count', () => {
  const state = new SupervisorState(), f = frame('recheck', 0);
  f.guidance.reason = 'multiple_tool_candidates';
  f.extra = { yolo_reason: 'ok', driver_count: 2 };
  state.apply(f, 1000, 1010);
  const feedback = supervisorFeedback(state.view(1020));
  assert.match(feedback.title, /재확인/);
  assert.match(feedback.detail, /하나만/);
  assert.equal(feedback.driver, '2개 검출');
  const kept = frame('retained', 1000);
  kept.guidance.reason = 'tool_not_visible';
  kept.frame_id = 2; kept.timestamp_ms++;
  state.apply(kept, 1030, 1040);
  assert.match(supervisorFeedback(state.view(1050)).detail, /시야 안에/);
});
