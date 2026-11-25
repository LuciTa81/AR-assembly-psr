import {open,readFile,unlink} from 'node:fs/promises';
import {createServer} from 'node:net';
import {createHash,randomUUID,timingSafeEqual} from 'node:crypto';
import type {Server} from 'node:http';

// A stale lock fails closed: do not guess whether its database is safe to reopen.
export async function claimLocalRuntime(path:string,port:number){
  const handle=await open(path,'wx');
  const value=JSON.stringify({pid:process.pid,id:randomUUID()});
  await handle.writeFile(value);await handle.close();
  let released=false;
  async function release(){
    if(released)return;
    if(await readFile(path,'utf8')!==value)throw new Error('Local runtime lock changed');
    await unlink(path);released=true;
  }
  const probe=createServer();
  try{
    await new Promise<void>((resolve,reject)=>{
      probe.once('error',reject);probe.listen(port,'127.0.0.1',resolve);
    });
    await new Promise<void>((resolve,reject)=>probe.close(e=>e?reject(e):resolve()));
    return release;
  }catch(error){await release();throw error;}
}

export function addLocalStopRoute(server:Server,key:string,stop:()=>Promise<void>){
  const normal=server.listeners('request');
  const digest=(v:string)=>createHash('sha256').update(v).digest();
  server.removeAllListeners('request');
  server.on('request',(req,res)=>{
    if(req.url!=='/__local/stop'){
      for(const listener of normal)listener.call(server,req,res);
      return;
    }
    if(req.method!=='POST'||req.headers.origin||
      !timingSafeEqual(digest(req.headers.authorization??''),digest(`Bearer ${key}`))){
      res.writeHead(403);res.end();return;
    }
    res.once('finish',()=>setImmediate(()=>void stop().catch(()=>{
      console.error('Local shutdown failed; runtime lock retained');process.exitCode=1;
    })));
    res.writeHead(202,{'Content-Type':'application/json','Cache-Control':'no-store'});
    res.end('{"stopping":true}');
  });
}
