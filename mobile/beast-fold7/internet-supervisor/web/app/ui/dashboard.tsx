'use client';
import {useEffect,useState,useRef} from 'react';
import {signOut} from 'next-auth/react';
import {Box,Monitor,History,Film,Settings,Sun,Maximize,LogOut,RefreshCw,Smartphone,Unplug} from 'lucide-react';
import {currentState,parseWire,type Packet} from '../../lib/wire';
import type {Snapshot} from '../../../shared/protocol';
import PairDevice from './pair-device';
import VideoPreview from './video-preview';
import Recordings from './recordings';

const names=['상자 배치','뚜껑 닫기','나사 A','나사 B','나사 C','나사 D','최종 확인'];
const phaseNames:Record<string,string>={PREPARATION:'배치 안내',APPROACH:'목표 맞추기',WORKING:'나사 조이기',RELEASE:'드라이버 떼기',INSPECTION:'최종 확인'};
const kinds:Record<string,string>={step:'단계 전환',phase:'안내 변경',gap:'수신 공백',stop:'작업 종료'};
const recordingNames:Record<string,string>={off:'녹화 꺼짐',waiting:'녹화 대기',busy:'녹화 대기',starting:'녹화 준비 중',capturing:'녹화 중',saving:'저장 중',saved:'저장 완료',interrupted:'녹화 중단 · 재연결 대기',recovering:'녹화 재개 대기',limit:'한도 도달 · 녹화 종료',quota_full:'저장 공간 부족 · 녹화 안 됨',error:'저장 오류 · 녹화 안 됨'};
type Device={id:string;name:string;revoked:boolean};
type Event={kind:string;received_ms:string;state:Snapshot};
type WorkSession={session:string;started_ms:string;last_ms:string;event_count:string};
const workDate=(ms:string)=>new Date(Number(ms)).toLocaleString('ko-KR',{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
const tabs=[['live','실시간 관제',Monitor],['history','작업 기록',History],['recordings','저장 영상',Film],['devices','기기·설정',Settings]] as const;
async function api(path:string,method='GET'){
  const r=await fetch('/api/observer/'+path,{method,cache:'no-store',signal:AbortSignal.timeout(6000)});
  if(r.status===401){location.assign('/login');throw new Error('로그인이 필요해요');}
  if(!r.ok)throw new Error('관제 서버에 연결하지 못했어요');return r.json();
}
const duration=(ms:number)=>`${Math.floor(ms/60000).toString().padStart(2,'0')}:${Math.floor(ms/1000%60).toString().padStart(2,'0')}`;
export default function Dashboard(){
  const [view,setView]=useState('live'),[devices,setDevices]=useState<Device[]>([]),[device,setDevice]=useState('');
  const [packet,setPacket]=useState<Packet|null>(null),[age,setAge]=useState(Infinity),[connection,setConnection]=useState('연결 대기');
  const [error,setError]=useState(''),[events,setEvents]=useState<Event[]>([]),[filter,setFilter]=useState('steps'),[historyError,setHistoryError]=useState('');
  const [work,setWork]=useState(''),[works,setWorks]=useState<WorkSession[]>([]),[historyLoading,setHistoryLoading]=useState(false);
  const [reload,setReload]=useState(0),[busy,setBusy]=useState(false),[loaded,setLoaded]=useState(false);
  const received=useRef(0),activeSocket=useRef<WebSocket|null>(null),lastSeen=useRef<string|null>(null);
  const s=currentState(packet,age),stage=s?.stage??-1;
  useEffect(()=>{
    let done=false;setLoaded(false);
    api('devices').then(data=>{
      if(done)return;setDevices(data.devices);setLoaded(true);setError('');
      setDevice(old=>data.devices.some((d:Device)=>d.id===old&&!d.revoked)?old:data.devices.find((d:Device)=>!d.revoked)?.id??'');
    }).catch(e=>{if(!done){setError(e.message);setLoaded(true);}});
    return ()=>{done=true;};
  },[reload]);
  useEffect(()=>{
    let done=false,timer:ReturnType<typeof setTimeout>|undefined,ws:WebSocket|undefined,attempt=0;
    setPacket(null);setAge(Infinity);setConnection(device?'연결 중':'연결 대기');received.current=0;lastSeen.current=null;
    const heartbeat=setInterval(()=>{if(received.current){const elapsed=performance.now()-received.current;setAge(elapsed);}},500);
    async function connect(){
      try{
        const result=await api(`devices/${device}/ticket`,'POST');if(done)return;
        ws=new WebSocket(result.url);activeSocket.current=ws;
        ws.onopen=()=>{if(done){ws?.close();return;}ws!.send(JSON.stringify({role:'observer',token:result.ticket}));};
        ws.onmessage=e=>{
          if(done)return;
          try{const raw=JSON.parse(e.data);if(raw.type==='ready')return;
            const next=parseWire(raw);received.current=performance.now();setAge(0);setPacket(next);setError('');attempt=0;
            if(next.received_at_ms)lastSeen.current=new Date(next.received_at_ms).toLocaleTimeString('ko-KR');
            setConnection({live:'연결됨',stale:'상태 수신 지연',offline:'기기 연결 끊김',waiting:'작업 대기'}[next.status]);
          }catch{ws?.close();}
        };
        ws.onclose=()=>{if(!done){setAge(Infinity);received.current=0;setConnection('연결 끊김');retry();}};
        ws.onerror=()=>ws?.close();
      }catch(e){if(!done){setError((e as Error).message);setConnection('연결 끊김');retry();}}
    }
    function retry(){if(!done)timer=setTimeout(()=>void connect(),Math.min(30000,1000*2**Math.min(attempt++,5))*(0.8+Math.random()*0.4));}
    if(device)void connect();
    return()=>{done=true;clearInterval(heartbeat);clearTimeout(timer);ws?.close();activeSocket.current=null;};
  },[device,reload]);
  const session=packet?.snapshot?.state.session,phase=packet?.snapshot?.state.phase,currentStage=packet?.snapshot?.state.stage,historyStatus=packet?.history_status,streamStatus=packet?.status;
  useEffect(()=>{setWork('');setWorks([]);setEvents([]);},[device]);
  useEffect(()=>{if(currentStage!==undefined&&currentStage>=0)setWork('');},[session]);
  useEffect(()=>{
    let done=false;setHistoryError('');if(!device||view!=='history'){setHistoryLoading(false);return;}
    setHistoryLoading(true);
    const timer=setTimeout(()=>{api(`devices/${device}/history${work?`?session=${encodeURIComponent(work)}`:''}`).then(data=>{if(!done){setEvents(data.events);setWorks(data.sessions??[]);}}).catch(()=>{if(!done){setEvents([]);setHistoryError('기록을 불러오지 못했어요');}}).finally(()=>{if(!done)setHistoryLoading(false);});},150);
    return()=>{done=true;clearTimeout(timer);};
  },[device,session,phase,currentStage,historyStatus,streamStatus,view,reload,work]);
  async function logout(){setBusy(true);try{await api('logout','POST');activeSocket.current?.close();await signOut({callbackUrl:'/login'});}catch(e){setError('로그아웃 연결을 마무리하지 못했어요. 다시 눌러 주세요.');setBusy(false);}}
  async function revoke(){if(!device||!window.confirm('이 기기의 관제 연결을 해제할까요? 안경 안내는 계속됩니다.'))return;setBusy(true);try{await api(`devices/${device}/revoke`,'POST');setDevice('');setReload(n=>n+1);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const list=events.filter(e=>filter==='all'||e.kind==='step'||e.kind==='stop'||e.kind==='gap');
  const shownWork=works.find(w=>w.session===(work||events[0]?.state.session));
  const recordingState=age<=3500&&packet?.recording_enabled===false?'서버 녹화 꺼짐':!s?'확인 불가':packet?.recording_status&&packet.recording_status!=='off'?recordingNames[packet.recording_status]:!s.running?'작업 대기':!s.video_available?'영상 공유 꺼짐':!s.recording_consent?'녹화 동의 필요':'녹화 대기';
  return <><a className="skip-link" href="#content">본문으로 이동</a><header className="topbar supervisor-header"><a className="brand" href="/"><Box className="icon brand-icon"/><span>AR Assembly<small>조립 작업 관제</small></span></a>
    <nav className="main-nav" aria-label="주 메뉴"><div role="tablist" aria-label="관제 화면">{tabs.map(([id,label,Icon])=>{
      const I=Icon as typeof Monitor;return <button key={id as string} role="tab" aria-selected={view===id} tabIndex={view===id?0:-1} aria-controls={`view-${id}`} id={`tab-${id}`} onClick={()=>setView(id as string)} onKeyDown={e=>{
        const ids=tabs.map(t=>t[0]),index=ids.findIndex(id=>id===view);
        const next=e.key==='ArrowRight'?ids[(index+1)%ids.length]:e.key==='ArrowLeft'?ids[(index+ids.length-1)%ids.length]:e.key==='Home'?ids[0]:e.key==='End'?ids.at(-1):null;
        if(next){e.preventDefault();setView(next);document.getElementById(`tab-${next}`)?.focus();}
      }}><I size={19}/>{label as string}</button>;
    })}</div></nav><div className="header-tools">
    <button className="icon-button" title="화면 테마 바꾸기" aria-label="화면 테마 바꾸기" onClick={()=>{const h=document.documentElement;h.dataset.theme=h.dataset.theme==='dark'?'light':'dark';}}><Sun size={20}/></button>
    <button className="icon-button" title="전체 화면 전환" aria-label="전체 화면 전환" onClick={()=>{void (document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()).catch(()=>{});}}><Maximize size={20}/></button>
    <button className="icon-button" title="로그아웃" aria-label="로그아웃" disabled={busy} onClick={()=>void logout()}><LogOut size={20}/></button></div></header>
    <main id="content" className="supervisor"><div className="page-heading"><div className="page-heading-left"><h1>{tabs.find(t=>t[0]===view)?.[1]}</h1>
    <span id="connection" role="status" data-state={age>3500&&packet?.status==='live'?'stale':packet?.status??'waiting'}>{packet?.status==='live'&&age>3500?'연결 확인 필요':connection}</span></div>
    <div className="device-toolbar"><label><Smartphone size={16} aria-hidden="true"/><span className="sr-only">기기</span><select aria-label="기기 선택" value={device} onChange={e=>{setEvents([]);setDevice(e.target.value);}}><option value="">기기 선택</option>{devices.filter(d=>!d.revoked).map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><button className="icon-button" aria-label="새로고침" title="새로고침" onClick={()=>setReload(n=>n+1)}><RefreshCw size={18}/></button></div></div>
    {error&&<p className="warning" role="alert">{error}</p>}
    <section id="view-live" role="tabpanel" aria-labelledby="tab-live" hidden={view!=='live'}>
    {age<=3500&&packet?.recording_enabled===false&&<p className="warning" role="status">서버 녹화가 꺼져 있어 새 영상은 저장되지 않아요.</p>}
    {age<=3500&&['interrupted','recovering'].includes(packet?.recording_status??'')&&<p className="warning" role="status">{recordingNames[packet!.recording_status!]}. 끊기기 전 영상은 저장됐어요.</p>}
    {s&&packet?.recording_status==='quota_full'&&<p className="warning" role="alert">저장 공간이 부족해 녹화를 시작하지 못했어요. 저장 영상에서 기존 영상을 정리한 뒤 새 작업을 시작해 주세요.</p>}
    {s&&packet?.recording_status==='error'&&<p className="warning" role="alert">영상 저장에 실패했어요. 현재 작업은 녹화되지 않고 있어요.</p>}
    <div className="observer-workspace media-workspace" aria-busy={!s}>
    <VideoPreview key={device} device={device} active={view==='live'&&!busy}/>
    <section className="guidance" id="actionSurface" data-tone={!s?.running||!s.overlay_visible?'neutral':s.phase==='WORKING'?'observe':s.phase==='APPROACH'?'caution':'good'} aria-label="현재 작업">
    <div className="state-row"><span className="label">현재 작업</span><span>{s?(s.running?phaseNames[s.phase]:'카메라 꺼짐'):'수신 대기'}</span></div>
    <div className="target-heading"><strong>{stage>=2&&stage<=5?'ABCD'[stage-2]:stage>=0?String(stage+1).padStart(2,'0'):'--'}</strong><h2>{stage>=0?names[stage]:'작업 대기'}</h2></div>
    <div className="instruction-block"><p className="label">현재 안내</p><p id="actionTitle" aria-live="polite">{s?s.action:!device?'연결할 기기를 선택해 주세요':'현재 안내를 확인할 수 없어요'}</p></div>
    <ol className="phase-rail" data-phase={s?.phase} aria-hidden={stage<2||stage>5}><li className={s?.phase==='APPROACH'?'active':''}>목표 맞추기</li><li className={s?.phase==='WORKING'?'active':''}>조이기</li><li className={s?.phase==='RELEASE'?'active':''}>드라이버 떼기</li></ol>
    <div className="target-map-row"><div className="target-map" aria-label="작업자 기준 나사 위치">{['A','B','C','D'].map((letter,i)=><span key={letter} data-screw={letter} className={stage===i+2?'active':''}>{letter}</span>)}<span className="map-near">작업자 쪽</span></div><div className="work-clock"><span className="label">작업 경과</span><strong>{s?duration(s.elapsed_ms):'--:--'}</strong></div></div></section></div>
    <section className="sequence" aria-label="작업 순서"><div className="section-heading"><h2>작업 순서</h2><span>{stage>=0?`현재 단계 ${stage+1} / 7`:'수신 대기'}</span></div><ol className="steps">{names.map((name,i)=><li key={name} aria-current={stage===i?'step':undefined} className={stage===i?'current':stage>i?'past':''}><b>{String(i+1).padStart(2,'0')}</b>{name}</li>)}</ol></section>
    <section className="observer-status" aria-label="연결 상태"><h2>작업 상태</h2><dl>{[
      ['안경 안내',s?(s.overlay_visible?'위치 안내 중':'위치 안내 대기'):'확인 불가'],['마커 추적',s?(s.tracked?'추적 중':'작업대 확인 필요'):'확인 불가'],['검출 마커',s?`${s.markers}개`:'--'],['영상 공유',s?.video_available?'켜짐':s?'꺼짐':'확인 불가'],['녹화 동의',s?(s.recording_consent?'동의함':'동의 안 함'):'확인 불가'],['영상 저장',recordingState],
    ].map(([name,value])=><div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
    <details><summary>연결 상세</summary><dl><div><dt>재투영 오차</dt><dd>{s?.rms_px?.toFixed(2)??'--'} px</dd></div><div><dt>관측 경과</dt><dd>{s?.pose_age_ms??'--'} ms</dd></div><div><dt>프레임</dt><dd>{s?.frame??'--'}</dd></div></dl></details></section></section>
    <section id="view-history" role="tabpanel" aria-labelledby="tab-history" hidden={view!=='history'} aria-busy={historyLoading}>
    <div className="history-heading"><div><span className="label">{work?'선택한 작업':'최근 작업'}</span><h2>{historyLoading?'기록 확인 중':shownWork?workDate(shownWork.started_ms):'아직 작업 기록이 없어요'}</h2></div><label><span className="sr-only">작업 선택</span><select value={work} onChange={e=>{setEvents([]);setWork(e.target.value);}}><option value="">최근 작업</option>{works.map(w=><option key={w.session} value={w.session}>{workDate(w.started_ms)}</option>)}</select></label></div>
    <div className="table-toolbar"><span>{historyLoading?'불러오는 중':`표시 기록 ${list.length}개`}{!historyLoading&&shownWork&&Number(shownWork.event_count)>events.length?' · 최근 240개 기준':''}</span><label>표시 <select aria-label="표시 범위" value={filter} onChange={e=>setFilter(e.target.value)}><option value="steps">단계 전환</option><option value="all">전체 변화</option></select></label></div>
    {(historyError||packet?.history_status==='error')&&<p className="warning" role="alert">{historyError||'일부 기록을 저장하지 못했어요. 수신 공백을 확인해 주세요.'}</p>}
    {historyLoading?<p className="empty-state" role="status">작업 기록을 불러오는 중이에요</p>:!list.length?<p className="empty-state">{device?'표시할 기록이 없어요':'기기를 선택해 주세요'}</p>:<div className="history-scroll"><table><thead><tr><th>수신 시각</th><th>작업</th><th>변화</th></tr></thead><tbody>{list.map((e,i)=><tr key={`${e.received_ms}-${i}`}><td>{new Date(Number(e.received_ms)).toLocaleTimeString('ko-KR')}</td><td>{names[e.state.stage]??'작업 대기'}</td><td>{e.kind==='phase'?e.state.action:kinds[e.kind]??e.kind}</td></tr>)}</tbody></table></div>}</section>
    <section id="view-recordings" role="tabpanel" aria-labelledby="tab-recordings" hidden={view!=='recordings'}><Recordings key={device} device={device} active={view==='recordings'}/></section>
    <section id="view-devices" role="tabpanel" aria-labelledby="tab-devices" hidden={view!=='devices'}><PairDevice connected={id=>{setDevice(id);setReload(n=>n+1);}}/><h2>연결된 기기</h2>{!devices.length?<p className="empty-state">{loaded?'아직 연결된 기기가 없어요':'기기를 확인하고 있어요'}</p>:<ul className="device-list">{devices.map(d=><li key={d.id}><Smartphone size={24}/><span>{d.name}<small>{d.revoked?'연결 해제됨':'관제 등록됨'}</small></span>{d.id===device&&!d.revoked&&<button className="secondary-button" disabled={busy} onClick={()=>void revoke()}><Unplug size={18}/>연결 해제</button>}</li>)}</ul>}</section>
    <footer><span>휴대폰 관제 · 상태 수신</span><span>{lastSeen.current?`마지막 수신 ${lastSeen.current}`:'수신 대기'}</span></footer></main></>;
}
