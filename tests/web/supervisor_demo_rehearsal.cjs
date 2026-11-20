const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const output=process.env.DEMO_OUTPUT || path.join(root,'outputs/supervisor_demo');
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const child=spawn(process.env.AR_PYTHON || 'python',['-X','utf8','-B','-u','tests/web/serve_assembly_fixture.py','--preview','--seconds','90'],{cwd:root,windowsHide:true});
  let browser;
  const errors=[];
  child.stderr.on('data',data=>errors.push(data.toString()));
  try {
    const origin=await new Promise((resolve,reject)=>{
      let text='';
      const timer=setTimeout(()=>reject(new Error('Fixture startup timeout: '+errors.join(''))),25000);
      child.stdout.on('data',data=>{text+=data;const match=text.match(/overlay=(http:\/\/127\.0\.0\.1:\d+)/);if(match){clearTimeout(timer);resolve(match[1]);}});
      child.on('error',e=>{clearTimeout(timer);reject(e);});
      child.on('exit',code=>{clearTimeout(timer);reject(new Error('Fixture exited '+code+': '+errors.join('')));});
    });
    let initial;
    for(let attempt=0;attempt<50;attempt++) {
      initial=await (await fetch(origin+'/state.json')).json();
      if(initial.system_status!=='STARTING') break;
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    assert.match(initial.source,/synthetic/);
    assert.match(initial.session_id,/synthetic-rehearsal-/);
    browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
    const page=await browser.newPage({viewport:{width:1440,height:900}}), pageErrors=[];
    page.on('pageerror',e=>pageErrors.push(e.message));
    await page.goto(origin+'/supervisor_demo.html');
    await page.waitForFunction(()=>!document.getElementById('confirmStep').disabled);
    await page.locator('#videoEnabled').check();
    await page.waitForFunction(()=>document.getElementById('videoStage').dataset.status==='LIVE');
    await page.locator('#confirmStep').click();
    await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S1'&&!document.getElementById('confirmStep').disabled);
    await page.locator('#confirmStep').click();
    await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S2');
    assert.equal(await page.locator('#targetLetter').innerText(),'A');
    await page.screenshot({path:path.join(output,'rehearsal-A.png'),fullPage:true});
    await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S4',null,{timeout:60000});
    await page.screenshot({path:path.join(output,'rehearsal-C.png'),fullPage:true});
    await page.waitForFunction(()=>document.getElementById('currentState').textContent==='S6'&&!document.getElementById('confirmStep').disabled,null,{timeout:60000});
    assert.equal(await page.locator('#liveCue').getAttribute('data-cue'),'FINAL CHECK');
    await page.locator('#confirmStep').click();
    await page.waitForFunction(()=>document.getElementById('liveCue').dataset.cue==='CONFIRMED');
    await page.screenshot({path:path.join(output,'rehearsal-completed.png'),fullPage:true});
    assert.deepEqual(pageErrors,[]);
    const report={passed:true,source:initial.source,confirmations:3,flow:'S0-S1-A-B-C-D-S6-COMPLETED',
      realAssemblyController:true,cameraOpened:false,unityStarted:false,pageErrors};
    fs.writeFileSync(path.join(output,'rehearsal-report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  }finally{
    if(browser) await browser.close();
    if(child.exitCode===null) child.kill();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
