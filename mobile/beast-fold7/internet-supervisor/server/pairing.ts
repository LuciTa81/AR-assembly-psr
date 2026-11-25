import {createHash,createHmac,randomBytes,randomUUID} from 'node:crypto';
import {z} from 'zod';
import type {Store} from './store.ts';

export class PairingError extends Error {status:number;constructor(status=410){super('Pairing unavailable');this.status=status;}}
export const codeSchema=z.string().regex(/^[A-HJ-NP-Z2-9]{8}$/);
const nameSchema=z.string().trim().min(1).max(64).regex(/^[^\x00-\x1f\x7f]+$/);
const hash=(value:string)=>createHash('sha256').update(value).digest('hex');
const alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const pairingLifetimeMs=12*60*60*1000;
type Pair={id:string;poll_hash:string;device_name:string;expires_ms:string;approved_device_id:string|null};
export class Pairing {
  private store:Store;private key:string;
  constructor(store:Store,key:string){this.store=store;this.key=key;}
  private token(pollHash:string){return createHmac('sha256',this.key).update('pairing-device-v1:'+pollHash).digest('hex');}
  async request(name:string,now=Date.now()){
    name=nameSchema.parse(name);
    await this.store.db.query('DELETE FROM pairing_requests WHERE expires_ms<=$1',[now]);
    for(let attempt=0;attempt<4;attempt++){
      const code=[...randomBytes(8)].map(n=>alphabet[n&31]).join(''),pollToken=randomBytes(32).toString('hex'),id=randomUUID();
      // Unique bounded slots enforce capacity even across concurrent DB connections.
      const result=await this.store.db.query(`INSERT INTO pairing_requests(id,slot,code_hash,poll_hash,device_name,expires_ms)
        SELECT $1,s,$2,$3,$4,$5 FROM generate_series(0,127) s
        WHERE NOT EXISTS(SELECT 1 FROM pairing_requests p WHERE p.slot=s)
        ORDER BY s LIMIT 1 ON CONFLICT DO NOTHING RETURNING id`,[id,hash(code),hash(pollToken),name,now+pairingLifetimeMs]);
      if(result.rows.length)return {code,poll_token:pollToken,expires_ms:now+pairingLifetimeMs,interval_ms:2000};
    }
    throw new PairingError(429);
  }
  private async find(code:string,now:number){
    codeSchema.parse(code);
    const row=(await this.store.db.query<Pair>('SELECT * FROM pairing_requests WHERE code_hash=$1 AND expires_ms>$2 AND approved_device_id IS NULL',[hash(code),now])).rows[0];
    if(!row)throw new PairingError();return row;
  }
  async lookup(code:string,now=Date.now()){
    const row=await this.find(code,now);return {request_id:row.id,name:row.device_name,expires_ms:Number(row.expires_ms)};
  }
  async approve(owner:string,code:string,requestId:string,viewer:string,now=Date.now()){
    const row=await this.find(code,now);if(row.id!==requestId)throw new PairingError();
    const id=randomUUID(),tokenHash=hash(this.token(row.poll_hash));
    // The viewer row lock serializes approval with logout in this one DB statement.
    const result=await this.store.db.query<{id:string;name:string}>(`WITH authorized AS (
      SELECT id FROM viewer_sessions WHERE id=$8 AND owner_id=$5 AND NOT revoked FOR UPDATE
    ), approved AS (
      UPDATE pairing_requests SET approved_device_id=$1 WHERE id=$2 AND code_hash=$3 AND expires_ms>$4 AND approved_device_id IS NULL
      AND EXISTS(SELECT 1 FROM authorized) RETURNING device_name
    ) INSERT INTO devices(id,owner_id,name,token_hash,expires_ms)
      SELECT $1,$5,device_name,$6,$7 FROM approved RETURNING id,name`,[id,row.id,hash(code),now,owner,tokenHash,now+30*86400000,viewer]);
    if(!result.rows.length)throw new PairingError();
    return {device_id:result.rows[0].id,name:result.rows[0].name};
  }
  async poll(pollToken:string,now=Date.now()){
    if(!/^[a-f0-9]{64}$/.test(pollToken))throw new PairingError();
    const row=(await this.store.db.query<Pair>('SELECT * FROM pairing_requests WHERE poll_hash=$1 AND expires_ms>$2',[hash(pollToken),now])).rows[0];
    if(!row)throw new PairingError();
    if(!row.approved_device_id)return {status:'pending' as const,expires_ms:Number(row.expires_ms)};
    const token=this.token(row.poll_hash),device=await this.store.device(token,now);
    if(!device||device.id!==row.approved_device_id)throw new PairingError();
    return {status:'approved' as const,device_id:device.id,device_token:token,expires_ms:Number(device.expires_ms)};
  }
}
