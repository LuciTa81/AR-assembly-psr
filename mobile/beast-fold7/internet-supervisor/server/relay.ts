import {createServer} from 'node:http';
import {createHash,timingSafeEqual} from 'node:crypto';
import type {Socket} from 'node:net';
import {WebSocket,WebSocketServer} from 'ws';
import {z} from 'zod';
import {AccessError, type Store, type Device} from './store.ts';
import {MAX_BYTES,parsePublish,type Publish} from '../shared/protocol.ts';
import {pairingHandler} from './pairing-http.ts';
import {clientIP} from './client-ip.ts';
import {MAX_VIDEO_BYTES,VIDEO_STALE_MS,validJpeg} from '../shared/video.ts';
import {MAX_AVC_BYTES,parseAvc} from '../shared/avc.ts';
import {requestOwner} from './owner.ts';
import type {Recorder} from './recorder.ts';
import type {RecordingFiles} from './recording-files.ts';

export interface RelayConfig {ownerId:string;serviceKey:string;origins:string[];multiUser?:boolean;monotonic?:()=>number;trustedProxy?:'127.0.0.1';}
type Auth = {role:'publisher'|'observer';device:Device;video:boolean};
type Entry = {
  id:string;recordingStatus:string;
  publisher?:WebSocket; observers:Set<WebSocket>; snapshot?:Publish;
  received:number; receivedWall:number; status:'waiting'|'live'|'stale'|'offline';gap:boolean;
  history:'ok'|'pending'|'error'; writes:number; chain:Promise<void>;retired:Set<string>;
  lossVersion:number;savedLossVersion:number;
  videoPublisher?:WebSocket;videoObservers:Set<WebSocket>;videoAt:number|null;
  videoSequence:number;
};
const authSchema=z.strictObject({role:z.enum(['publisher','observer']),token:z.string().regex(/^[a-zA-Z0-9_-]{32,128}$/)});
const digest=(s:string)=>createHash('sha256').update(s).digest();
export function createRelay(store:Store,config:RelayConfig,recording?:{files:RecordingFiles;recorder?:Recorder}){
  if(config.serviceKey.length<32||!config.ownerId||!config.origins.length)throw new Error('Invalid relay configuration');
  const clock=config.monotonic??(()=>performance.now());
  const handlePairing=pairingHandler(store,config.serviceKey,config.ownerId,clock,config.multiUser);
  const entries=new Map<string,Entry>(), identities=new Map<WebSocket,Auth>();
  const heartbeats=new Map<WebSocket,{due:number;awaiting:boolean}>();
  const needsKey=new WeakSet<WebSocket>();
  const apiBuckets=new Map<string,{at:number;count:number}>();
  let closing=false,authGeneration=0,viewerGeneration=0;
  const sockets=new Set<Socket>();
  const entry=(id:string)=>{
    let e=entries.get(id);
    if(!e){
      if(entries.size>=64)throw new Error('Device limit');
      e={id,recordingStatus:'off',observers:new Set(),received:0,receivedWall:0,status:'waiting',gap:false,history:'ok',writes:0,chain:Promise.resolve(),retired:new Set(),lossVersion:0,savedLossVersion:0,videoObservers:new Set(),videoAt:null,videoSequence:0};entries.set(id,e);
    }
    return e;
  };
  function send(ws:WebSocket,data:unknown){
    if(ws.readyState!==WebSocket.OPEN)return;
    if(ws.bufferedAmount>65536){ws.close(4429,'Slow receiver');return;}
    ws.send(JSON.stringify(data));
  }
  function broadcast(e:Entry,only?:WebSocket){
    e.recordingStatus=recording?.recorder?.status(e.id)??'off';
    const data={type:'state',status:e.status,snapshot:e.snapshot??null,received_at_ms:e.receivedWall||null,history_status:e.history,recording_status:e.recordingStatus,recording_enabled:!!recording?.recorder};
    for(const ws of only?[only]:e.observers)send(ws,data);
  }
  function clearVideo(e:Entry){
    e.videoAt=null;
    for(const ws of e.videoObservers){needsKey.add(ws);send(ws,{type:'video-status',status:'paused'});}
  }
  function append(e:Entry,id:string,p:Publish,kind:string,repair=false){
    if(e.writes>=32){e.lossVersion++;e.history='error';e.gap=true;return;}
    e.writes++;e.history=e.lossVersion>e.savedLossVersion?'error':'pending';
    const received=Date.now(),lossVersion=e.lossVersion;
    e.chain=e.chain.then(()=>store.event(id,p,kind,received)).then(()=>{
      if(kind==='gap')e.savedLossVersion=Math.max(e.savedLossVersion,lossVersion);
    }).catch(()=>{if(!repair)e.lossVersion++;e.gap=true;}).finally(()=>{
      e.writes--;
      e.history=e.lossVersion>e.savedLossVersion?'error':e.writes?'pending':'ok';
      broadcast(e);
      // One repair attempt when a batch drains, including after the phone disconnects.
      // Failure stays visible; a future received snapshot can trigger another attempt.
      if(!e.writes&&e.lossVersion>e.savedLossVersion&&!repair)append(e,id,e.snapshot??p,'gap',true);
    });
  }
  const server=createServer(async(req,res)=>{
    res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
    const reply=(status:number,body:unknown)=>{res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(body));};
    const ip=clientIP(req,config.trustedProxy);
    if(ip===null){reply(403,{error:'invalid_proxy'});return;}
    if(req.url==='/health'&&req.method==='GET'){reply(200,{ok:true});return;}
    if(await handlePairing(req,res,ip))return;
    const requestUrl=new URL(req.url??'/', 'http://localhost');
    const match=/^\/devices\/([a-f0-9-]{36})\/(ticket|history|revoke|recordings)$/.exec(requestUrl.pathname);
    const file=/^\/recordings\/([a-f0-9-]{36})\/(download|delete)$/.exec(req.url??'');
    const viewer=/^\/viewers\/([a-f0-9-]{36})\/revoke$/.exec(req.url??'');
    const list=req.url==='/devices';
    if(!match&&!viewer&&!list&&!file){reply(404,{error:'not_found'});return;}
    if(req.headers.origin){reply(403,{error:'server_only'});return;}
    let bucket=apiBuckets.get(ip);
    if(!bucket||clock()-bucket.at>=60000){bucket={at:clock(),count:0};apiBuckets.set(ip,bucket);}
    if(++bucket.count>120){reply(429,{error:'rate_limited'});return;}
    if(!timingSafeEqual(digest(req.headers.authorization??''),digest(`Bearer ${config.serviceKey}`))){reply(401,{error:'unauthorized'});return;}
    const owner=requestOwner(req.headers,config.ownerId,config.multiUser);
    if(!owner||(config.multiUser&&typeof req.headers['x-viewer-session']!=='string')){reply(401,{error:'unauthorized'});return;}
    const [,id,action]=match??file??['',viewer?.[1]??'',list?'history':'revoke'];
    if(req.method!==(['history','recordings'].includes(action)?'GET':'POST')){reply(405,{error:'method_not_allowed'});return;}
    try{
      const sid=req.headers['x-viewer-session'];
      if(sid!==undefined&&(typeof sid!=='string'||! /^[a-f0-9-]{36}$/.test(sid))){reply(400,{error:'invalid_session'});return;}
      if(sid&&!viewer){
        try{await store.checkViewer(owner,sid);}catch(e){if(e instanceof AccessError){reply(401,{error:'session_revoked'});return;}throw e;}
      }
      if(file){
        if(!recording){reply(503,{error:'recording_disabled'});return;}
        if(action==='download')reply(200,await recording.files.download(owner,id));
        else{await recording.files.remove(owner,id);reply(200,{ok:true});}
      }
      else if(action==='recordings'){
        await store.owns(owner,id);
        const rows=recording?await recording.files.records.list(owner,id):[];
        reply(200,{enabled:!!recording?.recorder,recordings:rows.map(({id,status,created_ms,completed_ms,expires_ms,bytes,duration_ms,reason,segment,gap_before_ms})=>({id,status,created_ms,completed_ms,expires_ms,bytes,duration_ms,reason,segment,gap_before_ms}))});
      }
      else if(list)reply(200,{devices:await store.listDevices(owner)});
      else if(viewer){
        await store.revokeViewer(owner,id);viewerGeneration++;
        for(const [ws,identity] of identities)if(identity.role==='observer'&&identity.device.owner_id===owner&&identity.device.viewer_session===id)ws.close(4401,'Viewer signed out');
        reply(200,{ok:true});
      }
      else if(action==='ticket'){
        reply(200,{ticket:await store.ticket(owner,id,Date.now(),sid)});
      }
      else if(action==='history'){
        const session=requestUrl.searchParams.get('session')??undefined;
        if(session!==undefined&&!/^[a-zA-Z0-9_-]{1,128}$/.test(session)){reply(400,{error:'invalid_work_session'});return;}
        reply(200,{events:await store.history(owner,id,session),sessions:await store.workSessions(owner,id)});
      }
      else{
        await store.revoke(owner,id);
        recording?.recorder?.stop(id,'revoked');
        authGeneration++;
        for(const [ws,identity] of identities)if(identity.device.id===id)ws.close(4401,'Device revoked');
        reply(200,{ok:true});
      }
    }catch(e){reply(e instanceof AccessError?404:503,{error:e instanceof AccessError?'not_found':'unavailable'});}
  });
  server.on('connection',socket=>{sockets.add(socket);socket.once('close',()=>sockets.delete(socket));});
  server.requestTimeout=5000;server.headersTimeout=5000;server.maxConnections=64;
  const wss=new WebSocketServer({noServer:true,maxPayload:MAX_AVC_BYTES,perMessageDeflate:false});
  server.on('upgrade',(req,socket,head)=>{
    const ip=clientIP(req,config.trustedProxy);
    if(ip===null){socket.destroy();return;}
    const sameIP=[...wss.clients].filter(ws=>(ws as WebSocket&{peer?:string}).peer===ip).length;
    const sameChannel=[...wss.clients].filter(ws=>{const client=ws as WebSocket&{peer?:string;channel?:string};return client.peer===ip&&client.channel===req.url;}).length;
    if(closing||!['/ws','/video'].includes(req.url??'')||wss.clients.size>=32||sameIP>=12||sameChannel>=(req.url==='/video'?4:8)||
      (req.headers.origin&&!config.origins.includes(req.headers.origin))){socket.destroy();return;}
    wss.handleUpgrade(req,socket,head,ws=>{
      (ws as WebSocket&{peer?:string}).peer=ip;
      (ws as WebSocket&{channel?:string}).channel=req.url;
      wss.emit('connection',ws,req);
    });
  });
  wss.on('connection',(ws,req)=>{
    const video=req.url==='/video';
    const heartbeat={due:clock()+20000,awaiting:false};heartbeats.set(ws,heartbeat);
    ws.on('pong',()=>{heartbeat.awaiting=false;});
    let pending=false,window=clock(),count=0;
    const timeout=setTimeout(()=>ws.close(pending?1013:4401,pending?'Authentication unavailable':'Authentication required'),5000);
    const expire=setTimeout(()=>ws.close(4401,'Reauthenticate'),15*60000);
    ws.on('error',()=>{});
    ws.on('message',async(data,binary)=>{
      if(ws.readyState!==WebSocket.OPEN||closing)return;
      if(clock()-window>=1000){window=clock();count=0;}
      let identity=identities.get(ws);
      if(++count>(video&&identity?40:10)){ws.close(4429,'Rate limit');return;}
      const bytes=Array.isArray(data)?Buffer.concat(data):Buffer.isBuffer(data)?data:Buffer.from(data);
      if((!video||!identity)&&bytes.length>MAX_BYTES){ws.close(1009,'Payload too large');return;}
      if(binary&&(!video||!identity)){ws.close(4400,'Text messages required');return;}
      if(!identity){
        if(pending){ws.close(4400,'Authentication pending');return;}pending=true;
        const generation=authGeneration,viewerVersion=viewerGeneration;
        try{
          const auth=authSchema.parse(JSON.parse(data.toString()));
          if(auth.role==='observer'&&!config.origins.includes(req.headers.origin??'')){ws.close(4403,'Origin required');return;}
          const device=auth.role==='publisher'?await store.device(auth.token):await store.consumeTicket(auth.token);
          if(!device||(!config.multiUser&&device.owner_id!==config.ownerId)||Number(device.expires_ms)<=Date.now()){
            ws.close(4401,'Unauthorized');return;
          }
          if(generation!==authGeneration||(auth.role==='observer'&&viewerVersion!==viewerGeneration)){
            ws.close(4401,'Reauthenticate');return;
          }
          if(ws.readyState!==WebSocket.OPEN||closing)return;
          identity={role:auth.role,device,video};identities.set(ws,identity);clearTimeout(timeout);
          const e=entry(device.id);
          if(video){
            if(auth.role==='publisher'){
              recording?.recorder?.stop(device.id,'video_reconnected');
              const previous=e.videoPublisher;e.videoPublisher=ws;e.videoSequence=0;clearVideo(e);
              if(previous&&previous!==ws)previous.close(4409,'Publisher replaced');
            }else{e.videoObservers.add(ws);needsKey.add(ws);}
          }else if(auth.role==='publisher'){
            recording?.recorder?.stop(device.id,'state_reconnected');
            const previous=e.publisher;e.publisher=ws;
            if(previous&&previous!==ws){e.gap=!!e.snapshot;previous.close(4409,'Publisher replaced');}
          }else e.observers.add(ws);
          send(ws,{type:'ready',role:auth.role,device_id:device.id,recording_enabled:!!recording?.recorder});
          if(auth.role==='observer'){
            if(video)send(ws,{type:'video-status',status:'waiting'});else broadcast(e,ws);
          }
        }catch(e){
          const invalid=e instanceof SyntaxError||e instanceof z.ZodError||e instanceof AccessError;
          ws.close(invalid?4401:1013,invalid?'Authentication failed':'Authentication unavailable');
        }
        return;
      }
      if(identity.role!=='publisher'){ws.close(4403,'Read only');return;}
      const e=entries.get(identity.device.id)!;
      if(video){
        if(e.videoPublisher!==ws)return;
        const avc=parseAvc(bytes);
        if(!binary||(!avc&&!validJpeg(bytes))){ws.close(4400,'Invalid video');return;}
        if(!avc&&count>6){ws.close(4429,'Video rate limit');return;}
        if(avc){
          if(avc.sequence<=e.videoSequence)return;
          if(avc.sequence!==e.videoSequence+1)for(const viewer of e.videoObservers)needsKey.add(viewer);
          e.videoSequence=avc.sequence;
        }
        if(e.status!=='live'||clock()-e.received>VIDEO_STALE_MS||!e.snapshot?.state.running||!e.snapshot.state.video_available)return;
        e.videoAt=clock();
        if(avc)recording?.recorder?.offer(identity.device,e.snapshot!,avc);
        for(const viewer of e.videoObservers){
          // Never queue behind a slow viewer, and never share its socket with state updates.
          if(viewer.readyState!==WebSocket.OPEN)continue;
          if(viewer.bufferedAmount!==0){needsKey.add(viewer);continue;}
          if(avc&&needsKey.has(viewer)&&!avc.key)continue;
          if(avc?.key)needsKey.delete(viewer);
          viewer.send(bytes,{binary:true});
        }
        return;
      }
      if(e.publisher!==ws)return;
      try{
        const p=parsePublish(data.toString());
        if(e.retired.has(p.stream_id))return;
        if(e.snapshot?.stream_id===p.stream_id&&p.seq<=e.snapshot.seq)return;
        const previous=e.snapshot;
        if(previous&&previous.stream_id!==p.stream_id){
          if(e.retired.size>=1024){ws.close(4429,'Stream limit');return;}
          e.retired.add(previous.stream_id);e.gap=true;
        }
        const sessionChanged=previous?.state.session!==p.state.session;
        const eventKind=previous?.state.running&&!p.state.running?'stop':
          !previous||sessionChanged||previous.state.stage!==p.state.stage?'step':previous.state.phase!==p.state.phase?'phase':null;
        e.snapshot=p;e.received=clock();e.receivedWall=Date.now();e.status='live';
        recording?.recorder?.state(identity.device,p);
        if(!p.state.running||!p.state.video_available)clearVideo(e);
        if(e.gap){e.gap=false;append(e,identity.device.id,p,'gap');}
        if(eventKind)append(e,identity.device.id,p,eventKind);
        broadcast(e);
      }catch{ws.close(4400,'Invalid state');}
    });
    ws.on('close',()=>{
      heartbeats.delete(ws);
      clearTimeout(timeout);clearTimeout(expire);
      const identity=identities.get(ws);identities.delete(ws);
      if(!identity)return;
      const e=entries.get(identity.device.id);if(!e)return;
      e.observers.delete(ws);
      e.videoObservers.delete(ws);
      if(e.videoPublisher===ws){recording?.recorder?.stop(identity.device.id,'disconnected');e.videoPublisher=undefined;clearVideo(e);}
      if(e.publisher===ws){recording?.recorder?.stop(identity.device.id,'disconnected');e.publisher=undefined;e.status='offline';e.gap=!!e.snapshot;clearVideo(e);broadcast(e);}
    });
  });
  const timer=setInterval(()=>{
    // Bound half-open connections even when no close event reaches the server.
    for(const [ws,heartbeat] of heartbeats){
      if(clock()<heartbeat.due)continue;
      if(heartbeat.awaiting||ws.readyState!==WebSocket.OPEN){ws.terminate();continue;}
      heartbeat.awaiting=true;heartbeat.due=clock()+20000;ws.ping();
    }
    for(const [ws,identity] of identities)if(Number(identity.device.expires_ms)<=Date.now())ws.close(4401,'Credential expired');
    for(const [id,e] of entries){
      if(e.status==='live'&&clock()-e.received>3000)recording?.recorder?.stop(id,'state_stale');
      else if(e.videoAt!==null&&clock()-e.videoAt>VIDEO_STALE_MS)recording?.recorder?.stop(id,'video_stale');
      if(e.recordingStatus!==(recording?.recorder?.status(id)??'off'))broadcast(e);
      if(e.status==='live'&&clock()-e.received>3000){e.status='stale';e.gap=true;clearVideo(e);broadcast(e);}
      if(e.videoAt!==null&&clock()-e.videoAt>VIDEO_STALE_MS)clearVideo(e);
    }
    for(const [ip,b] of apiBuckets)if(clock()-b.at>60000)apiBuckets.delete(ip);
  },250);
  return {server,async close(){
    closing=true;clearInterval(timer);
    for(const ws of wss.clients)ws.terminate();
    await new Promise<void>(resolve=>wss.close(()=>resolve()));
    for(const socket of sockets)socket.destroy();
    await new Promise<void>(resolve=>server.close(()=>resolve()));
    for(const e of entries.values())while(e.writes)await e.chain;
    await recording?.recorder?.close();
  }};
}
