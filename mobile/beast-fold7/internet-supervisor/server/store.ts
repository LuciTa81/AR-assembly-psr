import {createHash,randomBytes,randomUUID} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import type {Publish, Snapshot} from '../shared/protocol.ts';

export interface Database { query<T=Record<string,unknown>>(sql:string, params?:unknown[]):Promise<{rows:T[]}>; }
export interface Device {id:string; owner_id:string; expires_ms:string;viewer_session?:string;}
export interface HistoryEvent {kind:string; received_ms:string; state:Snapshot;}
export interface WorkSession {session:string; started_ms:string; last_ms:string; event_count:string;}
export class AccessError extends Error {}
const hash=(s:string)=>createHash('sha256').update(s).digest('hex');
const secret=()=>randomBytes(32).toString('hex');
export class Store {
  readonly db:Database;
  constructor(db:Database){this.db=db;}
  async init(){
    const sql=await readFile(new URL('./schema.sql',import.meta.url),'utf8');
    for(const statement of sql.split(';').filter(s=>s.trim()))await this.db.query(statement);
  }
  async provision(owner:string,name:string,now=Date.now()){
    const id=randomUUID(),token=secret();
    await this.db.query('INSERT INTO devices(id,owner_id,name,token_hash,expires_ms) VALUES($1,$2,$3,$4,$5)',[id,owner,name,hash(token),now+30*86400000]);
    return {id,token};
  }
  async device(token:string,now=Date.now()):Promise<Device|null>{
    const r=await this.db.query<Device>('SELECT id,owner_id,expires_ms FROM devices WHERE token_hash=$1 AND NOT revoked AND expires_ms>$2',[hash(token),now]);
    return r.rows[0]??null;
  }
  async owns(owner:string,id:string){
    const r=await this.db.query('SELECT id FROM devices WHERE id=$1 AND owner_id=$2',[id,owner]);
    if(!r.rows.length)throw new AccessError('Not found');
  }
  async ticket(owner:string,id:string,now=Date.now(),viewer?:string):Promise<string>{
    const token=secret();
    if(viewer)await this.checkViewer(owner,viewer);
    await this.db.query('DELETE FROM tickets WHERE expires_ms<=$1',[now]);
    const r=await this.db.query(`INSERT INTO tickets(token_hash,device_id,owner_id,expires_ms,viewer_session)
      SELECT $1,id,owner_id,$2,$6 FROM devices WHERE id=$3 AND owner_id=$4 AND NOT revoked AND expires_ms>$5 RETURNING token_hash`,[hash(token),now+30000,id,owner,now,viewer??null]);
    if(!r.rows.length)throw new AccessError('Not found');
    return token;
  }
  async consumeTicket(token:string,now=Date.now()):Promise<Device|null>{
    const r=await this.db.query<Device>(`WITH used AS (
      DELETE FROM tickets WHERE token_hash=$1 RETURNING *)
      SELECT d.id,d.owner_id,d.expires_ms,t.viewer_session FROM used t JOIN devices d ON d.id=t.device_id
      WHERE t.expires_ms>$2 AND d.expires_ms>$2 AND NOT d.revoked
      AND (t.viewer_session IS NULL OR EXISTS (SELECT 1 FROM viewer_sessions v WHERE v.id=t.viewer_session AND v.owner_id=t.owner_id AND NOT v.revoked))`,[hash(token),now]);
    return r.rows[0]??null;
  }
  async revoke(owner:string,id:string){
    const r=await this.db.query('UPDATE devices SET revoked=TRUE WHERE id=$1 AND owner_id=$2 RETURNING id',[id,owner]);
    if(!r.rows.length)throw new AccessError('Not found');
  }
  async event(id:string,p:Publish,kind:string,now=Date.now()){
    await this.db.query(`INSERT INTO events(device_id,stream_id,seq,kind,received_ms,state)
      VALUES($1,$2,$3,$4,$5,$6::jsonb) ON CONFLICT DO NOTHING`,[id,p.stream_id,p.seq,kind,now,JSON.stringify(p.state)]);
  }
  async workSessions(owner:string,id:string):Promise<WorkSession[]>{
    await this.owns(owner,id);
    return (await this.db.query<WorkSession>(`SELECT state->>'session' AS session,
      MIN(received_ms) FILTER (WHERE state->>'running'='true') AS started_ms,
      MAX(received_ms) AS last_ms, COUNT(*) AS event_count
      FROM events WHERE device_id=$1 AND (state->>'running'='true' OR kind='stop') GROUP BY state->>'session'
      HAVING BOOL_OR(state->>'running'='true')
      ORDER BY MIN(id) FILTER (WHERE state->>'running'='true') DESC LIMIT 50`,[id])).rows;
  }
  async history(owner:string,id:string,session?:string):Promise<HistoryEvent[]>{
    await this.owns(owner,id);
    // Choose a started work session before limiting events; idle app launches are not work.
    return (await this.db.query<HistoryEvent>(`WITH work AS (
      SELECT state->>'session' AS session FROM events
      WHERE device_id=$1 AND state->>'running'='true'
      AND ($2::text IS NULL OR state->>'session'=$2)
      GROUP BY state->>'session' ORDER BY MIN(id) DESC LIMIT 1
    ) SELECT kind,received_ms,state FROM events
      WHERE device_id=$1 AND state->>'session'=(SELECT session FROM work)
      AND (state->>'running'='true' OR kind='stop')
      ORDER BY id DESC LIMIT 240`,[id,session??null])).rows;
  }
  async listDevices(owner:string){
    return (await this.db.query<{id:string;name:string;revoked:boolean}>('SELECT id,name,revoked FROM devices WHERE owner_id=$1 ORDER BY name LIMIT 64',[owner])).rows;
  }
  async revokeViewer(owner:string,sid:string){
    const r=await this.db.query(`INSERT INTO viewer_sessions(id,owner_id,revoked) VALUES($1,$2,TRUE)
      ON CONFLICT(id) DO UPDATE SET revoked=TRUE WHERE viewer_sessions.owner_id=$2 RETURNING id`,[sid,owner]);
    if(!r.rows.length)throw new AccessError('Not found');
  }
  async checkViewer(owner:string,sid:string){
    await this.db.query('INSERT INTO viewer_sessions(id,owner_id) VALUES($1,$2) ON CONFLICT DO NOTHING',[sid,owner]);
    const r=await this.db.query('SELECT id FROM viewer_sessions WHERE id=$1 AND owner_id=$2 AND NOT revoked',[sid,owner]);
    if(!r.rows.length)throw new AccessError('Session revoked');
  }
}
