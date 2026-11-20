const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const output = path.join(root, 'outputs/supervisor_visual_feedback');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [], requests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => requests.push(r.url()));
  const jpeg = Buffer.from(await page.evaluate(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 960; canvas.height = 540;
    const c = canvas.getContext('2d');
    c.fillStyle = '#dbe8e1'; c.fillRect(0, 0, 960, 540);
    c.strokeStyle = '#bfd1c6';
    for (let x = 0; x < 960; x += 40) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, 540); c.stroke(); }
    for (let y = 0; y < 540; y += 40) { c.beginPath(); c.moveTo(0, y); c.lineTo(960, y); c.stroke(); }
    c.fillStyle = '#f8faf9'; c.fillRect(300, 125, 350, 290);
    c.lineWidth = 6; c.strokeStyle = '#65736c'; c.strokeRect(300, 125, 350, 290);
    c.font = 'bold 26px sans-serif';
    [[315,140,'A'],[635,140,'B'],[315,400,'C'],[635,400,'D']].forEach(([x,y,n]) => {
      c.beginPath(); c.arc(x,y,13,0,2*Math.PI); c.fillStyle='#4d5c54'; c.fill();
      c.fillText(n,x+20,y+8);
    });
    c.fillStyle='#fff'; c.fillRect(20,20,450,52);
    c.fillStyle='#31423a'; c.fillText('SYNTHETIC WORKSPACE',34,55);
    return canvas.toDataURL('image/jpeg').split(',')[1];
  }), 'base64');
  let state = 'S2', phase = 'OBSERVED', marker = 'OK', markerCount = 4, reason = '';
  let frame = 0, imageFrame = 0, imageTime = Date.now(), frozen = false, imageRequests = 0, broken = false;
  let responseDelay = 0;
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    res.setHeader('Cache-Control', 'no-store');
    if (pathname === '/state.json') {
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({
        schema_version:'realtime_v1',session_id:'visual-fixture',source:'synthetic_guidance_fixture',
        system_status:'RUNNING',frame_id:++frame,timestamp_ms:Date.now(),frame_age_ms:0,
        current_state:state,current_label:'Lid closed',target:'screw_a',next_action:'When finished, move driver clear of screw A',
        marker_status:marker,marker_count:markerCount,warp_quality:.75,fps:10,latency_ms:41,
        guidance:{schema_version:'assembly_guidance_v1',phase,reason,acknowledgement:'',acknowledgement_remaining_ms:0},
        extra:{yolo_reason:marker==='OK'?'ok':'before_tracking_recovery',driver_count:1,tool_tip_source:2},
      }));
    } else if (pathname === '/frame.jpg') {
      imageRequests++;
      if (!frozen) { imageFrame++; imageTime=Date.now(); }
      res.setHeader('Content-Type','image/jpeg');
      res.setHeader('X-AR-Session','visual-fixture');
      res.setHeader('X-AR-Source','synthetic_guidance_fixture');
      res.setHeader('X-AR-Frame-Id',imageFrame);
      res.setHeader('X-AR-Timestamp-Ms',imageTime);
      res.setHeader('X-AR-Frame-Age-Ms',Date.now()-imageTime);
      if (broken) { res.statusCode=503; res.end('unavailable'); }
      else setTimeout(() => res.end(jpeg), responseDelay);
    } else {
      const name = pathname.slice(1);
      if (!['supervisor.html','supervisor.css','supervisor.js','supervisor_state.js','supervisor_video.js'].includes(name)) {
        res.statusCode=404; res.end(); return;
      }
      res.setHeader('Content-Type', name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.css')?'text/css':'text/javascript');
      res.end(fs.readFileSync(path.join(root,'web_overlay',name)));
    }
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  try {
    await page.goto(base+'/supervisor.html');
    await page.waitForFunction(() => document.querySelector('#status').dataset.status === 'OBSERVED');
    assert.equal(imageRequests,0);
    await page.check('#videoEnabled');
    await page.waitForFunction(() => document.querySelector('#videoStage').dataset.status === 'LIVE');
    assert.match(await page.textContent('#feedbackTitle'),/이탈/);
    assert.equal(await page.textContent('#currentState'),'S2');
    assert.equal(await page.textContent('#target'),'나사 A');
    assert.equal(await page.locator('#phaseRail .active').count(),1);
    const colors = await page.evaluate(() => {
      const img=document.querySelector('#videoImage'), c=document.createElement('canvas');
      c.width=64;c.height=36;
      const ctx=c.getContext('2d');ctx.drawImage(img,0,0,64,36);
      const data=ctx.getImageData(0,0,64,36).data;
      return new Set(Array.from(data).filter((_,i)=>i%4!==3)).size;
    });
    assert.ok(colors>20,'image must be decoded and nonblank');
    await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
    for (const width of [390,768,1024,1440]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      const overlaps = await page.evaluate(() => {
        const nodes = ['.camera-view','.guidance','#diagnostics'].map(s=>document.querySelector(s).getBoundingClientRect());
        return nodes.some((a,i)=>nodes.slice(i+1).some(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1));
      });
      assert.equal(overlaps,false);
      if(width===390) await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
    }
    marker='LOST';markerCount=3;phase='PAUSED';reason='marker_not_stable';
    await page.waitForFunction(()=>document.querySelector('#status').dataset.status==='TRACKING_LOST');
    assert.equal(await page.getAttribute('#videoStage','data-status'),'LIVE');
    assert.equal(await page.locator('#videoImage').isVisible(),true);
    assert.equal(await page.locator('#phaseRail .active').count(),0);
    assert.equal(await page.textContent('#driverEvidence'),'판정 보류');
    await page.screenshot({path:path.join(output,'tracking-lost.png'),fullPage:true});
    frozen=true;
    await page.waitForFunction(()=>document.querySelector('#videoStage').dataset.status==='STALE');
    assert.equal(await page.locator('#videoImage').isVisible(),true);
    await page.screenshot({path:path.join(output,'video-stale.png'),fullPage:true});
    frozen=false;broken=true;
    await page.waitForFunction(()=>document.querySelector('#videoStage').dataset.status==='DISCONNECTED');
    broken=false;responseDelay=500;
    await page.uncheck('#videoEnabled');
    const stopped=imageRequests;
    await delay(800);
    assert.equal(imageRequests,stopped);
    assert.equal(await page.locator('#videoImage').isVisible(),false);
    await page.check('#videoEnabled');
    await delay(100);
    await page.uncheck('#videoEnabled');
    await delay(700);
    assert.equal(await page.locator('#videoImage').isVisible(),false,'late response must not revive an opted-out image');
    assert.equal(await page.getAttribute('#videoStage','data-status'),'OFF');
    assert.deepEqual(errors,[]);
    assert.equal(requests.some(url=>!url.startsWith(base)&&!url.startsWith('blob:')),false);
    const report={cameraOpened:false,realPhotosUsed:false,nonblankImageColors:colors,defaultVideoOff:true,
      lossKeepsVideo:true,frozenImageLabelled:true,lateOptOutSafe:true,pageErrors:errors,viewports:[390,768,1024,1440]};
    fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
    await new Promise(resolve=>server.close(resolve));
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
