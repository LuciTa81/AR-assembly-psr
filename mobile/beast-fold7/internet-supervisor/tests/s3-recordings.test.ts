import {test} from 'node:test';
import assert from 'node:assert/strict';
import {S3Client} from '@aws-sdk/client-s3';
import {s3Recordings} from '../server/s3-recordings.ts';
test('S3 signing anchors its expiration to the authorization time without contacting AWS',async()=>{
  const client=new S3Client({region:'ap-northeast-2',credentials:{accessKeyId:'TESTONLYACCESSKEY',secretAccessKey:'test-only-not-a-real-credential'}});
  try{
    const storage=s3Recordings('ar-unit-test','ap-northeast-2',client);
    const key='recordings/101/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-000000000002.mp4';
    const url=new URL(await storage.download(key,5,Date.UTC(2026,10,25,0,0,0,999)));
    assert.equal(url.searchParams.get('X-Amz-Date'),'20261125T000000Z');assert.equal(url.searchParams.get('X-Amz-Expires'),'5');
    await assert.rejects(()=>storage.download('outside/file.mp4',5,Date.now()));
  }finally{client.destroy();}
});
