const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'outputs/supervisor_usability');
let phase = 'GUIDING', index = 0, marker = 'OK', sequence = 0, progress = 'none', fault = false;
function snapshot() {
  const manual = [0,1,6].includes(index);
  return {schema_version:'realtime_v1',session_id:'synthetic-usability',source:'synthetic_fixture',
    frame_id:++sequence,timestamp_ms:Date.now(),frame_age_ms:0,system_status:'RUNNING',
    marker_status:marker,marker_count:marker==='OK'?5:0,current_state:'S'+index,current_label:'Raw label',
    target:['box','lid','screw_a','screw_b','screw_c','screw_d','complete'][index],
    next_action:'Exact server action',guidance:{schema_version:'assembly_guidance_v1',phase,
      reason:manual?'operator_confirmation':'tool_not_visible',acknowledgement:'',acknowledgement_remaining_ms:0,
      hold_progress:progress,hold_remaining_ms:progress==='retained'?1500:0},
    extra:{operator:{mode:'hybrid',revision:index,can_confirm:manual,pending:false,completed:phase==='COMPLETED'}}};
}
(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({headless:true});
  const checks = [];
  try {
    for (const [width,height] of [[1440,900],[1280,720],[390,844],[320,740]]) {
      const page = await browser.newPage({viewport:{width,height}}), errors=[], requests=[];
      page.on('pageerror', e=>errors.push(e.message));
      page.on('request', r=>requests.push(r.url()));
      await page.route('http://127.0.0.1:18769/**', route => {
        const file = new URL(route.request().url()).pathname.slice(1);
        if (file==='state.json') return fault ? route.abort() : route.fulfill({json:snapshot()});
        if (!['supervisor.html','supervisor.css','supervisor.js','supervisor_state.js','supervisor_video.js'].includes(file))
          return route.fulfill({status:404,body:''});
        return route.fulfill({path:path.join(root,'web_overlay',file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
      });
      index=0; phase='GUIDING'; marker='OK'; progress='none'; fault=false;
      await page.goto('http://127.0.0.1:18769/supervisor.html');
      await page.waitForFunction(()=>document.querySelector('#confirmStep').disabled===false);
      assert.equal(await page.locator('#diagnostics').getAttribute('open'), null);
      assert.equal(await page.locator('#feedback').getAttribute('aria-live'), 'polite');
      await page.locator('#diagnostics summary').click();
      assert.equal(await page.locator('#instruction').innerText(), 'Exact server action');
      await page.locator('#diagnostics summary').click();
      if (width===1440) {
        await page.locator('#fullscreen').click();
        await page.waitForFunction(()=>Boolean(document.fullscreenElement));
        assert.equal(await page.locator('#collapseIcon').isVisible(), true);
        assert.equal(await page.locator('#expandIcon').isVisible(), false);
        await page.locator('#fullscreen').click();
        await page.waitForFunction(()=>!document.fullscreenElement);
        await page.evaluate(()=>{document.documentElement.requestFullscreen=()=>Promise.reject(new Error('denied'));});
        await page.locator('#fullscreen').click();
        await page.waitForFunction(()=>!document.querySelector('#displayError').hidden);
        assert.equal(await page.locator('#currentState').innerText(), 'S0');
      }
      for (const mode of ['setup','hold','release','retained','recheck','final','completed','disconnected']) {
        phase = mode==='hold'?'OBSERVING':mode==='release'?'OBSERVED':mode==='retained'||mode==='recheck'?'PAUSED':mode==='final'?'AWAITING_CONFIRMATION':mode==='completed'?'COMPLETED':'GUIDING';
        index=mode==='setup'?0:['final','completed'].includes(mode)?6:2;
        progress=['retained','recheck'].includes(mode)?mode:'none';
        marker=mode==='final'?'LOST':'OK'; fault=mode==='disconnected';
        const expected=fault?'DISCONNECTED':phase;
        await page.waitForFunction(s=>document.querySelector('#status').dataset.status===s, expected);
        await page.waitForTimeout(120);
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        const overflowing = await page.evaluate(()=>['actionTitle','feedbackTitle','feedbackDetail','confirmStep','stateLabel'].filter(id=>{
          const el=document.getElementById(id); return el.getClientRects().length && el.scrollWidth>el.clientWidth+1;
        }));
        assert.deepEqual(overflowing,[]);
        // Disconnect retains the last S6 snapshot, but its confirmation must be disabled.
        assert.equal(await page.locator('#confirmStep').isVisible(),['setup','final','completed','disconnected'].includes(mode));
        if(mode==='final') assert.equal(await page.locator('#confirmStep').isEnabled(),true);
        if(mode==='completed') assert.equal(await page.locator('#confirmStep').isEnabled(),false);
        if(mode==='disconnected') {
          assert.equal(await page.locator('#confirmStep').isEnabled(),false);
          assert.doesNotMatch(await page.locator('#actionTitle').innerText(),/대어|떼어/);
        }
        if(width<=390) {
          const action=await page.locator('#actionTitle').boundingBox(), video=await page.locator('#videoStage').boundingBox();
          assert(action.y<video.y);
        }
        await page.screenshot({path:path.join(output,`${width}-${mode}.png`),fullPage:true});
        checks.push({width,mode,overflow:false});
      }
      assert.deepEqual(errors,[]);
      assert.equal(requests.some(url=>url.includes('frame.jpg')),false);
      await page.close();
    }
    fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify({checks,pageErrors:0,videoDefaultOff:true},null,2));
    console.log(JSON.stringify({screenshots:checks.length,viewports:4,pageErrors:0,videoDefaultOff:true}));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
