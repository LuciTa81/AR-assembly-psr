import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {Pool} from 'pg';
import {WebSocket} from 'ws';
import {Store} from '../server/store.ts';
import {parseAvc} from '../shared/avc.ts';

const pool=new Pool({connectionString:process.env.DATABASE_URL,max:2});
const store=new Store({async query<T>(sql:string,params?:unknown[]){return {rows:(await pool.query(sql,params)).rows as T[]};}});
const base='https://54.116.139.37',origin=process.env.WEB_ORIGIN!,owner=process.env.OWNER_GITHUB_ID!;
const sockets:WebSocket[]=[];let device:string|undefined,ticker:ReturnType<typeof setInterval>|undefined;
async function wait(check:()=>boolean){for(let i=0;i<100;i++){if(check())return;await delay(50);}throw new Error('Video smoke timeout');}
async function connect(path:string,role:'publisher'|'observer',token:string){
  const ws=new WebSocket(base.replace('https:','wss:')+path,role==='observer'?{origin}:{});sockets.push(ws);
  const control:any[]=[],frames:Buffer[]=[];
  ws.on('message',(bytes,binary)=>binary?frames.push(Buffer.from(bytes as Buffer)):control.push(JSON.parse(bytes.toString())));
  ws.on('error',()=>{});
  await Promise.race([once(ws,'open'),delay(8000).then(()=>{throw new Error('Connection timed out');})]);
  ws.send(JSON.stringify({role,token}));await wait(()=>control.some(m=>m.type==='ready'));return {ws,control,frames};
}
try{
  assert.equal((await fetch(base+'/health')).status,200);
  assert.equal((await fetch(base+'/devices')).status,401);
  const d=await store.provision(owner,'Video deployment smoke');device=d.id;
  const state=await connect('/ws','publisher',d.token),observer=await connect('/ws','observer',await store.ticket(owner,d.id));
  const video=await connect('/video','publisher',d.token),viewer=await connect('/video','observer',await store.ticket(owner,d.id));
  const stream=randomUUID();let seq=0;
  function publish(sharing:boolean){state.ws.send(JSON.stringify({protocol:1,stream_id:stream,seq:++seq,sent_at_ms:Date.now(),state:{
    schema:1,session:stream,updated_ms:0,elapsed_ms:0,running:true,stage:2,phase:'WORKING',action:'Synthetic video smoke',
    tracked:true,overlay_visible:true,markers:5,rms_px:2,pose_age_ms:0,frame:seq,message:'Synthetic; no camera',remaining_ms:0,
    video_available:sharing,recording:false,fastening_verified:false,
  }}));}
  publish(true);ticker=setInterval(()=>publish(true),500);
  await wait(()=>observer.control.some(m=>m.status==='live'));
  // Structural Annex B fixture: validates transport, not decoding or real camera fps.
  for(let n=1;n<=30;n++){
    const header=Buffer.alloc(21);header.write('ARV2');header[4]=n===1?1:0;header.writeUInt32BE(n,5);header.writeBigUInt64BE(BigInt(n*33333),9);header.writeUInt16BE(1280,17);header.writeUInt16BE(720,19);
    const payload=Buffer.from(n===1?[0,0,0,1,0x67,1,0,0,0,1,0x68,1,0,0,0,1,0x65,1]:[0,0,0,1,0x41,1]);
    video.ws.send(Buffer.concat([header,payload]));await delay(34);
  }
  await wait(()=>viewer.frames.length===30);
  assert(viewer.frames.every((bytes,index)=>parseAvc(bytes)?.sequence===index+1));
  clearInterval(ticker);publish(false);
  await wait(()=>viewer.control.some(m=>m.type==='video-status'&&m.status==='paused'));
  assert.equal(state.ws.readyState,WebSocket.OPEN);
  const response=await fetch(`${base}/devices/${d.id}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${process.env.SERVICE_KEY}`}});
  assert.equal(response.status,200);await wait(()=>sockets.every(ws=>ws.readyState===WebSocket.CLOSED));
  console.log('PASS TLS/WSS video: 30 ordered synthetic packets, state isolation, consent stop, revocation; no camera');
}finally{
  clearInterval(ticker);for(const ws of sockets)ws.terminate();
  if(device){
    await pool.query('DELETE FROM tickets WHERE device_id=$1',[device]);
    await pool.query('DELETE FROM events WHERE device_id=$1',[device]);
    await pool.query("DELETE FROM devices WHERE id=$1 AND name='Video deployment smoke'",[device]);
  }
  await pool.end();
}
