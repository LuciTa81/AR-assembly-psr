import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {publish} from './fixture.ts';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
let db:PGlite, store:Store;
before(async()=>{db=new PGlite();store=new Store(db);await store.init();});
after(async()=>{await db.close();});

test('device tokens authenticate only while valid and are stored as hashes',async()=>{
  const d=await store.provision('owner','Fold7',1000);
  assert.equal((await store.device(d.token,1001))?.id,d.id);
  assert.equal(await store.device('incorrect',1001),null);
  assert.equal(await store.device(d.token,1000+31*86400000),null);
  const raw=await db.query<{token_hash:string}>('SELECT token_hash FROM devices WHERE id=$1',[d.id]);
  assert.notEqual(raw.rows[0].token_hash,d.token);
});
test('tickets are owner scoped, expire in 30s and are consumed atomically once',async()=>{
  const d=await store.provision('owner','Ticket',1000);
  await assert.rejects(()=>store.ticket('intruder',d.id,1000));
  const token=await store.ticket('owner',d.id,1000);
  const results=await Promise.all([store.consumeTicket(token,1001),store.consumeTicket(token,1001)]);
  assert.equal(results.filter(Boolean).length,1);
  assert.equal(await store.consumeTicket(await store.ticket('owner',d.id,1000),31000),null);
});
test('revocation invalidates device tokens and already issued tickets',async()=>{
  const d=await store.provision('owner','Revoked',1000);
  const ticket=await store.ticket('owner',d.id,1000);
  await assert.rejects(()=>store.revoke('other',d.id));
  await store.revoke('owner',d.id);
  assert.equal(await store.device(d.token,1001),null);
  assert.equal(await store.consumeTicket(ticket,1001),null);
});
test('events are idempotent, owner isolated, and contain actual session/phase rather than invented completion',async()=>{
  const d=await store.provision('owner','History',1000);
  await store.event(d.id,publish(), 'step',1000);
  await store.event(d.id,publish(), 'step',1000);
  const rows=await store.history('owner',d.id);
  assert.equal(rows.length,1);assert.equal(rows[0].state.stage,2);assert.equal(rows[0].kind,'step');
  await assert.rejects(()=>store.history('other',d.id));
  const second=new Store(db);assert.equal((await second.history('owner',d.id)).length,1);
});
test('records survive closing and reopening a database, without persisting device token plaintext',async()=>{
  const folder=await mkdtemp(join(tmpdir(),'ar-relay-test-'));
  let disk:PGlite|undefined;
  try{
    disk=new PGlite(folder);let s=new Store(disk);await s.init();
    const device=await s.provision('owner','Persisted');await s.event(device.id,publish(),'step');
    await disk.close();disk=new PGlite(folder);s=new Store(disk);
    assert.equal((await s.history('owner',device.id))[0].state.phase,'WORKING');
    assert.equal((await s.device(device.token))?.id,device.id);
  }finally{if(disk&&!disk.closed)await disk.close();await rm(folder,{recursive:true,force:true});}
});
test('viewer logout invalidates pending tickets but never revokes the phone',async()=>{
  const d=await store.provision('owner','Logout');
  const sid='viewer-session-1';const ticket=await store.ticket('owner',d.id,Date.now(),sid);
  await store.revokeViewer('owner',sid);
  assert.equal(await store.consumeTicket(ticket),null);
  await assert.rejects(()=>store.ticket('owner',d.id,Date.now(),sid));
  assert.equal((await store.device(d.token))?.id,d.id);
});
test('device list returns only owner metadata, not credentials',async()=>{
  const devices=await store.listDevices('other-owner');assert.deepEqual(devices,[]);
  const own=await store.listDevices('owner');assert(own.length>0);
  assert.deepEqual(Object.keys(own[0]).sort(),['id','name','revoked']);
});

test('viewer access check cannot reactivate a logged-out session',async()=>{
  await store.checkViewer('owner','checked-viewer');
  await assert.rejects(()=>store.checkViewer('other','checked-viewer'));
  await store.revokeViewer('owner','checked-viewer');
  await assert.rejects(()=>store.checkViewer('owner','checked-viewer'));
  await store.checkViewer('owner','new-viewer');
});

test('history defaults to latest started work, including its stop but excluding later idle sessions',async()=>{
  const d=await store.provision('owner','Latest work');
  for(const [seq,session,running] of [[1,'old',true],[2,'latest',true],[3,'latest',false],[4,'app-idle',false]] as const){
    const p=publish(seq);p.state={...p.state,session,running,stage:running?2:-1};
    await store.event(d.id,p,running?'step':'stop',seq*1000);
  }
  const idle=publish(5);idle.state={...idle.state,session:'latest',running:false,stage:-1};
  await store.event(d.id,idle,'step',5000);
  const rows=await store.history('owner',d.id);
  assert.deepEqual(rows.map(r=>r.state.session),['latest','latest']);
  assert.equal(rows[0].kind,'stop');
  assert.equal((await store.history('owner',d.id,'old'))[0].state.session,'old');
  assert.deepEqual(await store.history('owner',d.id,'app-idle'),[]);
  const sessions=await store.workSessions('owner',d.id);
  assert.deepEqual(sessions.map(s=>s.session),['latest','old']);
  await assert.rejects(()=>store.workSessions('intruder',d.id));
  await assert.rejects(()=>store.history('intruder',d.id,'latest'));
});

test('work selection happens before the event limit and persists across Store instances',async()=>{
  const d=await store.provision('owner','Long history');
  const p=publish();p.state.session='first';await store.event(d.id,p,'step',1);
  for(let seq=2;seq<=245;seq++){
    const p=publish(seq);p.state.session='second';await store.event(d.id,p,'phase',seq);
  }
  assert.equal((await store.history('owner',d.id)).length,240);
  assert.equal((await new Store(db).history('owner',d.id,'first')).length,1);
  assert.deepEqual(await store.history('owner',d.id,'missing'),[]);
});
