// Synthetic device, isolated viewer session. No real phone, camera or OAuth credentials are used.
import assert from 'node:assert/strict';
import {loadEnvFile} from 'node:process';
import {randomUUID} from 'node:crypto';
import {createRequire} from 'node:module';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {WebSocket} from 'ws';
import {publish} from '../tests/fixture.ts';
const require=createRequire(new URL('../web/package.json',import.meta.url)),{encode}=require('next-auth/jwt');
loadEnvFile(new URL('../web/.env.local',import.meta.url));
const web=new URL(process.env.NEXTAUTH_URL!),relay=new URL(process.env.RELAY_HTTP_URL!);
for(const url of [web,relay])assert(['localhost','127.0.0.1'].includes(url.hostname)&&url.protocol==='http:','Local checks only');
const token=await encode({secret:process.env.NEXTAUTH_SECRET,maxAge:600,token:{ownerId:process.env.OWNER_GITHUB_ID,viewerSession:randomUUID()}});
const cookie=`next-auth.session-token=${token}`;
async function bff(path:string,body?:unknown,method=body===undefined?'GET':'POST',origin=web.origin){
  return fetch(new URL('/api/observer/'+path,web),{method,headers:{Cookie:cookie,Origin:origin,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
}
async function phone(path:string,body?:unknown,secret?:string){
  return fetch(new URL('/pairing/'+path,relay),{method:'POST',headers:{'Content-Type':'application/json',...(secret?{Authorization:`Bearer ${secret}`}:{})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
}
let device='',publisher:WebSocket|undefined,observer:WebSocket|undefined;
try{
  const request=await phone('request',{name:'[합성 시험] 연결 검증'});assert.equal(request.status,200);const p=await request.json();
  assert.equal((await bff('pairing/lookup',{code:p.code},'POST','https://untrusted.invalid')).status,403);
  assert.equal((await bff('pairing/lookup',{code:'bad'})).status,400);
  const lookup=await bff('pairing/lookup',{code:p.code});assert.equal(lookup.status,200);const preview=await lookup.json();
  assert.equal(preview.name,'[합성 시험] 연결 검증');
  const approved=await bff('pairing/approve',{code:p.code,request_id:preview.request_id});assert.equal(approved.status,200);
  const safe=await approved.json();assert.deepEqual(Object.keys(safe).sort(),['device_id','name']);device=safe.device_id;
  const poll=await phone('poll',undefined,p.poll_token);assert.equal(poll.status,200);const credential=await poll.json();
  assert.equal(credential.device_id,device);
  const ticket=await bff(`devices/${device}/ticket`,undefined,'POST');assert.equal(ticket.status,200);const t=await ticket.json();
  async function connect(role:string,secret:string){
    const ws=new WebSocket(t.url,role==='observer'?{origin:web.origin}:{});await once(ws,'open',{signal:AbortSignal.timeout(5000)});
    const ready=once(ws,'message',{signal:AbortSignal.timeout(5000)});ws.send(JSON.stringify({role,token:secret}));
    assert.equal(JSON.parse(String((await ready)[0])).type,'ready');return ws;
  }
  observer=await connect('observer',t.ticket);publisher=await connect('publisher',credential.device_token);
  const seen=new Set<number>();observer.on('message',raw=>{const m=JSON.parse(raw.toString());if(m.status==='live')seen.add(m.snapshot.state.stage);});
  const stream='synthetic-'+randomUUID();
  for(let stage=0;stage<=6;stage++){
    const packet=publish(stage+1);packet.stream_id=stream;packet.state.session='synthetic-pairing';
    packet.state.stage=stage;packet.state.phase=stage<2?'PREPARATION':stage===6?'INSPECTION':'WORKING';
    packet.state.action='합성 연결 시험';publisher.send(JSON.stringify(packet));await delay(160);
  }
  assert.deepEqual([...seen],[0,1,2,3,4,5,6]);
  const history=await bff(`devices/${device}/history`);assert.equal(history.status,200);assert.equal((await history.json()).events.length,7);
  const closed=once(publisher,'close',{signal:AbortSignal.timeout(5000)});
  assert.equal((await bff(`devices/${device}/revoke`,undefined,'POST')).status,200);await closed;
  assert.equal((await phone('poll',undefined,p.poll_token)).status,410);
  console.log('PASS: local Next BFF code lookup/name confirmation/approval, phone-only credential, WebSocket seven-stage relay/history and revocation. Synthetic device only; revoked test entry retained.');
}finally{
  publisher?.terminate();observer?.terminate();
  if(device)await bff(`devices/${device}/revoke`,undefined,'POST').catch(()=>{});
  await bff('logout',undefined,'POST').catch(()=>{});
}
