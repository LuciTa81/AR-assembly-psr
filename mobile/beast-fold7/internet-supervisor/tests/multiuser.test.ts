import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {PGlite} from '@electric-sql/pglite';
import {Store,AccessError} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
const key='d'.repeat(64),origin='http://localhost:3000';
let db:PGlite,store:Store,relay:ReturnType<typeof createRelay>,base:string;
const sessions=new Map<string,string>();
function headers(owner?:string){
  if(owner&&!sessions.has(owner))sessions.set(owner,randomUUID());
  return {Authorization:`Bearer ${key}`,...(owner?{'X-Owner-Id':owner,'X-Viewer-Session':sessions.get(owner)!}:{})};
}
before(async()=>{
  db=new PGlite();store=new Store(db);await store.init();
  relay=createRelay(store,{ownerId:'101',serviceKey:key,origins:[origin],multiUser:true});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
  base=`http://127.0.0.1:${(relay.server.address() as any).port}`;
});
after(async()=>{await relay.close();await db.close();});
test('multi-user API requires a trusted owner and session, not the legacy fallback',async()=>{
  for(const owner of [undefined,'name','0','-1','123,456'])assert.equal((await fetch(base+'/devices',{headers:headers(owner)})).status,401);
  assert.equal((await fetch(base+'/devices',{headers:{Authorization:`Bearer ${key}`,'X-Owner-Id':'202'}})).status,401);
});
test('each owner lists only their devices and cannot ticket, read or revoke another device',async()=>{
  const a=await store.provision('101','A'),b=await store.provision('202','B');
  const response=await fetch(base+'/devices',{headers:headers('202')});
  assert.equal(response.status,200);assert.deepEqual((await response.json()).devices.map((d:any)=>d.id),[b.id]);
  for(const action of ['history','ticket','revoke']){
    assert.equal((await fetch(`${base}/devices/${a.id}/${action}`,{method:action==='history'?'GET':'POST',headers:headers('202')})).status,404);
  }
  assert.equal((await fetch(`${base}/devices/${b.id}/ticket`,{method:'POST',headers:headers('202')})).status,200);
});
test('public pairing assigns the approving owner rather than the server owner',async()=>{
  const post=(path:string,body:unknown,h:Record<string,string>={})=>fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json',...h},body:JSON.stringify(body)});
  const request=await (await post('/pairing/request',{name:'Second phone'})).json();
  const lookup=await (await post('/pairing/lookup',{code:request.code},headers('303'))).json();
  const approved=await post('/pairing/approve',{code:request.code,request_id:lookup.request_id},headers('303'));
  assert.equal(approved.status,200);
  assert.equal((await store.listDevices('303')).length,1);
});
test('one owner cannot revoke or reuse another owner viewer session',async()=>{
  const sid=randomUUID();await store.checkViewer('101',sid);
  await assert.rejects(()=>store.revokeViewer('202',sid),AccessError);
  await store.checkViewer('101',sid);
  assert.equal((await fetch(base+'/devices',{headers:{...headers('202'),'X-Viewer-Session':sid}})).status,401);
  assert.equal((await fetch(`${base}/viewers/${sid}/revoke`,{method:'POST',headers:headers('202')})).status,404);
});
test('a valid second-owner publisher and its observer can authenticate on both channels',async()=>{
  const d=await store.provision('404','Second owner');
  for(const channel of ['/ws','/video'])for(const role of ['publisher','observer'] as const){
    const token=role==='publisher'?d.token:await store.ticket('404',d.id);
    const ws=new WebSocket(base.replace('http:','ws:')+channel,role==='observer'?{origin}:{});
    const first=Promise.race([once(ws,'message').then(([b])=>JSON.parse(b.toString())),once(ws,'close').then(([code])=>({closed:code}))]);
    try{await once(ws,'open');ws.send(JSON.stringify({role,token}));assert.equal((await first).type,'ready');}
    finally{ws.terminate();}
  }
});
