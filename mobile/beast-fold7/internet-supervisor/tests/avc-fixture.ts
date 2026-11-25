export function avc(sequence=1,key=true){
 const nal=Buffer.from(key?[0,0,0,1,103,66,224,31,0,0,0,1,104,1,0,0,0,1,101,1]:[0,0,0,1,65,1]);
 const header=Buffer.alloc(21);header.write('ARV2');header[4]=key?1:0;header.writeUInt32BE(sequence,5);header.writeBigUInt64BE(BigInt(sequence*33333),9);header.writeUInt16BE(1280,17);header.writeUInt16BE(720,19);
 return Buffer.concat([header,nal]);
}
