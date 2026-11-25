import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {WebSocket} from 'ws';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
import {validJpeg,MAX_VIDEO_BYTES} from '../shared/video.ts';
import {publish} from './fixture.ts';
import {avc} from './avc-fixture.ts';
// Minimal structural fixture; decoder/display verification uses a separately generated real JPEG.
const jpeg=Buffer.from([255,216,255,192,0,11,8,0,180,1,64,1,1,17,0,255,218,0,8,1,1,0,0,63,0,0,255,217]);
test('JPEG protocol bounds dimensions, marker lengths and payload',()=>{
 assert(validJpeg(jpeg));assert(!validJpeg(Buffer.alloc(MAX_VIDEO_BYTES+1)));
 const large=Buffer.from(jpeg);large[9]=10;assert(!validJpeg(large));
 const broken=Buffer.from(jpeg);broken[5]=255;assert(!validJpeg(broken));
 const progressive=Buffer.from(jpeg);progressive[3]=194;assert(!validJpeg(progressive));
 const duplicate=Buffer.concat([jpeg.subarray(0,15),jpeg.subarray(2)]);assert(!validJpeg(duplicate));
 assert(!validJpeg(jpeg.subarray(0,jpeg.length-1)));assert(!validJpeg(Buffer.from('not JPEG')));
});
let db:PGlite,store:Store,relay:ReturnType<typeof createRelay>,base:string,clock=0;
const origin='http://localhost:3000',owner='owner',key='a'.repeat(64);
before(async()=>{db=new PGlite();store=new Store(db);await store.init();relay=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin],monotonic:()=>clock});relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');base=`ws://127.0.0.1:${(relay.server.address() as any).port}`;});
after(async()=>{await relay.close();await db.close();});
async function until(check:()=>boolean){for(let n=0;n<100;n++){if(check())return;await delay(20);}assert.fail('Timeout');}
async function connect(path:string,role:string,token:string){
 const ws=new WebSocket(base+path,role==='observer'?{origin}:{}),messages:any[]=[],frames:Buffer[]=[];
 ws.on('message',(data,binary)=>{if(binary)frames.push(Buffer.from(data as Buffer));else messages.push(JSON.parse(data.toString()));});
 await once(ws,'open');ws.send(JSON.stringify({role,token}));return {ws,messages,frames};
}
test('separate video channel authenticates, isolates devices, clears on stop, never stores images',async()=>{
 const d=await store.provision(owner,'video'),other=await store.provision(owner,'other');
 const state=await connect('/ws','publisher',d.token),video=await connect('/video','publisher',d.token);
 const viewer=await connect('/video','observer',await store.ticket(owner,d.id));
 const stranger=await connect('/video','observer',await store.ticket(owner,other.id));
 await until(()=>[state,video,viewer,stranger].every(c=>c.messages.some(m=>m.type==='ready')));
 const p=publish();p.state.video_available=true;state.ws.send(JSON.stringify(p));await delay(100);
 video.ws.send(jpeg);await until(()=>viewer.frames.length===1);assert.deepEqual(viewer.frames[0],jpeg);assert.equal(stranger.frames.length,0);
 assert.equal(state.ws.readyState,WebSocket.OPEN);
 const stop=publish(2);stop.state.running=false;stop.state.stage=-1;stop.state.phase='PREPARATION';stop.state.tracked=false;stop.state.overlay_visible=false;
 state.ws.send(JSON.stringify(stop));await until(()=>viewer.messages.some(m=>m.type==='video-status'&&m.status==='paused'));
 video.ws.send(jpeg);await delay(80);assert.equal(viewer.frames.length,1);
 const events=await store.history(owner,d.id);assert(events.every(e=>!JSON.stringify(e).includes('image/jpeg')));
 for(const c of [state,video,viewer,stranger])c.ws.close();
});
test('unauthenticated and observer media sends are rejected',async()=>{
 const bad=await connect('/video','publisher','x'.repeat(64));assert.equal((await once(bad.ws,'close'))[0],4401);
 const d=await store.provision(owner,'read only'),viewer=await connect('/video','observer',await store.ticket(owner,d.id));
 await until(()=>viewer.messages.some(m=>m.type==='ready'));viewer.ws.send(jpeg);assert.equal((await once(viewer.ws,'close'))[0],4403);
});
test('media stale timeout clears viewers without killing state channel',async()=>{
 const d=await store.provision(owner,'stale'),state=await connect('/ws','publisher',d.token),video=await connect('/video','publisher',d.token),viewer=await connect('/video','observer',await store.ticket(owner,d.id));
 await until(()=>[state,video,viewer].every(c=>c.messages.some(m=>m.type==='ready')));
 const p=publish();p.state.video_available=true;state.ws.send(JSON.stringify(p));await delay(80);video.ws.send(jpeg);await until(()=>viewer.frames.length===1);
 clock+=3001;await until(()=>viewer.messages.some(m=>m.type==='video-status'&&m.status==='paused'));
 assert.equal(state.ws.readyState,WebSocket.OPEN);state.ws.close();video.ws.close();viewer.ws.close();
});

