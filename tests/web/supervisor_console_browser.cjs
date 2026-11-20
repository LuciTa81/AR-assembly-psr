const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const origin = 'http://127.0.0.1:18774';
const out = process.env.DEMO_OUTPUT || path.join(root, 'outputs/console');
(async () => {
  fs.mkdirSync(out, {recursive: true});
  const browser = await chromium.launch({headless: true, ...(process.env.CHROME_EXECUTABLE ? {executablePath:process.env.CHROME_EXECUTABLE} : {})});
  try {
    for (const [width,height] of [[1440,900],[1280,720],[390,844],[320,740]]) {
      const page = await browser.newPage({viewport:{width,height}});
      const errors = [], actions = [];
      let status = 'idle', ready = false, imageRequests = 0, stage = 0, frame = 0, offline = false, marker = 'OK';
      page.on('pageerror', e => errors.push(e.message));
      await page.route(origin+'/**', async route => {
        const req = route.request(), name = new URL(req.url()).pathname.slice(1);
        if (name === 'console/status' && offline) return route.abort();
        if (name === 'console/status') return route.fulfill({json:{schema_version:'beast_console_v1',status,
          preflight:ready?{ready:true,checks:[{name:'files',ok:true}]}:null,error:'',session_id:status==='running'?'test':null}});
        if (name.startsWith('console/')) {
          actions.push(name);
          assert.equal(req.headers()['x-ar-console'],'control');
          assert.deepEqual(req.postDataJSON(),{});
          status=name.endsWith('/start')?'running':'idle'; ready=true;
          return route.fulfill({status:202,json:{accepted:true}});
        }
        if (name === 'operator/confirm') {
          assert.deepEqual(req.postDataJSON(),{session_id:'test',revision:stage});
          stage++;
          return route.fulfill({status:202,json:{accepted:true}});
        }
        if (name === 'state.json') return status!=='running'
          ? route.fulfill({status:503,json:{error:'test_camera_off'}})
          : route.fulfill({json:{schema_version:'realtime_v1',session_id:'test',source:'synthetic_fixture',
            frame_id:++frame,timestamp_ms:Date.now(),frame_age_ms:0,system_status:'RUNNING',marker_status:marker,
            marker_count:marker==='OK'?5:0,current_state:'S'+stage,current_label:'Test state',target:stage?'lid':'box',
            next_action:'Fixture instruction',fps:20,latency_ms:40,
            guidance:{schema_version:'assembly_guidance_v1',phase:'GUIDING',reason:'operator_confirmation',
              acknowledgement:'',acknowledgement_remaining_ms:0,hold_progress:'none',hold_remaining_ms:0},
            extra:{operator:{mode:'hybrid',revision:stage,can_confirm:true,pending:false,completed:false}}}});
        if (name === 'frame.jpg') { imageRequests++; return route.fulfill({status:503,body:''}); }
        const file = name || 'supervisor_demo.html';
        if (!fs.existsSync(path.join(root,'web_overlay',file))) return route.fulfill({status:404,body:''});
        let body=fs.readFileSync(path.join(root,'web_overlay',file));
        if(file === 'supervisor_demo.html') body=Buffer.from(body.toString().replace('</head>',
          '<link rel="stylesheet" href="/supervisor_console.css"><script defer src="/supervisor_console.js"></script></head>'));
        return route.fulfill({body,contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.woff2')?'font/woff2':'text/html'});
      });
      await page.goto(origin);
      await page.waitForSelector('#consoleStart', {timeout:5000});
      assert(await page.locator('#consoleStart').isDisabled());
      await page.locator('#consoleCheck').click();
      await page.waitForFunction(()=>document.getElementById('consoleChecks').textContent.includes('files'));
      await page.locator('#consolePrepared').check();
      await page.waitForFunction(()=>!document.getElementById('consoleStart').disabled);
      assert.equal(imageRequests,0);
      await page.screenshot({path:path.join(out,`ready-${width}.png`),fullPage:true});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false, 'horizontal overflow at '+width);
      await page.locator('#consoleStart').click();
      await page.waitForFunction(()=>document.body.dataset.console==='running');
      assert.equal(actions.filter(x=>x==='console/start').length,1);
      await page.waitForFunction(()=>!document.getElementById('confirmStep').disabled);
      await page.evaluate(()=>document.fonts.ready);
      const readyButton=await page.locator('#confirmStep').boundingBox();
      for (const nextMarker of ['LOST','OK','LOST','OK']) {
        marker=nextMarker;
        await page.waitForFunction(expected=>document.getElementById('status').dataset.status===expected,
          marker==='OK'?'GUIDING':'TRACKING_LOST');
        const button=await page.locator('#confirmStep').boundingBox();
        if (width>800) assert(Math.abs(button.y-readyButton.y)<1,`Confirmation moved at ${width}: ${readyButton.y} -> ${button.y}`);
        assert.equal(await page.locator('#confirmStep').isDisabled(),marker!=='OK');
        assert.equal(await page.locator('#feedback').isVisible(),marker!=='OK');
        assert.equal(await page.locator('#confirmationHint').isVisible(),marker==='OK');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      }
      await page.screenshot({path:path.join(out,`confirmation-${width}.png`),fullPage:true});
      await page.locator('#confirmStep').click();
      await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S1');
      await page.screenshot({path:path.join(out,`running-${width}.png`),fullPage:true});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.reload();
      await page.waitForFunction(()=>document.body.dataset.console==='running');
      assert.equal(actions.filter(x=>x==='console/start').length,1);
      await page.locator('#consoleStop').click();
      await page.waitForFunction(()=>document.body.dataset.console==='idle');
      assert.equal(await page.locator('#consolePrepared').isChecked(),false);
      assert(await page.locator('#consoleStart').isDisabled());
      offline=true;
      await page.waitForFunction(()=>document.body.dataset.console==='offline');
      assert.equal(await page.locator('#consoleDetail').textContent(),'실행 상태 확인 필요');
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('console desktop/mobile start, stop, reload and opt-in checks passed');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
