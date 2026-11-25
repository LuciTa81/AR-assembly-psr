import {z} from 'zod';

export const MAX_BYTES = 16 * 1024;
const counter = z.number().int().min(0).max(Number.MAX_SAFE_INTEGER);
const id = z.string().min(1).max(128).regex(/^[a-zA-Z0-9_-]+$/);
const snapshotSchema = z.strictObject({
  schema:z.literal(1), session:id, updated_ms:counter, elapsed_ms:counter,
  running:z.boolean(), stage:z.number().int().min(-1).max(6),
  phase:z.enum(['PREPARATION','APPROACH','WORKING','RELEASE','INSPECTION']),
  action:z.string().max(256), tracked:z.boolean(), overlay_visible:z.boolean(),
  markers:z.number().int().min(0).max(100), rms_px:z.number().min(0).nullable(),
  pose_age_ms:z.number().int().min(-1).max(Number.MAX_SAFE_INTEGER), frame:counter,
  message:z.string().max(512), remaining_ms:counter,
  video_available:z.boolean(), recording:z.literal(false), fastening_verified:z.literal(false),
  recording_consent:z.boolean().optional(),
}).superRefine((s,ctx)=>{
  const expected = s.stage<2 ? ['PREPARATION'] : s.stage===6 ? ['INSPECTION'] : ['APPROACH','WORKING','RELEASE'];
  if(!expected.includes(s.phase) || s.running !== (s.stage>=0) || (s.overlay_visible&&!s.tracked))
    ctx.addIssue({code:'custom',message:'Inconsistent state'});
});
const publishSchema = z.strictObject({protocol:z.literal(1),stream_id:id,seq:counter.min(1),sent_at_ms:counter,state:snapshotSchema});
export type Snapshot = z.infer<typeof snapshotSchema>;
export type Publish = z.infer<typeof publishSchema>;
export function parseSnapshot(input: unknown): Snapshot { return snapshotSchema.parse(input); }
export function parsePublish(input: unknown): Publish {
  if(typeof input==='string') {
    if(Buffer.byteLength(input)>MAX_BYTES)throw new Error('Payload too large');
    input=JSON.parse(input);
  }
  return publishSchema.parse(input);
}
