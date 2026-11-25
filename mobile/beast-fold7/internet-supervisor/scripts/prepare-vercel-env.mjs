import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {parseEnv} from 'node:util';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const file=resolve(root,'.local/production-handoff/vercel-production.env');
if(existsSync(file))throw new Error('Existing handoff file preserved');
const local=parseEnv(readFileSync(resolve(root,'web/.env.local'),'utf8'));
if(!local.GITHUB_ID||!local.GITHUB_SECRET)throw new Error('Local OAuth configuration missing');
const remote=execFileSync('ssh',['-i',resolve(root,'.local/ssh/nova.pem'),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
  'ubuntu@54.116.139.37','sudo cat /etc/ar-assembly/vercel-runtime.env'],{encoding:'utf8',stdio:['ignore','pipe','pipe']});
const config=parseEnv(remote);
if(config.NEXTAUTH_URL!=='https://ar-assembly-supervisor.vercel.app'||! /^[a-f0-9]{64}$/.test(config.RELAY_SERVICE_KEY??''))
  throw new Error('Unexpected remote configuration');
config.GITHUB_ID=local.GITHUB_ID;config.GITHUB_SECRET=local.GITHUB_SECRET;
const expected=['NEXTAUTH_URL','NEXTAUTH_SECRET','OWNER_GITHUB_ID','RELAY_HTTP_URL','RELAY_SERVICE_KEY','GITHUB_ID','GITHUB_SECRET'];
if(Object.keys(config).length!==expected.length)throw new Error('Unexpected environment variable');
writeFileSync(file,expected.map(k=>`${k}=${JSON.stringify(config[k])}`).join('\n')+'\n',{flag:'wx',mode:0o600});
console.log('Prepared seven production variables in the access-restricted handoff file; no values printed');
