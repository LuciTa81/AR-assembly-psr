import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Recorder} from '../server/recorder.ts';
import type {RecordingFiles} from '../server/recording-files.ts';
const limits={directory:'unused',fileBytes:2000000,ownerBytes:2000000,seconds:1,concurrent:1};
test('recovery retains the slot until the previous finalizer including unlink has finished',async()=>{
  let finish!:()=>void,calls=0;
  const chain=new Promise<void>(resolve=>{finish=resolve;});
  const recorder=new Recorder({records:{abandon:async()=>{calls++;}}} as unknown as RecordingFiles,limits);
  const jobs=(recorder as any).jobs as Map<string,unknown>,job={recovery:true,row:{id:'old'},chain};jobs.set('phone',job);
  const recovery=recorder.recover();await new Promise(r=>setTimeout(r,10));
  try{assert.equal(jobs.get('phone'),job);assert.equal(calls,0);}finally{finish();await recovery;}
  assert.equal(jobs.size,0);assert.equal(calls,1);
});
test('a late recovery cannot remove a replacement job for the same device',async()=>{
  let release!:()=>void;
  const blocked=new Promise<void>(r=>{release=r;});
  const recorder=new Recorder({records:{abandon:()=>blocked}} as unknown as RecordingFiles,limits);
  const jobs=(recorder as any).jobs as Map<string,unknown>,old={recovery:true,row:{id:'old'},chain:Promise.resolve()},replacement={row:{id:'new'}};
  jobs.set('phone',old);const recovery=recorder.recover();await new Promise(r=>setTimeout(r,10));
  jobs.set('phone',replacement);release();await recovery;assert.equal(jobs.get('phone'),replacement);
});
