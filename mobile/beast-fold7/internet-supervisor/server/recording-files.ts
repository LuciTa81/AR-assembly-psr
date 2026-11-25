import {Recordings} from './recordings.ts';
import {AccessError} from './store.ts';
export interface ObjectStorage {
  put(key:string,path:string,bytes:number):Promise<void>;
  remove(key:string):Promise<void>;
  download(key:string,seconds:number,signingMs:number):Promise<string>;
}
export class RecordingFiles {
  readonly records:Recordings;readonly storage:ObjectStorage;private clock:()=>number;
  constructor(records:Recordings,storage:ObjectStorage,clock=Date.now){this.records=records;this.storage=storage;this.clock=clock;}
  async download(owner:string,id:string,testNow?:number){
    const clock=testNow===undefined?this.clock:()=>testNow;
    const r=await this.records.downloadable(owner,id,clock());
    const now=clock(),seconds=Math.min(60,Math.floor((Number(r.expires_ms)-now)/1000));
    if(seconds<1)throw new AccessError('Not found');
    const expires=now+seconds*1000,url=await this.storage.download(r.object_key,seconds,now);
    if(clock()>=expires)throw new AccessError('Not found');
    return {url,expires_ms:expires};
  }
  async remove(owner:string,id:string){
    const r=await this.records.get(owner,id);
    await this.records.markDeleting(owner,id);
    await this.storage.remove(r.object_key);
    await this.records.removed(id);
  }
  async cleanup(now=Date.now()){
    let failed=0;
    for(const r of await this.records.expired(now)){
      try{
        if(r.status==='ready')await this.records.markDeleting(r.owner_id,r.id);
        await this.storage.remove(r.object_key);await this.records.removed(r.id);
      }catch{failed++;}
    }
    return {failed};
  }
}
