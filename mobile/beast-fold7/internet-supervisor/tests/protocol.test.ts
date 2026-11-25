import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parsePublish, parseSnapshot} from '../shared/protocol.ts';
import {snapshot, publish} from './fixture.ts';

test('accepts real Android monotonic snapshot and does not treat time as Unix epoch', () => {
  assert.deepEqual(parseSnapshot(snapshot), snapshot);
  assert.equal(parsePublish(publish()).seq, 1);
});
for (const [name, patch] of Object.entries({
  stage: {stage: 7}, fractionalStage: {stage: 2.5}, invalidPhase: {phase: 'DONE'},
  forgedVerification: {fastening_verified: true}, video: {video_available: 'true'}, recording: {recording: true},
  extra: {owner: 'other'}, longText: {action: 'a'.repeat(257)}, negativeTime: {elapsed_ms: -1},
  unsafeFrame: {frame: Number.MAX_SAFE_INTEGER + 1}, badRms: {rms_px: Infinity},
  wrongStagePhase: {stage: 0, phase: 'WORKING'}, invisibleTracking: {tracked: false, overlay_visible: true},
})) test(`rejects ${name}`, () => assert.throws(() => parseSnapshot({...snapshot, ...patch})));
test('permits idle and tracking gaps without inventing completion', () => {
  assert.equal(parseSnapshot({...snapshot, running:false, stage:-1, phase:'PREPARATION', tracked:false, overlay_visible:false, rms_px:null, pose_age_ms:-1}).stage,-1);
});
test('video sharing does not imply recording or fastening verification',()=>{
  const state=parseSnapshot({...snapshot,video_available:true});
  assert.equal(state.video_available,true);
  assert.equal(state.recording,false);assert.equal(state.fastening_verified,false);
});
test('rejects replay sequence zero, unknown fields and oversized wire messages', () => {
  assert.throws(() => parsePublish({...publish(), seq:0}));
  assert.throws(() => parsePublish({...publish(), device_id:'forged'}));
  assert.throws(() => parsePublish(' '.repeat(16385)));
});
