import assert from 'node:assert/strict';
import {readConfig} from '../server/config.ts';
const config=readConfig(process.env);
assert.equal(config.recording?.capture?.seconds,600);
assert.equal(config.recording?.capture?.fileBytes,100000000);
assert.equal(config.recording?.capture?.ownerBytes,100000000);
assert.equal(config.multiUser,false);
const headers={Authorization:`Bearer ${process.env.SERVICE_KEY}`,'X-Real-IP':'127.0.0.1'};
const request=async(path:string)=>{const r=await fetch('http://127.0.0.1:8787'+path,{headers});assert.equal(r.status,200);return r.json();};
const {devices}=await request('/devices');
let count=0,bytes=0;
for(const d of devices){
  const data=await request(`/devices/${d.id}/recordings`);
  assert.equal(data.enabled,true);
  assert(Array.isArray(data.recordings));
  count+=data.recordings.length;
  bytes+=data.recordings.reduce((sum:number,row:any)=>sum+Number(row.bytes),0);
}
console.log(`PASS read-only: recording enabled; 600 seconds; 100MB file/owner; ${count} existing recordings, ${bytes} bytes. No media started.`);
