import {z} from 'zod';
import {parseSnapshot} from '../../shared/protocol.ts';
const schema=z.object({type:z.literal('state'),status:z.enum(['waiting','live','stale','offline']),
  snapshot:z.object({protocol:z.literal(1),seq:z.number().int().positive(),stream_id:z.string(),state:z.unknown().transform(parseSnapshot)}).nullable(),
  received_at_ms:z.number().nullable(),history_status:z.enum(['ok','pending','error']),recording_enabled:z.boolean().optional(),
  recording_status:z.enum(['off','waiting','busy','starting','capturing','saving','saved','interrupted','recovering','limit','quota_full','error']).optional()});
export type Packet=z.infer<typeof schema>;
export function parseWire(value:unknown):Packet{return schema.parse(value);}
export function currentState(packet:Packet|null,age:number){return packet?.status==='live'&&age<=3500?packet.snapshot?.state??null:null;}
