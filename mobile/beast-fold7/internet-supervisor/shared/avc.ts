export const AVC_HEADER=21;
export const MAX_AVC_BYTES=256*1024;
export type AvcPacket={key:boolean;sequence:number;timestamp:number;data:Uint8Array};
export function parseAvc(bytes:Uint8Array):AvcPacket|null{
  if(bytes.length<=AVC_HEADER||bytes.length>MAX_AVC_BYTES||bytes[0]!==65||bytes[1]!==82||bytes[2]!==86||bytes[3]!==50||bytes[4]>1)return null;
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  const sequence=view.getUint32(5),timestamp=Number(view.getBigUint64(9));
  if(!sequence||!Number.isSafeInteger(timestamp)||view.getUint16(17)!==1280||view.getUint16(19)!==720)return null;
  const data=bytes.subarray(AVC_HEADER);let idr=false,sps=false,pps=false,slice=false,first=-1;
  for(let i=0;i<data.length-3;i++){
    if(data[i]!==0||data[i+1]!==0)continue;
    const start=data[i+2]===1?i+3:data[i+2]===0&&data[i+3]===1?i+4:-1;
    if(start<0)continue;if(start>=data.length)return null;
    if(first<0)first=i;
    const kind=data[start]&31;
    if(data[start]&128||kind===0||kind>23)return null;
    idr ||= kind===5;sps ||= kind===7;pps ||= kind===8;slice ||= kind===1||kind===5;i=start;
  }
  const key=bytes[4]===1;
  if(first!==0||!slice||key!==idr||(key&&(!sps||!pps)))return null;
  return {key,sequence,timestamp,data};
}
