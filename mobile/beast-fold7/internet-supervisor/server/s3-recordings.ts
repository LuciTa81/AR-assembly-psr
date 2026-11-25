import {createReadStream} from 'node:fs';
import {S3Client,PutObjectCommand,DeleteObjectCommand,GetObjectCommand} from '@aws-sdk/client-s3';
import {getSignedUrl} from '@aws-sdk/s3-request-presigner';
import type {ObjectStorage} from './recording-files.ts';
const validKey=(key:string)=>{
  if(!/^recordings\/[1-9][0-9]{0,19}\/[a-f0-9-]{36}\/[a-f0-9-]{36}\.mp4$/.test(key))throw new Error('Invalid recording key');
};
export function s3Recordings(bucket:string,region:string,client=new S3Client({region,maxAttempts:2})):ObjectStorage{
  return {
    async put(key,path,bytes){
      validKey(key);const body=createReadStream(path);
      try{await client.send(new PutObjectCommand({Bucket:bucket,Key:key,Body:body,ContentLength:bytes,ContentType:'video/mp4',ServerSideEncryption:'AES256'}),{abortSignal:AbortSignal.timeout(60000)});}finally{body.destroy();}
    },
    async remove(key){validKey(key);await client.send(new DeleteObjectCommand({Bucket:bucket,Key:key}),{abortSignal:AbortSignal.timeout(10000)});},
    async download(key,seconds,signingMs){
      validKey(key);
      if(!Number.isInteger(seconds)||seconds<1||seconds>60)throw new Error('Invalid link lifetime');
      return getSignedUrl(client,new GetObjectCommand({Bucket:bucket,Key:key,ResponseContentType:'video/mp4',ResponseContentDisposition:`attachment; filename="AR-Assembly-${key.split('/').at(-1)}"`}),{expiresIn:seconds,signingDate:new Date(signingMs)});
    },
  };
}
