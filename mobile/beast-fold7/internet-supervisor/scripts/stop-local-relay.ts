import {loadEnvFile} from 'node:process';
import {access} from 'node:fs/promises';
import {setTimeout} from 'node:timers/promises';

loadEnvFile(new URL('../web/.env.local',import.meta.url));
const url=new URL(process.env.RELAY_HTTP_URL??'http://127.0.0.1:8787');
const key=process.env.RELAY_SERVICE_KEY??'';
if(url.protocol!=='http:'||url.hostname!=='127.0.0.1'||!/^[a-f0-9]{64}$/.test(key))throw new Error('Local development only');
const response=await fetch(new URL('/__local/stop',url),{
  method:'POST',headers:{authorization:`Bearer ${key}`},signal:AbortSignal.timeout(5000),redirect:'error'
});
if(response.status!==202)throw new Error('Local stop was not accepted');
const lock=new URL('../.local/relay.lock',import.meta.url);
let closed=false;
for(let i=0;i<100;i++){
  try{await access(lock);}catch(error){
    if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;
    closed=true;break;
  }
  await setTimeout(100);
}
if(!closed)throw new Error('Database shutdown not confirmed; do not force-stop');
console.log('Local relay and database closed cleanly');
