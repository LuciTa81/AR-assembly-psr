import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {randomUUID} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {Recordings} from '../server/recordings.ts';
import {RecordingFiles} from '../server/recording-files.ts';
import {createRelay} from '../server/relay.ts';
test('recording HTTP routes enforce service/session/owner and never reveal object keys',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const d=await store.provision('101','Phone'),records=new Recordings(store);let downloads=0,removed=0;
  const files=new RecordingFiles(records,{put:async()=>{},remove:async()=>{removed++;},download:async()=>{downloads++;return 'https://example.invalid/file';}});
  const relay=createRelay(store,{ownerId:'101',multiUser:true,serviceKey:'a'.repeat(64),origins:['http://localhost:3000']},{files});
  relay.server.listen(0,'127.0.0.1');await once(relay.server,'listening');const base=`http://127.0.0.1:${(relay.server.address() as any).port}`;
  const headers=(owner='101')=>({Authorization:`Bearer ${'a'.repeat(64)}`,'X-Owner-Id':owner,'X-Viewer-Session':owner==='101'?sid:other});
  const sid=randomUUID(),other=randomUUID();
  try{
    const r=await records.begin('101',d.id,'session',1000,1000);await records.ready(r.id,500,1000,'completed');
    const list=await fetch(`${base}/devices/${d.id}/recordings`,{headers:headers()});assert.equal(list.status,200);
    const json=await list.json();assert.equal(json.recordings.length,1);assert.equal(json.enabled,false);assert.equal(json.recordings[0].object_key,undefined);
    for(const action of ['download','delete']){
      const path=`${base}/recordings/${r.id}/${action}`;
      assert.equal((await fetch(path,{method:'POST'})).status,401);
      assert.equal((await fetch(path,{method:'POST',headers:headers('202')})).status,404);
      assert.equal((await fetch(path,{method:'POST',headers:{...headers(),Origin:'https://evil.invalid'}})).status,403);
    }
    assert.equal(downloads,0);assert.equal(removed,0);
    assert.equal((await fetch(`${base}/recordings/${r.id}/download`,{method:'POST',headers:headers()})).status,200);
    assert.equal(downloads,1);
    await store.revokeViewer('101',sid);
    assert.equal((await fetch(`${base}/recordings/${r.id}/delete`,{method:'POST',headers:headers()})).status,401);
    assert.equal(removed,0);
  }finally{await relay.close();await db.close();}
});
