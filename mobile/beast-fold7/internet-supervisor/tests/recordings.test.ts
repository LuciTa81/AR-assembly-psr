import {test,before,after,afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {PGlite} from '@electric-sql/pglite';
import {Store,AccessError} from '../server/store.ts';
import {Recordings,RetentionError} from '../server/recordings.ts';
let db:PGlite,store:Store,records:Recordings,device:string;
before(async()=>{db=new PGlite();store=new Store(db);await store.init();records=new Recordings(store);device=(await store.provision('101','Phone')).id;});
after(async()=>{await db.close();});
afterEach(async()=>{for(const r of (await db.query<{id:string}>("SELECT id FROM recordings WHERE status<>'deleted'")).rows)await records.removed(r.id);});

test('10GB quota supports 300MB reservations beyond 32-bit range without overbooking',async()=>{
  for(let n=0;n<33;n++){
    const row=await records.begin('101',device,`large-quota-${n}`,300000000,10000000000);
    assert.equal(Number(row.bytes),300000000);
  }
  const last=await records.begin('101',device,'large-quota-last',300000000,10000000000,Date.now(),2097152);
  assert.equal(Number(last.bytes),100000000);
  assert.equal(Number((await db.query<{used_bytes:string}>('SELECT used_bytes FROM recording_accounts WHERE owner_id=$1',['101'])).rows[0].used_bytes),10000000000);
  await assert.rejects(()=>records.begin('101',device,'large-quota-full',300000000,10000000000,Date.now(),2097152),RetentionError);
});
test('segments share a durable deadline and byte budget even after old clips are deleted',async()=>{
  const first=await records.begin('101',device,'segmented',1000,2000,10000,100,{seconds:5});
  await records.ready(first.id,600,500,'state_stale',11000);await records.removed(first.id);
  const second=await records.begin('101',device,'segmented',1000,2000,12000,100,{seconds:5});
  assert.equal(Number(second.bytes),400);assert.equal(second.segment,2);assert.equal(second.deadline_ms,15000);
  assert.equal(Number(second.gap_before_ms),1500);
  await records.ready(second.id,400,500,'video_stale',13000);await records.removed(second.id);
  await assert.rejects(()=>records.begin('101',device,'segmented',1000,2000,14000,100,{seconds:5}),/limit/);
  const timed=await records.begin('101',device,'timed-segments',1000,2000,10000,100,{seconds:5});
  await records.ready(timed.id,100,500,'state_stale',11000);
  await assert.rejects(()=>records.begin('101',device,'timed-segments',1000,2000,15000,100,{seconds:5}),/limit/);
  await records.removed(timed.id);
});
test('normal completion and withdrawn consent never auto-resume a work session',async()=>{
  for(const reason of ['stopped','completed','revoked','duration_limit','size_limit','storage_error']){
    const r=await records.begin('101',device,`terminal-${reason}`,1000,2000,10000,100,{seconds:5});
    await records.ready(r.id,100,500,reason,11000);
    await assert.rejects(()=>records.begin('101',device,`terminal-${reason}`,1000,2000,12000,100,{seconds:5}));await records.removed(r.id);
  }
  const r=await records.begin('101',device,'withdrawn',1000,2000,10000,100,{seconds:5});
  await records.ready(r.id,100,500,'state_stale',11000);await records.blockResume('101',device,'withdrawn');
  await assert.rejects(()=>records.begin('101',device,'withdrawn',1000,2000,12000,100,{seconds:5}));await records.removed(r.id);
});
test('a new recording reserves remaining quota without deleting an existing clip',async()=>{
  const old=await records.begin('101',device,'short-clip',100000000,100000000);
  await records.ready(old.id,329241,2269,'stopped');
  try{
    const next=await records.begin('101',device,'remaining',100000000,100000000,Date.now(),2097152);
    assert.equal(Number(next.bytes),99670759);
    assert.equal(Number((await db.query<{used_bytes:string}>('SELECT used_bytes FROM recording_accounts WHERE owner_id=$1',['101'])).rows[0].used_bytes),100000000);
    await assert.rejects(()=>records.begin('101',device,'no-room',100000000,100000000,Date.now(),2097152),RetentionError);
    await records.removed(next.id);
    assert.equal((await records.get('101',old.id)).status,'ready');
  }finally{await records.removed(old.id);}
});
test('partial reservations cannot oversubscribe quota across simultaneous starts',async()=>{
  const old=await records.begin('101',device,'concurrent-old',1000,2000);
  await records.ready(old.id,500,1000,'stopped');
  const attempts=await Promise.allSettled([1,2,3].map(n=>records.begin('101',device,`partial-${n}`,1000,2000,Date.now(),400)));
  const accepted=attempts.filter(r=>r.status==='fulfilled').map(r=>(r as PromiseFulfilledResult<any>).value);
  try{assert.deepEqual(accepted.map(r=>Number(r.bytes)).sort((a,b)=>a-b),[500,1000]);}
  finally{for(const r of [...accepted,old])await records.removed(r.id);}
});
test('recordings cannot be created or read for another owner device',async()=>{
  await assert.rejects(()=>records.begin('202',device,'s',1000,2000,100),AccessError);
  const r=await records.begin('101',device,'s',1000,2000,100);
  await assert.rejects(()=>records.get('202',r.id,101),AccessError);
  await assert.rejects(()=>records.list('202',device),AccessError);
  assert(r.object_key.startsWith(`recordings/101/${device}/`));
  await records.removed(r.id);
});
test('quota reservations are atomic and release only once after confirmed removal',async()=>{
  const attempts=await Promise.allSettled([1,2,3].map(n=>records.begin('101',device,`q${n}`,1000,2000,200)));
  const accepted=attempts.filter(r=>r.status==='fulfilled').map(r=>(r as PromiseFulfilledResult<any>).value);
  assert.equal(accepted.length,2);assert.equal(attempts.filter(r=>r.status==='rejected').length,1);
  await records.removed(accepted[0].id);await records.removed(accepted[0].id);
  const third=await records.begin('101',device,'q4',1000,2000,200);
  await assert.rejects(()=>records.begin('101',device,'q5',1000,2000,200),RetentionError);
  for(const r of [accepted[1],third])await records.removed(r.id);
});
test('only ready files are downloadable and access ends exactly seven days after completion',async()=>{
  const r=await records.begin('101',device,'expiry',1000,2000,1000);
  await assert.rejects(()=>records.downloadable('101',r.id,1001),AccessError);
  await records.ready(r.id,800,1000,'completed',2000);
  assert.equal(Number((await records.downloadable('101',r.id,604801999)).bytes),800);
  await assert.rejects(()=>records.downloadable('101',r.id,604802000),AccessError);
  assert((await records.expired(604802000)).some(v=>v.id===r.id));
  await records.markDeleting('101',r.id);
  await assert.rejects(()=>records.downloadable('101',r.id,3000),AccessError);
  assert((await records.expired(3000)).some(v=>v.id===r.id));
  await records.removed(r.id);
});
test('oversized or duplicate completion cannot bypass reserved quota or extend retention',async()=>{
  const r=await records.begin('101',device,'limits',1000,2000,1000);
  await assert.rejects(()=>records.ready(r.id,1001,1000,'completed',2000),RetentionError);
  await records.ready(r.id,500,1000,'completed',2000);
  await assert.rejects(()=>records.ready(r.id,500,1000,'completed',3000),RetentionError);
  await records.removed(r.id);
});
test('the same work session cannot restart recording after a relay restart or deletion',async()=>{
  const r=await records.begin('101',device,'once',1000,2000);
  await records.interrupted();await records.removed(r.id);
  await assert.rejects(()=>records.begin('101',device,'once',1000,2000));
  const next=await records.begin('101',device,'new-session',2000,2000);await records.removed(next.id);
});
