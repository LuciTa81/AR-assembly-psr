import {randomUUID} from 'node:crypto';
import {Store,AccessError} from './store.ts';
export const RETENTION_MS=7*86400000;
export class RetentionError extends Error {}
export class RecordingQuotaError extends RetentionError {}
export class RecordingLimitError extends RetentionError {}
export const resumableReasons=new Set(['stale','state_stale','video_stale','stream_gap','disconnected','state_reconnected','video_reconnected']);
export interface Recording {
  id:string;owner_id:string;device_id:string;session:string;object_key:string;
  status:'capturing'|'ready'|'deleting'|'deleted';created_ms:string;completed_ms:string|null;
  expires_ms:string;bytes:string;duration_ms:string;reason:string;
  segment:number;gap_before_ms:string;resume_blocked:boolean;deadline_ms?:number;
}
export class Recordings {
  readonly store:Store;
  constructor(store:Store){this.store=store;}
  async begin(owner:string,device:string,session:string,reserve:number,quota:number,now=Date.now(),minimum=reserve,work?:{seconds:number}){
    await this.store.owns(owner,device);
    if(!/^[1-9][0-9]{0,19}$/.test(owner)||!Number.isSafeInteger(reserve)||reserve<=0||!Number.isSafeInteger(quota)||quota<reserve||!Number.isSafeInteger(minimum)||minimum<=0||minimum>reserve)throw new RetentionError('Invalid quota');
    if(work&&(!Number.isSafeInteger(work.seconds)||work.seconds<=0))throw new RetentionError('Invalid work limit');
    const history=(await this.store.db.query<Recording>('SELECT * FROM recordings WHERE owner_id=$1 AND device_id=$2 AND session=$3 ORDER BY segment',[owner,device,session])).rows;
    const previous=history.at(-1),deadline=work?(Number(history[0]?.created_ms??now)+work.seconds*1000):undefined;
    if(previous&&(!work||!['ready','deleted'].includes(previous.status)||!resumableReasons.has(previous.reason)||history.some(r=>r.resume_blocked)))throw new RetentionError('Work session cannot resume');
    if(deadline!==undefined&&now>=deadline)throw new RecordingLimitError('duration_limit');
    const remaining=reserve-history.reduce((sum,r)=>sum+Number(r.bytes),0);
    if(remaining<minimum||history.length>=100)throw new RecordingLimitError('size_limit');
    const segment=(previous?.segment??0)+1,gap=previous?Math.max(0,now-Number(previous.created_ms)-Number(previous.duration_ms)):0;
    await this.store.db.query('INSERT INTO recording_accounts(owner_id) VALUES($1) ON CONFLICT DO NOTHING',[owner]);
    const id=randomUUID(),key=`recordings/${owner}/${device}/${id}.mp4`;
    // Lock the owner's balance before computing a partial reservation across concurrent devices.
    const result=await this.store.db.query<Recording>(`WITH available AS (
      SELECT owner_id,LEAST($2::bigint,$3::bigint-used_bytes) AS bytes FROM recording_accounts WHERE owner_id=$1 FOR UPDATE),
      reserved AS (
      UPDATE recording_accounts a SET used_bytes=a.used_bytes+v.bytes FROM available v
      WHERE a.owner_id=v.owner_id AND v.bytes>=$10
      AND EXISTS(SELECT 1 FROM devices WHERE id=$4 AND owner_id=$1 AND NOT revoked AND expires_ms>$8) RETURNING a.owner_id,v.bytes)
      INSERT INTO recordings(id,owner_id,device_id,session,object_key,created_ms,expires_ms,bytes,segment,gap_before_ms)
      SELECT $5,owner_id,$4,$6,$7,$8,$9,bytes,$11,$12 FROM reserved RETURNING *`,[owner,remaining,quota,device,id,session,key,now,now+RETENTION_MS,minimum,segment,gap]);
    if(!result.rows.length){await this.store.owns(owner,device);throw new RecordingQuotaError('Insufficient recording space');}return {...result.rows[0],deadline_ms:deadline};
  }
  async blockResume(owner:string,device:string,session:string){
    await this.store.db.query('UPDATE recordings SET resume_blocked=TRUE WHERE owner_id=$1 AND device_id=$2 AND session=$3',[owner,device,session]);
  }
  async get(owner:string,id:string,_now=Date.now()){
    const r=await this.store.db.query<Recording>('SELECT * FROM recordings WHERE owner_id=$1 AND id=$2 AND status<>\'deleted\'',[owner,id]);
    if(!r.rows.length)throw new AccessError('Not found');return r.rows[0];
  }
  async list(owner:string,device:string){
    await this.store.owns(owner,device);
    return (await this.store.db.query<Recording>(`SELECT * FROM recordings WHERE owner_id=$1 AND device_id=$2 AND status<>'deleted' ORDER BY created_ms DESC LIMIT 100`,[owner,device])).rows;
  }
  async downloadable(owner:string,id:string,now=Date.now()){
    const r=await this.get(owner,id);if(r.status!=='ready'||Number(r.expires_ms)<=now)throw new AccessError('Not found');return r;
  }
  async ready(id:string,bytes:number,duration:number,reason:string,now=Date.now()){
    if(!Number.isSafeInteger(bytes)||bytes<=0||!Number.isSafeInteger(duration)||duration<0)throw new RetentionError('Invalid file');
    const r=await this.store.db.query(`WITH previous AS (SELECT id,owner_id,bytes FROM recordings WHERE id=$1 AND status='capturing' AND bytes>=$2 FOR UPDATE),
      completed AS (UPDATE recordings r SET status='ready',bytes=$2,duration_ms=$3,reason=$4,completed_ms=$5,expires_ms=$6
      FROM previous p WHERE r.id=p.id RETURNING r.id)
      UPDATE recording_accounts a SET used_bytes=used_bytes-p.bytes+$2 FROM previous p,completed c WHERE a.owner_id=p.owner_id RETURNING c.id`,[id,bytes,duration,reason,now,now+RETENTION_MS]);
    if(!r.rows.length)throw new RetentionError('Recording no longer pending');
  }
  async markDeleting(owner:string,id:string){
    const r=await this.store.db.query(`UPDATE recordings SET status='deleting' WHERE id=$1 AND owner_id=$2 AND status IN ('ready','deleting') RETURNING id`,[id,owner]);
    if(!r.rows.length)throw new AccessError('Not found');
  }
  async expired(now=Date.now()){
    return (await this.store.db.query<Recording>(`SELECT * FROM recordings WHERE status='deleting' OR (status<>'deleted' AND expires_ms<=$1) ORDER BY expires_ms LIMIT 100`,[now])).rows;
  }
  async interrupted(){
    await this.store.db.query(`UPDATE recordings SET status='deleting',reason='server_restart' WHERE status='capturing'`);
  }
  async abandon(id:string){
    await this.store.db.query(`UPDATE recordings SET status='deleting',reason='storage_error' WHERE id=$1 AND status IN ('capturing','ready')`,[id]);
  }
  async removed(id:string){
    await this.store.db.query(`WITH removed AS (UPDATE recordings SET status='deleted' WHERE id=$1 AND status<>'deleted' RETURNING owner_id,bytes)
      UPDATE recording_accounts a SET used_bytes=used_bytes-r.bytes FROM removed r WHERE a.owner_id=r.owner_id`,[id]);
  }
}
