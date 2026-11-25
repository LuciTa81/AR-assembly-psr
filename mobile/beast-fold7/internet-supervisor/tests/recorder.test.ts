import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rmdir,readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {Recordings} from '../server/recordings.ts';
import {RecordingFiles} from '../server/recording-files.ts';
import {Recorder} from '../server/recorder.ts';
import {publish} from './fixture.ts';
import {syntheticPackets} from './synthetic-packets.ts';
test('late consent and restart record into remaining space and stop at the reserved size',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-remaining-')),records=new Recordings(store),uploads:number[]=[];
  const files=new RecordingFiles(records,{put:async(_key,_path,size)=>{uploads.push(size);},remove:async()=>{},download:async()=>''});
  const recorder=new Recorder(files,{directory:dir,fileBytes:4*1024*1024,ownerBytes:4*1024*1024,seconds:10,concurrent:1});
  try{
    await recorder.init();const old=await records.begin('101',device.id,'old',4*1024*1024,4*1024*1024);
    await records.ready(old.id,2*1024*1024,2269,'stopped');
    const p=publish(),packets=await syntheticPackets();p.state.video_available=true;
    recorder.offer(device,p,packets[0]);assert.equal(recorder.status(device.id),'off');
    p.state.recording_consent=true;recorder.state(device,p);
    recorder.offer(device,p,packets[0]);
    recorder.offer(device,p,{...packets[1],data:new Uint8Array(1024*1024)});
    await recorder.close();
    const rows=await records.list('101',device.id),saved=rows.find(r=>r.session===p.state.session)!;
    assert(saved);assert.equal(saved.status,'ready');assert.equal(saved.reason,'size_limit');
    assert.equal(uploads.length,1);assert(uploads[0]<=2*1024*1024);
    assert.equal((await records.get('101',old.id)).status,'ready');
    assert.deepEqual(await readdir(dir),[]);
  }finally{await recorder.close();await db.close();await rmdir(dir);}
});
test('insufficient remaining space is reported separately from connection or storage failure',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-full-')),records=new Recordings(store);
  const recorder=new Recorder(new RecordingFiles(records,{put:async()=>{assert.fail('must not upload');},remove:async()=>{},download:async()=>''}),{directory:dir,fileBytes:2*1024*1024,ownerBytes:2*1024*1024,seconds:10,concurrent:1});
  try{
    await recorder.init();const old=await records.begin('101',device.id,'old',2*1024*1024,2*1024*1024);
    await records.ready(old.id,1024*1024,1000,'stopped');
    const p=publish();p.state.video_available=true;p.state.recording_consent=true;
    recorder.offer(device,p,(await syntheticPackets())[0]);await recorder.close();
    assert.equal(recorder.status(device.id),'quota_full');assert.equal((await records.list('101',device.id)).length,1);
  }finally{await recorder.close();await db.close();await rmdir(dir);}
});
test('recording requires consent, finalizes accepted frames, and rejects gaps without damaging live traffic',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-recorder-')),uploads:string[]=[];
  const records=new Recordings(store),files=new RecordingFiles(records,{put:async key=>{uploads.push(key);},remove:async()=>{},download:async()=>''});
  const recorder=new Recorder(files,{directory:dir,fileBytes:2*1024*1024,ownerBytes:4*1024*1024,seconds:10,concurrent:1});
  try{
    await recorder.init();const packets=await syntheticPackets(),p=publish();p.state.video_available=true;
    recorder.offer(device,p,packets[0]);assert.equal(recorder.status(device.id),'off');assert.equal((await records.list('101',device.id)).length,0);
    p.state.recording_consent=true;recorder.state(device,p);
    recorder.offer(device,p,packets[0]);recorder.offer(device,p,{...packets[1],sequence:3});
    await recorder.close();assert.equal(uploads.length,1);
    const saved=await records.list('101',device.id);assert.equal(saved[0].status,'ready');assert.equal(saved[0].reason,'stream_gap');
    assert.deepEqual(await readdir(dir),[]);
  }finally{await recorder.close();await db.close();await rmdir(dir);}
});
test('failed upload stays non-downloadable and cleanup retries without leaking reservations',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-recorder-')),records=new Recordings(store);let offline=true;
  const files=new RecordingFiles(records,{put:async()=>{throw Error('upload failed');},remove:async()=>{if(offline)throw Error('offline');},download:async()=>''});
  const recorder=new Recorder(files,{directory:dir,fileBytes:2*1024*1024,ownerBytes:2*1024*1024,seconds:10,concurrent:1});
  try{
    await recorder.init();const p=publish();p.state.video_available=true;p.state.recording_consent=true;
    recorder.offer(device,p,(await syntheticPackets())[0]);await recorder.close();
    const rows=await records.list('101',device.id);assert.equal(rows[0].status,'deleting');assert.equal(recorder.status(device.id),'error');
    await assert.rejects(()=>records.downloadable('101',rows[0].id));
    await assert.rejects(()=>records.begin('101',device.id,'next',2*1024*1024,2*1024*1024));
    offline=false;await files.cleanup();assert.equal((await records.list('101',device.id)).length,0);
    const next=await records.begin('101',device.id,'next',2*1024*1024,2*1024*1024);await records.removed(next.id);
    assert.deepEqual(await readdir(dir),[]);
  }finally{await recorder.close();await db.close();await rmdir(dir);}
});
test('wall deadline finalizes recording even when no further AVC packets arrive',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-deadline-')),records=new Recordings(store);let uploads=0;
  const recorder=new Recorder(new RecordingFiles(records,{put:async()=>{uploads++;},remove:async()=>{},download:async()=>''}),{directory:dir,fileBytes:2*1024*1024,ownerBytes:2*1024*1024,seconds:1,concurrent:1});
  try{
    await recorder.init();const p=publish();p.state.video_available=true;p.state.recording_consent=true;recorder.offer(device,p,(await syntheticPackets())[0]);
    await new Promise(r=>setTimeout(r,1400));assert.equal(uploads,1);assert.equal((await records.list('101',device.id))[0].reason,'duration_limit');
  }finally{await recorder.close();await db.close();await rmdir(dir);}
});
test('database outage during completion is recovered before seven-day expiry',async()=>{
  const db=new PGlite();let offline=false;
  const store=new Store({async query(sql,params){if(offline&&(sql.includes('WITH previous AS')||sql.includes("reason='storage_error'")))throw Error('db offline');return db.query(sql,params);}});await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!,dir=await mkdtemp(join(tmpdir(),'ar-db-recovery-')),records=new Recordings(store);let removed=0;
  const files=new RecordingFiles(records,{put:async()=>{offline=true;},remove:async()=>{removed++;},download:async()=>''});
  const recorder=new Recorder(files,{directory:dir,fileBytes:2*1024*1024,ownerBytes:2*1024*1024,seconds:10,concurrent:1});
  try{
    await recorder.init();const p=publish();p.state.video_available=true;p.state.recording_consent=true;recorder.offer(device,p,(await syntheticPackets())[0]);await recorder.close();
    assert.equal((await records.list('101',device.id))[0].status,'capturing');
    offline=false;await recorder.recover();await files.cleanup();assert.equal(removed,1);assert.equal((await records.list('101',device.id)).length,0);
  }finally{offline=false;await recorder.close();await db.close();await rmdir(dir);}
});

