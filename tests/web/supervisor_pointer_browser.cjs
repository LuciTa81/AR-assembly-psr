const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {PNG}=require(process.env.PNGJS_MODULE||'pngjs');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'),output=process.env.DEMO_OUTPUT||path.join(root,'outputs/supervisor_demo');
const origin='http://127.0.0.1:18775';
function light(image,x,y) {
  let sum=0;
  for(let dy=-1;dy<=1;dy++) for(let dx=-1;dx<=1;dx++) {
    const i=((y+dy)*image.width+x+dx)*4;
    sum+=image.data[i]+image.data[i+1]+image.data[i+2];
  }
  return sum/27;
}
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:900},colorScheme:'dark'}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route(origin+'/**',route=>{
      const file=new URL(route.request().url()).pathname.slice(1);
      if(/^supervisor(?:_demo|_shell|_state|_video)?\.(html|js|css)$/.test(file))
        return route.fulfill({path:path.join(root,'web_overlay',file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
      if(/^fonts\/IBMPlexSansKR-(Regular|Medium|SemiBold|Bold)\.woff2$/.test(file))
        return route.fulfill({path:path.join(root,'web_overlay',file),contentType:'font/woff2'});
      return route.fulfill({status:503,body:''});
    });
    await page.goto(origin+'/supervisor_demo.html#settings');
    await page.evaluate(()=>document.fonts.ready);
    const card=page.locator('.theme-option').first();
    const box=await card.boundingBox(),scores=[];
    for(const side of ['left','right']) {
      const x=side==='left'?6:box.width-7,y=Math.floor(box.height/2);
      await card.hover({position:{x,y}});
      const buffer=await card.screenshot();
      fs.writeFileSync(path.join(output,'pointer-'+side+'.png'),buffer);
      const image=PNG.sync.read(buffer),left=light(image,6,y),right=light(image,image.width-7,y);
      scores.push({side,left,right});
      assert(side==='left'?left>right+3:right>left+3,`${side} pointer must brighten the same edge: ${JSON.stringify(scores.at(-1))}`);
    }
    await page.mouse.move(0,0);
    assert.equal(await card.getAttribute('data-hovering'),'false');
    await card.dispatchEvent('pointermove',{pointerType:'touch',clientX:box.x+6,clientY:box.y+20});
    assert.equal(await card.getAttribute('data-hovering'),'false');
    await page.locator('#highlightEnabled').uncheck();
    await card.hover();
    assert.equal(await card.evaluate(e=>getComputedStyle(e).backgroundImage),'none');
    await page.locator('#highlightEnabled').check();
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.waitForFunction(()=>document.documentElement.dataset.highlight==='off');
    await card.hover();
    assert.equal(await card.evaluate(e=>getComputedStyle(e).backgroundImage),'none');
    await page.emulateMedia({reducedMotion:'no-preference'});
    await page.waitForFunction(()=>document.documentElement.dataset.highlight==='on');
    await page.locator('#tab-history').click();
    // No received events: downloading is unavailable and must not glow.
    assert.equal(await page.locator('#downloadEvents').isDisabled(),true);
    await page.locator('#downloadEvents').hover();
    assert.notEqual(await page.locator('#downloadEvents').getAttribute('data-hovering'),'true');
    await page.locator('#tab-live').click();
    const tool=page.locator('#actionSurface'),toolBox=await tool.boundingBox(),toolScores=[];
    for(const side of ['left','right']) {
      const x=side==='left'?7:Math.floor(toolBox.width)-8,y=8;
      await tool.hover({position:{x,y}});
      const image=PNG.sync.read(await tool.screenshot());
      const left=light(image,7,y),right=light(image,image.width-8,y);
      toolScores.push({side,left,right});
      assert(side==='left'?left>right+3:right>left+3,'Tool glow follows the pointer: '+JSON.stringify(toolScores.at(-1)));
      assert(Math.max(left,right)>60,'Pointer center is brighter than the previous subtle glow');
    }
    assert.equal(await tool.evaluate(e=>parseFloat(getComputedStyle(e).getPropertyValue('--spot-radius'))<=300),true);
    const header=page.locator('.camera-view>.section-heading');
    await header.hover({position:{x:180,y:15}});
    assert.equal(await header.getAttribute('data-hovering'),'true');
    assert.equal(await tool.getAttribute('data-hovering'),'false');
    const videoBefore=PNG.sync.read(await page.locator('#videoStage').screenshot());
    await header.hover({position:{x:400,y:15}});
    const videoAfter=PNG.sync.read(await page.locator('#videoStage').screenshot());
    assert.deepEqual(videoAfter.data,videoBefore.data,'Pointer light must not alter video pixels');
    await page.locator('#feedback').hover();
    assert.equal(await tool.getAttribute('data-hovering'),'false');
    const feedback=page.locator('#feedback');
    const warningBefore=PNG.sync.read(await feedback.screenshot());
    await tool.hover({position:{x:7,y:8}});
    const warningAfter=PNG.sync.read(await feedback.screenshot());
    // Fractional grid edges blend with adjacent pixels; compare the warning's interior.
    for(let y=2;y<warningBefore.height-2;y++) {
      const start=(y*warningBefore.width+2)*4,end=((y+1)*warningBefore.width-2)*4;
      assert.deepEqual(warningAfter.data.subarray(start,end),warningBefore.data.subarray(start,end),
        'Warning content stays unchanged when adjacent areas glow');
    }
    assert.deepEqual(errors,[]);
    const report={scores,toolScores,pageErrors:0,touchIgnored:true,reducedMotion:true,disabledGuard:true,videoUnchanged:true,warningUnchanged:true};
    fs.writeFileSync(path.join(output,'pointer-report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
