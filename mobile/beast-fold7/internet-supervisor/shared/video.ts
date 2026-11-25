export const MAX_VIDEO_BYTES=100*1024;
export const VIDEO_STALE_MS=3000;

/** Read bounded JPEG marker segments; media is never decoded or persisted by the relay. */
export function validJpeg(data:Uint8Array):boolean {
  if(data.length<16||data.length>MAX_VIDEO_BYTES||data[0]!==255||data[1]!==216||data.at(-2)!==255||data.at(-1)!==217)return false;
  let offset=2,dimensions=false;
  while(offset+4<=data.length){
    if(data[offset++]!==255)return false;
    while(data[offset]===255)offset++;
    const marker=data[offset++];
    if(marker===217)return false;
    const size=(data[offset]<<8)|data[offset+1];
    if(size<2||offset+size>data.length)return false;
    if(marker===192){
      if(dimensions||size<8||data[offset+2]!==8)return false;
      const components=data[offset+7];
      if((components!==1&&components!==3)||size!==8+3*components)return false;
      const height=(data[offset+3]<<8)|data[offset+4],width=(data[offset+5]<<8)|data[offset+6];
      if(width<2||height<2||width>640||height>360)return false;
      dimensions=true;
    }
    // Only the baseline JPEG emitted by Android's YuvImage is accepted.
    if(marker>=193&&marker<=207&&![196,200,204].includes(marker))return false;
    if(marker===218)return dimensions;
    offset+=size;
  }
  return false;
}
