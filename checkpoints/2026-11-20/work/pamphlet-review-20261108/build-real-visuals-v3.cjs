const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const deps = 'C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const sharp = require(path.join(deps, 'sharp'));
const {chromium} = require(path.join(deps, 'playwright'));
const root = process.argv[2];
const out = __dirname;
const photo = 'C:/Users/fresh/Downloads/Beast_202mm_AD_20261108/live-20261108T012754Z-f8cf2d50/frame-000017/raw.png';
const unity = path.join(root, 'outputs/unity_p1/cue-capture-final-20261107/170-SBS_GUIDANCE_OBSERVED_screw_a.png');
const session = 'viture_aruco_rt_20261108_015905_4c04f6b11ffe';
const log = path.join(root, 'outputs/realtime_sessions', session, 'overlay_messages.jsonl');
const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');

// Recover coverage from Unity's black-background render; do not redraw UI glyphs.
async function extractUi(rect, width) {
  const {data, info} = await sharp(unity).extract(rect).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const rgba = Buffer.alloc(info.width * info.height * 4);
  let visible = 0;
  for (let i=0; i<info.width*info.height; i++) {
    const p = i * info.channels, q = i * 4;
    const alpha = Math.max(data[p], data[p+1], data[p+2]);
    if (alpha) visible++;
    rgba[q] = alpha ? Math.round(data[p]*255/alpha) : 0;
    rgba[q+1] = alpha ? Math.round(data[p+1]*255/alpha) : 0;
    rgba[q+2] = alpha ? Math.round(data[p+2]*255/alpha) : 0;
    rgba[q+3] = alpha;
  }
  assert(visible > 25);
  return sharp(rgba, {raw:{width:info.width,height:info.height,channels:4}}).resize({width}).png().toBuffer();
}

async function composite() {
  const crop = {left:415,top:240,width:460,height:345};
  const width=1200, height=900, scale=width/crop.width;
  const base = await sharp(photo).extract(crop).resize(width,height).toBuffer();
  const components = [
    {name:'title',rect:{left:308,top:16,width:155,height:27},width:360,y:22},
    {name:'ring',rect:{left:368,top:184,width:25,height:25},width:78,x:Math.round((545.5-crop.left)*scale-39),y:Math.round((299.5-crop.top)*scale-39)},
    {name:'cue',rect:{left:300,top:301,width:170,height:33},width:400,y:780},
    {name:'instruction',rect:{left:190,top:339,width:390,height:30},width:770,y:834},
  ];
  const layers=[
    {input:await sharp({create:{width,height:90,channels:4,background:{r:0,g:0,b:0,alpha:.32}}}).png().toBuffer(),left:0,top:0},
    {input:await sharp({create:{width,height:140,channels:4,background:{r:0,g:0,b:0,alpha:.2}}}).png().toBuffer(),left:0,top:760},
  ];
  for (const c of components) {
    const img=await extractUi(c.rect,c.width);
    const x=c.x??Math.round((width-c.width)/2);
    const {data,info}=await sharp(img).raw().toBuffer({resolveWithObject:true});
    const shadow=Buffer.from(data);
    for(let i=0;i<info.width*info.height;i++) {
      shadow[i*4]=shadow[i*4+1]=shadow[i*4+2]=0;
      shadow[i*4+3]=Math.round(shadow[i*4+3]*.75);
    }
    layers.push({input:await sharp(shadow,{raw:{width:info.width,height:info.height,channels:4}}).blur(2).png().toBuffer(),left:x+1,top:c.y+2});
    layers.push({input:img,left:x,top:c.y});
    await sharp(img).toFile(path.join(out,'unity-source-'+c.name+'-v3.png'));
  }
  await sharp(base).composite(layers).png().toFile(path.join(out,'unity-photo-composite-v3.png'));
  await sharp(photo).extract(crop).png().toFile(path.join(out,'workbench-crop-v3.png'));
  return {photo,unity,photo_sha256:sha(photo),unity_sha256:sha(unity),crop,output:{width,height},components,
    note:'Photograph crop plus extracted Unity UI pixels. UI relocated/scaled for explanation, not a through-lens capture or accuracy measurement. No generated imagery.'};
}

