const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const adb='C:/Users/fresh/Documents/Codex/2026-10-25/new-chat/work/toolchain/android-sdk/platform-tools/adb.exe';
const device='192.168.200.191:41211';
const run=(...args)=>execFileSync(adb,['-s',device,...args],{encoding:'utf8',windowsHide:true});
(async()=>{
  const link=run('shell','run-as','com.lucita.beastgate','cat','files/observer-test-link.txt').trim();
  const url=new URL(link),key=new URLSearchParams(url.hash.slice(1)).get('key');
  assert.equal(url.hostname,'192.168.200.191');
  assert.equal((await fetch(url.origin+'/state.json')).status,401);
  const state=await(await fetch(url.origin+'/state.json',{headers:{Authorization:`Bearer ${key}`}})).json();
  assert.equal(state.running,false);assert.equal(state.stage,-1);assert.equal(state.video_available,false);assert.equal(state.recording,false);
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(link);await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결됨');
    assert.equal(await page.textContent('#stateLabel'),'작업 대기');assert.equal(await page.textContent('#liveCue'),'카메라 꺼짐');
    await page.screenshot({path:path.join(__dirname,'supervisor-qa/real-phone-idle.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    run('shell','run-as','com.lucita.beastgate','touch','files/observer-test-done');
    await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결 끊김');
    assert.equal(await page.textContent('#overlay'),'확인 불가');
    console.log('PASS: real Fold7 Wi-Fi HTTP, token authentication, actual idle state, browser rendering, server stop detection. Camera remained off.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e.message);try{run('shell','run-as','com.lucita.beastgate','touch','files/observer-test-done');}catch{}process.exitCode=1;});
