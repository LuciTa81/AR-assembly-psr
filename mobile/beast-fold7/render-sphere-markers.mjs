import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const require=createRequire('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1116-1210-0_26.1116.1210.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright/package.json');
const {chromium}=require('playwright');
const output=resolve('app/src/main/assets/markers'),qa=resolve('sphere-marker-qa');
await mkdir(output,{recursive:true});await mkdir(qa,{recursive:true});
const html=`<!doctype html><html><body style="margin:0;background:#000"><canvas></canvas><script type="module">
import * as THREE from '/three.module.min.js';
const canvas=document.querySelector('canvas');
const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.setSize(96,96);renderer.setClearColor(0,0);
renderer.outputColorSpace=THREE.SRGBColorSpace;
const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1.1,1.1,1.1,-1.1,.1,10);
camera.position.z=3;
scene.add(new THREE.AmbientLight(0xffffff,.65));
const light=new THREE.DirectionalLight(0xffffff,1.4);light.position.set(-2,3,4);scene.add(light);
const material=new THREE.MeshPhongMaterial({color:0xffffff,transparent:true,opacity:.58,shininess:48,specular:0x666666,depthWrite:false});
const sphere=new THREE.Mesh(new THREE.SphereGeometry(1,64,48),material);scene.add(sphere);
window.renderSphere=(color)=>{
 material.color.setHex(color);renderer.render(scene,camera);
 const gl=renderer.getContext(),pixels=new Uint8Array(96*96*4);gl.readPixels(0,0,96,96,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
 let count=0,alphaMax=0,minX=96,minY=96,maxX=-1,maxY=-1,shadeMin=255,shadeMax=0;
 for(let y=0;y<96;y++)for(let x=0;x<96;x++){
  const i=(y*96+x)*4;if(!pixels[i+3])continue;
  count++;alphaMax=Math.max(alphaMax,pixels[i+3]);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
  if(pixels[i+3]>100){const value=Math.max(pixels[i],pixels[i+1],pixels[i+2]);shadeMin=Math.min(shadeMin,value);shadeMax=Math.max(shadeMax,value);}
 }
 return {png:canvas.toDataURL('image/png'),count,alphaMax,minX,maxX,minY,maxY,shadeMin,shadeMax};
};
</script></body></html>`;
const server=createServer(async(req,res)=>{
 if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end(html);return;}
 if(!['/three.module.min.js','/three.core.min.js'].includes(req.url)){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type','application/javascript');res.end(await readFile(resolve('app/src/main/assets/parts',req.url.slice(1))));
});
await new Promise(done=>server.listen(0,'127.0.0.1',done));
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const results=[];
try{
 for(const viewport of [{width:3840,height:1080},{width:412,height:915}]){
  const page=await browser.newPage({viewport,deviceScaleFactor:1});const errors=[];page.on('pageerror',error=>errors.push(String(error)));
  await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>window.renderSphere);
  for(const [name,color] of [['orange',0xffb841],['blue',0x59d9ff],['green',0x59ffbf]]){
   const {png,...stats}=await page.evaluate(color=>window.renderSphere(color),color);
   assert.ok(stats.count>5000&&stats.alphaMax>100&&stats.alphaMax<180,JSON.stringify(stats));
   assert.ok(stats.minX>0&&stats.maxX<95&&stats.minY>0&&stats.maxY<95);
   assert.ok(Math.abs((stats.minX+stats.maxX)/2-47.5)<=.5&&Math.abs((stats.minY+stats.maxY)/2-47.5)<=.5);
   assert.ok(stats.shadeMax-stats.shadeMin>35,'Sphere needs visible volume shading');
   if(viewport.width===3840)await writeFile(resolve(output,name+'.png'),Buffer.from(png.split(',')[1],'base64'));
   await page.locator('canvas').screenshot({path:resolve(qa,viewport.width+'-'+name+'.png')});
   results.push({viewport:viewport.width,name,...stats});
  }
  assert.deepEqual(errors,[]);await page.close();
 }
 await writeFile(resolve(qa,'results.json'),JSON.stringify(results,null,2));
 console.log('PASS: 6 Three.js sphere renders, alpha, centered bounds, shading, desktop/mobile, no errors');
}finally{await browser.close();await new Promise(done=>server.close(done));}
