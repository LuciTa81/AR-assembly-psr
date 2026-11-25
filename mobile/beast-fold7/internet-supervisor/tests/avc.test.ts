import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseAvc,MAX_AVC_BYTES} from '../shared/avc.ts';
import {avc} from './avc-fixture.ts';
test('AVC packet bounds, order metadata and key parameter sets',()=>{
 assert.equal(parseAvc(avc())?.key,true);assert.equal(parseAvc(avc(2,false))?.sequence,2);
 const bad=avc();bad[17]=10;assert.equal(parseAvc(bad),null);
 const missing=avc(1,false);missing[4]=1;assert.equal(parseAvc(missing),null);
 const forged=avc();forged[4]=0;assert.equal(parseAvc(forged),null);
 assert.equal(parseAvc(avc(0)),null);assert.equal(parseAvc(Buffer.alloc(MAX_AVC_BYTES+1)),null);
});
