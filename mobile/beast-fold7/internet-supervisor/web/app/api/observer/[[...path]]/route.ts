import {ownerSession} from '../../../../lib/auth';
import {relayConfig,relayRequest,RelayError} from '../../../../lib/relay';
import {safeOrigin} from '../../../../lib/policy';
import {readPairingInput} from '../../../../lib/pairing-input';
export const dynamic='force-dynamic';
async function route(req:Request,ctx:{params:Promise<{path?:string[]}>}){
  const session=await ownerSession();
  const reply=(data:unknown,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
  if(!session)return reply({error:'로그인이 필요해요'},401);
  if(req.method==='POST'&&!safeOrigin(req.headers.get('origin'),process.env.NEXTAUTH_URL))return reply({error:'허용되지 않은 요청이에요'},403);
  const p=(await ctx.params).path??[];
  const identity={viewer:session.viewerSession,owner:session.ownerId};
  try{
    if(req.method==='POST'&&p.length===2&&p[0]==='pairing'&&(p[1]==='lookup'||p[1]==='approve')){
      let body;try{body=await readPairingInput(req,p[1]);}catch{return reply({error:'연결 코드를 확인해 주세요'},400);}
      return reply(await relayRequest(`/pairing/${p[1]}`,{method:'POST',...identity,body}));
    }
    if(req.method==='GET'&&p.length===1&&p[0]==='devices')return reply(await relayRequest('/devices',identity));
    if(req.method==='POST'&&p.length===3&&p[0]==='recordings'&&/^[a-f0-9-]{36}$/.test(p[1])&&['download','delete'].includes(p[2]))
      return reply(await relayRequest(`/recordings/${p[1]}/${p[2]}`,{method:'POST',...identity}));
    if(req.method==='POST'&&p.length===1&&p[0]==='logout'){
      await relayRequest(`/viewers/${session.viewerSession}/revoke`,{method:'POST',...identity});return reply({ok:true});
    }
    if(p.length===3&&p[0]==='devices'&&/^[a-f0-9-]{36}$/.test(p[1])){
      const action=p[2];
      if(req.method==='GET'&&['history','recordings'].includes(action)){
        const work=new URL(req.url).searchParams.get('session');
        if(action==='history'&&work!==null&&!/^[a-zA-Z0-9_-]{1,128}$/.test(work))return reply({error:'작업을 확인해 주세요'},400);
        const query=action==='history'&&work!==null?`?session=${encodeURIComponent(work)}`:'';
        return reply(await relayRequest(`/devices/${p[1]}/${action}${query}`,identity));
      }
      if(req.method==='POST'&&action==='ticket'){
        const data=await relayRequest(`/devices/${p[1]}/ticket`,{method:'POST',...identity});
        return reply({...data,url:relayConfig().ws});
      }
      if(req.method==='POST'&&action==='revoke')return reply(await relayRequest(`/devices/${p[1]}/revoke`,{method:'POST',...identity}));
    }
    return reply({error:'요청을 찾을 수 없어요'},404);
  }catch(e){
    if(e instanceof RelayError){
      if(e.status===401)return reply({error:'다시 로그인해 주세요'},401);
      if(e.status===404)return reply({error:'파일이 만료되었거나 접근할 수 없어요'},404);
      if(e.status===410)return reply({error:'코드가 만료되었거나 이미 사용됐어요. 휴대폰에서 새 코드를 받아 주세요.'},410);
      if(e.status===429)return reply({error:'요청이 많아요. 잠시 후 다시 시도해 주세요.'},429);
    }
    return reply({error:'관제 서버에 연결하지 못했어요'},503);
  }
}
export {route as GET,route as POST};
