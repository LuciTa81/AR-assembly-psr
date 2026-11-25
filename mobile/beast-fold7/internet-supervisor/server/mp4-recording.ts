import {Output,Mp4OutputFormat,FilePathTarget,EncodedVideoPacketSource,EncodedPacket} from 'mediabunny';
import type {AvcPacket} from '../shared/avc.ts';
export class Mp4Recording {
  private readonly source=new EncodedVideoPacketSource('avc');
  private readonly output:Output;
  private pending:AvcPacket|null=null;
  private first=0;private started=false;private closed=false;private codec='';
  constructor(path:string){
    this.output=new Output({format:new Mp4OutputFormat({fastStart:'fragmented',minimumFragmentDuration:1}),target:new FilePathTarget(path)});
    this.output.addVideoTrack(this.source);
  }
  private config(data:Uint8Array){
    for(let i=0;i<data.length-7;i++){
      if(data[i]!==0||data[i+1]!==0)continue;
      const n=data[i+2]===1?i+3:data[i+2]===0&&data[i+3]===1?i+4:-1;
      if(n>=0&&(data[n]&31)===7)return 'avc1.'+Buffer.from(data.subarray(n+1,n+4)).toString('hex');
    }
    throw new Error('Key frame lacks SPS');
  }
  async add(packet:AvcPacket){
    if(!this.started){
      if(!packet.key)throw new Error('Key frame required');
      this.codec=this.config(packet.data);this.first=packet.timestamp;
      await this.output.start();this.started=true;
    }
    if(packet.key&&this.config(packet.data)!==this.codec)throw new Error('Codec changed');
    if(this.pending){
      const duration=(packet.timestamp-this.pending.timestamp)/1e6;
      if(duration<=0||duration>1)throw new Error('Discontinuous timestamps');
      await this.write(this.pending,duration);
    }
    this.pending=packet;
  }
  private async write(packet:AvcPacket,duration:number){
    await this.source.add(new EncodedPacket(packet.data,packet.key?'key':'delta',(packet.timestamp-this.first)/1e6,duration),{
      decoderConfig:{codec:this.codec,codedWidth:1280,codedHeight:720},
    });
  }
  async finish(){
    if(!this.pending)throw new Error('Empty recording');
    await this.write(this.pending,1/30);this.pending=null;
    await this.output.finalize();this.closed=true;
  }
  async cancel(){if(!this.closed){await this.output.cancel();this.closed=true;}}
}
