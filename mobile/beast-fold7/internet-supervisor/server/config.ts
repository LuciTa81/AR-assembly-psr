import {z} from 'zod';
import {isAbsolute} from 'node:path';
import type {RecordingLimits} from './recorder.ts';
export function readConfig(env:Record<string,string|undefined>){
  const parsed=z.object({
    DATABASE_URL:z.string().url().regex(/^postgres(ql)?:\/\//),
    OWNER_GITHUB_ID:z.string().regex(/^\d+$/),SERVICE_KEY:z.string().regex(/^[a-f0-9]{64}$/),
    WEB_ORIGIN:z.string().url(),HOST:z.literal('127.0.0.1').default('127.0.0.1'),
    PORT:z.coerce.number().int().min(1024).max(65535).default(8787),
    TRUSTED_PROXY:z.literal('127.0.0.1').optional(),
    MULTI_USER:z.enum(['true','false']).default('false'),
    RECORDING_ENABLED:z.enum(['true','false']).default('false'),
  }).parse(env);
  const origin=new URL(parsed.WEB_ORIGIN);
  if(origin.origin!==parsed.WEB_ORIGIN || (origin.protocol!=='https:'&&!['http://localhost:3000','http://127.0.0.1:3000'].includes(origin.origin)))
    throw new Error('WEB_ORIGIN must be an HTTPS origin or a loopback development origin');
  let recording:{bucket:string;region:string;capture?:RecordingLimits}|undefined;
  if(env.S3_RECORDING_BUCKET||parsed.RECORDING_ENABLED==='true'){
    const storage=z.object({S3_RECORDING_BUCKET:z.string().regex(/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/),AWS_REGION:z.string().regex(/^[a-z]{2}-[a-z]+-\d$/)}).parse(env);
    recording={bucket:storage.S3_RECORDING_BUCKET,region:storage.AWS_REGION};
    if(parsed.RECORDING_ENABLED==='true'){
      const c=z.object({RECORDING_DIRECTORY:z.string().refine(isAbsolute),RECORDING_FILE_BYTES:z.coerce.number().int().min(2*1024*1024).max(512*1024*1024),RECORDING_OWNER_BYTES:z.coerce.number().int().positive().max(10_000_000_000),RECORDING_MAX_SECONDS:z.coerce.number().int().min(1).max(600),RECORDING_CONCURRENT:z.coerce.number().int().min(1).max(4)}).parse(env);
      if(c.RECORDING_OWNER_BYTES<c.RECORDING_FILE_BYTES)throw new Error('Owner quota below file reservation');
      recording.capture={directory:c.RECORDING_DIRECTORY,fileBytes:c.RECORDING_FILE_BYTES,ownerBytes:c.RECORDING_OWNER_BYTES,seconds:c.RECORDING_MAX_SECONDS,concurrent:c.RECORDING_CONCURRENT};
    }
  }
  return {databaseUrl:parsed.DATABASE_URL,ownerId:parsed.OWNER_GITHUB_ID,serviceKey:parsed.SERVICE_KEY,
    origins:[parsed.WEB_ORIGIN],host:parsed.HOST,port:parsed.PORT,trustedProxy:parsed.TRUSTED_PROXY,multiUser:parsed.MULTI_USER==='true',recording};
}
