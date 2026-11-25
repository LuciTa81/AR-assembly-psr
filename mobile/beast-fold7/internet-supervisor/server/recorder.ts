import {mkdir,stat,unlink,writeFile,readdir} from 'node:fs/promises';
import {join} from 'node:path';
import type {Device} from './store.ts';
import type {Publish} from '../shared/protocol.ts';
import type {AvcPacket} from '../shared/avc.ts';
import {Mp4Recording} from './mp4-recording.ts';
import {RecordingQuotaError,RecordingLimitError,resumableReasons,type Recording} from './recordings.ts';
import {RecordingFiles} from './recording-files.ts';
export interface RecordingLimits {directory:string;fileBytes:number;ownerBytes:number;seconds:number;concurrent:number;}
type Job={device:Device;session:string;row?:Recording;mux?:Mp4Recording;path?:string;deadline?:ReturnType<typeof setTimeout>;recovery?:boolean;resumeBlocked?:boolean;chain:Promise<void>;queued:number;bytes:number;muxBytes:number;muxLast:number;sizeReached:boolean;first:number;last:number;startedAt:number;sequence:number;stopped:boolean;failed:boolean;reason:string;};
export class Recorder {
  readonly files:RecordingFiles;readonly limits:RecordingLimits;
  private jobs=new Map<string,Job>();private attempted=new Map<string,string>();
  private intents=new Map<string,{session:string;allowed:boolean}>();
  private pendingBlocks=new Set<Promise<void>>();
  private states=new Map<string,string>();private closing=false;
  constructor(files:RecordingFiles,limits:RecordingLimits){this.files=files;this.limits=limits;}
  async init(){
    await mkdir(this.limits.directory,{recursive:true,mode:0o700});
    // This spool is dedicated to a single relay process; interrupted uploads remain non-downloadable.
    await this.files.records.interrupted();
    for(const name of await readdir(this.limits.directory))if(/^[a-f0-9-]{36}\.mp4$/.test(name))await unlink(join(this.limits.directory,name));
    await this.files.cleanup();
  }
  status(device:string){return this.states.get(device)??'off';}
  state(device:Device,p:Publish){
    const job=this.jobs.get(device.id);
    const allowed=p.state.running&&p.state.video_available&&p.state.recording_consent===true;
    const previous=this.intents.get(device.id);
    this.intents.set(device.id,{session:p.state.session,allowed});
    if(previous?.allowed&&(!allowed||previous.session!==p.state.session)){
      this.attempted.set(device.id,previous.session);
      const block=this.files.records.blockResume(device.owner_id,device.id,previous.session).catch(()=>{this.states.set(device.id,'error');}).finally(()=>{this.pendingBlocks.delete(block);});
      this.pendingBlocks.add(block);
    }
    if(job&&(!allowed||job.session!==p.state.session))this.stop(device.id,allowed?'session_changed':'stopped');
    if(!job&&!allowed)this.states.set(device.id,'off');
    if(!job&&allowed&&this.attempted.get(device.id)!==p.state.session)this.states.set(device.id,['interrupted','recovering'].includes(this.status(device.id))?'recovering':'waiting');
  }
  offer(device:Device,p:Publish,packet:AvcPacket){
    if(this.closing||!p.state.running||!p.state.video_available||p.state.recording_consent!==true)return;
    if(!this.intents.has(device.id))this.intents.set(device.id,{session:p.state.session,allowed:true});
    const intent=this.intents.get(device.id)!;if(intent.session!==p.state.session||!intent.allowed)return;
    let job=this.jobs.get(device.id);
    if(!job){
      if(!packet.key||this.attempted.get(device.id)===p.state.session)return;
      if(this.jobs.size>=this.limits.concurrent){this.states.set(device.id,'busy');return;}
      this.attempted.set(device.id,p.state.session);
      job={device,session:p.state.session,chain:Promise.resolve(),queued:0,bytes:0,muxBytes:0,muxLast:packet.timestamp,sizeReached:false,first:packet.timestamp,last:packet.timestamp,startedAt:performance.now(),sequence:packet.sequence-1,stopped:false,failed:false,reason:'completed'};
      this.jobs.set(device.id,job);this.states.set(device.id,'starting');
      const current=job;
      current.chain=this.start(current).catch(error=>{current.failed=true;current.reason=error instanceof RecordingQuotaError?'quota_full':error instanceof RecordingLimitError?error.message:'error';this.stop(device.id,current.reason);});
    }
    if(job.stopped||job.session!==p.state.session)return;
    if(packet.sequence!==job.sequence+1||(job.bytes>0&&(packet.timestamp<=job.last||packet.timestamp-job.last>1000000))){this.stop(device.id,'stream_gap');return;}
    if(packet.timestamp-job.first>=this.limits.seconds*1e6||performance.now()-job.startedAt>=this.limits.seconds*1000){this.stop(device.id,'duration_limit');return;}
    if(job.queued>=16){this.stop(device.id,'slow_storage');return;}
    job.sequence=packet.sequence;job.last=packet.timestamp;job.bytes+=packet.data.length;job.queued++;
    const current=job,owned={...packet,data:Uint8Array.from(packet.data)};
    current.chain=current.chain.then(async()=>{
      if(current.failed||!current.mux||!current.row||current.sizeReached)return;
      // Queued frames must use the actual reservation once the database operation completes.
      if(current.muxBytes+owned.data.length>Number(current.row.bytes)-1024*1024){
        current.sizeReached=true;current.reason='size_limit';this.stop(device.id,'size_limit');return;
      }
      await current.mux.add(owned);current.muxBytes+=owned.data.length;current.muxLast=owned.timestamp;
    }).catch(()=>{current.failed=true;this.stop(device.id,'error');}).finally(()=>{current.queued--;});
  }
  private async start(job:Job){
    job.row=await this.files.records.begin(job.device.owner_id,job.device.id,job.session,this.limits.fileBytes,this.limits.ownerBytes,Date.now(),Math.min(this.limits.fileBytes,2*1024*1024),{seconds:this.limits.seconds});
    const remaining=job.row.deadline_ms!-Date.now();
    if(remaining<=0)throw new RecordingLimitError('duration_limit');
    job.path=join(this.limits.directory,`${job.row.id}.mp4`);
    await writeFile(job.path,'',{flag:'wx',mode:0o600});
    job.mux=new Mp4Recording(job.path);
    if(!job.stopped){
      job.deadline=setTimeout(()=>{if(this.jobs.get(job.device.id)===job)this.stop(job.device.id,'duration_limit');},remaining);job.deadline.unref();
      this.states.set(job.device.id,'capturing');
    }
  }
  stop(device:string,reason:string){
    const job=this.jobs.get(device);if(!job)return;
    if(job.stopped){if(!resumableReasons.has(reason))job.resumeBlocked=true;return;}
    clearTimeout(job.deadline);
    job.stopped=true;job.reason=reason;this.states.set(device,'saving');
    // Enqueue completion after accepted frames without blocking either WebSocket channel.
    const frames=job.chain;
    job.chain=frames.then(()=>this.finish(job)).catch(()=>{this.states.set(device,'error');}).finally(()=>{if(!job.recovery&&this.jobs.get(device)===job)this.jobs.delete(device);});
  }
  private async finish(job:Job){
    try{
      if(job.failed||!job.mux||!job.row||!job.path||!job.muxBytes)throw new Error('Capture failed');
      await job.mux.finish();
      const size=(await stat(job.path)).size;if(size>Number(job.row.bytes))throw new Error('File limit');
      await this.files.storage.put(job.row.object_key,job.path,size);
      await this.files.records.ready(job.row.id,size,Math.round((job.muxLast-job.first)/1000+1000/30),job.reason);
      const intent=this.intents.get(job.device.id);
      const resume=resumableReasons.has(job.reason)&&intent?.session===job.session&&intent.allowed&&!this.closing&&!job.resumeBlocked;
      if(!resume)await this.files.records.blockResume(job.device.owner_id,job.device.id,job.session);
      if(resume&&this.attempted.get(job.device.id)===job.session)this.attempted.delete(job.device.id);
      this.states.set(job.device.id,resume?'interrupted':job.reason.endsWith('_limit')?'limit':'saved');
    }catch{
      await job.mux?.cancel().catch(()=>{});
      if(job.row){
        // Hide failed uploads before retrying their deletion; never free quota until S3 confirms removal.
        try{await this.files.records.abandon(job.row.id);}catch(error){job.recovery=true;throw error;}
        try{await this.files.storage.remove(job.row.object_key);await this.files.records.removed(job.row.id);}catch{}
      }
      this.states.set(job.device.id,job.reason==='quota_full'?'quota_full':job.reason.endsWith('_limit')?'limit':'error');
    }finally{if(job.path)await unlink(job.path).catch(()=>{});}
  }
  async recover(){
    for(const [id,job] of this.jobs)if(job.recovery&&job.row){
      try{await job.chain;await this.files.records.abandon(job.row.id);job.recovery=false;if(this.jobs.get(id)===job)this.jobs.delete(id);}catch{}
    }
  }
  async close(){this.closing=true;for(const id of this.jobs.keys())this.stop(id,'server_stop');await Promise.all([...this.jobs.values()].map(j=>j.chain));await Promise.all(this.pendingBlocks);await this.recover();}
}
