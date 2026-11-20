const { test } = require('node:test');
const assert = require('node:assert/strict');
const { DemoHistory, demoPresentation } = require('../../web_overlay/supervisor_demo.js');
const { SupervisorState, supervisorFeedback } = require('../../web_overlay/supervisor_state.js');

function view(status='GUIDING', state='S2', holdProgress='none', session='one') {
  return {status, isReference:['PAUSED','DISCONNECTED','STALE','TRACKING_LOST'].includes(status),
    holdProgress, snapshot:{session_id:session,current_state:state,target:'screw_'+('ABCD'[Number(state[1])-2]||'a').toLowerCase(),extra:{operator:{mode:'hybrid'}}}};
}
test('presentation distinguishes retention, recheck, faults and actual final confirmation', () => {
  assert.equal(demoPresentation(view('OBSERVING')).cue, 'HOLD');
  assert.equal(demoPresentation(view('OBSERVED')).cue, 'MOVE CLEAR');
  assert.equal(demoPresentation(view('PAUSED','S4','retained')).cue, 'PAUSED · KEPT');
  assert.equal(demoPresentation(view('PAUSED','S4','recheck')).cue, 'RECHECK');
  assert.equal(demoPresentation(view('DISCONNECTED','S4','retained')).cue, 'OFFLINE');
  assert.equal(demoPresentation(view('AWAITING_CONFIRMATION','S6')).cue, 'FINAL CHECK');
  assert.equal(demoPresentation(view('COMPLETED','S6')).cue, 'CONFIRMED');
  assert.equal(demoPresentation(view('STALE','S6')).cue, 'PAUSED');
});
test('history ignores repeated frames and short phase flicker, but records a settled change', () => {
  const h=new DemoHistory();
  assert(h.update(view(),0));
  assert.equal(h.items.length,1);
  for(let t=1;t<100;t++) h.update(view(),t);
  h.update(view('PAUSED'),100); h.update(view(),200);
  assert.equal(h.items.length,1);
  h.update(view('OBSERVING'),300); h.update(view('OBSERVING'),550);
  assert.equal(h.items.length,2);
  assert.equal(h.items[0].cue,'HOLD');
});

test('user-facing cues use plain language without changing phase semantics', () => {
  assert.equal(demoPresentation(view('OBSERVING')).cueLabel, '드라이버 유지 중');
  assert.equal(demoPresentation(view('OBSERVED')).cueLabel, '드라이버를 떼어 주세요');
  assert.equal(demoPresentation(view('PAUSED','S4','retained')).cueLabel, '잠시 멈춤 · 진행 보존');
  assert.equal(demoPresentation(view('PAUSED','S4','recheck')).cueLabel, '현재 나사 재확인');
  assert.equal(demoPresentation(view('COMPLETED','S6')).cueLabel, '작업자 최종 확인 완료');
});

test('target diagram describes the fixed workbench from the worker side', () => {
  assert.equal(demoPresentation(view('GUIDING','S2')).locationLabel,'먼 쪽 · 왼쪽');
  assert.equal(demoPresentation(view('GUIDING','S3')).locationLabel,'먼 쪽 · 오른쪽');
  assert.equal(demoPresentation(view('GUIDING','S4')).locationLabel,'가까운 쪽 · 왼쪽');
  assert.equal(demoPresentation(view('GUIDING','S5')).locationLabel,'가까운 쪽 · 오른쪽');
  assert.equal(demoPresentation(view('GUIDING','S0')).locationLabel,null);
});

test('only redundant normal feedback is reduced; recovery and faults stay visible', () => {
  assert.equal(demoPresentation(view('OBSERVING')).showFeedback,false);
  for (const status of ['PAUSED','TRACKING_LOST','DISCONNECTED','STALE','INVALID_DATA','WAITING'])
    assert.equal(demoPresentation(view(status)).showFeedback,true,status);
  assert.equal(demoPresentation(view('PAUSED','S4','retained')).showFeedback,true);
  assert.equal(demoPresentation(view('PAUSED','S4','recheck')).showFeedback,true);
  assert.equal(demoPresentation(view('GUIDING')).showFeedback,true);
  assert.equal(demoPresentation(view('AWAITING_CONFIRMATION','S6')).showFeedback,false);
});

