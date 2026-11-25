import {z} from 'zod';
const lookup=z.strictObject({code:z.string().regex(/^[A-HJ-NP-Z2-9]{8}$/)});
const approve=lookup.extend({request_id:z.string().uuid()});
export async function readPairingInput(req:Request,action:'lookup'|'approve'){
  if(req.headers.get('content-type')?.split(';')[0].trim()!=='application/json'||!req.body)throw new Error('Invalid request');
  const reader=req.body.getReader(),chunks:Uint8Array[]=[];let size=0;
  try{
    while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;
      if(size>2048){await reader.cancel();throw new Error('Request too large');}chunks.push(value);
    }
  }finally{reader.releaseLock();}
  const body=new Uint8Array(size);let at=0;for(const chunk of chunks){body.set(chunk,at);at+=chunk.length;}
  return (action==='lookup'?lookup:approve).parse(JSON.parse(new TextDecoder().decode(body)));
}
