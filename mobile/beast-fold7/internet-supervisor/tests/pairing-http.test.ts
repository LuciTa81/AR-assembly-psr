import {test,before,after,beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {PGlite} from '@electric-sql/pglite';
import {WebSocket} from 'ws';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
const key='c'.repeat(64),viewer='44444444-4444-4444-8444-444444444444';
const headers={Authorization:`Bearer ${key}`,'X-Viewer-Session':viewer};
let db:PGlite,store:Store,relay:ReturnType<typeof createRelay>,base:string,clock=0;
before(async()=>{db=new PGlite();store=new Store(db);await store.init();relay=createRelay(store,{ownerId:'owner',serviceKey:key,origins:['http://localhost:3000'],monotonic:()=>clock});relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');base=`http://127.0.0.1:${(relay.server.address() as {port:number}).port}`;});
beforeEach(()=>{clock+=60001;});
after(async()=>{await relay.close();await db.close();});
async function post(action:string,data?:unknown,extra:Record<string,string>={}){return fetch(base+'/pairing/'+action,{method:'POST',headers:{'Content-Type':'application/json',...extra},body:data===undefined?undefined:JSON.stringify(data)});}
test('real HTTP approval produces credential accepted by publisher websocket',async()=>{
  const request=await post('request',{name:'Synthetic Fold7'});assert.equal(request.status,200);const p=await request.json();
  assert.equal(request.headers.get('cache-control'),'no-store');
  assert.equal((await post('poll',undefined,{Authorization:p.poll_token})).status,410);
  assert.equal((await post('poll',{unexpected:true},{Authorization:`Bearer ${p.poll_token}`})).status,400);
  assert.equal((await post('lookup',{code:p.code})).status,401);
  assert.equal((await post('lookup',{code:p.code},{Authorization:`Bearer ${key}`})).status,401);
  const view=await post('lookup',{code:p.code},headers);assert.equal(view.status,200);const v=await view.json();
  assert.equal((await post('approve',{code:p.code,request_id:v.request_id},headers)).status,200);
  const poll=await post('poll',undefined,{Authorization:`Bearer ${p.poll_token}`});assert.equal(poll.status,200);const d=await poll.json();
  const ws=new WebSocket(base.replace('http:','ws:')+'/ws');await once(ws,'open');
  try{const message=once(ws,'message');ws.send(JSON.stringify({role:'publisher',token:d.device_token}));assert.equal(JSON.parse(String((await message)[0])).type,'ready');}finally{ws.terminate();}
  await store.revoke('owner',d.device_id);assert.equal((await post('poll',undefined,{Authorization:`Bearer ${p.poll_token}`})).status,410);
});
test('pairing rejects browser origins, invalid bodies, oversized requests and missing secrets',async()=>{
  assert.equal((await post('request',{name:'Phone'},{Origin:'https://evil.invalid'})).status,403);
  assert.equal((await post('request',{name:''})).status,400);
  assert.equal((await post('request',{name:'Phone',unexpected:true})).status,400);
  assert.equal((await post('request',{name:'x'.repeat(2200)})).status,413);
  assert.equal((await post('poll')).status,410);
  assert.equal((await fetch(base+'/pairing/request')).status,405);
});
test('pairing request attempts are bounded per minute',async()=>{
  for(let i=0;i<5;i++)assert.equal((await post('request',{name:'Rate'},{'X-Real-IP':`192.0.2.${i+1}`})).status,200);
  assert.equal((await post('request',{name:'Rate'},{'X-Real-IP':'192.0.2.99'})).status,429);
});
test('logged-out viewer cannot look up or approve a phone',async()=>{
  const sid='55555555-5555-4555-8555-555555555555';await store.revokeViewer('owner',sid);
  assert.equal((await post('lookup',{code:'ABCDEFGH'},{...headers,'X-Viewer-Session':sid})).status,401);
});
test('logout wins when an approval passed its first session check but has not issued a device',async()=>{
  const sid='66666666-6666-4666-8666-666666666666',extra={...headers,'X-Viewer-Session':sid};
  const p=await (await post('request',{name:'Logout race'})).json();
  const v=await (await post('lookup',{code:p.code},extra)).json();
  let checked!:()=>void,release!:()=>void;
  const reached=new Promise<void>(resolve=>{checked=resolve;}),paused=new Promise<void>(resolve=>{release=resolve;});
  const original=store.checkViewer;store.checkViewer=async(owner,viewer)=>{await original.call(store,owner,viewer);checked();await paused;};
  try{
    const approval=post('approve',{code:p.code,request_id:v.request_id},extra);await reached;
    await store.revokeViewer('owner',sid);release();
    assert.equal((await approval).status,410);
    assert.equal((await (await post('poll',undefined,{Authorization:`Bearer ${p.poll_token}`})).json()).status,'pending');
  }finally{release();store.checkViewer=original;}
});
test('database failures cannot mint credentials or expose internal errors',async()=>{
  const original=store.db.query;store.db.query=async()=>{throw new Error('private database detail');};
  try{
    const response=await post('request',{name:'Database failure'});assert.equal(response.status,503);
    assert.deepEqual(await response.json(),{error:'unavailable'});
  }finally{store.db.query=original;}
});
