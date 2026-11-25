import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readPairingInput} from '../web/lib/pairing-input.ts';
const req=(body:string)=>new Request('http://localhost/pairing',{method:'POST',headers:{'Content-Type':'application/json'},body});
test('pairing BFF accepts only a bound code and request id',async()=>{
  assert.deepEqual(await readPairingInput(req('{"code":"ABCDEFGH"}'),'lookup'),{code:'ABCDEFGH'});
  const value={code:'ABCDEFGH',request_id:'12345678-1234-4123-8123-123456789abc'};
  assert.deepEqual(await readPairingInput(req(JSON.stringify(value)),'approve'),value);
  for(const value of [{code:'abcdefgh'},{code:'1234'},{code:'ABCDEFGH',token:'secret'}])await assert.rejects(readPairingInput(req(JSON.stringify(value)),'lookup'));
  await assert.rejects(readPairingInput(req('{"code":"ABCDEFGH"}'),'approve'));
});
test('pairing BFF bounds the actual body, including streams without a content length',async()=>{
  await assert.rejects(readPairingInput(req('x'.repeat(2049)),'lookup'));
  await assert.rejects(readPairingInput(req('{bad'),'lookup'));
  await assert.rejects(readPairingInput(new Request('http://localhost',{method:'POST',body:'{}'}),'lookup'));
});