async function supervisor() {
  const records=fs.readFileSync(log,'utf8').trim().split(/\r?\n/).map(JSON.parse);
  const candidates=records.filter(r=>r.current_state==='S2' && r.guidance.phase==='OBSERVED' && r.marker_status==='OK');
  assert(candidates.length>0);
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  const errors=[], requests=[];
  let seq=0;
  try {
    const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:2});
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>requests.push(r.url()));
    const record=candidates[0];
    await page.route('http://127.0.0.1:18769/**',route=>{
      const file=new URL(route.request().url()).pathname.slice(1);
      if(file==='state.json') {
        // Replay transport clock advances; observed state/evidence remain the saved record.
        const state=structuredClone(record);
        state.source='session';state.frame_age_ms=0;
        state.frame_id=record.frame_id+seq;state.timestamp_ms=record.timestamp_ms+seq*100;seq++;
        return route.fulfill({json:state});
      }
      if(!['supervisor.html','supervisor.css','supervisor.js','supervisor_state.js','supervisor_video.js'].includes(file)) return route.fulfill({status:404,body:''});
      return route.fulfill({path:path.join(root,'web_overlay',file),contentType:file.endsWith('.css')?'text/css':file.endsWith('.js')?'application/javascript':'text/html'});
    });
    await page.goto('http://127.0.0.1:18769/supervisor.html');
    await page.waitForFunction(()=>document.querySelector('#status').dataset.status==='OBSERVED');
    await page.evaluate(()=>document.fonts.ready);
    assert.equal(await page.locator('#sourceKind').innerText(),'저장 세션 재생');
    assert.equal(await page.locator('#currentState').innerText(),'S2');
    assert.equal(await page.locator('#target').innerText(),'나사 A');
    const state=await page.locator('.state-row').boundingBox();
    const action=await page.locator('#actionTitle').boundingBox();
    const guidance=await page.locator('.guidance').boundingBox();
    const ink=await page.locator('#actionTitle').evaluate(el=>{
      const range=document.createRange();range.selectNodeContents(el);
      const rect=range.getBoundingClientRect();return {bottom:rect.bottom};
    });
    const clip={x:Math.floor(guidance.x+12),y:Math.floor(state.y-8),width:Math.floor(guidance.width-24),height:Math.ceil(ink.bottom-state.y+16)};
    await page.screenshot({path:path.join(out,'supervisor-full-log-replay-v3.png'),fullPage:true});
    await page.screenshot({path:path.join(out,'supervisor-detail-log-replay-v3.png'),clip});
    await page.locator('.guidance').screenshot({path:path.join(out,'supervisor-guidance-log-replay-v3.png')});
    const text=await page.locator('.guidance').innerText();
    assert.deepEqual(errors,[]);
    assert.equal(requests.some(r=>r.includes('frame.jpg')),false);
    fs.writeFileSync(path.join(out,'supervisor-source-record-v3.json'),JSON.stringify(record,null,2));
    return {log,log_sha256:sha(log),source_frame:record.frame_id,source_phase:record.guidance.phase,clip,text,errors,
      note:'Unmodified application UI rendered from one actual saved observation. Replay transport timestamps incremented. No camera capture or substituted camera photo. Image in pamphlet is a cropped UI detail.'};
  } finally {await browser.close();}
}

(async()=>{
  const assets={unity:await composite(),supervisor:await supervisor()};
  fs.writeFileSync(path.join(out,'visual-provenance-v3.json'),JSON.stringify(assets,null,2));
  console.log(JSON.stringify({generated:false,unity:'unity-photo-composite-v3.png',supervisor:'supervisor-detail-log-replay-v3.png',sourceFrame:assets.supervisor.source_frame,clip:assets.supervisor.clip,errors:assets.supervisor.errors}));
})().catch(e=>{console.error(e);process.exitCode=1;});
