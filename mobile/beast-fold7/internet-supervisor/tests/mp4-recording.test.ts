import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdtemp,rm,rmdir,stat} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {Input,ALL_FORMATS,BufferSource,EncodedPacketSink} from 'mediabunny';
import {Mp4Recording} from '../server/mp4-recording.ts';
import {syntheticPackets} from './synthetic-packets.ts';
for(const predictive of [false,true])test(`real Annex B ${predictive?'I/P':'I-only'} frames remux to a silent MP4 with preserved dimensions and timestamps`,async()=>{
  const dir=await mkdtemp(join(tmpdir(),'ar-recording-')),path=join(dir,'test.mp4');
  try{
    const mux=new Mp4Recording(path);const packets=await syntheticPackets(predictive);assert.equal(packets.length,3);
    for(const p of packets)await mux.add(p);
    await mux.finish();assert((await stat(path)).size>0);
    const input=new Input({source:new BufferSource(await readFile(path)),formats:ALL_FORMATS});
    try{
      assert.equal((await input.getAudioTracks()).length,0);
      const track=await input.getPrimaryVideoTrack();assert(track);assert.equal(track.displayWidth,1280);assert.equal(track.displayHeight,720);
      const sink=new EncodedPacketSink(track),saved=[];for await(const p of sink.packets())saved.push(p);
      assert.equal(saved.length,3);assert.equal(saved[0].timestamp,0);assert(Math.abs(saved[2].timestamp-0.066666)<0.001);
    }finally{input.dispose();}
  }finally{await rm(path,{force:true});await rmdir(dir);}
});
