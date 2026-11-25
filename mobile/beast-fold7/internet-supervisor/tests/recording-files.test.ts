import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {PGlite} from '@electric-sql/pglite';
import {Store,AccessError} from '../server/store.ts';
import {Recordings} from '../server/recordings.ts';
import {RecordingFiles,type ObjectStorage} from '../server/recording-files.ts';
let db:PGlite,records:Recordings,device:string;
before(async()=>{db=new PGlite();const store=new Store(db);await store.init();records=new Recordings(store);device=(await store.provision('101','Phone')).id;});
after(async()=>{await db.close();});
test('download authenticates owner and never issues a link beyond retention',async()=>{
  const signed:number[]=[];const storage:ObjectStorage={put:async()=>{},remove:async()=>{},download:async(_key,seconds)=>{signed.push(seconds);return 'https://example.invalid/signed';}};
  const files=new RecordingFiles(records,storage),r=await records.begin('101',device,'one',1000,1000,100);
  await records.ready(r.id,500,1000,'completed',200);
  await assert.rejects(()=>files.download('202',r.id,201),AccessError);
  await files.download('101',r.id,201);assert.deepEqual(signed,[60]);
  await files.download('101',r.id,604799000);assert.equal(signed[1],1);
  await assert.rejects(()=>files.download('101',r.id,604800000),AccessError);
  await records.removed(r.id);
});
test('failed object removal hides file, retains quota and is retried',async()=>{
  let fail=true,attempts=0;
  const storage:ObjectStorage={put:async()=>{},download:async()=>'',remove:async()=>{attempts++;if(fail)throw Error('offline');}};
  const files=new RecordingFiles(records,storage),r=await records.begin('101',device,'two',1000,1000,100);
  await records.ready(r.id,500,1000,'completed',200);
  await assert.rejects(()=>files.remove('202',r.id),AccessError);assert.equal(attempts,0);
  await assert.rejects(()=>files.remove('101',r.id));
  await assert.rejects(()=>records.downloadable('101',r.id,201),AccessError);
  assert.equal((await records.get('101',r.id)).status,'deleting');
  fail=false;await files.cleanup(300);assert.equal(attempts,2);
  await assert.rejects(()=>records.get('101',r.id),AccessError);
});
test('slow database/signing cannot issue a link after cutoff and signing uses the checked time',async()=>{
  const r=await records.begin('101',device,'slow-signing',1000,1000,100);await records.ready(r.id,500,1000,'completed',200);
  let now=604798000,anchor=0;
  const files=new RecordingFiles(records,{put:async()=>{},remove:async()=>{},download:async(_key,_seconds,at)=>{anchor=at;now+=3000;return 'https://example.invalid/expired';}},()=>now);
  await assert.rejects(()=>files.download('101',r.id),AccessError);assert.equal(anchor,604798000);
  await records.removed(r.id);
});
