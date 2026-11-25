import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {Pool} from 'pg';
import {WebSocket} from 'ws';
import {Store} from '../server/store.ts';

const pool=new Pool({connectionString:process.env.DATABASE_URL,max:2});
const store=new Store({async query<T>(sql:string,params?:unknown[]){return {rows:(await pool.query(sql,params)).rows as T[]};}});
const base='https://54.116.139.37',origin=process.env.WEB_ORIGIN!,owner=process.env.OWNER_GITHUB_ID!;
const sockets:WebSocket[]=[];
let device:string|undefined;
async function wait(check:()=>boolean){for(let i=0;i<100;i++){if(check())return;await delay(50);}throw new Error('WebSocket check timed out');}
async function connect(role:'publisher'|'observer',token:string){
  const ws=new WebSocket(base.replace('https:','wss:')+'/ws',role==='observer'?{origin}:{});sockets.push(ws);
  const messages:any[]=[];ws.on('message',b=>messages.push(JSON.parse(b.toString())));ws.on('error',()=>{});
  await Promise.race([once(ws,'open'),delay(8000).then(()=>{throw new Error('Connection timed out');})]);
  ws.send(JSON.stringify({role,token}));await wait(()=>messages.some(m=>m.type==='ready'));return {ws,messages};
}
try{
  assert.equal((await fetch(base+'/health')).status,200);
  assert.equal((await fetch(base+'/devices')).status,401);
  assert.equal((await fetch(base+'/__local/stop',{method:'POST'})).status,404);
  const d=await store.provision(owner,'Deployment smoke test');device=d.id;
  const observer=await connect('observer',await store.ticket(owner,d.id));
  const publisher=await connect('publisher',d.token);
  const stream=randomUUID();
  publisher.ws.send(JSON.stringify({protocol:1,stream_id:stream,seq:1,sent_at_ms:Date.now(),state:{
    schema:1,session:stream,updated_ms:0,elapsed_ms:0,running:false,stage:-1,phase:'PREPARATION',
    action:'Deployment smoke test',tracked:false,overlay_visible:false,markers:0,rms_px:null,
    pose_age_ms:-1,frame:0,message:'Synthetic idle state; no camera',remaining_ms:0,
    video_available:false,recording:false,fastening_verified:false,
  }}));
  await wait(()=>observer.messages.some(m=>m.status==='live'&&m.snapshot?.stream_id===stream&&m.history_status==='ok'));
  assert.equal((await store.history(owner,d.id)).length,1);
  if(process.env.RELIABILITY_SOAK==='1'){
    let pings=0;observer.ws.on('ping',()=>pings++);
    for(let seq=2;seq<=46;seq++){
      await delay(1000);
      publisher.ws.send(JSON.stringify({
        ...observer.messages.find(m=>m.snapshot?.stream_id===stream).snapshot,
        seq,sent_at_ms:Date.now(),
      }));
      await wait(()=>observer.messages.some(m=>m.snapshot?.seq===seq));
    }
    assert(pings>=2,'Expected two verified heartbeat cycles');
    assert.equal(observer.ws.readyState,WebSocket.OPEN);
    assert.equal((await store.history(owner,d.id)).length,1);
    console.log('PASS: 45-second TLS/WSS soak, two heartbeat cycles, ordered state, no duplicate step events');
  }
  const r=await fetch(`${base}/devices/${d.id}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${process.env.SERVICE_KEY}`}});
  assert.equal(r.status,200);
  await wait(()=>sockets.every(ws=>ws.readyState===WebSocket.CLOSED));
  assert.equal(await store.device(d.token),null);
  console.log('PASS: verified TLS, HTTP authorization, WSS publish/observe, PostgreSQL history, revocation, local-stop blocked');
}finally{
  for(const ws of sockets)ws.terminate();
  if(device){
    // Remove only the synthetic device created by this invocation, never user data.
    await pool.query('DELETE FROM tickets WHERE device_id=$1',[device]);
    await pool.query('DELETE FROM events WHERE device_id=$1',[device]);
    await pool.query("DELETE FROM devices WHERE id=$1 AND name='Deployment smoke test'",[device]);
  }
  await pool.end();
}
