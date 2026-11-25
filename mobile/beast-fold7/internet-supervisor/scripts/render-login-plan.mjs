import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(join(process.env.CODEX_NODE_MODULES,'playwright'));
const profile=JSON.parse(await readFile(new URL('../../app/src/main/assets/box-outline.json',import.meta.url),'utf8'));
const browser=await chromium.launch({headless:true,channel:'chrome'});
try{
  const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});
  await page.setContent('<style>body{margin:0;background:#121817}canvas{display:block}</style><canvas width="1920" height="1080"></canvas>');
  await page.evaluate(({exterior,lid})=>{
    const c=document.querySelector('canvas').getContext('2d');
    c.fillStyle='#121817';c.fillRect(0,0,1920,1080);
    const line=(points,color='#23312b',width=1)=>{c.strokeStyle=color;c.lineWidth=width;c.beginPath();points.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y));c.stroke();};
    for(let x=0;x<1920;x+=48)line([[x,0],[x,1080]],'#18231e');
    for(let y=0;y<1080;y+=48)line([[0,y],[1920,y]],'#18231e');
    const rect=(x,y,w,h,r,color,width=1)=>{c.strokeStyle=color;c.lineWidth=width;c.beginPath();c.roundRect(x,y,w,h,r);c.stroke();};
    const text=(s,x,y,color='#385449',size=14)=>{c.font=`${size}px sans-serif`;c.fillStyle=color;c.fillText(s,x,y);};
    function plate(x,y,side,name){
      const scale=side/exterior[0];
      rect(x,y,side,exterior[1]*scale,3*scale,'#365148',2);
      rect(x+16,y+16,side-32,side-32,5,'#273c33');
      const corners=[[x+35,y+35],[x+side-35,y+35],[x+35,y+side-35],[x+side-35,y+side-35]];
      corners.forEach(([px,py],i)=>{
        c.strokeStyle='#41675c';c.lineWidth=2;c.beginPath();c.arc(px,py,12,0,Math.PI*2);c.stroke();
        c.setLineDash([3,5]);c.beginPath();c.arc(px,py,27,0,Math.PI*2);c.stroke();c.setLineDash([]);
        line([[px-39,py],[px+39,py]],'#2d483d');line([[px,py-39],[px,py+39]],'#2d483d');
        text('ABCD'[i],px+37,py+5,'#4c7163',16);
      });
      line([[x,y-48],[x,y-20],[x,y-38],[x+side,y-38],[x+side,y-48],[x+side,y-20]],'#2b463b');
      text(String(exterior[0])+' mm',x+side/2-25,y-48);
      text(name,x,y+side+35,'#416252',12);
    }
    plate(115,235,570,'01 / BODY');plate(1220,135,540,'02 / LID');
    rect(1220,785,540,lid*540/exterior[0],4,'#2e4b40');
    line([[1220,870],[1760,870]],'#263d32');text('SECTION / LID',1220,900,'#355346',12);
    c.setLineDash([5,8]);line([[400,200],[400,120],[1020,120],[1020,950],[1490,950],[1490,850]],'#253d33');c.setLineDash([]);
    // The login stays visually quiet; the reference drawing remains at the edges.
    c.fillStyle='#12181788';c.fillRect(720,0,480,1080);
  },{exterior:profile.provenance.exterior_mm,lid:profile.lid_height_mm});
  const output=fileURLToPath(new URL('../web/public/assembly-plan.png',import.meta.url));
  await page.locator('canvas').screenshot({path:output});console.log(output);
}finally{await browser.close();}
