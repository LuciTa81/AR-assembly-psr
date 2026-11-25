import type {IncomingMessage,ServerResponse} from 'node:http';
import {createHash,timingSafeEqual} from 'node:crypto';
import {z} from 'zod';
import {Pairing,PairingError,codeSchema} from './pairing.ts';
import {AccessError,type Store} from './store.ts';
import {requestOwner} from './owner.ts';

const digest=(s:string)=>createHash('sha256').update(s).digest();
const requestSchema=z.strictObject({name:z.string()});
const lookupSchema=z.strictObject({code:codeSchema});
const approveSchema=lookupSchema.extend({request_id:z.string().uuid()});
async function json(req:IncomingMessage){
  if(req.headers['content-type']?.split(';')[0].trim()!=='application/json')throw new PairingError(400);
  let bytes=0;const chunks:Buffer[]=[];
  try{
    for await(const value of req.iterator({destroyOnReturn:false})){
      const chunk=Buffer.from(value);bytes+=chunk.length;
      if(bytes>2048)throw new PairingError(413);chunks.push(chunk);
    }
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  }catch(e){req.resume();if(e instanceof PairingError)throw e;throw new PairingError(400);}
}
export function pairingHandler(store:Store,key:string,fallbackOwner:string,clock:()=>number,multiUser=false){
  const pairing=new Pairing(store,key),buckets=new Map<string,{at:number;count:number}>();
  return async(req:IncomingMessage,res:ServerResponse,ip=req.socket.remoteAddress??'unknown')=>{
    const action=/^\/pairing\/(request|poll|lookup|approve)$/.exec(req.url??'')?.[1];if(!action)return false;
    const reply=(status:number,body:unknown)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(body));};
    if(req.method!=='POST'){reply(405,{error:'method_not_allowed'});return true;}
    if(req.headers.origin){reply(403,{error:'server_or_phone_only'});return true;}
    const now=clock();for(const [id,b] of buckets)if(now-b.at>=60000)buckets.delete(id);
    const group=action==='lookup'||action==='approve'?'approval':action;
    const bucketId=`${ip}:${group}`;
    if(!buckets.has(bucketId)){
      if(buckets.size>=1024){reply(429,{error:'rate_limited'});return true;}
      buckets.set(bucketId,{at:now,count:0});
    }
    const limit=group==='request'?5:group==='poll'?60:10;
    if(++buckets.get(bucketId)!.count>limit){reply(429,{error:'rate_limited'});return true;}
    try{
      let owner=fallbackOwner;
      if(group==='approval'){
        const sid=req.headers['x-viewer-session'];
        if(!timingSafeEqual(digest(req.headers.authorization??''),digest(`Bearer ${key}`))||typeof sid!=='string'||! /^[a-f0-9-]{36}$/.test(sid)){
          reply(401,{error:'unauthorized'});return true;
        }
        const resolved=requestOwner(req.headers,fallbackOwner,multiUser);
        if(!resolved){reply(401,{error:'unauthorized'});return true;}owner=resolved;
        try{await store.checkViewer(owner,sid);}catch(e){if(e instanceof AccessError){reply(401,{error:'session_revoked'});return true;}throw e;}
      }
      if(action==='request'){const data=requestSchema.parse(await json(req));reply(200,await pairing.request(data.name));}
      else if(action==='poll'){
        const token=/^Bearer ([a-f0-9]{64})$/.exec(req.headers.authorization??'')?.[1];
        if(!token)throw new PairingError(410);
        if(req.headers['transfer-encoding']||Number(req.headers['content-length']??0)!==0){req.resume();throw new PairingError(400);}
        reply(200,await pairing.poll(token));
      }
      else if(action==='lookup'){const data=lookupSchema.parse(await json(req));reply(200,await pairing.lookup(data.code));}
      else{const data=approveSchema.parse(await json(req));reply(200,await pairing.approve(owner,data.code,data.request_id,req.headers['x-viewer-session'] as string));}
    }catch(e){const status=e instanceof PairingError?e.status:e instanceof z.ZodError?400:503;reply(status,{error:status===410?'expired_or_unavailable':status===429?'rate_limited':status===400?'invalid_request':'unavailable'});}
    return true;
  };
}
