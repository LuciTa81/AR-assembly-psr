import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {mkdtemp,rmdir,readFile} from 'node:fs/promises';
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
test('authenticated phone state and AVC stream produce one private owner MP4 on observed stop',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();const d=await store.provision('101','Phone');
  const dir=await mkdtemp(join(tmpdir(),'ar-stream-')),records=new Recordings(store);let uploaded:Buffer|null=null;
  const files=new RecordingFiles(records,{put:async(key,path)=>{assert(key.startsWith(`recordings/101/${d.id}/`));uploaded=await readFile(path);},remove:async()=>{},download:async()=>''});
  const recorder=new Recorder(files,{directory:dir,fileBytes:2*1024*1024,ownerBytes:2*1024*1024,seconds:10,concurrent:1});await recorder.init();
  const relay=createRelay(store,{ownerId:'101',serviceKey:'a'.repeat(64),origins:['http://localhost:3000']},{files,recorder});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');const base=`ws://127.0.0.1:${(relay.server.address() as any).port}`;
  const clients:WebSocket[]=[];
  async function connect(path:string){const ws=new WebSocket(base+path);clients.push(ws);await once(ws,'open');const ready=once(ws,'message');ws.send(JSON.stringify({role:'publisher',token:d.token}));assert.equal(JSON.parse((await ready)[0].toString()).recording_enabled,true);return ws;}
  async function until(fn:()=>Promise<boolean>){for(let i=0;i<100;i++){if(await fn())return;await new Promise(r=>setTimeout(r,20));}assert.fail('timed out');}
  try{
    const state=await connect('/ws'),video=await connect('/video'),p=publish();p.state.video_available=true;p.state.recording_consent=true;
    state.send(JSON.stringify(p));await until(async()=>(await store.history('101',d.id)).length>0);
    for(const packet of await syntheticPackets()){
      const bytes=Buffer.alloc(21+packet.data.length);bytes.write('ARV2');bytes[4]=1;bytes.writeUInt32BE(packet.sequence,5);bytes.writeBigUInt64BE(BigInt(packet.timestamp),9);bytes.writeUInt16BE(1280,17);bytes.writeUInt16BE(720,19);bytes.set(packet.data,21);video.send(bytes);
    }
    await until(async()=>recorder.status(d.id)==='capturing');
    state.send(JSON.stringify({...p,seq:2,state:{...p.state,running:false,stage:-1,phase:'PREPARATION',video_available:false}}));
    await until(async()=>(await records.list('101',d.id))[0]?.status==='ready');
    const rows=await records.list('101',d.id);assert.equal(rows.length,1);assert.equal(rows[0].reason,'stopped');assert(Number(rows[0].duration_ms)>60);assert(uploaded);assert(Buffer.from(uploaded).includes(Buffer.from('ftyp')));
    await assert.rejects(()=>records.downloadable('202',rows[0].id));
  }finally{for(const ws of clients)ws.terminate();await relay.close();await db.close();await rmdir(dir);}
});
