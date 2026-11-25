import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readConfig} from '../server/config.ts';
const valid={DATABASE_URL:'postgres://ar:password@127.0.0.1:5432/ar',OWNER_GITHUB_ID:'12345',SERVICE_KEY:'a'.repeat(64),WEB_ORIGIN:'http://localhost:3000'};
test('recording accepts 10GB owner quota and 300MB files with bounded duration',()=>{
  const env={...valid,S3_RECORDING_BUCKET:'ar-test-recordings',AWS_REGION:'ap-northeast-2',RECORDING_ENABLED:'true',RECORDING_DIRECTORY:process.cwd(),RECORDING_FILE_BYTES:'300000000',RECORDING_OWNER_BYTES:'10000000000',RECORDING_MAX_SECONDS:'600',RECORDING_CONCURRENT:'1'};
  const config=readConfig(env);
  assert.deepEqual(config.recording?.capture,{directory:process.cwd(),fileBytes:300000000,ownerBytes:10000000000,seconds:600,concurrent:1});
  assert.equal(config.multiUser,false);
  for(const change of [{RECORDING_OWNER_BYTES:'10000000001'},{RECORDING_OWNER_BYTES:'299999999'},{RECORDING_MAX_SECONDS:'601'}])
    assert.throws(()=>readConfig({...env,...change}));
});
test('configuration requires explicit database, owner and secret',()=>{
  for(const key of Object.keys(valid))assert.throws(()=>readConfig({...valid,[key]:''}));
});
test('development binds loopback and remote deployment is not silently enabled',()=>{
  assert.equal(readConfig(valid).host,'127.0.0.1');
  assert.throws(()=>readConfig({...valid,HOST:'0.0.0.0'}));
  assert.throws(()=>readConfig({...valid,WEB_ORIGIN:'http://example.com'}));
  assert.throws(()=>readConfig({...valid,WEB_ORIGIN:'https://example.com/path'}));
  assert.throws(()=>readConfig({...valid,PORT:'nan'}));
});

test('proxy trust requires an explicit single loopback proxy',()=>{
  assert.equal(readConfig(valid).trustedProxy,undefined);
  assert.equal(readConfig({...valid,TRUSTED_PROXY:'127.0.0.1'}).trustedProxy,'127.0.0.1');
  for(const value of ['true','*','0.0.0.0','10.0.0.1'])assert.throws(()=>readConfig({...valid,TRUSTED_PROXY:value}));
});
test('paid recording is off by default and requires explicit storage and quotas',()=>{
  assert.equal(readConfig(valid).recording,undefined);
  assert.throws(()=>readConfig({...valid,RECORDING_ENABLED:'true'}));
  const storage={S3_RECORDING_BUCKET:'ar-test-recordings',AWS_REGION:'ap-northeast-2'};
  assert.equal(readConfig({...valid,...storage}).recording?.capture,undefined);
  assert.throws(()=>readConfig({...valid,...storage,RECORDING_ENABLED:'true'}));
  const r=readConfig({...valid,...storage,RECORDING_ENABLED:'true',RECORDING_DIRECTORY:'C:/ar-spool',RECORDING_FILE_BYTES:'20000000',RECORDING_OWNER_BYTES:'100000000',RECORDING_MAX_SECONDS:'600',RECORDING_CONCURRENT:'2'}).recording;
  assert.equal(r?.capture?.seconds,600);
});
