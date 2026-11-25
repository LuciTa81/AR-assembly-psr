import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {setTimeout as delay} from 'node:timers/promises';
import {WebSocket} from 'ws';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
import {publish} from './fixture.ts';

const owner='reliability-owner',key='b'.repeat(64),origin='http://localhost:3000';
async function until(check:()=>boolean){
  for(let i=0;i<150;i++){if(check())return;await delay(20);}
  assert.fail('Timed out');
}
async function connect(base:string,role:'publisher'|'observer',token:string,autoPong=true){
  const ws=new WebSocket(base+'/ws',{autoPong,...(role==='observer'?{origin}:{})});
  const messages:any[]=[];ws.on('error',()=>{});
  ws.on('message',data=>messages.push(JSON.parse(data.toString())));
  await once(ws,'open');ws.send(JSON.stringify({role,token}));
  await until(()=>messages.some(m=>m.type==='ready'));
  return {ws,messages};
}

test('silent sockets are evicted while responsive idle observers survive',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();let clock=0;
  const relay=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin],monotonic:()=>clock});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
  const base=`ws://127.0.0.1:${(relay.server.address() as any).port}`;
  try{
    const d=await store.provision(owner,'Silent phone');
    const observer=await connect(base,'observer',await store.ticket(owner,d.id));
    const silent=await connect(base,'publisher',d.token,false);
    let probes=0;silent.ws.on('ping',()=>probes++);
    silent.ws.send(JSON.stringify(publish()));
    await until(()=>observer.messages.some(m=>m.status==='live'));
    clock=20001;await until(()=>probes===1);
    await delay(300);
    clock=40002;await until(()=>silent.ws.readyState===WebSocket.CLOSED);
    await until(()=>observer.messages.some(m=>m.status==='offline'));
    assert.equal(observer.ws.readyState,WebSocket.OPEN);
    assert.equal((await store.device(d.token))?.id,d.id);
    const restored=await connect(base,'publisher',d.token);
    restored.ws.send(JSON.stringify(publish(2)));
    await until(()=>observer.messages.some(m=>m.status==='live'&&m.snapshot?.seq===2));
    await until(()=>observer.messages.some(m=>m.history_status==='ok'&&m.snapshot?.seq===2));
    assert((await store.history(owner,d.id)).some(e=>e.kind==='gap'));
    restored.ws.close();observer.ws.close();
  }finally{await relay.close();await db.close();}
});

test('relay restart preserves enrollment and history without replaying old live state',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  let relay=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin]});
  async function listen(){
    relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
    return `ws://127.0.0.1:${(relay.server.address() as any).port}`;
  }
  try{
    let base=await listen();const d=await store.provision(owner,'Restart phone');
    const before=await connect(base,'observer',await store.ticket(owner,d.id));
    const first=await connect(base,'publisher',d.token);
    first.ws.send(JSON.stringify(publish()));
    await until(()=>before.messages.some(m=>m.snapshot?.seq===1&&m.history_status==='ok'));
    assert.equal((await store.history(owner,d.id)).length,1);
    await relay.close();
    relay=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin]});base=await listen();
    const observer=await connect(base,'observer',await store.ticket(owner,d.id));
    await until(()=>observer.messages.some(m=>m.type==='state'));
    const initial=observer.messages.find(m=>m.type==='state');
    assert.equal(initial.status,'waiting');assert.equal(initial.snapshot,null);
    const restored=await connect(base,'publisher',d.token);
    const next=publish(2);next.state.stage=3;restored.ws.send(JSON.stringify(next));
    await until(()=>observer.messages.some(m=>m.snapshot?.state.stage===3&&m.history_status==='ok'));
    const history=await store.history(owner,d.id);
    assert.equal(history.filter(e=>e.kind==='step').length,2);
    restored.ws.close();observer.ws.close();
  }finally{await relay.close();await db.close();}
});
