import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {mkdtemp,rmdir} from 'node:fs/promises';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {WebSocket} from 'ws';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {Recordings} from '../server/recordings.ts';
import {RecordingFiles} from '../server/recording-files.ts';
import {Recorder} from '../server/recorder.ts';
import {createRelay} from '../server/relay.ts';
import {publish} from './fixture.ts';
import {syntheticPackets} from './synthetic-packets.ts';

for(const interruption of ['state_stale','disconnected'])test(`${interruption} resumes as a new keyframe segment after fresh consented state`,async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const d=await store.provision('101','Synthetic stale check'),dir=await mkdtemp(join(tmpdir(),'ar-stale-'));
  const records=new Recordings(store);let uploads=0,clock=0;
  const files=new RecordingFiles(records,{put:async()=>{uploads++;},remove:async()=>{},download:async()=>''});
  const recorder=new Recorder(files,{directory:dir,fileBytes:4194304,ownerBytes:4194304,seconds:30,concurrent:1});
  await recorder.init();
  const relay=createRelay(store,{ownerId:'101',serviceKey:'a'.repeat(64),origins:['http://localhost:3000'],monotonic:()=>clock},{files,recorder});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
  const base=`ws://127.0.0.1:${(relay.server.address() as any).port}`,clients:WebSocket[]=[];
  async function until(check:()=>Promise<boolean>){for(let i=0;i<100;i++){if(await check())return;await new Promise(r=>setTimeout(r,20));}assert.fail('timed out');}
  async function connect(path:string){const ws=new WebSocket(base+path);clients.push(ws);await once(ws,'open');const ready=once(ws,'message');ws.send(JSON.stringify({role:'publisher',token:d.token}));await ready;return ws;}
  try{
    let state=await connect('/ws');const video=await connect('/video'),p=publish();p.state.video_available=true;p.state.recording_consent=true;
    state.send(JSON.stringify(p));await until(async()=>(await store.history('101',d.id)).length>0);
    const packets=await syntheticPackets(true);
    function sendFrame(seq:number,timestamp:number,key=true){
      const packet=packets[key?0:1];
      const bytes=Buffer.alloc(21+packet.data.length);bytes.write('ARV2');bytes[4]=key?1:0;bytes.writeUInt32BE(seq,5);
      bytes.writeBigUInt64BE(BigInt(timestamp),9);bytes.writeUInt16BE(1280,17);bytes.writeUInt16BE(720,19);bytes.set(packet.data,21);video.send(bytes);
    }
    sendFrame(1,1000000);await until(async()=>recorder.status(d.id)==='capturing');
    if(interruption==='state_stale')clock=3101;else state.terminate();
    await until(async()=>(await records.list('101',d.id))[0]?.status==='ready');
    assert.equal((await records.list('101',d.id))[0].reason,interruption);assert.equal(uploads,1);
    sendFrame(2,1033333);await new Promise(r=>setTimeout(r,100));
    assert.equal((await records.list('101',d.id)).length,1);
    if(interruption==='disconnected')state=await connect('/ws');
    state.send(JSON.stringify({...p,seq:2}));
    await until(async()=>(await store.history('101',d.id)).some(e=>e.kind==='gap'));
    sendFrame(3,1066666,false);await new Promise(r=>setTimeout(r,100));
    assert.equal((await records.list('101',d.id)).length,1);
    sendFrame(4,1100000);await until(async()=>recorder.status(d.id)==='capturing');
    assert.equal(state.readyState,WebSocket.OPEN);assert.equal(video.readyState,WebSocket.OPEN);
    const rows=await records.list('101',d.id);assert.equal(rows.length,2);assert.equal(rows[0].segment,2);
    assert(Number(rows[0].gap_before_ms)>0);
    state.send(JSON.stringify({...p,seq:3,state:{...p.state,running:false,stage:-1,phase:'PREPARATION',recording_consent:false,video_available:false}}));
    await until(async()=>(await records.list('101',d.id)).every(r=>r.status==='ready'));
    assert.equal(uploads,2);
  }finally{for(const ws of clients)ws.terminate();await relay.close();await db.close();await rmdir(dir);}
});
