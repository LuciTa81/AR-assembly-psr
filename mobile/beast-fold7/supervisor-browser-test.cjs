const {chromium}=require('playwright');
const fs=require('node:fs'),http=require('node:http'),path=require('node:path'),assert=require('node:assert/strict');
const assets=path.join(__dirname,'app/src/main/assets/supervisor');
const out=path.join(__dirname,'supervisor-qa');fs.mkdirSync(out,{recursive:true});
let phase='APPROACH',stage=2,running=true,tracked=true,unauthorized=false,frozen=false,session='test-1',requests=0;
const initial=Date.now();
const server=http.createServer((req,res)=>{
  if(req.url==='/state.json'){
    requests++;if(unauthorized||req.headers.authorization!=='Bearer test-key'){res.writeHead(401);return res.end();}
    const action=stage===6?'조립 상태를 확인해주세요':stage<0?'작업 대기':!tracked?'작업대가 보이도록 바라봐주세요':stage===0?'상자를 놓아주세요':stage===1?'뚜껑을 닫아주세요':phase==='WORKING'?`나사 ${'ABCD'[stage-2]}를 조여주세요`:phase==='RELEASE'?'드라이버를 떼어주세요':`드라이버 끝을 나사 ${'ABCD'[stage-2]}에 맞춰주세요`;
    res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({schema:1,session,updated_ms:frozen?initial:Date.now(),elapsed_ms:47000,running,stage,phase,action,tracked,overlay_visible:tracked,markers:6,rms_px:2.1,pose_age_ms:40,frame:470,message:'ok',remaining_ms:phase==='RELEASE'?2000:0}));
  }
  const file=path.join(assets,req.url==='/'?'index.html':req.url);
  if(!file.startsWith(assets)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
  res.setHeader('Content-Type',file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.woff2')?'font/woff2':'text/html');fs.createReadStream(file).pipe(res);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/#key=test-key`);
    await page.waitForFunction(()=>document.getElementById('stateLabel').textContent==='나사 A');
    assert.equal(new URL(page.url()).hash,'');
    for(const s of [0,1,2,3,4,5,6]){stage=s;await page.waitForFunction(s=>document.querySelectorAll('#steps .current')[0]?.textContent.includes(['상자 배치','뚜껑 닫기','나사 A','나사 B','나사 C','나사 D','최종 확인'][s]),s);}
    stage=2;phase='WORKING';await page.waitForFunction(()=>document.getElementById('actionTitle').textContent==='나사 A를 조여주세요');
    await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
    phase='RELEASE';await page.waitForFunction(()=>document.getElementById('actionTitle').textContent==='드라이버를 떼어주세요');
    await page.click('#tab-history');assert.equal(await page.inputValue('#historyFilter'),'steps');
    const steps=await page.locator('#history tr').count();await page.selectOption('#historyFilter','all');assert((await page.locator('#history tr').count())>steps);
    await page.click('#tab-live');tracked=false;await page.waitForFunction(()=>document.getElementById('tracking').textContent==='작업대 확인 필요');
    frozen=true;await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결 끊김');
    assert.equal(await page.textContent('#overlay'),'확인 불가');
    frozen=false;tracked=true;await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결됨');
    for(const [width,height] of [[390,844],[915,412],[1920,1080]]){
      await page.setViewportSize({width,height});await page.screenshot({path:path.join(out,`${width}.png`),fullPage:true});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`horizontal overflow at ${width}`);
      assert(await page.evaluate(()=>[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length).every(e=>e.getBoundingClientRect().width>20)));
    }
    await page.click('#theme');await page.screenshot({path:path.join(out,'light.png'),fullPage:true});
    session='test-2';stage=0;await page.waitForTimeout(600);await page.click('#tab-history');assert.equal(await page.locator('#history tr').count(),1);
    unauthorized=true;await page.waitForFunction(()=>document.getElementById('connectionDetail').textContent.includes('만료'));
    const stopped=requests;await page.waitForTimeout(1300);assert.equal(requests,stopped);assert.deepEqual(errors,[]);
    console.log('PASS: stage mapping, phases, history filter, stale/recovery, new session, auth expiry, 4 viewports, no page errors');
  }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
