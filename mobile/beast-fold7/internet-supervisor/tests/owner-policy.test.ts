import {test} from 'node:test';
import assert from 'node:assert/strict';
import {isOwner, safeOrigin,canSignIn} from '../web/lib/policy.ts';
test('public login accepts numeric GitHub identities only and is off by default',()=>{
  assert.equal(canSignIn('202','101'),false);
  assert.equal(canSignIn('202','101','true'),true);
  for(const id of ['',undefined,'LuciTa81','0','-10','2e3'])assert.equal(canSignIn(id,'101','true'),false);
  assert.equal(canSignIn('101','101'),true);
});
test('owner uses immutable GitHub numeric ID, not display name or email',()=>{
  assert.equal(isOwner('101696460','101696460'),true);
  for(const input of [undefined,'LuciTa81','other',101696460,''])assert.equal(isOwner(input,'101696460'),false);
  assert.equal(isOwner('',''),false);
});
test('mutation Origin must exactly match configured web origin',()=>{
  assert(safeOrigin('http://localhost:3000','http://localhost:3000'));
  for(const origin of [null,'https://evil.test','http://localhost:3000.evil.test','null'])assert(!safeOrigin(origin,'http://localhost:3000'));
});
