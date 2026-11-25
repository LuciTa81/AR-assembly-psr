import assert from 'node:assert/strict';
import {Pool} from 'pg';
import {Store} from '../server/store.ts';
import {Recordings,RecordingQuotaError,RecordingLimitError} from '../server/recordings.ts';

const pool=new Pool({connectionString:process.env.DATABASE_URL,max:1});
const client=await pool.connect();
try{
  await client.query('BEGIN');
  // Session-local tables shadow production tables; rollback removes all synthetic data.
  for(const table of ['devices','recording_accounts','recordings'])
    await client.query(`CREATE TEMP TABLE ${table} (LIKE public.${table} INCLUDING ALL) ON COMMIT DROP`);
  const store=new Store({async query<T>(sql:string,params?:unknown[]){return {rows:(await client.query(sql,params)).rows as T[]};}});
  const records=new Recordings(store),device=await store.provision('101','Synthetic quota check');
  const old=await records.begin('101',device.id,'old',100000000,100000000);
  await records.ready(old.id,329241,2269,'stopped');
  const next=await records.begin('101',device.id,'next',100000000,100000000,Date.now(),2097152);
  assert.equal(Number(next.bytes),99670759);
  assert.equal(Number((await client.query('SELECT used_bytes FROM recording_accounts')).rows[0].used_bytes),100000000);
  await assert.rejects(()=>records.begin('101',device.id,'full',100000000,100000000,Date.now(),2097152),RecordingQuotaError);
  await records.ready(next.id,50000000,200000,'stopped');
  assert.equal(Number((await client.query('SELECT used_bytes FROM recording_accounts')).rows[0].used_bytes),50329241);
  assert.equal((await records.get('101',old.id)).status,'ready');
  const d=await store.provision('102','Synthetic segment check'),now=Date.now();
  const first=await records.begin('102',d.id,'segments',100000000,100000000,now,2097152,{seconds:300});
  await records.ready(first.id,1000,1000,'state_stale',now+1000);await records.removed(first.id);
  const second=await records.begin('102',d.id,'segments',100000000,100000000,now+3000,2097152,{seconds:300});
  assert.equal(second.segment,2);assert.equal(Number(second.bytes),99999000);
  assert.equal(second.deadline_ms,now+300000);assert.equal(Number(second.gap_before_ms),2000);
  await records.ready(second.id,500,1000,'video_stale',now+4000);
  await assert.rejects(()=>records.begin('102',d.id,'segments',100000000,100000000,now+300000,2097152,{seconds:300}),RecordingLimitError);
  await records.blockResume('102',d.id,'segments');
  await assert.rejects(()=>records.begin('102',d.id,'segments',100000000,100000000,now+5000,2097152,{seconds:300}));
  console.log('PASS PostgreSQL: quota reservation, segment recovery, shared deadline/bytes after deletion, consent block; temporary rows rolled back, no S3 access');
}finally{await client.query('ROLLBACK');client.release();await pool.end();}
