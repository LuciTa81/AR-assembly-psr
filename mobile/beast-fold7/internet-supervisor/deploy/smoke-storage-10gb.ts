import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseEnv} from 'node:util';
import {readConfig} from '../server/config.ts';
import {RETENTION_MS} from '../server/recordings.ts';
const config=readConfig(process.env);
assert.equal(config.recording?.capture?.fileBytes,300000000);
assert.equal(config.recording?.capture?.ownerBytes,10000000000);
assert.equal(config.recording?.capture?.seconds,600);
assert.equal(config.recording?.capture?.concurrent,1);
assert.equal(config.multiUser,false);
assert.equal(RETENTION_MS,7*86400000);
if(process.argv[2]){
  assert.match(process.argv[2],/^\d+$/);
  const live=parseEnv(readFileSync(`/proc/${process.argv[2]}/environ`,'utf8').replaceAll('\0','\n'));
  for(const key of ['RECORDING_FILE_BYTES','RECORDING_OWNER_BYTES','RECORDING_MAX_SECONDS','RECORDING_ENABLED','MULTI_USER'])
    assert.equal(live[key],process.env[key]);
}
const headers={Authorization:`Bearer ${config.serviceKey}`,'X-Real-IP':'127.0.0.1'};
const request=async(path:string)=>{const r=await fetch('http://127.0.0.1:8787'+path,{headers});assert.equal(r.status,200);return r.json();};
const {devices}=await request('/devices');
let count=0,bytes=0;
for(const d of devices){
  const data=await request(`/devices/${d.id}/recordings`);
  assert.equal(data.enabled,true);
  count+=data.recordings.length;
  bytes+=data.recordings.reduce((sum:number,row:{bytes:number})=>sum+Number(row.bytes),0);
}
console.log(JSON.stringify({fileBytes:300000000,ownerBytes:10000000000,seconds:600,retentionDays:7,recordings:count,listedBytes:bytes}));
