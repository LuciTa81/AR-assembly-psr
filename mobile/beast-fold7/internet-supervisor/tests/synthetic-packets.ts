import {readFile} from 'node:fs/promises';
export async function syntheticPackets(predictive=false){
  const bytes=await readFile(new URL(predictive?'./synthetic-predictive.h264':'./synthetic-recording.h264',import.meta.url));
  const starts:number[]=[];
  for(let i=0;i<bytes.length-4;i++)if(bytes.readUInt32BE(i)===1&&(bytes[i+4]&31)===9)starts.push(i);
  return starts.map((s,i)=>({key:!predictive||i===0,sequence:i+1,timestamp:1000000+i*33333,data:bytes.subarray(s,starts[i+1]??bytes.length)}));
}
