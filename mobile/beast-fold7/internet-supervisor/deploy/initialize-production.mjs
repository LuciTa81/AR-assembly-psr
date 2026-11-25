import {randomBytes} from 'node:crypto';
import {existsSync,writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';

if(process.getuid()!==0)throw new Error('Run as root');
const file='/etc/ar-assembly/relay.env';
if(existsSync(file))throw new Error('Existing configuration preserved; refusing initialization');
function sql(input){
  const r=spawnSync('runuser',['-u','postgres','--','psql','-X','-v','ON_ERROR_STOP=1','-At'],{input,encoding:'utf8'});
  if(r.status!==0)throw new Error('PostgreSQL setup failed; inspect server locally');
  return r.stdout.trim();
}
if(sql("SELECT count(*) FROM pg_roles WHERE rolname='ar_supervisor';")!=='0'||
   sql("SELECT count(*) FROM pg_database WHERE datname='ar_supervisor';")!=='0')
  throw new Error('Existing role/database preserved; refusing initialization');
const password=randomBytes(32).toString('hex'),service=randomBytes(32).toString('hex');
sql(`CREATE ROLE ar_supervisor LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '${password}';`);
sql('CREATE DATABASE ar_supervisor OWNER ar_supervisor;');
sql('REVOKE ALL ON DATABASE ar_supervisor FROM PUBLIC;');
writeFileSync(file,[
  `DATABASE_URL=postgresql://ar_supervisor:${password}@127.0.0.1:5432/ar_supervisor`,
  'OWNER_GITHUB_ID=101696460',`SERVICE_KEY=${service}`,
  'WEB_ORIGIN=https://ar-assembly-supervisor.vercel.app',
  'HOST=127.0.0.1','PORT=8787','TRUSTED_PROXY=127.0.0.1','',
].join('\n'),{mode:0o600,flag:'wx'});
writeFileSync('/etc/ar-assembly/vercel-runtime.env',[
  'NEXTAUTH_URL=https://ar-assembly-supervisor.vercel.app',
  `NEXTAUTH_SECRET=${randomBytes(32).toString('hex')}`,
  'OWNER_GITHUB_ID=101696460','RELAY_HTTP_URL=https://54.116.139.37',
  `RELAY_SERVICE_KEY=${service}`,'',
].join('\n'),{mode:0o600,flag:'wx'});
console.log('AR database and root-only production configuration created; no secrets printed');
