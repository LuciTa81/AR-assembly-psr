import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:http';
import {claimLocalRuntime,addLocalStopRoute} from '../scripts/local-lifecycle.ts';

test('local runtime refuses a second owner and releases its own lock',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'ar-local-')),path=join(dir,'relay.lock');
  try{
    const release=await claimLocalRuntime(path,0);
    assert.equal(JSON.parse(await readFile(path,'utf8')).pid,process.pid);
    await assert.rejects(()=>claimLocalRuntime(path,0));
    await release();await release();
    const again=await claimLocalRuntime(path,0);await again();
  }finally{await rm(dir,{recursive:true,force:true});}
});

test('an occupied port is rejected before DB open and removes only the new lock',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'ar-local-')),path=join(dir,'relay.lock');
  const server=createServer();await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));
  const port=(server.address() as {port:number}).port;
  try{await assert.rejects(()=>claimLocalRuntime(path,port));await assert.rejects(()=>readFile(path),{code:'ENOENT'});}
  finally{await new Promise<void>(r=>server.close(()=>r()));await rm(dir,{recursive:true,force:true});}
});

test('local stop requires POST, no browser Origin, and the existing service key',async()=>{
  let stopped=0;
  const server=createServer((_req,res)=>res.end('normal'));
  addLocalStopRoute(server,'b'.repeat(64),async()=>{stopped++;});
  await new Promise<void>(r=>server.listen(0,'127.0.0.1',r));
  const url=`http://127.0.0.1:${(server.address() as {port:number}).port}`;
  const auth={authorization:`Bearer ${'b'.repeat(64)}`};
  try{
    assert.equal(await (await fetch(url)).text(),'normal');
    assert.equal((await fetch(url+'/__local/stop')).status,403);
    assert.equal((await fetch(url+'/__local/stop',{method:'POST'})).status,403);
    assert.equal((await fetch(url+'/__local/stop',{method:'POST',headers:{...auth,origin:url}})).status,403);
    assert.equal(stopped,0);
    assert.equal((await fetch(url+'/__local/stop',{method:'POST',headers:auth})).status,202);
    await new Promise(r=>setImmediate(r));assert.equal(stopped,1);
  }finally{server.closeAllConnections();await new Promise<void>(r=>server.close(()=>r()));}
});
