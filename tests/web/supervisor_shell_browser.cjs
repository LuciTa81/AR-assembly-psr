const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),output=process.env.DEMO_OUTPUT||path.join(root,'outputs/supervisor_demo');
const origin='http://127.0.0.1:18774';
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
  const checks=[];
  try{
    for(const [width,height] of [[2048,1076],[1440,900],[1366,768],[1280,720],[390,844],[320,740]]){
      const page=await browser.newPage({viewport:{width,height},colorScheme:'light',acceptDownloads:true}),errors=[];
      let frame=0,index=2,videoRequests=0;
      const photo=process.env.DEMO_REFERENCE_IMAGE?fs.readFileSync(process.env.DEMO_REFERENCE_IMAGE):null;
      page.on('pageerror',e=>errors.push(e.message));
      await page.route(origin+'/**',route=>{
        const file=new URL(route.request().url()).pathname.slice(1);
        if(file==='state.json')return route.fulfill({json:{schema_version:'realtime_v1',source:'synthetic_fixture',session_id:'synthetic-shell-test',frame_id:++frame,timestamp_ms:Date.now(),frame_age_ms:0,system_status:'RUNNING',marker_status:'OK',marker_count:5,current_state:'S'+index,current_label:'Test',target:'screw_'+('ABCD'[index-2].toLowerCase()),next_action:'Hold the tool',fps:20,latency_ms:40,guidance:{schema_version:'assembly_guidance_v1',phase:'OBSERVING',reason:'',acknowledgement:'',acknowledgement_remaining_ms:0},extra:{operator:{mode:'hybrid',revision:index,can_confirm:false,pending:false,completed:false}}}});
        if(file==='frame.jpg'){
          videoRequests++;
          return photo?route.fulfill({body:photo,headers:{'Content-Type':'image/jpeg','X-AR-Session':'synthetic-shell-test','X-AR-Source':'synthetic_fixture','X-AR-Frame-Id':String(++frame),'X-AR-Timestamp-Ms':String(Date.now()),'X-AR-Frame-Age-Ms':'0'}}):route.fulfill({status:503,body:''});
        }
        if(/^fonts\/IBMPlexSansKR-(Regular|Medium|SemiBold|Bold)\.woff2$/.test(file))
          return route.fulfill({path:path.join(root,'web_overlay',file),contentType:'font/woff2'});
        if(!/^supervisor(?:_demo|_shell|_state|_video)?\.(html|js|css)$/.test(file))return route.fulfill({status:404,body:''});
        return route.fulfill({path:path.join(root,'web_overlay',file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
      });
      await page.goto(origin+'/supervisor_demo.html');
      await page.waitForFunction(()=>document.querySelector('#liveCue').dataset.cue==='HOLD');
      await page.evaluate(()=>document.fonts.ready);
      assert.equal(await page.evaluate(()=>[...document.fonts].some(f=>f.family.includes('IBM Plex Sans KR')&&f.status==='loaded')),true,'Use the bundled reference font');
      assert.equal(await page.locator('#showVideo').isVisible(),true);
      assert(await page.locator('#feedbackDetail').evaluate(e=>parseFloat(getComputedStyle(e).fontSize)>=14));
      assert.equal(await page.locator('#liveCue').innerText(),'드라이버 유지 중');
      assert.equal(await page.locator('.summary-strip').count(),0);
      assert.equal(await page.evaluate(()=>{
        const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);
        return new Set(ids).size===ids.length;
      }),true,'Moving diagnostics must not duplicate controller IDs');
      assert.equal(await page.evaluate(()=>[...document.querySelectorAll('[data-hover]')]
        .every(e=>e.matches('button,#actionSurface,.camera-view>.section-heading')||(e.matches('label')&&e.querySelector('input[type=radio]')))),true);
      assert.equal(await page.locator('.camera-view>.section-heading').getAttribute('data-hover'),'tool');
      assert.equal(await page.locator('#videoStage[data-hover],#videoImage[data-hover],#feedback[data-hover]').count(),0);
      assert.equal(await page.locator('#currentState').isVisible(),false);
      assert.equal(await page.locator('#videoFrame').isVisible(),false);
      assert.equal(await page.locator('#feedback').isVisible(),false);
      const actionBox=await page.locator('#actionTitle').boundingBox();
      assert(actionBox.y+actionBox.height<height,'Next action should fit in the first viewport');
      if(width>=1280){
        const camera=await page.locator('.camera-view').boundingBox(),action=await page.locator('#actionSurface').boundingBox();
        assert(camera.width/action.width>=1.95&&camera.width/action.width<=2.1,'Video uses two thirds; guidance retains one third');
        assert(Math.abs(camera.y-action.y)<2,'Video and current task begin on the same row');
        const video=await page.locator('#videoStage').boundingBox();
        assert(video.y<=160,'No summary cards should push the video down');
        assert(video.height>=height-358,'Video leaves room for its toolbar, metadata and the task sequence');
        assert.equal(await page.locator('#videoImage').evaluate(e=>getComputedStyle(e).objectFit),'contain');
        assert(await page.locator('#actionTitle').evaluate(e=>parseFloat(getComputedStyle(e).fontSize)<=24));
        assert.equal(await page.locator('.target-map-row').isVisible(),true,'Laptop and projector layouts retain the screw location');
        const rail=await page.locator('#phaseRail').boundingBox(),map=await page.locator('.target-map-row').boundingBox();
        assert(map.y-(rail.y+rail.height)<=24,'Screw location stays with the current action instead of at the far bottom');
      }
      assert.equal(await page.locator('[role=tab]').count(),4);
      await page.locator('.recent-section a').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(()=>!document.getElementById('view-history').hidden);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'tab-history');
      await page.locator('#returnToLive a').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(()=>!document.getElementById('view-live').hidden);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'tab-live');
      assert.equal(videoRequests,0);
      assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
      await page.locator('#themeToggle').click();
      assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
      await page.reload();
      await page.waitForFunction(()=>document.querySelector('#liveCue').dataset.cue==='HOLD');
      assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
      await page.locator('#showVideo').click();
      assert.equal(await page.locator('#videoEnabled').isChecked(),true);
      assert.equal(await page.locator('#settingsVideo').isChecked(),true);
      await page.waitForFunction(()=>document.getElementById('videoStage').dataset.status!=='OFF');
      assert.equal(await page.locator('#showVideo').isVisible(),false);
      if(photo)await page.waitForFunction(()=>document.querySelector('#videoStage').dataset.status==='LIVE');
      await page.evaluate(()=>window.originalVideo=document.getElementById('videoImage'));
      for(const theme of ['light','dark']){
        if(await page.locator('html').getAttribute('data-theme')!==theme)await page.locator('#themeToggle').click();
        for(const tab of ['live','history','tracking','settings']){
          await page.locator('#tab-'+tab).click();
          await page.waitForFunction(id=>!document.getElementById('view-'+id).hidden,tab);
          assert.equal(await page.locator('[role=tabpanel]:visible').count(),1);
          assert.equal(await page.locator('#tab-'+tab).getAttribute('aria-selected'),'true');
          assert.equal(await page.evaluate(()=>originalVideo===document.getElementById('videoImage')),true);
          assert.equal(await page.locator('#videoEnabled').isChecked(),true);
          assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
          await page.waitForTimeout(220);
          await page.screenshot({path:path.join(output,`shell-${width}-${theme}-${tab}.png`),fullPage:true});
          checks.push({width,theme,tab});
        }
      }
      await page.locator('#motionEnabled').uncheck();
      assert.equal(await page.locator('html').getAttribute('data-motion'),'off');
      await page.locator('#motionEnabled').check();
      await page.emulateMedia({reducedMotion:'reduce'});
      await page.waitForFunction(()=>document.documentElement.dataset.motion==='off');
      assert.equal(await page.locator('html').getAttribute('data-highlight'),'off');
      await page.emulateMedia({reducedMotion:'no-preference'});
      await page.waitForFunction(()=>document.documentElement.dataset.motion==='on');
      await page.locator('#settingsVideo').uncheck();
      assert.equal(await page.locator('#videoEnabled').isChecked(),false);
      await page.waitForTimeout(350);const stopped=videoRequests;
      await page.waitForTimeout(350);assert.equal(videoRequests,stopped);
      await page.locator('#tab-live').click();
      await page.locator('.video-details summary').click();
      assert.equal(await page.locator('#videoFrame').isVisible(),true);
      await page.locator('.video-details summary').click();
      await page.locator('#tab-live').focus();await page.keyboard.press('ArrowRight');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'tab-history');
      await page.waitForFunction(()=>!document.getElementById('view-history').hidden);
      index=3;
      await page.waitForFunction(()=>document.getElementById('targetLetter').textContent==='B');
      await page.waitForFunction(()=>document.getElementById('historyRows').textContent.includes('나사 B'));
      const downloadPromise=page.waitForEvent('download');
      await page.locator('#downloadEvents').click();
      const download=await downloadPromise,pathOut=path.join(output,`events-${width}.json`);
      await download.saveAs(pathOut);
      const report=JSON.parse(fs.readFileSync(pathOut,'utf8'));
      assert.equal(report.scope,'page_session_events');
      assert.equal(report.session_id,'synthetic-shell-test');
      assert(report.events.length>0);
      await page.locator('#tab-tracking').click();
      await page.goBack();
      await page.waitForFunction(()=>!document.getElementById('view-history').hidden);
      await page.locator('#tab-live').click();
      assert.equal(await page.locator('#targetLetter').innerText(),'B');
      if(width===1440){
        await page.locator('#tab-settings').click();
        await page.locator('.theme-option').first().hover();
        assert.equal(await page.locator('.theme-option').first().getAttribute('data-hovering'),'true');
        assert.notEqual(await page.locator('.theme-option').first().evaluate(e=>e.style.getPropertyValue('--hover-x')),'');
        await page.screenshot({path:path.join(output,'shell-hover-dark.png'),fullPage:true});
      }
      assert.deepEqual(errors,[]);
      await page.close();
    }
    fs.writeFileSync(path.join(output,'shell-browser-report.json'),JSON.stringify({checks,pageErrors:0,videoContinuity:true,themePersistence:true,reducedMotion:true,keyboardNavigation:true,historyExport:true},null,2));
    console.log(JSON.stringify({checks:checks.length,pageErrors:0,videoContinuity:true}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
