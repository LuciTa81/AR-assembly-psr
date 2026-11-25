import {Pool} from 'pg';
import {readConfig} from './config.ts';
import {Store,type Database} from './store.ts';
import {createRelay} from './relay.ts';
import {Recordings} from './recordings.ts';
import {RecordingFiles} from './recording-files.ts';
import {s3Recordings} from './s3-recordings.ts';
import {Recorder} from './recorder.ts';

async function main(){
  const config=readConfig(process.env);
  const pool=new Pool({connectionString:config.databaseUrl,max:4,connectionTimeoutMillis:3000,statement_timeout:3000,query_timeout:4000});
  pool.on('error',()=>console.error('Database connection unavailable'));
  const db:Database={async query<T>(text:string,params?:unknown[]){const r=await pool.query(text,params);return {rows:r.rows as T[]};}};
  const store=new Store(db);
  try{await store.init();}catch{await pool.end();throw new Error('Database initialization failed');}
  const files=config.recording?new RecordingFiles(new Recordings(store),s3Recordings(config.recording.bucket,config.recording.region)):undefined;
  const recorder=files&&config.recording?.capture?new Recorder(files,config.recording.capture):undefined;
  try{
    if(recorder)await recorder.init();
    else if(files){await files.records.interrupted();await files.cleanup();}
  }catch{await pool.end();throw new Error('Recording initialization failed');}
  const relay=createRelay(store,config,files?{files,recorder}:undefined);
  let cleanup:Promise<unknown>|undefined;
  const retention=setInterval(()=>{
    if(files&&!cleanup)cleanup=(async()=>{await recorder?.recover();const result=await files.cleanup();if(result.failed)console.error('Recording deletion pending retry');})().catch(()=>console.error('Recording cleanup unavailable')).finally(()=>{cleanup=undefined;});
  },60000);retention.unref();
  relay.server.on('error',async()=>{console.error('Relay listener failed');await stop();process.exitCode=1;});
  relay.server.listen(config.port,config.host,()=>console.log(`Relay listening at http://${config.host}:${config.port}; no camera or phone connection started`));
  let stopping=false;
  async function stop(){if(stopping)return;stopping=true;clearInterval(retention);await relay.close();await cleanup;await pool.end();}
  process.once('SIGINT',()=>void stop());process.once('SIGTERM',()=>void stop());
}
main().catch(()=>{console.error('Startup failed: check required configuration and database availability');process.exitCode=1;});
