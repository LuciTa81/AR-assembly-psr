import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {PGlite} from '@electric-sql/pglite';
import {WebSocket} from 'ws';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
import type {IncomingMessage} from 'node:http';
import {clientIP} from '../server/client-ip.ts';

test('forwarded headers never grant trust to a remote peer or an unconfigured relay',()=>{
  const req=(peer:string,ip?:string|string[])=>({socket:{remoteAddress:peer},headers:{'x-real-ip':ip,'x-forwarded-for':'192.0.2.99'}} as unknown as IncomingMessage);
  assert.equal(clientIP(req('192.0.2.1','192.0.2.2')),'192.0.2.1');
  assert.equal(clientIP(req('192.0.2.1','192.0.2.2'),'127.0.0.1'),null);
  assert.equal(clientIP(req('127.0.0.1',['192.0.2.1','192.0.2.2']),'127.0.0.1'),null);
  assert.equal(clientIP(req('127.0.0.1'),'127.0.0.1'),null);
  assert.equal(clientIP(req('::ffff:127.0.0.1','2001:0db8:0:0::1'),'127.0.0.1'),'2001:db8::1');
});

test('single loopback proxy separates client limits and rejects missing or ambiguous IPs',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const relay=createRelay(store,{ownerId:'owner',serviceKey:'d'.repeat(64),origins:['https://web.example'],trustedProxy:'127.0.0.1'});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');
  const base=`http://127.0.0.1:${(relay.server.address() as {port:number}).port}`;
  const sockets:WebSocket[]=[];
  const request=(ip?:string)=>fetch(base+'/pairing/request',{method:'POST',headers:{'Content-Type':'application/json',...(ip?{'X-Real-IP':ip}:{})},body:JSON.stringify({name:'Proxy test'})});
  try{
    assert.equal((await request()).status,403);
    for(const ip of ['garbage','192.0.2.1, 192.0.2.2','192.0.2.1:1234'])assert.equal((await request(ip)).status,403);
    for(let i=0;i<5;i++)assert.equal((await request('192.0.2.1')).status,200);
    assert.equal((await request('192.0.2.1')).status,429);
    assert.equal((await request('192.0.2.2')).status,200);
    for(let i=0;i<120;i++)assert.equal((await fetch(base+'/devices',{headers:{'X-Real-IP':'192.0.2.5'}})).status,401);
    assert.equal((await fetch(base+'/devices',{headers:{'X-Real-IP':'192.0.2.5'}})).status,429);
    assert.equal((await fetch(base+'/devices',{headers:{'X-Real-IP':'192.0.2.6'}})).status,401);
    const missing=new WebSocket(base.replace('http:','ws:')+'/ws');
    sockets.push(missing);await once(missing,'error');
    for(let i=0;i<9;i++){
      const ws=new WebSocket(base.replace('http:','ws:')+'/ws',{headers:{'X-Real-IP':i<8?'192.0.2.3':'192.0.2.4'}});
      sockets.push(ws);await once(ws,'open');
    }
    const rejected=new WebSocket(base.replace('http:','ws:')+'/ws',{headers:{'X-Real-IP':'192.0.2.3'}});
    sockets.push(rejected);await once(rejected,'error');
  }finally{for(const ws of sockets)ws.terminate();await relay.close();await db.close();}
});
