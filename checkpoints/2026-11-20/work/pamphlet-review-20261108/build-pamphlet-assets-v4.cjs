const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const deps = 'C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const sharp = require(path.join(deps, 'sharp'));
const {chromium} = require(path.join(deps, 'playwright'));
const root = process.argv[2], out = __dirname;
const source = 'C:/Users/fresh/AppData/Local/Temp/codex-clipboard-f5caedcf-f17f-4fee-b9b1-2914bd734717.png';
const photo = 'C:/Users/fresh/Downloads/Beast_202mm_AD_20261108/live-20261108T012754Z-f8cf2d50/frame-000017/raw.png';
(async () => {
  const meta = await sharp(source).metadata();
  assert.equal(meta.width % 3, 0);
  const width = meta.width / 3, top = Math.round(meta.height * .17);
  for (const [i, name] of ['aruco','mediapipe','yolo'].entries()) {
    await sharp(source).extract({left:i*width,top,width,height:meta.height-top}).png().toFile(path.join(out,`detection-${name}-v4.png`));
  }
  const record = JSON.parse(fs.readFileSync(path.join(out,'supervisor-source-record-v3.json'),'utf8'));
  const browser = await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors = [], requests = []; let seq = 0;
  try {
    const page = await browser.newPage({viewport:{width:1440,height:650},deviceScaleFactor:2});
    page.on('pageerror', e=>errors.push(e.message));
    page.on('request', r=>requests.push(r.url()));
    await page.route('http://127.0.0.1:18769/**', async route=> {
      const file = new URL(route.request().url()).pathname.slice(1);
      if (file === 'state.json') {
        const state = structuredClone(record);
        state.source='session'; state.frame_age_ms=0; state.frame_id=record.frame_id+seq++;
        state.timestamp_ms=Date.now();
        return route.fulfill({json:state});
      }
      if (file === 'frame.jpg') return route.fulfill({body:await sharp(photo).jpeg().toBuffer(),headers:{
        'Content-Type':'image/jpeg','X-AR-Session':record.session_id,'X-AR-Source':'session',
        'X-AR-Frame-Id':String(record.frame_id+seq++),'X-AR-Timestamp-Ms':String(Date.now()),'X-AR-Frame-Age-Ms':'0'}});
      if (/^fonts\/IBMPlexSansKR-(Regular|Medium|SemiBold|Bold)\.woff2$/.test(file))
        return route.fulfill({path:path.join(root,'web_overlay',file),contentType:'font/woff2'});
      if (!/^supervisor(?:_demo|_shell|_state|_video)?\.(html|css|js)$/.test(file)) return route.fulfill({status:404,body:''});
      return route.fulfill({path:path.join(root,'web_overlay',file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
    });
    await page.goto('http://127.0.0.1:18769/supervisor_demo.html');
    await page.waitForFunction(()=>document.querySelector('#liveCue').dataset.cue==='MOVE CLEAR');
    await page.locator('#videoEnabled').check();
    await page.waitForFunction(()=>document.querySelector('#videoImage').naturalWidth>0);
    await page.evaluate(()=>document.fonts.ready);
    const workspace = await page.locator('.workspace').boundingBox();
    const sequence = await page.locator('.sequence').boundingBox();
    const clip = {x:workspace.x,y:workspace.y,width:workspace.width,height:sequence.y+sequence.height-workspace.y};
    await page.screenshot({path:path.join(out,'supervisor-current-full-v4.png'),fullPage:true});
    await sharp(path.join(out,'supervisor-current-full-v4.png')).extract({left:Math.round(clip.x*2),top:Math.round(clip.y*2),width:Math.round(clip.width*2),height:Math.round(clip.height*2)}).png().toFile(path.join(out,'supervisor-current-saved-data-v4.png'));
    assert.deepEqual(errors,[]);
    assert.equal(await page.locator('#currentState').innerText(),'S2');
    fs.writeFileSync(path.join(out,'visual-provenance-v4.json'),JSON.stringify({detection:{source,cropTop:top,width},supervisor:{record:'supervisor-source-record-v3.json',photo,clip,sourceFrame:record.frame_id,errors,note:'Unmodified latest UI; saved state and separately saved camera image. Not synchronized footage or live operation. Transport clocks updated for UI playback only.'}},null,2));
    console.log(JSON.stringify({images:4,clip,errors,sourceFrame:record.frame_id}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
