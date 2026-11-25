import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseWire,currentState} from '../web/lib/wire.ts';
import {publish} from './fixture.ts';
test('recording quota failure does not invalidate an otherwise live AR connection',()=>{
  const packet=parseWire({type:'state',status:'live',snapshot:publish(),received_at_ms:1000,history_status:'ok',recording_status:'quota_full'});
  assert.equal(packet.recording_status,'quota_full');assert.equal(currentState(packet,0)?.stage,2);
});

test('recording availability and recording limits do not change AR state',()=>{
  for(const enabled of [false,true]){
    const packet=parseWire({type:'state',status:'live',snapshot:publish(),received_at_ms:1000,history_status:'ok',recording_enabled:enabled,recording_status:'limit'});
    assert.equal(packet.recording_enabled,enabled);
    assert.equal(currentState(packet,0)?.stage,2);
  }
});
test('stale/offline and silent connections never supply current green guidance',()=>{
  const wire={type:'state',status:'live',snapshot:publish(),received_at_ms:1000,history_status:'ok'};
  assert.equal(currentState(parseWire(wire),0)?.stage,2);
  assert.equal(currentState(parseWire(wire),3501),null);
  for(const status of ['stale','offline','waiting'])assert.equal(currentState(parseWire({...wire,status}),0),null);
});
test('wire rejects untrusted action shape and a fake completion flag',()=>{
  assert.throws(()=>parseWire({type:'state',status:'live',snapshot:{...publish(),state:{...publish().state,fastening_verified:true}}}));
});