test('video is denied without consent and device revocation closes all channels',async()=>{
 const d=await store.provision(owner,'consent'),state=await connect('/ws','publisher',d.token),video=await connect('/video','publisher',d.token),viewer=await connect('/video','observer',await store.ticket(owner,d.id));
 await until(()=>[state,video,viewer].every(c=>c.messages.some(m=>m.type==='ready')));
 state.ws.send(JSON.stringify(publish()));await delay(80);video.ws.send(jpeg);await delay(100);assert.equal(viewer.frames.length,0);
 const closures=[state,video,viewer].map(c=>once(c.ws,'close'));
 const response=await fetch(base.replace('ws:','http:')+`/devices/${d.id}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}});
 assert.equal(response.status,200);for(const closed of closures)assert.equal((await closed)[0],4401);
});

test('viewer logout closes media but leaves publisher and state independent',async()=>{
 const d=await store.provision(owner,'logout'),sid='12345678-1234-1234-1234-123456789012';
 const video=await connect('/video','publisher',d.token),viewer=await connect('/video','observer',await store.ticket(owner,d.id,Date.now(),sid));
 await until(()=>[video,viewer].every(c=>c.messages.some(m=>m.type==='ready')));
 const closed=once(viewer.ws,'close');
 const response=await fetch(base.replace('ws:','http:')+`/viewers/${sid}/revoke`,{method:'POST',headers:{Authorization:`Bearer ${key}`}});
 assert.equal(response.status,200);assert.equal((await closed)[0],4401);assert.equal(video.ws.readyState,WebSocket.OPEN);video.ws.close();
});

test('30 AVC frames pass, while join and packet loss wait for the next key',async()=>{
 const d=await store.provision(owner,'avc30'),state=await connect('/ws','publisher',d.token),video=await connect('/video','publisher',d.token),viewer=await connect('/video','observer',await store.ticket(owner,d.id));
 await until(()=>[state,video,viewer].every(c=>c.messages.some(m=>m.type==='ready')));
 const p=publish();p.state.video_available=true;state.ws.send(JSON.stringify(p));await delay(80);
 video.ws.send(avc(1,false));await delay(50);assert.equal(viewer.frames.length,0);
 for(let n=2;n<=31;n++){video.ws.send(avc(n,n===2));await delay(2);}
 await until(()=>viewer.frames.length===30);assert.equal(video.ws.readyState,WebSocket.OPEN);
 video.ws.send(avc(33,false));await delay(50);assert.equal(viewer.frames.length,30);
 video.ws.send(avc(34,true));await until(()=>viewer.frames.length===31);
 for(const c of [state,video,viewer])c.ws.close();
});
