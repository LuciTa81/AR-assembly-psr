const { test } = require('node:test');
const assert = require('node:assert/strict');
const { SupervisorState } = require('../../web_overlay/supervisor_state.js');

test('completed checkpoint is non-actionable, fresh-only, and explicit about position recheck', () => {
  const {supervisorFeedback} = require('../../web_overlay/supervisor_state.js');
  for (const marker_status of ['OK', 'LOST']) {
    const frame = snapshot({marker_status});
    Object.assign(frame.guidance, {phase: 'PAUSED', hold_progress: 'checkpoint', hold_remaining_ms: 0});
    const state = new SupervisorState();
    assert.equal(state.apply(frame, 0, 0), true);
    const view = state.view(10);
    assert.equal(view.holdProgress, 'checkpoint');
    assert.equal(view.isReference, true);
    assert.match(supervisorFeedback(view).title, /HOLD/);
    assert.match(supervisorFeedback(view).detail, marker_status === 'OK' ? /위치/ : /마커/);
    assert.equal(state.view(501).holdProgress, 'none');
    state.disconnect();
    assert.equal(state.view(20).holdProgress, 'none');
  }
});

test('checkpoint cannot masquerade as observed or carry a countdown', () => {
  for (const [phase, remaining] of [['OBSERVED', 0], ['PAUSED', 1]]) {
    const frame = snapshot();
    Object.assign(frame.guidance, {phase, hold_progress: 'checkpoint', hold_remaining_ms: remaining});
    assert.equal(new SupervisorState().apply(frame, 0, 0), false);
  }
});

test('explicit final check survives marker loss but not stale state', () => {
  for (const phase of ['AWAITING_CONFIRMATION', 'COMPLETED']) {
    const frame = snapshot({current_state: 'S6', target: 'complete', marker_status: 'LOST'});
    frame.guidance.phase = phase; frame.guidance.reason = 'operator_confirmation';
    const state = new SupervisorState();
    assert.equal(state.apply(frame, 0, 0), true);
    assert.equal(state.view(1).status, phase);
    assert.equal(state.view(501).status, 'STALE');
    state.disconnect();
    assert.equal(state.view(2).status, 'DISCONNECTED');
  }
});

test('hybrid confirmation controls exist only at explicit boundaries', () => {
  const {supervisorConfirmation} = require('../../web_overlay/supervisor_state.js');
  for (let index = 0; index <= 6; index++) {
    const data = snapshot({current_state: 'S' + index});
    data.extra = {operator: {mode: 'hybrid', can_confirm: [0,1,6].includes(index), pending: false, completed: false}};
    const view = {snapshot: data, isReference: false};
    assert.equal(supervisorConfirmation(view).visible, [0,1,6].includes(index));
    assert.equal(supervisorConfirmation(view).enabled, [0,1,6].includes(index));
    view.isReference = true;
    assert.equal(supervisorConfirmation(view).enabled, false);
  }
});

test('completion requires explicit operator confirmation and expires normally', () => {
  const frame = snapshot({ current_state: 'S6', target: 'complete' });
  frame.guidance.phase = 'COMPLETED';
  const state = new SupervisorState();
  assert.equal(state.apply(frame, 0, 0), false);
  frame.guidance.reason = 'operator_confirmation';
  assert.equal(state.apply(frame, 0, 0), true);
  assert.equal(state.view(10).status, 'COMPLETED');
  assert.equal(state.view(10).isReference, false);
  assert.equal(state.view(501).status, 'STALE');
});

function snapshot(overrides = {}) {
  return {
    schema_version: 'realtime_v1', session_id: 'test', source: 'camera',
    system_status: 'RUNNING', frame_id: 1, timestamp_ms: 10000, frame_age_ms: 0,
    marker_status: 'OK', marker_count: 6, current_state: 'S2',
    current_label: 'Lid closed', target: 'screw_a', next_action: 'Fasten screw A',
    guidance: { schema_version: 'assembly_guidance_v1', phase: 'GUIDING', reason: '',
      acknowledgement: '', acknowledgement_remaining_ms: 0 }, ...overrides,
  };
}

