import {randomUUID} from 'node:crypto';
import type {NextAuthOptions} from 'next-auth';
import {getServerSession} from 'next-auth';
import GithubProvider from 'next-auth/providers/github';
import {canSignIn} from './policy';
const allowed=(id:unknown)=>canSignIn(id,process.env.OWNER_GITHUB_ID,process.env.PUBLIC_GITHUB_LOGIN);

export function authConfigured(){return !!(process.env.GITHUB_ID&&process.env.GITHUB_SECRET&&process.env.NEXTAUTH_SECRET&&process.env.OWNER_GITHUB_ID);}
export const authOptions:NextAuthOptions={
  secret:process.env.NEXTAUTH_SECRET,
  providers:authConfigured()?[GithubProvider({clientId:process.env.GITHUB_ID!,clientSecret:process.env.GITHUB_SECRET!,authorization:{params:{scope:'read:user'}}})]:[],
  pages:{signIn:'/login',error:'/login'},session:{strategy:'jwt',maxAge:3600},
  callbacks:{
    async signIn({account,profile}){return account?.provider==='github'&&allowed(String((profile as {id?:number}|undefined)?.id??''));},
    async jwt({token,account,profile}){
      if(account){token.ownerId=String((profile as {id?:number}|undefined)?.id??'');token.viewerSession=randomUUID();}
      return token;
    },
    async session({session,token}){
      session.ownerId=allowed(token.ownerId)?String(token.ownerId):'';
      session.viewerSession=typeof token.viewerSession==='string'?token.viewerSession:'';
      return session;
    },
  },
};
export async function ownerSession(){
  if(!authConfigured())return null;
  const session=await getServerSession(authOptions);
  return session&&allowed(session.ownerId)&&/^[a-f0-9-]{36}$/.test(session.viewerSession)?session:null;
}
