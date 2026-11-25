import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {Pairing,PairingError} from '../server/pairing.ts';
let db:PGlite,store:Store,pairing:Pairing;
const viewer='77777777-7777-4777-8777-777777777777';
before(async()=>{db=new PGlite();store=new Store(db);await store.init();await store.checkViewer('owner',viewer);pairing=new Pairing(store,'b'.repeat(64));});
after(async()=>{await db.close();});
test('pairing needs owner approval, hashes all secrets, and issues publisher-only credential',async()=>{
  const p=await pairing.request('Fold7',1000);
  assert.match(p.code,/^[A-HJ-NP-Z2-9]{8}$/);assert.equal(p.expires_ms,43201000);
  assert.deepEqual(await pairing.poll(p.poll_token,1001),{status:'pending',expires_ms:43201000});
  const view=await pairing.lookup(p.code,1001);assert.equal(view.name,'Fold7');
  assert.deepEqual(Object.keys(view).sort(),['expires_ms','name','request_id']);
  const d=await pairing.approve('owner',p.code,view.request_id,viewer,1002);
  const result=await pairing.poll(p.poll_token,1003);assert.equal(result.status,'approved');
  if(result.status!=='approved')throw new Error('Not approved');
  assert.equal(result.device_id,d.device_id);assert.equal((await store.device(result.device_token,1003))?.owner_id,'owner');
  assert.deepEqual(await pairing.poll(p.poll_token,1004),result);
  const raw=JSON.stringify((await db.query('SELECT * FROM pairing_requests')).rows);
  assert(!raw.includes(p.code));assert(!raw.includes(p.poll_token));assert(!raw.includes(result.device_token));
  assert(!JSON.stringify((await db.query('SELECT * FROM devices')).rows).includes(result.device_token));
  await store.revoke('owner',d.device_id);
  await assert.rejects(()=>pairing.poll(p.poll_token,1005),PairingError);
});
test('only one concurrent approval wins; wrong request binding never approves',async()=>{
  const p=await pairing.request('Concurrent',1000),v=await pairing.lookup(p.code,1001);
  await assert.rejects(()=>pairing.approve('owner',p.code,'00000000-0000-4000-8000-000000000000',viewer,1002));
  const results=await Promise.allSettled([pairing.approve('owner',p.code,v.request_id,viewer,1002),pairing.approve('owner',p.code,v.request_id,viewer,1002)]);
  assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
});
test('expiry, forged poll and invalid input cannot create a credential',async()=>{
  const p=await pairing.request('Expiring',1000),v=await pairing.lookup(p.code,1001);
  await assert.rejects(()=>pairing.poll('a'.repeat(64),1002));
  assert.equal((await pairing.lookup(p.code,301000)).name,'Expiring');
  assert.equal((await pairing.poll(p.poll_token,43200999)).status,'pending');
  await assert.rejects(()=>pairing.lookup(p.code,43201000));
  await assert.rejects(()=>pairing.approve('owner',p.code,v.request_id,viewer,43201000));
  await assert.rejects(()=>pairing.poll(p.poll_token,43201000));
  for(const name of ['', ' ', 'a'.repeat(65)])await assert.rejects(()=>pairing.request(name,1000));
});
test('pending request capacity is bounded and expires before reuse',async()=>{
  await db.query('DELETE FROM pairing_requests');
  for(let i=0;i<128;i++)await pairing.request('Bounded',1000);
  await assert.rejects(()=>pairing.request('Excess',1001),PairingError);
  assert.equal((await pairing.request('After expiry',43201000)).expires_ms,86401000);
});