test('withdrawing consent during segment upload blocks recovery even if consent is restored',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-consent-')),records=new Recordings(store);
  let release!:()=>void,uploading!:()=>void;
  const held=new Promise<void>(r=>{release=r;}),started=new Promise<void>(r=>{uploading=r;});
  const recorder=new Recorder(new RecordingFiles(records,{put:async()=>{uploading();await held;},remove:async()=>{},download:async()=>''}),{directory:dir,fileBytes:4*1024*1024,ownerBytes:4*1024*1024,seconds:10,concurrent:1});
  try{
    await recorder.init();const p=publish(),packet=(await syntheticPackets())[0];p.state.video_available=true;p.state.recording_consent=true;
    recorder.state(device,p);recorder.offer(device,p,packet);recorder.stop(device.id,'stream_gap');await started;
    recorder.state(device,{...p,state:{...p.state,recording_consent:false}});recorder.state(device,p);release();
    for(let i=0;i<100&&recorder.status(device.id)==='saving';i++)await new Promise(r=>setTimeout(r,10));
    assert.equal(recorder.status(device.id),'saved');
    recorder.offer(device,p,{...packet,sequence:3,timestamp:2000000});await new Promise(r=>setTimeout(r,50));
    const rows=await records.list('101',device.id);assert.equal(rows.length,1);assert.equal(rows[0].resume_blocked,true);
    await assert.rejects(()=>new Recordings(store).begin('101',device.id,p.state.session,4*1024*1024,4*1024*1024,Date.now(),2097152,{seconds:10}));
  }finally{release();await recorder.close();await db.close();await rmdir(dir);}
});

test('resumed segment ends at the original work deadline, not a new full duration',async()=>{
  const db=new PGlite(),store=new Store(db);await store.init();
  const token=await store.provision('101','Phone'),device=(await store.device(token.token))!;
  const dir=await mkdtemp(join(tmpdir(),'ar-segment-deadline-')),records=new Recordings(store);
  const recorder=new Recorder(new RecordingFiles(records,{put:async()=>{},remove:async()=>{},download:async()=>''}),{directory:dir,fileBytes:4*1024*1024,ownerBytes:4*1024*1024,seconds:2,concurrent:1});
  async function until(check:()=>boolean){for(let i=0;i<150;i++){if(check())return;await new Promise(r=>setTimeout(r,20));}assert.fail('timed out');}
  try{
    await recorder.init();const p=publish(),packet=(await syntheticPackets())[0];p.state.video_available=true;p.state.recording_consent=true;
    recorder.state(device,p);recorder.offer(device,p,packet);await until(()=>recorder.status(device.id)==='capturing');
    recorder.stop(device.id,'video_stale');await until(()=>recorder.status(device.id)==='interrupted');
    const first=(await records.list('101',device.id))[0];await new Promise(r=>setTimeout(r,700));
    recorder.state(device,p);recorder.offer(device,p,{...packet,sequence:3,timestamp:2000000});await until(()=>recorder.status(device.id)==='capturing');
    await until(()=>recorder.status(device.id)==='limit');const rows=await records.list('101',device.id);
    assert.equal(rows.length,2);assert.equal(rows[0].reason,'duration_limit');
    assert(Number(rows[0].completed_ms)-Number(first.created_ms)<2600,'deadline was reset');
    recorder.offer(device,p,{...packet,sequence:5,timestamp:3000000});await new Promise(r=>setTimeout(r,50));assert.equal((await records.list('101',device.id)).length,2);
  }finally{await recorder.close();await db.close();await rmdir(dir);}
});
