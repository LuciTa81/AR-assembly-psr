import 'server-only';
export class RelayError extends Error {status:number;constructor(status:number){super('Relay unavailable');this.status=status;}}

export function relayConfig(){
  const base=new URL(process.env.RELAY_HTTP_URL??'http://127.0.0.1:8787');
  if(base.username||base.password||base.search||base.hash||base.pathname!=='/')throw new Error('Invalid relay URL');
  const local=['localhost','127.0.0.1'].includes(base.hostname);
  if(base.protocol!=='https:'&&!(local&&base.protocol==='http:'&&process.env.NODE_ENV!=='production'))throw new Error('Relay requires HTTPS');
  const secret=process.env.RELAY_SERVICE_KEY;
  if(!secret||! /^[a-f0-9]{64}$/.test(secret))throw new Error('Relay not configured');
  const ws=new URL('/ws',base);ws.protocol=base.protocol==='https:'?'wss:':'ws:';
  return {base:base.origin,secret,ws:ws.href};
}
export async function relayRequest(path:string,{method='GET',viewer,owner,body}:{method?:string;viewer?:string;owner?:string;body?:unknown}={}){
  const c=relayConfig();
  const response=await fetch(c.base+path,{method,body:body===undefined?undefined:JSON.stringify(body),headers:{Authorization:`Bearer ${c.secret}`,...(viewer?{'X-Viewer-Session':viewer}:{}),...(owner?{'X-Owner-Id':owner}:{}),...(body===undefined?{}:{'Content-Type':'application/json'})},
    cache:'no-store',redirect:'error',signal:AbortSignal.timeout(4500)});
  if(!response.ok)throw new RelayError(response.status);
  return response.json();
}