test('missing input is waiting, not S0 or healthy', () => {
  const state = new SupervisorState();
  assert.equal(state.view(0).status, 'WAITING');
  assert.equal(state.view(0).snapshot, null);
});
test('uses the exact server instruction, target and phase', () => {
  const state = new SupervisorState();
  const frame = snapshot();
  frame.guidance.phase = 'OBSERVED';
  frame.next_action = 'Move the driver clear of screw A';
  assert.equal(state.apply(frame, 10, 20), true);
  assert.equal(state.view(21).status, 'OBSERVED');
  assert.equal(state.view(21).instruction, frame.next_action);
  assert.equal(state.view(21).snapshot.target, 'screw_a');
  frame.next_action = 'mutated';
  assert.equal(state.view(21).instruction, 'Move the driver clear of screw A');
});
test('server age plus full RTT counts toward 500ms budget', () => {
  const state = new SupervisorState();
  state.apply(snapshot({ frame_age_ms: 200 }), 0, 100);
  assert.equal(state.view(299).status, 'GUIDING');
  assert.equal(state.view(300).status, 'STALE');
  assert.notEqual(state.view(300).instruction, 'Fasten screw A');
  assert.equal(state.view(300).isReference, true);
});
test('duplicate frames cannot renew the deadline or recover a disconnect', () => {
  const state = new SupervisorState();
  state.apply(snapshot(), 0, 0);
  state.apply(snapshot(), 400, 400);
  assert.equal(state.view(500).status, 'STALE');
  state.disconnect();
  state.apply(snapshot(), 600, 600);
  assert.equal(state.view(600).status, 'DISCONNECTED');
  state.apply(snapshot({ frame_id: 2, timestamp_ms: 10100 }), 650, 650);
  assert.equal(state.view(650).status, 'GUIDING');
});
test('mutated duplicate and out-of-order frames cannot advance guidance', () => {
  const state = new SupervisorState();
  state.apply(snapshot({ frame_id: 5 }), 0, 0);
  state.apply(snapshot({ frame_id: 5, next_action: 'Changed' }), 10, 10);
  assert.equal(state.view(10).status, 'INVALID_DATA');
  state.apply(snapshot({ frame_id: 4 }), 20, 20);
  assert.equal(state.view(20).status, 'INVALID_DATA');
  assert.equal(state.view(20).snapshot.target, 'screw_a');
});
test('lost and fallback tracking pause guidance and hide acknowledgements', () => {
  for (const marker_status of ['LOST', 'FALLBACK', 'DISABLED', 'UNSTABLE']) {
    const state = new SupervisorState();
    state.apply(snapshot({ marker_status }), 0, 0);
    assert.equal(state.view(0).status, 'TRACKING_LOST');
    assert.equal(state.view(0).acknowledgement, '');
    assert.notEqual(state.view(0).instruction, 'Fasten screw A');
  }
});
test('server PAUSED reason remains visible without a current action claim', () => {
  const state = new SupervisorState();
  const frame = snapshot();
  frame.guidance.phase = 'PAUSED';
  frame.next_action = 'Driver not visible. Keep target in view.';
  state.apply(frame, 0, 0);
  assert.equal(state.view(0).status, 'PAUSED');
  assert.equal(state.view(0).instruction, frame.next_action);
  assert.equal(state.view(0).isReference, true);
});
test('S6 remains confirmation pending, never inferred as completed', () => {
  const state = new SupervisorState();
  const frame = snapshot({ current_state: 'S6', target: 'complete', next_action: 'Confirm assembly' });
  frame.guidance.phase = 'AWAITING_CONFIRMATION';
  state.apply(frame, 0, 0);
  assert.equal(state.view(0).status, 'AWAITING_CONFIRMATION');
  assert.equal(state.view(0).instruction, 'Confirm assembly');
});
test('ack is independent of next instruction and expires without new frames', () => {
  const state = new SupervisorState();
  const frame = snapshot({ current_state: 'S3', target: 'screw_b', next_action: 'Fasten screw B' });
  frame.guidance.acknowledgement = 'Screw A observed';
  frame.guidance.acknowledgement_remaining_ms = 250;
  state.apply(frame, 0, 0);
  assert.equal(state.view(100).acknowledgement, 'Screw A observed');
  assert.equal(state.view(100).instruction, 'Fasten screw B');
  state.apply({ ...frame, frame_id: 2, timestamp_ms: 10100 }, 100, 100);
  assert.equal(state.view(250).acknowledgement, '');
});
test('session change accepts new frame numbering and resets acknowledgement', () => {
  const state = new SupervisorState();
  state.apply(snapshot({ frame_id: 100 }), 0, 0);
  state.apply(snapshot({ session_id: 'new', frame_id: 1, source: 'synthetic_guidance_fixture' }), 20, 20);
  assert.equal(state.view(20).snapshot.session_id, 'new');
  assert.equal(state.view(20).snapshot.source, 'synthetic_guidance_fixture');
});
test('invalid schema, targets, ages, phase and timings fail closed', () => {
  for (const patch of [null, { current_state: 'S9' }, { target: 'screw_d' },
    { schema_version: 'unknown' }, { timestamp_ms: -1 }, { frame_age_ms: -1 },
    { frame_age_ms: NaN }, { guidance: {} }, { guidance: null },
    { next_action: '' }, { marker_status: 'maybe' }]) {
    const state = new SupervisorState();
    state.apply(patch === null ? null : snapshot(patch), 0, 0);
    assert.equal(state.view(0).status, 'INVALID_DATA', JSON.stringify(patch));
  }
  const state = new SupervisorState();
  state.apply(snapshot(), 20, 10);
  assert.equal(state.view(20).status, 'INVALID_DATA');
});
if (process.env.GUIDANCE_FIXTURE) {
  test('all real R4 filter snapshots and milestones agree with the supervisor', () => {
    const fixture = JSON.parse(require('node:fs').readFileSync(process.env.GUIDANCE_FIXTURE, 'utf8'));
    const state = new SupervisorState();
    fixture.snapshots.forEach((frame, i) => {
      const now = i * 50;
      assert.equal(state.apply(frame, now, now), true, `frame ${i}`);
      const view = state.view(now);
      assert.equal(view.snapshot.current_state, frame.current_state);
      assert.equal(view.snapshot.target, frame.target);
      if (frame.marker_status === 'OK') {
        assert.equal(view.status, frame.guidance.phase);
        assert.equal(view.instruction, frame.next_action);
      } else assert.equal(view.status, 'TRACKING_LOST');
    });
    assert.equal(state.view(24000).status, 'AWAITING_CONFIRMATION');
    assert.equal(state.view(24500).status, 'STALE');
    assert.equal(fixture.snapshots.length, 481);
  });
}
test('starting, disconnection and malformed response do not default to live', () => {
  const state = new SupervisorState();
  state.apply({ system_status: 'STARTING' }, 0, 0);
  assert.equal(state.view(0).status, 'WAITING');
  state.disconnect();
  assert.equal(state.view(0).status, 'DISCONNECTED');
  state.invalid();
  assert.equal(state.view(0).status, 'INVALID_DATA');
});
