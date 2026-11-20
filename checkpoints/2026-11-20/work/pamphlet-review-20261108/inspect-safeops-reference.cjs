const {chromium}=require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  let status=null, error=null;
  try{const r=await page.goto('https://dashboard.safeops.sentientsys.io/insights',{waitUntil:'domcontentloaded',timeout:30000});status=r?.status();await page.waitForTimeout(4500);}catch(e){error=e.message;}
  await page.screenshot({path:path.join(__dirname,'safeops-reference.png'),fullPage:true});
  const record={url:page.url(),title:await page.title(),status,error,errors,text:await page.locator('body').innerText()};
  fs.writeFileSync(path.join(__dirname,'safeops-reference-read.json'),JSON.stringify(record,null,2));
  console.log(JSON.stringify(record).slice(0,8000));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
