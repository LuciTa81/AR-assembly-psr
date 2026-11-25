import assert from 'node:assert/strict';
const headers={Authorization:`Bearer ${process.env.SERVICE_KEY}`};
// Loopback is the only trusted proxy; this check never starts media or writes records.
Object.assign(headers,{'X-Real-IP':'127.0.0.1'});
const base='http://127.0.0.1:8787';
const request=async(path:string)=>{const r=await fetch(base+path,{headers});assert.equal(r.status,200);return r.json();};
const {devices}=await request('/devices');
for(const d of devices){
  const current=await request(`/devices/${d.id}/history`);
  assert(Array.isArray(current.sessions));assert(Array.isArray(current.events));
  assert(new Set(current.events.map((e:any)=>e.state.session)).size<=1);
  if(current.sessions.length){
    assert(current.events.every((e:any)=>e.state.session===current.sessions[0].session));
    const prior=current.sessions.at(-1);
    const selected=await request(`/devices/${d.id}/history?session=${encodeURIComponent(prior.session)}`);
    assert(selected.events.every((e:any)=>e.state.session===prior.session));
  }
}
console.log(`PASS: ${devices.length} owner devices; latest/selected work isolation; read-only`);
