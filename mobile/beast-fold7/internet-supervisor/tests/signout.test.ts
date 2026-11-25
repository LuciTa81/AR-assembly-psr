import {test} from 'node:test';
import assert from 'node:assert/strict';
import {guardSignOut} from '../web/lib/signout.ts';
const origin='http://localhost:3000';
test('failed remote revocation blocks cookie-clearing signout',async()=>{
  const response=await guardSignOut(origin,origin,'viewer',async()=>{throw new Error('unavailable');});
  assert.equal(response?.status,503);assert.equal(response?.headers.get('set-cookie'),null);
});
test('signout requires same Origin and awaits successful revocation',async()=>{
  let called=false;const revoke=async()=>{called=true;};
  assert.equal((await guardSignOut('https://evil.invalid',origin,'viewer',revoke))?.status,403);assert(!called);
  assert.equal(await guardSignOut(origin,origin,'viewer',revoke),null);assert(called);
});