test('withdrawal keeps the camera-visible instruction, but stale input cannot request withdrawal', () => {
  const release = view('OBSERVED');
  assert.equal(demoPresentation(release).showFeedback,true);
  assert.match(supervisorFeedback(release).detail,/카메라에는 보이게 유지/);
  for (const status of ['STALE','DISCONNECTED','INVALID_DATA']) {
    const stopped = {...release,status,isReference:true};
    assert.notEqual(demoPresentation(stopped).cue,'MOVE CLEAR');
    assert.equal(demoPresentation(stopped).showFeedback,true);
    assert.doesNotMatch(supervisorFeedback(stopped).detail,/목표에서 떼/);
  }
});
test('stage transitions and connection loss are immediate; no false completion on stale S6', () => {
  const h=new DemoHistory();
  h.update(view(),0); h.update(view('GUIDING','S3'),10);
  h.update(view('DISCONNECTED','S3'),20);
  assert.equal(h.items.length,3);
  assert.equal(h.items[0].cue,'OFFLINE');
  h.update(view('STALE','S6'),30);
  assert.notEqual(h.items[0].cue,'CONFIRMED');
});
test('history is bounded, clears on session change, and elapsed time is session-local', () => {
  const h=new DemoHistory(4);
  for(let i=0;i<20;i++) h.update(view('GUIDING',i%2?'S2':'S3'),i*1000);
  assert.equal(h.items.length,4);
  h.update(view('GUIDING','S0','none','two'),30000);
  assert.equal(h.items.length,1);
  assert.equal(h.items[0].seconds,0);
});
test('waiting without a snapshot has no target or invented history', () => {
  const h=new DemoHistory(), v={status:'WAITING',isReference:true,snapshot:null};
  h.update(v,100);
  assert.equal(h.items.length,0);
  assert.equal(demoPresentation(v).target,null);
});

test('default history contains stage changes and one completion, not cue changes', () => {
  const h=new DemoHistory(120);
  h.update(view('GUIDING','S2'),0);
  h.update(view('OBSERVING','S2'),1000);
  h.update(view('OBSERVING','S2'),1300);
  h.update(view('OBSERVED','S2'),2000);
  h.update(view('OBSERVED','S2'),2300);
  h.update(view('GUIDING','S3'),3000);
  h.update(view('DISCONNECTED','S3'),4000);
  h.update(view('AWAITING_CONFIRMATION','S6'),5000);
  h.update(view('COMPLETED','S6'),6000);
  h.update(view('DISCONNECTED','S6'),7000);
  h.update(view('COMPLETED','S6'),8000);
  assert.deepEqual(h.entries().map(e=>[e.state,e.kind,e.seconds]),
    [['S6','complete',6],['S6','transition',5],['S3','transition',3],['S2','start',0]]);
  assert.equal(h.entries('all').length,9);
  assert(h.entries('attention').some(e=>e.cue==='OFFLINE'));
});

test('step history survives noisy detail eviction and resets for a new session', () => {
  const h=new DemoHistory(4);
  h.update(view('GUIDING','S0'),0);
  h.update(view('GUIDING','S2'),1000);
  for(let i=2;i<20;i++) {
    const v=view(i%2?'OBSERVING':'OBSERVED','S2');
    h.update(v,i*1000); h.update(v,i*1000+300);
  }
  assert.equal(h.entries('all').length,4);
  assert.deepEqual(h.entries().map(e=>e.state),['S2','S0']);
  h.update(view('GUIDING','S3','none','two'),30000);
  assert.deepEqual(h.entries().map(e=>[e.kind,e.seconds]),[['start',0]]);
  h.update(view('STALE','S6','none','two'),31000);
  assert(!h.entries().some(e=>e.kind==='complete'));
});
test('cues and history follow operator mode instead of assuming hybrid control', () => {
  const automatic=view('GUIDING','S0');
  automatic.snapshot.extra.operator.mode='auto';
  assert.equal(demoPresentation(automatic).cue,'PLACE');
  automatic.status='OBSERVING';
  assert.equal(demoPresentation(automatic).cue,'OBSERVE');
  const manual=view('GUIDING','S4');
  manual.snapshot.extra.operator.mode='operator';
  assert.equal(demoPresentation(manual).cue,'CHECK');
  const h=new DemoHistory();h.update(manual,0);
  assert.equal(h.items[0].cue,'CHECK');
});
test('saved-session replay keeps targets and paused guidance consistent', {skip:!process.env.DEMO_REPLAY_LOG}, () => {
  const rows=require('node:fs').readFileSync(process.env.DEMO_REPLAY_LOG,'utf8').trim().split(/\r?\n/).map(JSON.parse);
  const model=new SupervisorState(), h=new DemoHistory();
  for(const row of rows) {
    // Logs omit transport age. This is semantic replay, not a latency measurement.
    const frame={...row,source:'session',frame_age_ms:0}, now=row.timestamp_ms;
    assert.equal(model.apply(frame,now,now),true);
    const v=model.view(now), p=demoPresentation(v);
    assert.equal(p.target,/^screw_[a-d]$/.test(row.target)?row.target.slice(-1).toUpperCase():null);
    if(v.isReference) assert(!['APPROACH','HOLD','MOVE CLEAR','CONFIRMED'].includes(p.cue));
    if(p.cue==='CONFIRMED') assert.equal(row.extra.operator.completed,true);
    h.update(v,now);
  }
  assert(rows.length>0);
  assert.equal(h.items.length<=12,true);
});
