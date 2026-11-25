// Local OAuth integration only. Production uses server/main.ts and PostgreSQL.
import {loadEnvFile} from 'node:process';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {PGlite} from '@electric-sql/pglite';
import {Store} from '../server/store.ts';
import {createRelay} from '../server/relay.ts';
import {claimLocalRuntime,addLocalStopRoute} from './local-lifecycle.ts';

loadEnvFile(new URL('../web/.env.local',import.meta.url));
if(process.env.NODE_ENV==='production')throw new Error('Local development only');
const owner=process.env.OWNER_GITHUB_ID??'',key=process.env.RELAY_SERVICE_KEY??'';
const origin=new URL(process.env.NEXTAUTH_URL??'http://localhost:3000');
const url=new URL(process.env.RELAY_HTTP_URL??'http://127.0.0.1:8787');
if(!/^\d+$/.test(owner)||!/^[a-f0-9]{64}$/.test(key)||url.hostname!=='127.0.0.1'||url.protocol!=='http:'||!['localhost','127.0.0.1'].includes(origin.hostname))throw new Error('Invalid local configuration');
const folder=fileURLToPath(new URL('../.local/database-v2-20261124',import.meta.url));
await mkdir(folder,{recursive:true});
const release=await claimLocalRuntime(fileURLToPath(new URL('../.local/relay.lock',import.meta.url)),Number(url.port));
let db:PGlite|undefined,relay:ReturnType<typeof createRelay>|undefined,closing:Promise<void>|undefined;
function stop(){return closing??=(async()=>{
  await relay?.close();await db?.close();await release();
})();}
process.on('SIGINT',()=>void stop());process.on('SIGTERM',()=>void stop());
try{
  db=new PGlite(folder);const store=new Store(db);await store.init();
  relay=createRelay(store,{ownerId:owner,serviceKey:key,origins:[origin.origin]});
  addLocalStopRoute(relay.server,key,stop);
  await new Promise<void>((resolve,reject)=>{
    relay!.server.once('error',reject);relay!.server.listen(Number(url.port),'127.0.0.1',resolve);
  });
  console.log('Local relay ready; no phone or camera activated');
}catch(error){
  console.error('Local relay startup failed; data retained');
  try{await stop();}catch{console.error('Database close failed; runtime lock retained');}
  process.exitCode=1;
}
