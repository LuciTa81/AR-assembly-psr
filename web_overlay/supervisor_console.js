/* Lifecycle controls are injected only by the local controller. */
(() => {
  'use strict';
  const icon = paths => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
  // Reuse the existing Lucide scan-line icon; play and square share its styling.
  const checkIcon = document.querySelector('#tab-tracking svg').outerHTML;
  const playIcon = icon('<polygon points="6 3 20 12 6 21 6 3"/>');
  const stopIcon = icon('<rect width="16" height="16" x="4" y="4" rx="2"/>');
  const bar = document.createElement('section');
  bar.className='console-bar'; bar.setAttribute('aria-label','실행 관리');
  bar.innerHTML=`<div class="console-status"><strong id="consoleStatus" role="status">관제 연결 중</strong><span id="consoleDetail">카메라 꺼짐</span></div>
    <div class="console-actions"><button id="consoleCheck" class="command-button" type="button">${checkIcon}연결 확인</button>
    <button id="consoleStart" class="command-button console-primary" type="button" disabled>${playIcon}<span>작업 시작</span></button>
    <button id="consoleStop" class="command-button" type="button" disabled>${stopIcon}실행 종료</button></div>`;
  document.querySelector('.page-heading').after(bar);
  const setup = document.createElement('div');
  setup.className='console-setup';
  setup.innerHTML=`<span class="label">시작 준비</span><h2>안경을 연결하고 작업대를 봐 주세요</h2>
    <ul id="consoleChecks" class="console-checks"><li>연결 확인 대기</li></ul>
    <label class="console-prepared"><input id="consolePrepared" type="checkbox"><span>Full SBS · 0DoF · Extra Large · 4.5m<br>착용 위치와 상자·마커 배치를 확인했어요</span></label>
    <p id="consoleError" class="console-error" role="status" hidden></p>
    <p class="console-privacy">시작 버튼을 누르면 카메라와 안경 안내가 켜집니다. 사진·영상은 저장하지 않습니다.</p>
    <details class="console-profile"><summary>실행 정보</summary><p>A–D 위치 보정 · 작업 진행 보존<br>작업 중 안내 2초 · 카메라 입력 0</p><p id="consoleLog"></p></details>`;
  document.querySelector('.guidance').prepend(setup);
  const $=id=>document.getElementById(id);
  document.title='AI Assembly Guide | 작업 관제';
  document.querySelector('footer>span').textContent='노트북 관제';
  let current=null, posting=false, previous='unknown';
  const labels={idle:'실행 대기',checking:'연결 확인 중',starting:'작업 시작 중',running:'실행 중',stopping:'안전하게 종료 중',error:'확인이 필요해요',offline:'관제 연결 끊김'};
  function update() {
    const state=current?.status || 'offline', busy=['checking','starting','running','stopping'].includes(state);
    document.body.dataset.console=state;
    $('consoleStatus').textContent=labels[state] || '연결 확인 중';
    $('consoleDetail').textContent=state==='offline'?'실행 상태 확인 필요':state==='running'?'카메라·안경 안내 실행 중':state==='starting'?'카메라 입력과 안경 화면 준비 중':state==='checking'?'카메라를 켜지 않고 장치·파일 확인 중':state==='stopping'?'카메라·안경 안내 종료 확인 중':'카메라 꺼짐 · 연결 확인 후 시작';
    $('consoleCheck').disabled=busy||posting||state==='offline';
    $('consoleStart').disabled=busy||posting||state==='offline'||!current?.preflight?.ready||!$('consolePrepared').checked;
    $('consoleStop').disabled=!busy||state==='stopping'||posting;
    $('consolePrepared').disabled=busy;
    $('consoleError').hidden=!current?.error;
    $('consoleError').textContent=current?.error || '';
    $('consoleLog').textContent=current?.log_folder || current?.preflight?.log_folder || '';
    const key=JSON.stringify(current?.preflight?.checks || []);
    if ($('consoleChecks').dataset.key!==key) {
      $('consoleChecks').dataset.key=key;
      $('consoleChecks').replaceChildren(...(current?.preflight?.checks || [{name:'연결 확인 대기',ok:null}]).map(check=>{
        const li=document.createElement('li'), mark=document.createElement('span');
        li.dataset.ok=String(check.ok); mark.textContent=check.ok===true?'확인':check.ok===false?'확인 필요':'대기';
        li.append(document.createTextNode(check.name),mark);return li;
      }));
    }
    for(const id of ['videoEnabled','settingsVideo','showVideo']) $(id).disabled=state!=='running';
  }
  async function request(action) {
    if(posting) return;
    posting=true;update();
    try {
      const response=await fetch('/console/'+action,{method:'POST',redirect:'error',
        headers:{'Content-Type':'application/json','X-AR-Console':'control'},body:'{}',signal:AbortSignal.timeout(5000)});
      if(!response.ok) throw new Error('요청을 접수하지 못했어요. 현재 실행 상태를 확인해 주세요.');
      current={...current,status:action==='stop'?'stopping':'checking',error:''};
    } catch(e) { current={...current,error:e.message}; }
    finally {posting=false;update();}
  }
  $('consolePrepared').addEventListener('change',update);
  $('consoleCheck').addEventListener('click',()=>request('check'));
  $('consoleStart').addEventListener('click',()=>request('start'));
  $('consoleStop').addEventListener('click',()=>request('stop'));
  async function pollConsole() {
    try {
      const response=await fetch('/console/status',{cache:'no-store',redirect:'error',signal:AbortSignal.timeout(2000)});
      if(!response.ok) throw new Error();
      const data=await response.json();
      if(data.schema_version!=='beast_console_v1') throw new Error();
      if(['idle','error'].includes(data.status) && ['running','starting','stopping'].includes(previous)) {
        $('consolePrepared').checked=false;
        if($('videoEnabled').checked) {$('videoEnabled').checked=false;$('videoEnabled').dispatchEvent(new Event('change'));}
      }
      previous=data.status;current=data;
    } catch {current={status:'offline',error:'관제 연결을 확인해 주세요. 실행 중인 작업이 종료됐는지는 아직 확인하지 못했습니다.'};}
    update();setTimeout(pollConsole,500);
  }
  update();pollConsole();
})();
