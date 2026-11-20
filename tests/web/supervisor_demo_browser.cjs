const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname,'../..');
const output = process.env.DEMO_OUTPUT || path.join(root,'outputs/supervisor_demo');
const origin = 'http://127.0.0.1:18773';
const files = ['supervisor_demo.html','supervisor_demo.css','supervisor_demo.js','supervisor_shell.js','supervisor_state.js','supervisor_video.js','supervisor.js'];
let index=0, phase='GUIDING', marker='OK', hold='none', fault=false, sequence=0, confirms=0, imageRequests=0;
function snapshot() {
  const manual=[0,1,6].includes(index);
  return {schema_version:'realtime_v1',session_id:'synthetic-demo-test',source:'synthetic_fixture',
    frame_id:++sequence,timestamp_ms:Date.now(),frame_age_ms:0,system_status:'RUNNING',
    marker_status:marker,marker_count:marker==='OK'?5:0,current_state:'S'+index,current_label:'Test state',
    target:['box','lid','screw_a','screw_b','screw_c','screw_d','complete'][index],next_action:'Fixture server instruction',
    fps:20,latency_ms:40,guidance:{schema_version:'assembly_guidance_v1',phase,
      reason:manual?'operator_confirmation':'tool_not_visible',acknowledgement:'',acknowledgement_remaining_ms:0,
      hold_progress:hold,hold_remaining_ms:hold==='retained'?1500:0},
    extra:{operator:{mode:'hybrid',revision:index,can_confirm:manual,pending:false,completed:phase==='COMPLETED'}}};
}
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
  const checks=[];
  const photo=process.env.DEMO_REFERENCE_IMAGE ? fs.readFileSync(process.env.DEMO_REFERENCE_IMAGE):null;
  try {
    for(const [width,height] of [[1440,900],[1366,768],[1280,720],[1920,1080],[390,844],[320,740]]) {
      index=0;phase='GUIDING';marker='OK';hold='none';fault=false;confirms=0;imageRequests=0;
      const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'}),errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.route(origin+'/**', async route=>{
        const file=new URL(route.request().url()).pathname.slice(1);
        if(/^fonts\/IBMPlexSansKR-(Regular|Medium|SemiBold|Bold)\.woff2$/.test(file))
          return route.fulfill({path:path.join(root,'web_overlay',file),contentType:'font/woff2'});
        if(file==='state.json') return fault?route.abort():route.fulfill({json:snapshot()});
        if(file==='operator/confirm') {
          confirms++;
          assert.deepEqual(route.request().postDataJSON(),{session_id:'synthetic-demo-test',revision:index});
          await new Promise(resolve=>setTimeout(resolve,250));
          index=Math.min(index+1,6);
          return route.fulfill({status:202,json:{accepted:true}});
        }
        if(file==='frame.jpg') {
          imageRequests++;
          if(!photo) return route.fulfill({status:503,body:''});
          return route.fulfill({body:photo,headers:{'Content-Type':'image/jpeg',
            'X-AR-Session':'synthetic-demo-test','X-AR-Source':'synthetic_fixture',
            'X-AR-Frame-Id':String(++sequence),'X-AR-Timestamp-Ms':String(Date.now()),'X-AR-Frame-Age-Ms':'0'}});
        }
        return files.includes(file)?route.fulfill({path:path.join(root,'web_overlay',file),
          contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'}):route.fulfill({status:404,body:''});
      });
      await page.goto(origin+'/supervisor_demo.html');
      await page.waitForFunction(()=>!document.getElementById('confirmStep').disabled);
      assert.equal(imageRequests,0);
      assert.equal(await page.locator('#videoEnabled').isChecked(),false);
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.className),'skip-link');
      await page.keyboard.press('Enter');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'actionSurface');
      assert.equal(await page.locator('.skip-link').evaluate(el=>el.getBoundingClientRect().bottom<=0),true);
      await page.locator('#confirmStep').click();
      assert.equal(await page.locator('#confirmStep').isDisabled(),true);
      await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S1');
      assert.equal(confirms,1);
      await page.locator('#confirmStep').click();
      await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S2');
      assert.equal(await page.locator('#confirmStep').isVisible(),false);
      await page.locator('#actionSurface').focus();
      if(width===1440) {
        await page.locator('#fullscreen').click();
        await page.waitForFunction(()=>Boolean(document.fullscreenElement));
        await page.mouse.move(100,100);
        assert.equal(await page.locator('html').getAttribute('data-fullscreen'),'true');
        assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollbarColor),'rgba(0, 0, 0, 0) rgba(0, 0, 0, 0)');
        const viewportWidth=await page.evaluate(()=>innerWidth);
        const beforeWidth=await page.locator('.workspace').evaluate(e=>e.getBoundingClientRect().width);
        await page.mouse.move(viewportWidth-18,180);
        assert.equal(await page.locator('html').getAttribute('data-scrollbar-visible'),'true');
        assert.notEqual(await page.evaluate(()=>getComputedStyle(document.documentElement).scrollbarColor),'rgba(0, 0, 0, 0) rgba(0, 0, 0, 0)');
        assert.equal(await page.locator('.workspace').evaluate(e=>e.getBoundingClientRect().width),beforeWidth);
        await page.mouse.move(100,100);
        assert.equal(await page.locator('html').getAttribute('data-scrollbar-visible'),'false');
        await page.keyboard.press('PageDown');
        await page.waitForFunction(()=>scrollY>0);
        assert.equal(await page.locator('html').getAttribute('data-scrollbar-visible'),'true');
        await page.evaluate(()=>scrollTo(0,0));
        await page.locator('#fullscreen').click();
        await page.waitForFunction(()=>!document.fullscreenElement);
        await page.waitForFunction(()=>document.documentElement.dataset.fullscreen==='false');
      }
      for(const mode of ['setup','hold','release','retained','recheck','lost','final','completed','disconnected']) {
        index=mode==='setup'?0:['final','completed','disconnected'].includes(mode)?6:4;
        phase=mode==='hold'?'OBSERVING':mode==='release'?'OBSERVED':['retained','recheck'].includes(mode)?'PAUSED':mode==='final'?'AWAITING_CONFIRMATION':mode==='completed'?'COMPLETED':'GUIDING';
        hold=['retained','recheck'].includes(mode)?mode:'none';
        marker=['lost','final'].includes(mode)?'LOST':'OK';fault=mode==='disconnected';
        const expected={setup:'CHECK',hold:'HOLD',release:'MOVE CLEAR',retained:'PAUSED · KEPT',recheck:'RECHECK',lost:'PAUSED',final:'FINAL CHECK',completed:'CONFIRMED',disconnected:'OFFLINE'}[mode];
        await page.waitForFunction(cue=>document.getElementById('liveCue').dataset.cue===cue,expected);
        await page.waitForTimeout(300);
        await page.evaluate(()=>window.scrollTo(0,0));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        const overflow=await page.evaluate(()=>['actionTitle','feedbackTitle','feedbackDetail','confirmStep','stateLabel','liveCue'].filter(id=>{
          const e=document.getElementById(id);return e.getClientRects().length&&e.scrollWidth>e.clientWidth+1;
        }));
        assert.deepEqual(overflow,[]);
        if(width>=1280 && mode==='hold') {
          const steps=await page.locator('#steps').boundingBox();
          assert(steps.y+steps.height<=height,'Task sequence must be visible in the first desktop viewport');
        }
        assert.doesNotMatch(await page.locator('#liveCue').innerText(),/HOLD|MOVE CLEAR|PAUSED|RECHECK|OFFLINE/);
        assert.equal(await page.locator('#currentState').isVisible(),false);
        if(['release','lost','retained','recheck','disconnected'].includes(mode))
          assert.equal(await page.locator('#feedback').isVisible(),true);
        if(['hold','setup','final','completed'].includes(mode))
          assert.equal(await page.locator('#feedback').isVisible(),false);
        if(['setup','final'].includes(mode)) {
          assert.equal(await page.locator('#targetLetter').isVisible(),false);
          assert.equal(await page.locator('.target-map-row').isVisible(),false);
        }
        if(mode==='disconnected') {
          assert.equal(await page.locator('#confirmationHint').isVisible(),false);
          assert.equal(await page.locator('#feedbackDetail').isVisible(),true);
        }
        if(['lost','retained','disconnected'].includes(mode)) {
          assert.doesNotMatch(await page.locator('#actionTitle').innerText(),/대어|떼어|완료/);
        }
        if(mode==='final') assert.equal(await page.locator('#confirmStep').isEnabled(),true);
        if(['completed','disconnected'].includes(mode)) assert.equal(await page.locator('#confirmStep').isEnabled(),false);
        if(width<=390) {
          const action=await page.locator('#actionTitle').boundingBox(),video=await page.locator('#videoStage').boundingBox();
          assert(action.y<video.y);
          const order=await page.locator('#steps').boundingBox();
          assert(order.y+order.height<video.y,'Mobile sequence precedes the video');
        }
        if(mode==='release') {
          assert.match(await page.locator('#feedbackDetail').innerText(),/카메라에는 보이게 유지/);
          await page.locator('#videoEnabled').check();
          await page.waitForFunction(()=>document.getElementById('videoStage').dataset.status!=='OFF');
          if(photo) {
            await page.waitForFunction(()=>document.getElementById('videoStage').dataset.status==='LIVE');
            assert.equal(await page.locator('#videoSource').innerText(),'미리보기 · 테스트 영상');
          }
          await page.evaluate(()=>window.scrollTo(0,0));
          await page.screenshot({path:path.join(output,`${width}-reference-photo-fixture.png`),fullPage:true});
          await page.locator('#videoEnabled').uncheck();
          await page.waitForTimeout(300);
          const stopped=imageRequests;
          await page.waitForTimeout(300);
          assert.equal(imageRequests,stopped);
          assert.equal(await page.locator('#videoImage').getAttribute('src'),null);
        }
        await page.evaluate(()=>window.scrollTo(0,0));
        await page.screenshot({path:path.join(output,`${width}-${mode}.png`),fullPage:true});
        checks.push({width,height,mode,overflow:false});
      }
      await page.locator('#tab-history').click();
      assert.equal(await page.locator('#historyFilter').inputValue(),'steps');
      assert.equal(await page.locator('#historySession').isVisible(),false);
      const stageRows=await page.locator('#historyRows tr').count();
      assert(stageRows>=4);
      const stageText=await page.locator('#historyRows').innerText();
      assert.match(stageText,/단계 전환/);
      assert.match(stageText,/최종 완료/);
      assert.doesNotMatch(stageText,/연결이 끊겼어요|드라이버 유지 중|안내 일시 정지/);
      const recentText=await page.locator('#recentEvents').textContent();
      assert.doesNotMatch(recentText,/연결이 끊겼어요|드라이버 유지 중|안내 일시 정지/);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.doesNotMatch(await page.locator('body').innerText(),/관제 화면 후보|현재 세션의 작업 흐름|최근 120개 주요 변화/);
      await page.screenshot({path:path.join(output,`${width}-history-steps.png`),fullPage:true});
      await page.locator('#historyFilter').selectOption('all');
      assert(await page.locator('#historyRows tr').count()>stageRows);
      assert.match(await page.locator('#historyRows').innerText(),/연결이 끊겼어요/);
      await page.locator('#historyFilter').selectOption('attention');
      assert.match(await page.locator('#historyRows').innerText(),/연결이 끊겼어요/);
      await page.locator('#historyFilter').selectOption('steps');
      assert.equal(await page.locator('#historyRows tr').count(),stageRows);
      await page.locator('.history-details summary').click();
      assert.equal(await page.locator('#historySession').isVisible(),true);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.locator('.history-details summary').click();
      if(width===1440) {
        const downloaded=page.waitForEvent('download');
        await page.locator('#downloadEvents').click();
        const download=await downloaded;
        const exported=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
        assert.equal(exported.stage_events.length,stageRows);
        assert(exported.events.length>exported.stage_events.length);
        assert(exported.events.some(event=>event.cue==='OFFLINE'));
        assert.equal(exported.stage_events.filter(event=>event.kind==='complete').length,1);
      }
      checks.push({width,height,mode:'history-filters',stageRows,detailsPreserved:true});
      await page.locator('#tab-tracking').click();
      await page.locator('#diagnostics summary').click();
      assert.equal(await page.locator('#instruction').isVisible(),true);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);
      assert.equal(await page.locator('#recentEvents li').count()<=12,true);
      await page.locator('#tab-live').click();
      if(width===1440) {
        await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
        fault=false;index=2;phase='GUIDING';marker='OK';hold='none';
        await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S2');
        await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
        await page.waitForFunction(()=>document.getElementById('targetLetter').textContent==='A',null,{timeout:3000});
        index=3;
        await page.waitForFunction(()=>document.getElementById('targetLetter').textContent==='B',null,{timeout:3000});
      }
      await page.close();
    }
    fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify({checks,pageErrors:0,
      videoDefaultOff:true,confirmationApiUnchanged:true,syntheticStates:true,
      referencePhoto:process.env.DEMO_REFERENCE_IMAGE||null,
      note:'Reference photo is illustrative test input, not synchronized footage or through-lens capture.'},null,2));
    console.log(JSON.stringify({checks:checks.length,viewports:new Set(checks.map(check=>`${check.width}x${check.height}`)).size,pageErrors:0,videoDefaultOff:true}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
