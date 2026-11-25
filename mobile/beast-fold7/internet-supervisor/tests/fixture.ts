import type {Snapshot, Publish} from '../shared/protocol.ts';
export const snapshot:Snapshot = {
  schema: 1, session: 'phone-session-1', updated_ms: 12345, elapsed_ms: 7000,
  running: true, stage: 2, phase: 'WORKING', action: '나사 A를 조여주세요',
  tracked: true, overlay_visible: true, markers: 5, rms_px: 2.1,
  pose_age_ms: 20, frame: 70, message: 'ok', remaining_ms: 0,
  video_available: false, recording: false, fastening_verified: false,
};
export const publish = (seq = 1):Publish => ({protocol: 1, stream_id: 'stream-1', seq, sent_at_ms: 98765, state: {...snapshot}});
