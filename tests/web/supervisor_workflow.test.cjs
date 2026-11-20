const { test } = require('node:test');
const assert = require('node:assert/strict');
const { SupervisorState, supervisorWorkflow } = require('../../web_overlay/supervisor_state.js');

function view(index = 2, phase = 'GUIDING', mode = 'hybrid', marker = 'OK') {
  const model = new SupervisorState();
  model.apply({schema_version:'realtime_v1', session_id:'workflow', frame_id:1, timestamp_ms:1000,
    frame_age_ms:0, system_status:'RUNNING', marker_status:marker, current_state:'S'+index,
    current_label:'legacy label', target:['box','lid','screw_a','screw_b','screw_c','screw_d','complete'][index],
    next_action:'Exact server instruction', guidance:{schema_version:'assembly_guidance_v1', phase,
      reason: mode === 'operator' || [0,1,6].includes(index) ? 'operator_confirmation' : '',
      acknowledgement:'', acknowledgement_remaining_ms:0},
    extra:{operator:{mode, revision:index, can_confirm:[0,1,6].includes(index), pending:false, completed:phase==='COMPLETED'}}
  }, 0, 0);
  return model.view(10);
}

test('workflow labels match targets for hybrid, operator and automatic modes', () => {
  for (const mode of ['hybrid','operator','auto']) for (let i=0; i<=6; i++) {
    const workflow = supervisorWorkflow(view(i, i===6 ? 'AWAITING_CONFIRMATION' : 'GUIDING', mode));
    assert.deepEqual(workflow.steps, ['상자 배치','뚜껑 닫기','나사 A','나사 B','나사 C','나사 D','최종 확인']);
    assert.equal(workflow.label, workflow.steps[i]);
    assert.match(workflow.progress, new RegExp(`${i+1} / 7`));
  }
});

test('screw actions distinguish approach, hold and visible withdrawal', () => {
  for (const [phase, word] of [['GUIDING','대어'],['OBSERVING','유지'],['OBSERVED','떼어']]) {
    const workflow = supervisorWorkflow(view(5, phase));
    assert.match(workflow.action, /나사 D/);
    assert.ok(workflow.action.includes(word));
    assert.equal(workflow.mode, '자동 관측');
  }
  const operator = supervisorWorkflow(view(2, 'GUIDING', 'operator'));
  assert.equal(operator.mode, '사용자 확인');
  assert.match(operator.action, /확인/);
});

test('withdrawal instruction waits for the operator to finish the physical work', () => {
  for (let i=2; i<=5; i++) assert.match(supervisorWorkflow(view(i, 'OBSERVED')).action, /작업을 마쳤으면.*떼어/);
});

test('operator screw confirmations describe the current screw, not the lid', () => {
  for (let i=2; i<=5; i++) {
    const workflow = supervisorWorkflow(view(i, 'GUIDING', 'operator'));
    assert.match(workflow.confirmationHint, new RegExp('나사 ' + 'ABCD'[i-2]));
    assert.doesNotMatch(workflow.confirmationHint, /뚜껑/);
  }
});

test('paused, stale and disconnected views cannot keep an actionable screw instruction', () => {
  for (const status of ['PAUSED','TRACKING_LOST','STALE','DISCONNECTED','INVALID_DATA']) {
    const v = view(); v.status=status; v.isReference=true;
    const workflow = supervisorWorkflow(v);
    assert.doesNotMatch(workflow.action, /대어|떼어|완료/);
    assert.equal(workflow.mode, '안내 보류');
  }
});

test('final check and completion stay distinct, including marker loss', () => {
  const pending = supervisorWorkflow(view(6, 'AWAITING_CONFIRMATION', 'hybrid', 'LOST'));
  assert.match(pending.action, /조립 상태.*확인/);
  assert.doesNotMatch(pending.action, /완료/);
  const complete = supervisorWorkflow(view(6, 'COMPLETED', 'hybrid', 'LOST'));
  assert.equal(complete.action, '작업자 최종 확인 완료');
});

test('empty state has no invented step and pending confirmation is explicit', () => {
  const empty = supervisorWorkflow(new SupervisorState().view(0));
  assert.equal(empty.progress, '단계 수신 대기');
  assert.equal(empty.label, '작업 대기');
  const pending = view(0); pending.snapshot.extra.operator.pending=true;
  assert.match(supervisorWorkflow(pending).confirmationHint, /접수.*반영/);
  const lost = view(0, 'GUIDING', 'hybrid', 'LOST');
  assert.match(supervisorWorkflow(lost).confirmationHint, /마커/);
});
