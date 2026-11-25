import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1116-1210-0_26.1116.1210.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright/package.json');
const {chromium}=require('playwright');
const assets=resolve('app/src/main/assets/parts'),output=resolve(process.argv[2]||'part-preview-qa');
await mkdir(output,{recursive:true});
const server=createServer(async(req,res)=>{
  const name=decodeURIComponent(new URL(req.url,'http://localhost').pathname).replace(/^\//,'')||'index.html';
  if(!/^[\w.-]+$/.test(name)){res.writeHead(404);res.end();return;}
  try{
    const file=await readFile(resolve(assets,name));
    res.setHeader('Content-Type',({'.html':'text/html','.js':'application/javascript','.css':'text/css'})[extname(name)]||'text/plain');
    res.end(file);
  }catch{res.writeHead(404);res.end();}
});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const results=[];
try{
  for(const viewport of [{width:3840,height:1080},{width:1920,height:1080},{width:412,height:915}]){
    const page=await browser.newPage({viewport,deviceScaleFactor:1});
    const errors=[];page.on('pageerror',error=>errors.push(String(error)));
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(()=>typeof window.setPart==='function');
    for(let part=0;part<4;part++){
      await page.evaluate(value=>window.setPart(value),part);
      await page.waitForTimeout(160);
      const moving=await page.locator('canvas').screenshot();
      await page.waitForTimeout(650);
      const stats=await page.evaluate(()=>window.partStats());
      assert.equal(stats.part,part);assert.equal(stats.outside,0);
      assert.equal(stats.nonMint,0);assert.ok(stats.maxGreen>50&&stats.maxGreen<=134);
      assert.ok(stats.counts[0]>25&&stats.counts[1]>25,JSON.stringify(stats));
      assert.ok(stats.modelCounts.every(n=>n>25)&&stats.frameCounts.every(n=>n>5),JSON.stringify(stats));
      assert.equal(stats.counts[0],stats.counts[1]);
      const final=await page.locator('canvas').screenshot();
      assert.ok(!moving.equals(final),'Model entrance should visibly move');
      await writeFile(resolve(output,`${viewport.width}-${part}.png`),final);
      if(viewport.width===3840)await page.screenshot({path:resolve(output,`detail-${part}.png`),clip:{x:1400,y:100,width:460,height:340}});
      results.push(stats);
    }
    await page.evaluate(()=>window.setPart(4));
    const hidden=await page.evaluate(()=>window.partStats());
    assert.deepEqual(hidden.counts,[0,0]);assert.equal(errors.length,0,errors.join('\n'));
    await page.close();
  }
  await writeFile(resolve(output,'results.json'),JSON.stringify(results,null,2));
  console.log('PASS: 12 part/viewport cases, both eyes, bounds, animation, clear, no JS errors');
}finally{await browser.close();await new Promise(done=>server.close(done));}
