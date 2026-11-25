import NextAuth from 'next-auth';
import {authConfigured,authOptions,ownerSession} from '../../../../lib/auth';
import {guardSignOut} from '../../../../lib/signout';
import {relayRequest} from '../../../../lib/relay';
const handler=NextAuth(authOptions);
async function route(request:Request,context:{params:Promise<{nextauth:string[]}>}){
  if(!authConfigured())return Response.json({error:'로그인 설정이 필요해요'},{status:503});
  if(request.method==='POST'&&(await context.params).nextauth?.[0]==='signout'){
    const session=await ownerSession();
    const rejected=await guardSignOut(request.headers.get('origin'),process.env.NEXTAUTH_URL,session?.viewerSession,
      sid=>relayRequest(`/viewers/${sid}/revoke`,{method:'POST',owner:session?.ownerId,viewer:sid}));
    if(rejected)return rejected;
  }
  return handler(request,context);
}
export {route as GET,route as POST};
