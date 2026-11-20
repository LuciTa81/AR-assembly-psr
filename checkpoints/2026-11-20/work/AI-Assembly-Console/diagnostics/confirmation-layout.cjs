const {chromium} = require(process.env.PLAYWRIGHT_MODULE);
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.ASSEMBLY_ROOT;
const origin = 'http://127.0.0.1:18775';
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
  try {
    for (const [width,height] of [[1440,900],[1280,720],[390,844]]) {
      const page = await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
      let marker='LOST',frame=0;
      await page.route(origin+'/**', async route => {
        const name=new URL(route.request().url()).pathname.slice(1);
        if (route.request().method() !== 'GET') return route.fulfill({status:405,body:'Read-only diagnostic'});
        if (name==='console/status') return route.fulfill({json:{schema_version:'beast_console_v1',status:'running',
          preflight:{ready:true,checks:[]},error:'',session_id:'layout-check'}});
        if (name==='state.json') return route.fulfill({json:{schema_version:'realtime_v1',session_id:'layout-check',source:'synthetic_fixture',
          frame_id:++frame,timestamp_ms:Date.now(),frame_age_ms:0,system_status:'RUNNING',marker_status:marker,
          marker_count:marker==='OK'?5:0,current_state:'S0',current_label:'Box',target:'box',next_action:'Fixture',fps:20,latency_ms:40,
          guidance:{schema_version:'assembly_guidance_v1',phase:'GUIDING',reason:'operator_confirmation',acknowledgement:'',
            acknowledgement_remaining_ms:0,hold_progress:'none',hold_remaining_ms:0},
          extra:{operator:{mode:'hybrid',revision:0,can_confirm:true,pending:false,completed:false}}}});
        const file=name || 'supervisor_demo.html', filename=path.join(root,'web_overlay',file);
        if (!fs.existsSync(filename)) return route.fulfill({status:404,body:''});
        let body=fs.readFileSync(filename);
        if (file==='supervisor_demo.html') body=Buffer.from(body.toString().replace('</head>',
          '<link rel="stylesheet" href="/supervisor_console.css"><script defer src="/supervisor_console.js"></script></head>'));
        return route.fulfill({body,contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.woff2')?'font/woff2':'text/html'});
      });
      await page.goto(origin);
      await page.waitForFunction(()=>document.body.dataset.console==='running');
      await page.evaluate(()=>document.fonts.ready);
      for (const state of ['LOST','OK','LOST','OK']) {
        marker=state;
        await page.waitForFunction(expected=>document.getElementById('status').dataset.status===expected,state==='OK'?'GUIDING':'TRACKING_LOST');
        await page.waitForTimeout(350);
        const layout=await page.evaluate(()=>Object.fromEntries(['actionSurface','confirmStep','confirmationHint','feedback','operatorControls'].map(id=>{
          const e=document.getElementById(id),r=e.getBoundingClientRect();
          return [id,{top:r.top,height:r.height,hidden:e.hidden,text:e.innerText.trim()}];
        })));
        console.log(JSON.stringify({width,height,marker,layout}));
      }
      await page.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
