import {readFile,writeFile} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
const path=new URL('../web/.env.local',import.meta.url);
const example=await readFile(new URL('../web/.env.example',import.meta.url),'utf8');
try{
  await writeFile(path,example.replace('NEXTAUTH_SECRET=','NEXTAUTH_SECRET='+randomBytes(32).toString('hex')).replace('RELAY_SERVICE_KEY=','RELAY_SERVICE_KEY='+randomBytes(32).toString('hex')),{flag:'wx',mode:0o600});
  console.log('Created web/.env.local. Enter GITHUB_ID and GITHUB_SECRET locally. No secret values printed.');
}catch(error){if((error as NodeJS.ErrnoException).code==='EEXIST')console.log('web/.env.local already exists; left unchanged.');else throw error;}
