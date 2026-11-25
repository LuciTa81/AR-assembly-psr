(() => {
  'use strict';
  const $=id=>document.getElementById(id), names=['상자 배치','뚜껑 닫기','나사 A','나사 B','나사 C','나사 D','최종 확인'];
  const key=new URLSearchParams(location.hash.slice(1)).get('key')||sessionStorage.getItem('ar-observer-key')||'';
  if(key)sessionStorage.setItem('ar-observer-key',key);
  history.replaceState(null,'',location.pathname);
  let events=[],previous=null,lastTime=-1,stuckSince=0,offline=true;
  const time=ms=>`${Math.floor(ms/60000).toString().padStart(2,'0')}:${Math.floor(ms/1000%60).toString().padStart(2,'0')}`;
  const phaseNames={APPROACH:'목표 맞추기',WORKING:'나사 조이기',RELEASE:'드라이버 떼기',INSPECTION:'최종 확인',PREPARATION:'배치 안내'};
  function historyView(){
    const rows=events.filter(e=>$('historyFilter').value==='all'||e.kind==='step');
    $('historyCount').textContent=`표시 기록 ${rows.length}개`;$('historyEmpty').hidden=!!rows.length;
    $('history').replaceChildren(...rows.map(e=>{const tr=document.createElement('tr');for(const value of [time(e.elapsed),e.stage<0?'작업 대기':names[e.stage],e.text]){const td=document.createElement('td');td.textContent=value;tr.append(td);}return tr;}));
  }
  function event(s,text,kind){events.unshift({elapsed:s.elapsed_ms,stage:s.stage,text,kind});events.length=Math.min(events.length,240);}
  function disconnected(message){
    if(!offline&&previous){event(previous,'관제 연결 끊김','status');historyView();}
    offline=true;$('connection').textContent='연결 끊김';$('connection').dataset.offline='true';
    $('connectionDetail').hidden=false;$('connectionDetail').textContent=message;
    $('actionTitle').textContent='현재 안내를 확인할 수 없어요';$('liveCue').textContent='마지막 수신 상태';
    $('overlay').textContent='확인 불가';$('tracking').textContent='확인 불가';$('remaining').textContent='--';
    $('actionSurface').dataset.tone='neutral';document.querySelector('.observer-workspace').setAttribute('aria-busy','true');
  }
  function render(s){
    if(s.schema!==1||!Number.isInteger(s.stage)||s.stage< -1||s.stage>6||!Number.isFinite(s.updated_ms))throw Error('invalid');
    if(!previous||s.session!==previous.session){events=[];previous=null;lastTime=-1;}
    if(s.updated_ms===lastTime){if(performance.now()-stuckSince>2000)throw Error('stale');}
    else{lastTime=s.updated_ms;stuckSince=performance.now();}
    if(!previous||s.stage!==previous.stage){if(s.stage>=0)event(s,previous?'단계 전환':'관제 수신 시작','step');}
    else if(s.phase!==previous.phase||s.action!==previous.action)event(s,s.action,'status');
    if(previous&&s.running!==previous.running)event(s,s.running?'작업 시작':'작업 종료','status');
    if(previous&&s.tracked!==previous.tracked)event(s,s.tracked?'추적 복귀':'추적 대기','status');
    if(offline&&previous)event(s,'관제 연결 복귀','status');
    previous=s;offline=false;historyView();
    $('connection').textContent='연결됨';$('connection').dataset.offline='false';$('connectionDetail').hidden=true;
    document.querySelector('.observer-workspace').setAttribute('aria-busy','false');
    $('stateLabel').textContent=s.stage<0?'작업 대기':names[s.stage];
    $('targetLetter').textContent=s.stage>=2&&s.stage<=5?'ABCD'[s.stage-2]:s.stage>=0?String(s.stage+1).padStart(2,'0'):'--';
    $('actionTitle').textContent=s.action;$('liveCue').textContent=s.running?(phaseNames[s.phase]||'안내 중'):'카메라 꺼짐';
    $('actionSurface').dataset.tone=!s.running||!s.overlay_visible?'neutral':s.phase==='WORKING'?'observe':s.phase==='APPROACH'?'caution':'good';
    $('overlay').textContent=!s.running?'꺼짐':s.stage===6?'최종 확인 안내':s.overlay_visible?'위치 안내 중':'위치 안내 대기';
    $('tracking').textContent=!s.running?'대기':s.tracked?'추적 중':'작업대 확인 필요';$('markers').textContent=`${s.markers}개`;
    $('rms').textContent=Number.isFinite(s.rms_px)?`${s.rms_px.toFixed(2)} px`:'--';$('age').textContent=s.pose_age_ms>=0?`${s.pose_age_ms} ms`:'--';
    $('frame').textContent=String(s.frame);$('reason').textContent=s.message;
    $('remaining').textContent=s.remaining_ms>0?`다음 안내까지 ${Math.ceil(s.remaining_ms/1000)}초`:s.stage===6?'조립 상태 확인':s.running?'안내 진행 중':'작업 대기';
    $('elapsed').textContent=s.running?`작업 경과 ${time(s.elapsed_ms)}`:'카메라 꺼짐';
    $('stepProgress').textContent=s.stage>=0?`현재 단계 ${s.stage+1} / 7`:'작업 대기';
    [...$('steps').children].forEach((el,i)=>{el.classList.toggle('current',i===s.stage);el.classList.toggle('past',i<s.stage);});
    document.querySelectorAll('[data-screw]').forEach(el=>el.classList.toggle('active',s.stage>=2&&s.stage<=5&&el.dataset.screw==='ABCD'[s.stage-2]));
    $('phaseRail').hidden=!(s.stage>=2&&s.stage<=5);$('phaseRail').dataset.phase=s.phase;
    [...$('phaseRail').children].forEach((el,i)=>el.classList.toggle('active',['APPROACH','WORKING','RELEASE'][i]===s.phase));
    $('updated').textContent=`최근 수신 ${new Date().toLocaleTimeString('ko-KR')}`;
  }
  async function poll(){
    if(!key){disconnected('폰의 관제 주소로 접속해 주세요.');return;}
    try{const r=await fetch('/state.json',{headers:{Authorization:`Bearer ${key}`},cache:'no-store',signal:AbortSignal.timeout(1600),redirect:'error'});
      if(r.status===401){sessionStorage.removeItem('ar-observer-key');disconnected('연결 주소가 만료됐어요. 폰에서 새 주소를 확인해 주세요.');return;}
      if(!r.ok)throw Error('http');render(await r.json());
    }catch(e){disconnected('폰의 관제 연결과 같은 Wi-Fi 연결을 확인해 주세요.');}
    setTimeout(poll,500);
  }
  function tab(view){for(const name of ['live','history']){$(`view-${name}`).hidden=name!==view;$(`tab-${name}`).setAttribute('aria-selected',String(name===view));$(`tab-${name}`).tabIndex=name===view?0:-1;}$('pageTitle').textContent=view==='live'?'실시간 관제':'작업 기록';}
  for(const name of ['live','history']){$(`tab-${name}`).onclick=()=>tab(name);$(`tab-${name}`).onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?'live':e.key==='End'?'history':name==='live'?'history':'live';tab(next);$(`tab-${next}`).focus();}};}
  $('historyFilter').onchange=historyView;
  $('theme').onclick=()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'light':'dark';};
  $('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{}};
  document.addEventListener('fullscreenchange',()=>{$('fullscreen').title=document.fullscreenElement?'전체 화면 종료':'전체 화면';$('fullscreen').setAttribute('aria-label',$('fullscreen').title);});
  poll();
})();
