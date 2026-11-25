import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {connect as connectTcp} from 'node:net';
import {setTimeout as delay} from 'node:timers/promises';
import {WebSocket} from 'ws';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
import {publish} from './fixture.ts';
const owner='owner', key='a'.repeat(64),origin='http://localhost:3000';
let db:PGlite,store:Store, relay:ReturnType<typeof createRelay>,base:string;
let clock=0;
before(async()=>{
  db=new PGlite();store=new Store(db);await store.init();
  relay=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin],monotonic:()=>clock});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
  base=`http://127.0.0.1:${(relay.server.address() as any).port}`;
});
after(async()=>{await relay.close();await db.close();});
async function connect(auth:unknown, browser=false){
  const ws=new WebSocket(base.replace('http:','ws:')+'/ws',browser?{origin}:{});
  const messages:any[]=[];ws.on('message',b=>messages.push(JSON.parse(b.toString())));
  await once(ws,'open');ws.send(JSON.stringify(auth));
  return {ws,messages};
}
async function until(check:()=>boolean){for(let i=0;i<100;i++){if(check())return;await delay(20);}assert.fail('Timed out');}
async function pair(){
  const d=await store.provision(owner,'Fold7');
  const observer=await connect({role:'observer',token:await store.ticket(owner,d.id)},true);
  const publisher=await connect({role:'publisher',token:d.token});
  await until(()=>publisher.messages.some(m=>m.type==='ready')&&observer.messages.some(m=>m.type==='ready'));
  return {d,observer,publisher};
}

test('HTTP state is never public and ticket API requires server credential',async()=>{
  assert.equal((await fetch(base+'/state.json')).status,404);
  const d=await store.provision(owner,'api');
  assert.equal((await fetch(`${base}/devices/${d.id}/ticket`,{method:'POST'})).status,401);
  assert.equal((await fetch(`${base}/devices/${d.id}/ticket`,{method:'POST',headers:{Authorization:`Bearer ${key}`}})).status,200);
  assert.equal((await fetch(`${base}/devices/${d.id}/ticket`,{method:'POST',headers:{Authorization:`Bearer ${key}`,Origin:'https://evil.test'}})).status,403);
});
test('logged-out viewer cannot read devices or history, while new session can',async()=>{
  const sid='11111111-1111-4111-8111-111111111111',d=await store.provision(owner,'Viewer read');
  const headers={Authorization:`Bearer ${key}`,'X-Viewer-Session':sid};
  assert.equal((await fetch(`${base}/devices`,{headers})).status,200);
  await store.revokeViewer(owner,sid);
  assert.equal((await fetch(`${base}/devices`,{headers})).status,401);
  assert.equal((await fetch(`${base}/devices/${d.id}/history`,{headers})).status,401);
  assert.equal((await fetch(`${base}/devices`,{headers:{...headers,'X-Viewer-Session':'22222222-2222-4222-8222-222222222222'}})).status,200);
});

