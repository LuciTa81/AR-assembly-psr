import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {once} from 'node:events';
import {randomBytes,randomUUID} from 'node:crypto';
import {mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';
import assert from 'node:assert/strict';
import {publish} from '../tests/fixture.ts';
import {syntheticPackets} from '../tests/synthetic-packets.ts';
const require=createRequire(import.meta.url),webRequire=createRequire(new URL('../web/package.json',import.meta.url));
const {chromium}=require(join(process.env.CODEX_NODE_MODULES,'playwright'));
const {encode}=webRequire('next-auth/jwt');
const web=fileURLToPath(new URL('../web',import.meta.url));
const probe=createServer();probe.listen(0,'127.0.0.1');await once(probe,'listening');const port=probe.address().port;await new Promise(r=>probe.close(r));
const base=`http://127.0.0.1:${port}`,secret=randomBytes(32).toString('hex');
const child=spawn(process.execPath,[webRequire.resolve('next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',String(port)],{cwd:web,windowsHide:true,env:{...process.env,NEXTAUTH_URL:base,NEXTAUTH_SECRET:secret,OWNER_GITHUB_ID:'101',GITHUB_ID:'local-qa-only',GITHUB_SECRET:'local-qa-only',PUBLIC_GITHUB_LOGIN:'false'},stdio:'pipe'});
let output='';child.stdout.on('data',b=>output+=b);child.stderr.on('data',b=>output+=b);
let browser;
try{
  let ready=false;for(let i=0;i<100;i++){try{await fetch(base+'/login');ready=true;break;}catch{await new Promise(r=>setTimeout(r,100));}}
  assert(ready,output);
  browser=await chromium.launch({headless:true,channel:'chrome'});const context=await browser.newContext();
  const token=await encode({secret,token:{ownerId:'101',viewerSession:randomUUID()},maxAge:600});
  await context.addCookies([{name:'next-auth.session-token',value:token,url:base,httpOnly:true,sameSite:'Lax'}]);
  const device=randomUUID(),record=randomUUID(),now=Date.now();let deleted=false,recordingEnabled=false;
  await context.route('**/api/observer/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    let data={};
    if(path.endsWith('/devices'))data={devices:[{id:device,name:'Fold7',revoked:false}]};
    else if(path.endsWith('/ticket'))data={ticket:'qa-only',url:`ws://127.0.0.1:${port}/qa-socket`};
    else if(path.endsWith('/history')){
      const selected=new URL(route.request().url()).searchParams.get('session')??'work-new';
      data={sessions:[{session:'work-new',started_ms:String(now),last_ms:String(now),event_count:'1'},{session:'work-old',started_ms:String(now-3600000),last_ms:String(now-3500000),event_count:'1'}],events:[{kind:'phase',received_ms:String(now),state:{...publish().state,session:selected,action:selected==='work-old'?'이전 작업 안내':'이번 작업 안내'}}]};
    }
    else if(path.endsWith('/recordings'))data={enabled:recordingEnabled,recordings:deleted?[]:[{id:record,status:'ready',created_ms:String(now-120000),expires_ms:String(now+604800000),duration_ms:'95000',bytes:'5000000',reason:'stopped',segment:2,gap_before_ms:'4300'}]};
    else if(path.endsWith('/download'))data={url:'https://download.invalid/qa.mp4'};
    else if(path.endsWith('/delete')){deleted=true;data={ok:true};}
    await route.fulfill({json:data});
  });
  let recordingStatus='quota_full',streamStatus='live',stateChanges={};
  await context.routeWebSocket('**/qa-socket',ws=>{
    let timer;ws.onMessage(message=>{
      if(JSON.parse(message).role!=='observer')return;
      const send=()=>{const snapshot=publish();snapshot.state={...snapshot.state,video_available:true,recording_consent:true,remaining_ms:2000,...stateChanges};
        ws.send(JSON.stringify({type:'state',status:streamStatus,snapshot,received_at_ms:Date.now(),history_status:'ok',recording_status:recordingStatus}));};
      send();timer=setInterval(send,500);
    });ws.onClose(()=>clearInterval(timer));
  });
  const syntheticFrame=(await syntheticPackets())[0];let videoConnections=0;
  await context.routeWebSocket('**/video',ws=>{
    let timer,seq=0;videoConnections++;
    ws.onMessage(()=>{
      ws.send(JSON.stringify({type:'ready'}));
      timer=setInterval(()=>{
        const frame=Buffer.alloc(21+syntheticFrame.data.length);frame.write('ARV2');frame[4]=1;frame.writeUInt32BE(++seq,5);
        frame.writeBigUInt64BE(BigInt(seq*100000),9);frame.writeUInt16BE(1280,17);frame.writeUInt16BE(720,19);frame.set(syntheticFrame.data,21);ws.send(frame);
      },100);
    });ws.onClose(()=>clearInterval(timer));
  });
  await context.route('https://download.invalid/qa.mp4',route=>route.fulfill({body:'synthetic download test',contentType:'video/mp4',headers:{'Content-Disposition':'attachment; filename="qa.mp4"'}}));
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.getByRole('tab',{name:'저장 영상',exact:true}).click({timeout:3000});
  await page.getByRole('button',{name:/영상 다운로드/}).waitFor();
  await page.getByText('서버 녹화가 꺼져 있어 새 영상은 저장되지 않아요.',{exact:true}).waitFor({timeout:3000});
  recordingEnabled=true;await page.getByRole('button',{name:'영상 목록 새로고침'}).click();
  await page.getByText('서버 녹화 사용 가능',{exact:true}).waitFor();
  await page.getByText('구간 2 · 앞 구간 이후 약 5초 공백',{exact:true}).waitFor();
  const dir=fileURLToPath(new URL('../.local/recording-ui',import.meta.url));await mkdir(dir,{recursive:true});
  for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
    await page.setViewportSize({width,height});await page.screenshot({path:join(dir,`${name}.png`),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'page overflow');
    assert(await page.getByRole('button',{name:/영상 다운로드/}).isEnabled());
    const bounds=await page.getByRole('button',{name:/영상 다운로드/}).boundingBox();assert(bounds&&bounds.x+bounds.width<=width,'download button off screen');
  }
  await page.getByRole('tab',{name:'실시간 관제',exact:true}).click();
  for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
    await page.setViewportSize({width,height});
    await page.getByText('저장 공간 부족 · 녹화 안 됨',{exact:true}).waitFor();
    assert(await page.getByRole('alert').filter({hasText:'저장 공간이 부족해'}).isVisible());
    assert(await page.getByText('동의함',{exact:true}).isVisible());
    assert(await page.getByText('연결됨',{exact:true}).isVisible());
    await page.screenshot({path:join(dir,`${name}-quota.png`),fullPage:true});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'quota page overflow');
  }
  for(const [status,label] of [['interrupted','녹화 중단 · 재연결 대기'],['recovering','녹화 재개 대기']]){
    recordingStatus=status;await page.getByText(label,{exact:true}).waitFor();
    assert(await page.getByRole('status').filter({hasText:'끊기기 전 영상은 저장됐어요'}).isVisible());
    assert(await page.getByText('연결됨',{exact:true}).isVisible());
    await page.screenshot({path:join(dir,`mobile-${status}.png`),fullPage:true});
  }
  recordingStatus='capturing';await page.getByText('녹화 중',{exact:true}).waitFor();
  assert.equal(await page.getByRole('status').filter({hasText:'끊기기 전 영상은 저장됐어요'}).count(),0);
  assert.equal(await page.getByRole('alert').filter({hasText:'저장 공간이 부족해'}).count(),0);
  assert.equal(videoConnections,0,'video must stay disconnected while hidden');
  for(const [name,width,height] of [['wide',1920,1080],['laptop',1440,900],['tablet',820,1180],['mobile',390,844],['small',320,740]]){
    await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));
    const video=page.locator('.video-surface'),toggle=page.getByRole('switch',{name:'영상 표시'});
    assert(await video.isVisible(),'video slot must remain visible while disabled');
    assert.equal(await page.getByText(/다음 안내까지.*초/).count(),0,'countdown must not be displayed');
    const bounds=()=>page.evaluate(()=>Object.fromEntries(['.video-surface','#actionSurface','.sequence','.observer-status'].map(selector=>{
      const r=document.querySelector(selector).getBoundingClientRect();return [selector,[r.x,r.y+scrollY,r.width,r.height]];
    })));
    const off=await bounds();await page.screenshot({path:join(dir,`${name}-layout-off.png`),fullPage:true});
    await toggle.check();await page.locator('.video-badge').waitFor();
    assert.deepEqual(await bounds(),off,'video toggle moved the workspace');
    assert(await page.locator('canvas').evaluate(c=>c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((value,index)=>index%4!==3&&value>0)),'decoded video is blank');
    await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:join(dir,`${name}-layout-on.png`),fullPage:true});
    await toggle.uncheck();assert.deepEqual(await bounds(),off,'video off moved the workspace');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'layout page overflow');
  }
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>scrollTo(0,0));
  await page.getByRole('button',{name:'화면 테마 바꾸기'}).click();
  assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
  await page.screenshot({path:join(dir,'laptop-light.png'),fullPage:true});
  await page.getByRole('button',{name:'화면 테마 바꾸기'}).click();
  for(const [stage,phase,action] of [[0,'PREPARATION','상자를 놓아주세요'],[1,'PREPARATION','뚜껑을 닫아주세요'],[6,'INSPECTION','조립 상태를 확인해주세요']]){
    stateChanges={stage,phase,action};await page.locator('#actionTitle').filter({hasText:action}).waitFor();
    assert.equal(await page.getByText(/다음 안내까지.*초/).count(),0);
    assert(await page.locator('.video-surface').isVisible());
    assert.equal(await page.locator('.phase-rail').getAttribute('aria-hidden'),'true');
  }
  recordingStatus='off';stateChanges={running:false,stage:-1,phase:'PREPARATION',action:'작업을 시작해주세요',overlay_visible:false,tracked:false,video_available:false,recording_consent:false};
  await page.locator('#actionTitle').filter({hasText:'작업을 시작해주세요'}).waitFor();
  await page.screenshot({path:join(dir,'laptop-idle.png'),fullPage:true});
  streamStatus='stale';await page.getByText('상태 수신 지연',{exact:true}).waitFor();
  assert.equal(await page.locator('#actionTitle').innerText(),'현재 안내를 확인할 수 없어요');
  assert.equal(await page.locator('.target-map .active').count(),0);
  assert(await page.locator('.video-surface').isVisible());
  await page.screenshot({path:join(dir,'laptop-stale.png'),fullPage:true});
  streamStatus='live';stateChanges={};await page.locator('#actionTitle').filter({hasText:'나사 A를 조여주세요'}).waitFor();
  await page.getByRole('tab',{name:'작업 기록',exact:true}).click();
  assert.equal(await page.getByRole('button',{name:/영상 다운로드/}).isVisible(),false,'recordings must be separate from work history');
  await page.getByLabel('표시 범위').selectOption('all');
  await page.getByText('이번 작업 안내',{exact:true}).waitFor();
  await page.getByLabel('작업 선택').selectOption('work-old');
  await page.getByText('이전 작업 안내',{exact:true}).waitFor();
  assert.equal(await page.getByText('이번 작업 안내',{exact:true}).count(),0);
  await page.getByLabel('작업 선택').selectOption('');
  await page.getByText('이번 작업 안내',{exact:true}).waitFor();
  await page.keyboard.press('Escape');await page.locator('h1').click();await page.mouse.move(500,200);
  await page.waitForFunction(()=>document.documentElement.dataset.scrollbarVisible==='false');
  await page.mouse.move(1439,300);
  assert.equal(await page.locator('html').getAttribute('data-scrollbar-visible'),'true');
  await page.keyboard.press('Tab');
  assert.equal(await page.locator('html').getAttribute('data-scrollbar-visible'),'true');
  await page.screenshot({path:join(dir,'history-latest.png'),fullPage:true});
  await page.getByRole('tab',{name:'저장 영상',exact:true}).click();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:/영상 다운로드/}).click();assert.equal((await download).suggestedFilename(),'qa.mp4');
  page.once('dialog',d=>d.accept());await page.getByRole('button',{name:/영상 삭제/}).click();
  await page.getByText('저장된 영상이 없어요',{exact:true}).waitFor();assert(deleted);assert.deepEqual(errors,[]);
  await page.goto(base+'/login');
  for(const [name,width,height] of [['desktop',1440,900],['mobile',390,844],['small',320,740]]){
    await page.setViewportSize({width,height});
    await page.getByRole('heading',{name:'관제 로그인'}).waitFor();
    assert(await page.getByRole('button',{name:'GitHub로 로그인'}).isVisible());
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'login overflow');
    assert(await page.evaluate(async()=>{const i=new Image();i.src='/assembly-plan.png';await i.decode();return i.naturalWidth===1920;}),'login asset failed');
    await page.screenshot({path:join(dir,`${name}-login.png`),fullPage:true});
  }
  await page.goto(base+'/login?error=AccessDenied');await page.getByRole('alert').filter({hasText:'로그인할 수 없어요'}).waitFor();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({screenshots:dir,checks:['desktop','mobile','visible-actions','no-page-overflow','quota-alert','segment-and-gap','interrupted','recovering','consent-not-capture','live-connection-survives-quota','capturing-state','no-countdown','stable-video-on-off-5-viewports','decoded-video-pixels','light-theme','box-lid-inspection-idle-stale','download','delete-confirmation','empty-state','no-js-errors']}));
}finally{
  await browser?.close();child.kill();await once(child,'exit').catch(()=>{});
}
