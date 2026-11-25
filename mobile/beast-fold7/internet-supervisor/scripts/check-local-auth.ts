// Exercises the running local BFF with isolated signed test sessions, never OAuth credentials.
import assert from 'node:assert/strict';
import {loadEnvFile} from 'node:process';
import {randomUUID} from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../web/package.json',import.meta.url));
const {encode}=require('next-auth/jwt');
loadEnvFile(new URL('../web/.env.local',import.meta.url));
const base=new URL(process.env.NEXTAUTH_URL??'http://localhost:3000');
assert(['localhost','127.0.0.1'].includes(base.hostname)&&base.protocol==='http:','Local checks only');
const secret=process.env.NEXTAUTH_SECRET,ownerId=process.env.OWNER_GITHUB_ID;
assert(secret&&ownerId);
async function cookie(owner=ownerId,maxAge=3600){
  const token=await encode({secret,maxAge,token:{ownerId:owner,viewerSession:randomUUID()}});
  return `next-auth.session-token=${token}`;
}
async function request(path:string,cookie='',method='GET',origin=base.origin){
  return fetch(new URL('/api/observer/'+path,base),{method,redirect:'manual',headers:{Cookie:cookie,...(method==='POST'?{Origin:origin}:{})}});
}
assert.equal((await request('devices')).status,401);
assert.equal((await request('devices',await cookie('not-owner'))).status,401);
assert.equal((await request('devices',await cookie(ownerId,-600))).status,401);
const session=await cookie();
const list=await request('devices',session);assert.equal(list.status,200);
assert.equal(list.headers.get('cache-control'),'no-store');
for(const device of (await list.json()).devices)assert.deepEqual(Object.keys(device).sort(),['id','name','revoked']);
assert.equal((await request('logout',session,'POST','https://untrusted.invalid')).status,403);
assert.equal((await request('devices',session)).status,200);
assert.equal((await request('logout',session,'POST')).status,200);
assert.equal((await request('devices',session)).status,401);
assert.equal((await request('devices/'+randomUUID()+'/history',session)).status,401);
const next=await cookie();assert.equal((await request('devices',next)).status,200);
const csrfResponse=await fetch(new URL('/api/auth/csrf',base));
const csrf=(await csrfResponse.json()).csrfToken;
const csrfCookies=csrfResponse.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');
const signout=await fetch(new URL('/api/auth/signout',base),{method:'POST',redirect:'manual',
  headers:{Cookie:`${next}; ${csrfCookies}`,Origin:base.origin,'Content-Type':'application/x-www-form-urlencoded'},
  body:new URLSearchParams({csrfToken:csrf,callbackUrl:new URL('/login',base).href,json:'true'})});
assert.equal(signout.status,200);
assert.equal((await request('devices',next)).status,401);
console.log('PASS: local BFF anonymous/wrong-owner/expired denial, metadata-only response, Origin rejection, logout revocation, new-session access and NextAuth default signout. No real user session changed.');
