// Synthetic loopback demonstration. No phone, camera, media or external server is accessed.
import {randomBytes} from 'node:crypto';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {PGlite} from '@electric-sql/pglite';
import {WebSocket} from 'ws';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
import {publish} from '../tests/fixture.ts';

const db=new PGlite(),store=new Store(db);
await store.init();
const owner='local-demo',origin='http://localhost:3000';
const relay=createRelay(store,{ownerId:owner,serviceKey:randomBytes(32).toString('hex'),origins:[origin]});
const sockets:WebSocket[]=[];
try{
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
  const url=`ws://127.0.0.1:${(relay.server.address() as {port:number}).port}/ws`;
  const device=await store.provision(owner,'Synthetic Fold7');
  async function connect(role:string,token:string){
    const ws=new WebSocket(url,role==='observer'?{origin}:{});sockets.push(ws);
    await once(ws,'open');const ready=once(ws,'message');ws.send(JSON.stringify({role,token}));await ready;return ws;
  }
  const observer=await connect('observer',await store.ticket(owner,device.id));
  const phone=await connect('publisher',device.token);
  let last=-1;
  observer.on('message',raw=>{const m=JSON.parse(raw.toString());if(m.status==='live'&&m.snapshot.seq!==last){last=m.snapshot.seq;console.log(`Received ${m.snapshot.state.action}`);}});
  for(let stage=0;stage<=6;stage++){
    const p=publish(stage+1);p.state.stage=stage;p.state.phase=stage<2?'PREPARATION':stage===6?'INSPECTION':'WORKING';
    p.state.action=stage===0?'상자를 놓아주세요':stage===1?'뚜껑을 닫아주세요':stage===6?'조립 상태를 확인해주세요':`나사 ${'ABCD'[stage-2]}를 조여주세요`;
    phone.send(JSON.stringify(p));await delay(150);
  }
  if(last!==7)throw new Error('Incomplete synthetic flow');
  console.log(`PASS: seven stages received; ${(await store.history(owner,device.id)).length} stored events. This is not a real-device test.`);
}finally{for(const ws of sockets)ws.terminate();await relay.close();await db.close();}
