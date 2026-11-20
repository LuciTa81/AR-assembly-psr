const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const sharp=require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root=process.argv[2], out=__dirname;
const old=JSON.parse(fs.readFileSync(path.join(out,'visual-provenance-v3.json'),'utf8'));
const photo=old.unity.photo;
const rows=fs.readFileSync(old.supervisor.log,'utf8').trim().split(/\r?\n/).map(JSON.parse);
const record=rows.find(x=>x.current_state==='S3' && x.marker_status==='OK' && !x.held_reason && x.guidance?.phase==='GUIDING');
assert(record && record.target==='screw_b');
fs.writeFileSync(path.join(out,'supervisor-source-record-v6.json'),JSON.stringify(record,null,2));
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors=[];let seq=0;
  try{
    const page=await browser.newPage({viewport:{width:1100,height:650},deviceScaleFactor:3});
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://127.0.0.1:18769/**',async route=>{
      const file=new URL(route.request().url()).pathname.slice(1);
      if(file==='state.json'){
        const state=structuredClone(record);
        state.source='session';state.frame_age_ms=0;state.frame_id=record.frame_id+seq++;state.timestamp_ms=Date.now();
        return route.fulfill({json:state});
      }
      if(file==='frame.jpg')return route.fulfill({body:await sharp(photo).jpeg().toBuffer(),headers:{'Content-Type':'image/jpeg','X-AR-Session':record.session_id,'X-AR-Source':'session','X-AR-Frame-Id':String(record.frame_id+seq++),'X-AR-Timestamp-Ms':String(Date.now()),'X-AR-Frame-Age-Ms':'0'}});
      if(/^fonts\/IBMPlexSansKR-(Regular|Medium|SemiBold|Bold)\.woff2$/.test(file))return route.fulfill({path:path.join(root,'web_overlay',file),contentType:'font/woff2'});
      if(!/^supervisor(?:_demo|_shell|_state|_video)?\.(html|css|js)$/.test(file))return route.fulfill({status:404,body:''});
      return route.fulfill({path:path.join(root,'web_overlay',file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
    });
    await page.goto('http://127.0.0.1:18769/supervisor_demo.html');
    await page.waitForFunction(()=>document.querySelector('#currentState').textContent==='S3');
    await page.locator('#videoEnabled').check();
    await page.waitForFunction(()=>document.querySelector('#videoImage').naturalWidth>0);
    await page.evaluate(()=>document.fonts.ready);
    const box=await page.locator('.workspace').boundingBox(), sequence=await page.locator('.sequence').boundingBox();
    await page.screenshot({path:path.join(out,'supervisor-B-full-v6.png'),fullPage:true});
    await page.screenshot({path:path.join(out,'supervisor-B-workspace-v6.png'),clip:box});
    const clip={x:box.x,y:box.y,width:box.width,height:sequence.y+sequence.height-box.y};
    await page.screenshot({path:path.join(out,'supervisor-B-sequence-v6.png'),clip});
    assert.equal(await page.locator('#targetLetter').innerText(),'B');
    assert.equal(await page.locator('#stateLabel').innerText(),'나사 B');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'visual-provenance-v6.json'),JSON.stringify({record:old.supervisor.log,frame:record.frame_id,state:record.current_state,photo,box,clip,errors,note:'Latest unchanged UI, actual saved B state and separately saved camera photo. Presentation replay example, not synchronized footage. Only transport clocks advanced.'},null,2));
    console.log(JSON.stringify({state:'S3',target:'B',box,clip,errors}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