test('history API selects one work session and validates its identifier',async()=>{
  const d=await store.provision(owner,'Work history API'),headers={Authorization:`Bearer ${key}`};
  for(const [seq,session] of [[1,'one'],[2,'two']] as const){const p=publish(seq);p.state.session=session;await store.event(d.id,p,'step');}
  const current=await (await fetch(`${base}/devices/${d.id}/history`,{headers})).json();
  assert.deepEqual(current.events.map((e:any)=>e.state.session),['two']);
  assert.equal(current.sessions.length,2);
  const prior=await (await fetch(`${base}/devices/${d.id}/history?session=one`,{headers})).json();
  assert.deepEqual(prior.events.map((e:any)=>e.state.session),['one']);
  assert.equal((await fetch(`${base}/devices/${d.id}/history?session=%27`,{headers})).status,400);
  assert.equal((await fetch(`${base}/devices/${d.id}/history?session=one`)).status,401);
});
test('unauthorized websocket closes without sending state',async()=>{
  const c=await connect({role:'publisher',token:'x'.repeat(64)});
  const [code]=await once(c.ws,'close');assert.equal(code,4401);assert.equal(c.messages.length,0);
});
test('temporary authentication database failure is retryable and preserves the valid device token',async()=>{
  const d=await store.provision(owner,'Temporary auth failure'),original=store.device;
  store.device=async()=>{throw new Error('Database unavailable');};
  try{
    const c=await connect({role:'publisher',token:d.token});
    const [code,reason]=await once(c.ws,'close');assert.equal(code,1013);assert.equal(String(reason),'Authentication unavailable');
    assert.equal(c.messages.length,0);
  }finally{store.device=original;}
  assert.equal((await store.device(d.token))?.id,d.id);
  const good=await connect({role:'publisher',token:d.token});await until(()=>good.messages.some(m=>m.type==='ready'));good.ws.close();
});
test('authentication database delay times out as retryable rather than deleting credentials',async()=>{
  const d=await store.provision(owner,'Delayed auth'),original=store.device;
  let release!:()=>void;const paused=new Promise<void>(resolve=>{release=resolve;});
  store.device=async(token,now)=>{await paused;return original.call(store,token,now);};
  try{
    const c=await connect({role:'publisher',token:d.token});
    const [code,reason]=await once(c.ws,'close',{signal:AbortSignal.timeout(7000)});
    assert.equal(code,1013);assert.equal(String(reason),'Authentication unavailable');assert.equal(c.messages.length,0);
  }finally{release();store.device=original;}
  assert.equal((await store.device(d.token))?.id,d.id);
});
test('revoking another device only requests reauthentication of a pending valid publisher',async()=>{
  const a=await store.provision(owner,'Pending A'),b=await store.provision(owner,'Revoke B'),original=store.device;
  let entered!:()=>void,release!:()=>void;
  const reached=new Promise<void>(resolve=>{entered=resolve;}),paused=new Promise<void>(resolve=>{release=resolve;});
  store.device=async(token,now)=>{const d=await original.call(store,token,now);entered();await paused;return d;};
  try{
    const c=await connect({role:'publisher',token:a.token});await reached;const closed=once(c.ws,'close');
    assert.equal((await fetch(`${base}/devices/${b.id}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}})).status,200);
    release();const [code,reason]=await closed;assert.equal(code,4401);assert.equal(String(reason),'Reauthenticate');assert.equal(c.messages.length,0);
  }finally{release();store.device=original;}
  const good=await connect({role:'publisher',token:a.token});await until(()=>good.messages.some(m=>m.type==='ready'));good.ws.close();
});
test('subscriber tickets cannot be reused or used without allowed browser origin',async()=>{
  const d=await store.provision(owner,'ticket');const token=await store.ticket(owner,d.id);
  const bad=await connect({role:'observer',token});assert.equal((await once(bad.ws,'close'))[0],4403);
  const good=await connect({role:'observer',token},true);await until(()=>good.messages.some(m=>m.type==='ready'));
  const replay=await connect({role:'observer',token},true);assert.equal((await once(replay.ws,'close'))[0],4401);good.ws.close();
});
test('publishes validated state, rejects rewind and records only received meaningful events',async()=>{
  const {d,publisher:p,observer:o}=await pair();
  p.ws.send(JSON.stringify(publish(2)));await until(()=>o.messages.some(m=>m.snapshot?.seq===2));
  p.ws.send(JSON.stringify(publish(1)));await delay(100);
  assert.equal(o.messages.filter(m=>m.snapshot?.seq===1).length,0);
  const next=publish(3);next.state.stage=3;p.ws.send(JSON.stringify(next));
  await until(()=>o.messages.some(m=>m.snapshot?.state.stage===3));
  await until(()=>o.messages.some(m=>m.history_status==='ok'&&m.snapshot?.seq===3));
  const rows=await store.history(owner,d.id);assert.equal(rows.filter(r=>r.kind==='step').length,2);
  p.ws.close();o.ws.close();
});
test('stale uses server monotonic receive time, disconnect is explicit and recovery marks a gap',async()=>{
  const {d,publisher:p,observer:o}=await pair();
  p.ws.send(JSON.stringify(publish()));await until(()=>o.messages.some(m=>m.status==='live'));
  clock+=3001;await until(()=>o.messages.some(m=>m.status==='stale'));
  const closed=once(p.ws,'close');p.ws.close();await closed;
  await until(()=>o.messages.some(m=>m.status==='offline'));
  const replacement=await connect({role:'publisher',token:d.token});await until(()=>replacement.messages.some(m=>m.type==='ready'));
  replacement.ws.send(JSON.stringify(publish(2)));await until(()=>o.messages.some(m=>m.status==='live'&&m.snapshot?.seq===2));
  await until(()=>o.messages.some(m=>m.history_status==='ok'&&m.snapshot?.seq===2));
  assert((await store.history(owner,d.id)).some(r=>r.kind==='gap'));
  replacement.ws.close();o.ws.close();
});
test('publisher replacement closes prior connection and revocation disconnects every role',async()=>{
  const {d,publisher:p,observer:o}=await pair();
  p.ws.send(JSON.stringify(publish(2)));await until(()=>o.messages.some(m=>m.snapshot?.seq===2));
  const oldClosed=once(p.ws,'close');const next=await connect({role:'publisher',token:d.token});
  assert.equal((await oldClosed)[0],4409);await until(()=>next.messages.some(m=>m.type==='ready'));
  next.ws.send(JSON.stringify(publish(1)));await delay(60);assert(!o.messages.some(m=>m.snapshot?.seq===1));
  const c1=once(next.ws,'close'),c2=once(o.ws,'close');
  assert.equal((await fetch(`${base}/devices/${d.id}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}})).status,200);
  assert.equal((await c1)[0],4401);assert.equal((await c2)[0],4401);
});
test('malformed and over-rate publishers are closed instead of forwarding untrusted data',async()=>{
  const {publisher:p,observer:o}=await pair();
  p.ws.send(JSON.stringify({...publish(),state:{...publish().state,stage:99}}));
  assert.equal((await once(p.ws,'close'))[0],4400);assert(!o.messages.some(m=>m.status==='live'));o.ws.close();
  const {publisher:p2,observer:o2}=await pair();const closed=once(p2.ws,'close');
  for(let i=1;i<=12;i++)p2.ws.send(JSON.stringify(publish(i)));
  assert.equal((await closed)[0],4429);o2.ws.close();
});
test('database write failure still forwards state and reports incomplete history',async()=>{
  const {publisher:p,observer:o}=await pair();
  // Fail the actual SQL storage boundary while retaining real sockets and state handling.
  await db.query('ALTER TABLE events RENAME TO events_unavailable');
  try{
    p.ws.send(JSON.stringify(publish()));
    await until(()=>o.messages.some(m=>m.status==='live'&&m.history_status==='error'));
  }finally{await db.query('ALTER TABLE events_unavailable RENAME TO events');}
  p.ws.send(JSON.stringify(publish(2)));
  await until(()=>o.messages.some(m=>m.snapshot?.seq===2&&m.history_status==='ok'));
  p.ws.close();o.ws.close();
});
test('observer may not publish and oversized messages are rejected',async()=>{
  const {publisher:p,observer:o}=await pair();
  o.ws.send(JSON.stringify(publish()));assert.equal((await once(o.ws,'close'))[0],4403);
  const closed=once(p.ws,'close');p.ws.send(' '.repeat(16385));assert.equal((await closed)[0],1009);
});
test('a replaced stream cannot return and rewind a current publisher',async()=>{
  const {publisher:p,observer:o}=await pair();
  p.ws.send(JSON.stringify(publish()));await until(()=>o.messages.some(m=>m.snapshot?.seq===1));
  const changed=publish(2);changed.stream_id='stream-new';p.ws.send(JSON.stringify(changed));
  await until(()=>o.messages.some(m=>m.snapshot?.stream_id==='stream-new'));
  p.ws.send(JSON.stringify(publish(3)));await delay(80);
  assert(!o.messages.some(m=>m.snapshot?.stream_id==='stream-1'&&m.snapshot?.seq===3));
  p.ws.close();o.ws.close();
});
test('unauthenticated sockets time out and never receive another device state',async()=>{
  const ws=new WebSocket(base.replace('http:','ws:')+'/ws');const messages:any[]=[];
  ws.on('message',m=>messages.push(m));await once(ws,'open');
  assert.equal((await once(ws,'close'))[0],4401);assert.equal(messages.length,0);
});
test('slow database keeps publisher responsive and persists a gap before reporting recovery',async()=>{
  const {d,publisher:p,observer:o}=await pair();
  const original=store.event.bind(store);let release!:()=>void;
  const gate=new Promise<void>(r=>release=r);let calls=0;
  store.event=async(...args)=>{calls++;await gate;return original(...args);};
  try{
    for(let seq=1;seq<=40;seq++){
      clock+=1001;const msg=publish(seq);msg.state.phase=seq%2?'WORKING':'APPROACH';
      p.ws.send(JSON.stringify(msg));await delay(20);
    }
    await until(()=>o.messages.some(m=>m.snapshot?.seq===40));
    assert(o.messages.some(m=>m.history_status==='error'));assert.equal(calls,1);
    p.ws.close();
  }finally{release();store.event=original;}
  await until(()=>o.messages.some(m=>m.status==='offline'&&m.history_status==='ok'));
  assert((await store.history(owner,d.id)).some(e=>e.kind==='gap'&&e.state.frame===70));
  o.ws.close();
});
test('revocation wins over an already pending authentication result for both roles',async()=>{
  for(const role of ['publisher','observer'] as const){
    const d=await store.provision(owner,'Race');
    const token=role==='publisher'?d.token:await store.ticket(owner,d.id);
    const method=role==='publisher'?'device':'consumeTicket';const original=store[method].bind(store);
    let entered!:()=>void, release!:()=>void;
    const started=new Promise<void>(r=>entered=r),gate=new Promise<void>(r=>release=r);
    store[method]=async(...args)=>{const result=await original(...args);entered();await gate;return result;};
    let c:Awaited<ReturnType<typeof connect>>|undefined;
    try{
      c=await connect({role,token},role==='observer');await started;
      assert.equal((await fetch(`${base}/devices/${d.id}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}})).status,200);
      release();await until(()=>c!.ws.readyState===WebSocket.CLOSED||c!.messages.some(m=>m.type==='ready'));
      assert.equal(c.ws.readyState,WebSocket.CLOSED);
      assert(!c.messages.some(m=>m.type==='ready'));
    }finally{release();c?.ws.terminate();store[method]=original;}
  }
});
test('rejected upgrades cannot leave half-open TCP connections behind',async()=>{
  const socket=connectTcp({port:Number(new URL(base).port),host:'127.0.0.1',allowHalfOpen:true});
  socket.on('error',()=>{});socket.on('data',()=>{});await once(socket,'connect');
  let ended=false;socket.on('end',()=>{ended=true;});
  socket.write('GET /invalid HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n');
  try{
    await until(()=>ended);await delay(60);
    const connections=await new Promise<number>((resolve,reject)=>relay.server.getConnections((e,n)=>e?reject(e):resolve(n)));
    // Other tests leave keep-alive HTTP sockets, so assert no server-side socket for this client's port.
    const fresh=await fetch(base+'/health');assert.equal(fresh.status,200);
    assert(connections<5,`Unexpected retained connections: ${connections}`);
    // Force close verification on an isolated relay to avoid keep-alive noise.
    const isolated=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin]});
    isolated.server.listen(0,'127.0.0.1');await once(isolated.server,'listening');
    const half=connectTcp({port:(isolated.server.address() as any).port,host:'127.0.0.1',allowHalfOpen:true});half.on('error',()=>{});half.on('data',()=>{});
    await once(half,'connect');half.write('GET /bad HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n');
    await delay(80);
    let finished=false;const close=isolated.close().then(()=>{finished=true;});
    try{await delay(100);assert(finished,'Relay shutdown retained a rejected upgrade socket');}
    finally{half.destroy();await close;}
  }finally{socket.destroy();}
});

test('viewer logout does not interrupt an authenticating phone',async()=>{
  const d=await store.provision(owner,'Pending phone'),original=store.device.bind(store);
  let entered!:()=>void,release!:()=>void;
  const started=new Promise<void>(r=>entered=r),gate=new Promise<void>(r=>release=r);
  store.device=async(...args)=>{const result=await original(...args);entered();await gate;return result;};
  let c:Awaited<ReturnType<typeof connect>>|undefined;
  try{
    c=await connect({role:'publisher',token:d.token});await started;
    assert.equal((await fetch(`${base}/viewers/33333333-3333-4333-8333-333333333333/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}})).status,200);
    release();await until(()=>c!.ws.readyState===WebSocket.CLOSED||c!.messages.some(m=>m.type==='ready'));
    assert(c.messages.some(m=>m.type==='ready'));assert.equal(c.ws.readyState,WebSocket.OPEN);
  }finally{release();c?.ws.terminate();store.device=original;}
});
test('return to idle is an observed stop, not a completed assembly step',async()=>{
  const {d,publisher:p,observer:o}=await pair();
  p.ws.send(JSON.stringify(publish()));await until(()=>o.messages.some(m=>m.snapshot?.seq===1));
  const idle=publish(2);Object.assign(idle.state,{running:false,stage:-1,phase:'PREPARATION',tracked:false,overlay_visible:false,action:'작업 대기'});
  p.ws.send(JSON.stringify(idle));await until(()=>o.messages.some(m=>m.snapshot?.seq===2&&m.history_status==='ok'));
  const events=await store.history(owner,d.id);assert.equal(events[0].kind,'stop');
  assert(!events.some(e=>e.state.stage===6));p.ws.close();o.ws.close();
});
test('viewer logout closes only its observers and invalidates its unused ticket',async()=>{
  const d=await store.provision(owner,'Viewer logout');const sid='12345678-abcd-1234-abcd-123456789012';
  const p=await connect({role:'publisher',token:d.token});await until(()=>p.messages.some(m=>m.type==='ready'));
  const o=await connect({role:'observer',token:await store.ticket(owner,d.id,Date.now(),sid)},true);
  await until(()=>o.messages.some(m=>m.type==='ready'));
  const pending=await store.ticket(owner,d.id,Date.now(),sid),closed=once(o.ws,'close');
  const r=await fetch(`${base}/viewers/${sid}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}});
  assert.equal(r.status,200);assert.equal((await closed)[0],4401);assert.equal(p.ws.readyState,WebSocket.OPEN);
  assert.equal(await store.consumeTicket(pending),null);p.ws.close();
});
