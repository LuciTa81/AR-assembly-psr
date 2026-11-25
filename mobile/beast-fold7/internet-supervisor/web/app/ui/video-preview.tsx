'use client';
import {useEffect,useRef,useState} from 'react';
import {Camera,VideoOff,Radio} from 'lucide-react';
import {MAX_VIDEO_BYTES,VIDEO_STALE_MS,validJpeg} from '../../../shared/video';
import {MAX_AVC_BYTES,parseAvc} from '../../../shared/avc';

export default function VideoPreview({device,active}:{device:string;active:boolean}){
  const [enabled,setEnabled]=useState(false),[status,setStatus]=useState('꺼짐'),[visible,setVisible]=useState(false);
  const canvas=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{
    let done=false,ws:WebSocket|undefined,retry:ReturnType<typeof setTimeout>|undefined;
    let lastFrame=0,decoding=false,generation=0,attempt=0,terminal=false;
    let decoder:VideoDecoder|undefined,sequence=0,needsKey=true,displayed=0,sampleAt=performance.now();
    let decoderConfig:VideoDecoderConfig={codec:'avc1.42E01F',codedWidth:1280,codedHeight:720,optimizeForLatency:true,hardwareAcceleration:'prefer-software'};
    const pendingFrames=new Map<number,number>();
    function resetDecoder(){if(decoder&&decoder.state!=='closed')decoder.close();decoder=undefined;needsKey=true;sequence=0;pendingFrames.clear();}
    function shown(){lastFrame=performance.now();attempt=0;displayed++;setVisible(true);setStatus('수신 중');}
    function decodeAvc(packet:NonNullable<ReturnType<typeof parseAvc>>){
      if(sequence&&packet.sequence!==sequence+1){resetDecoder();}
      if(decoder&&decoder.decodeQueueSize>3)resetDecoder();
      sequence=packet.sequence;
      if(needsKey&&!packet.key)return;
      if(!decoder){
        const token=generation;
        decoder=new VideoDecoder({output:frame=>{
          try{
            const received=pendingFrames.get(frame.timestamp);pendingFrames.delete(frame.timestamp);
            if(done||generation!==token||received===undefined||performance.now()-received>500)return;
            if(frame.displayWidth>1280||frame.displayHeight>720){clear('영상 해상도를 확인해 주세요');return;}
            canvas.current?.getContext('2d')?.drawImage(frame,0,0,1280,720);shown();
          }finally{frame.close();}
        },error:()=>{if(!done){clear('영상 복구 중');}}});
        decoder.configure(decoderConfig);
      }
      needsKey=false;pendingFrames.set(packet.timestamp,performance.now());
      if(pendingFrames.size>8){resetDecoder();return;}
      decoder.decode(new EncodedVideoChunk({type:packet.key?'key':'delta',timestamp:packet.timestamp,data:packet.data as Uint8Array<ArrayBuffer>}));
    }
    const controller=new AbortController();
    function clear(message:string){
      generation++;lastFrame=0;setVisible(false);setStatus(message);
      resetDecoder();displayed=0;if(canvas.current)canvas.current.dataset.displayFps='0';sampleAt=performance.now();
      canvas.current?.getContext('2d')?.clearRect(0,0,1280,720);
    }
    clear(enabled&&active&&device?'연결 중':'꺼짐');
    async function connect(){
      try{
        if(typeof VideoDecoder==='undefined'){terminal=true;clear('Chrome 또는 Edge에서 영상을 열어 주세요');return;}
        if(!(await VideoDecoder.isConfigSupported(decoderConfig)).supported)decoderConfig={...decoderConfig,hardwareAcceleration:'no-preference'};
        if(!(await VideoDecoder.isConfigSupported(decoderConfig)).supported){terminal=true;clear('Chrome 또는 Edge에서 영상을 열어 주세요');return;}
        if(done)return;
        const response=await fetch(`/api/observer/devices/${encodeURIComponent(device)}/ticket`,{
          method:'POST',cache:'no-store',signal:AbortSignal.any([controller.signal,AbortSignal.timeout(6000)])
        });
        if(done)return;
        if(response.status===401||response.status===403||response.status===404){terminal=true;clear('연결 권한을 확인해 주세요');return;}
        if(!response.ok)throw new Error('ticket');
        const result=await response.json();if(done)return;
        const url=new URL(result.url);url.pathname='/video';url.search='';url.hash='';
        const socket=new WebSocket(url);ws=socket;socket.binaryType='arraybuffer';
        const handshake=setTimeout(()=>socket.close(),10000);
        socket.onopen=()=>{if(done){socket.close();return;}socket.send(JSON.stringify({role:'observer',token:result.ticket}));};
        socket.onmessage=async event=>{
          if(done||ws!==socket)return;
          if(typeof event.data==='string'){
            try{
              const control=JSON.parse(event.data);
              if(control.type==='ready'){clearTimeout(handshake);setStatus('영상 수신 대기');}
              else if(control.type==='video-status')clear('영상 수신 대기');
              else socket.close();
            }catch{socket.close();}return;
          }
          if(!(event.data instanceof ArrayBuffer)||event.data.byteLength>MAX_AVC_BYTES){socket.close();return;}
          const avc=parseAvc(new Uint8Array(event.data));
          if(avc){try{decodeAvc(avc);}catch{clear('영상 복구 중');}return;}
          if(event.data.byteLength>MAX_VIDEO_BYTES||!validJpeg(new Uint8Array(event.data))){socket.close();return;}
          if(decoding)return;
          decoding=true;const token=generation,received=performance.now();
          let bitmap:ImageBitmap|undefined;
          try{
            bitmap=await createImageBitmap(new Blob([event.data],{type:'image/jpeg'}));
            if(done||ws!==socket||token!==generation||performance.now()-received>1000)return;
            if(bitmap.width>640||bitmap.height>360)throw new Error('dimensions');
            const context=canvas.current?.getContext('2d');if(!context)return;
            context.clearRect(0,0,1280,720);
            const scale=Math.min(1280/bitmap.width,720/bitmap.height),w=bitmap.width*scale,h=bitmap.height*scale;
            context.drawImage(bitmap,(1280-w)/2,(720-h)/2,w,h);shown();
          }catch{if(!done){clear('영상을 확인할 수 없어요');socket.close();}}
          finally{bitmap?.close();decoding=false;}
        };
        socket.onerror=()=>socket.close();
        socket.onclose=event=>{
          clearTimeout(handshake);if(done)return;
          clear('영상 연결 끊김');
          if(event.code===4403||event.code===4409||(event.code===4401&&['Device revoked','Viewer signed out','Credential expired'].includes(event.reason))){terminal=true;return;}
          schedule();
        };
      }catch{if(!done){clear('영상 연결 대기');schedule();}}
    }
    function schedule(){if(!done&&!terminal)retry=setTimeout(()=>void connect(),Math.min(30000,1000*2**Math.min(attempt++,5)));}
    if(enabled&&active&&device)void connect();
    const stale=setInterval(()=>{
      const now=performance.now();
      if(lastFrame&&now-lastFrame>VIDEO_STALE_MS)clear('영상 수신 지연');
      else if(now-sampleAt>=1000){if(canvas.current)canvas.current.dataset.displayFps=String(Math.round(displayed*1000/(now-sampleAt)));displayed=0;sampleAt=now;}
    },250);
    return()=>{done=true;generation++;resetDecoder();controller.abort();clearTimeout(retry);clearInterval(stale);ws?.close();canvas.current?.getContext('2d')?.clearRect(0,0,1280,720);};
  },[enabled,active,device]);
  return <section className="video-preview" aria-label="작업대 영상">
    <div className="video-heading"><h2><Camera size={20}/>작업대 영상</h2><label className="video-toggle"><input type="checkbox" role="switch" checked={enabled} disabled={!device||!active} onChange={e=>setEnabled(e.target.checked)}/>영상 표시</label></div>
    <div className="video-surface" data-visible={visible}>
      <canvas ref={canvas} width={1280} height={720} aria-label="작업대 실시간 카메라 영상" style={{visibility:visible?'visible':'hidden'}}/>
      {!visible&&<div className="video-placeholder" role="status">{enabled?<Radio size={28} strokeWidth={1.4} aria-hidden="true"/>:<VideoOff size={28} strokeWidth={1.4} aria-hidden="true"/>}<span>{!device?'연결된 기기 없음':!enabled?'영상 표시 꺼짐':status==='영상 수신 대기'?'폰의 영상 공유 대기':status}</span></div>}
      {visible&&<span className="video-badge">수신 중</span>}
    </div>
    <p className="video-caption"><span role="status">{status}</span><span>카메라 시점 · 안경 화면은 별도</span></p>
  </section>;
}
