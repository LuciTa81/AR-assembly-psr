const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out=__dirname;
const W=860,H=800;
const ink='#253138',muted='#52636d',wire='#627b86',teal='#2b7c78',blue='#57759f';
const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function text(s,x,y,size=40,color=ink,weight=400,anchor='middle'){
  return `<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}" text-anchor="${anchor}" dominant-baseline="central">${escape(s)}</text>`;
}
function rect(x,y,w,h,fill='#fff',stroke='#c6d1d7',r=5){return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`;}
function arrow(points,head=true,color=wire){return `<path d="${points}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"${head?' marker-end="url(#arrow)"':''}/>`;}
async function logo(name,x,y,w=74,h=74){
  const file=path.join(out,`logo-${name}-v5.png`),m=await sharp(file).metadata();
  const s=Math.min(w/m.width,h/m.height),iw=m.width*s,ih=m.height*s;
  return `<image x="${x+(w-iw)/2}" y="${y+(h-ih)/2}" width="${iw}" height="${ih}" href="data:image/png;base64,${fs.readFileSync(file).toString('base64')}"/>`;
}
const camera=`<g transform="translate(206 14) scale(2.55)" fill="none" stroke="${teal}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4a2 2 0 0 1 1.76 1.05l.49.9A2 2 0 0 0 18 7h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2a2 2 0 0 0 1.76-1.05l.49-.9A2 2 0 0 1 10 4z"/><circle cx="12" cy="13" r="3"/></g>`;
const monitor=`<g transform="translate(484 664) scale(2.65)" fill="none" stroke="${teal}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8m-4-4v4"/></g>`;
async function main(){
  const svg=[`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="AR assembly perception, recognition and guidance architecture">`,
    `<style>text{font-family:'Noto Sans KR',sans-serif;letter-spacing:0}</style><defs><marker id="arrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M1 1L11 6L1 11Z" fill="${wire}"/></marker></defs>`,
    `<rect width="860" height="800" fill="#fff"/>`,
    `<g data-bounds="180,0,500,80">${camera}${text('작업 영상 입력',491,46,42,ink,500)}</g>`,
    arrow('M430 78V100',false),arrow('M145 100H715',false),
    arrow('M145 100V126'),arrow('M430 100V126'),arrow('M715 100V126')];
  for(const [name,title,caption,cx] of [['opencv','ArUco','마커·PnP',145],['yolo','YOLO','도구 위치',430],['mediapipe','MediaPipe','손 랜드마크',715]]){
    svg.push(rect(cx-125,126,250,220,'#f8fafb','#bac9d1'),`<g data-bounds="${cx-125},126,250,220">`,await logo(name,cx-32,143,64,64),text(title,cx,240,42,ink,500),text(caption,cx,303,40,muted),'</g>');
  }
  svg.push(arrow('M145 346V366H715V346',false),arrow('M430 346V389'),rect(96,389,668,64,'#fff','#a8b9c2'),
    `<g data-bounds="96,389,668,64">`,await logo('python',120,399,44,44),text('좌표 변환·동작 특징',467,421,40,ink,500),'</g>',
    arrow('M430 453V473',false),arrow('M215 473H645',false),arrow('M215 473V493'),arrow('M645 473V493'),
    rect(18,493,394,128,'#f1f5fb',blue),rect(448,493,394,128,'#eff8f4',teal),
    `<g data-bounds="18,493,394,128">${text('HMM · Viterbi',215,526,42,blue,600)}${text('작업 단계 추정',215,588)}</g>`,
    `<g data-bounds="448,493,394,128">${text('FSM 안내 제어',645,526,42,teal,600)}${text('보존·복구·재확인',645,588)}</g>`,
    arrow('M645 621V641H215',false),arrow('M215 641V659'),arrow('M645 641V659'),
    rect(18,659,394,129,'#fff','#b5c6cf'),rect(448,659,394,129,'#fff','#b5c6cf'),
    `<g data-bounds="18,659,394,129">`,await logo('unity',48,664,64,64),text('Unity SBS',254,692,42,ink,500),text('양안 AR 안내',215,755),'</g>',
    `<g data-bounds="448,659,394,129">${monitor}${text('웹 관제',695,692,42,ink,500)}${text('단계·다음 행동',645,755)}</g>`,
    '</svg>');
  const source=svg.join('\n');
  fs.writeFileSync(path.join(out,'algorithm-architecture-v7.svg'),source);
  fs.writeFileSync(path.join(out,'algorithm-architecture-v7.html'),`<!doctype html><html lang="ko"><meta charset="utf-8"><title>AR Assembly Algorithm</title><style>html,body{margin:0;background:white}svg{display:block}</style>${source}</html>`);
  const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const page=await browser.newPage({viewport:{width:W,height:H},deviceScaleFactor:3});
    await page.goto('file:///'+path.join(out,'algorithm-architecture-v7.html').replaceAll('\\','/'));
    await page.evaluate(()=>document.fonts.ready);
    const issues=await page.evaluate(()=>{
      const failures=[];
      for(const g of document.querySelectorAll('[data-bounds]')){
        const [x,y,w,h]=g.dataset.bounds.split(',').map(Number);
        for(const e of g.querySelectorAll('text')){
          const b=e.getBBox();
          if(b.x<x-1||b.y<y-1||b.x+b.width>x+w+1||b.y+b.height>y+h+1)failures.push({text:e.textContent,box:[b.x,b.y,b.width,b.height],region:[x,y,w,h]});
        }
      }
      const texts=[...document.querySelectorAll('text')];
      for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){
        const a=texts[i].getBBox(),b=texts[j].getBBox();
        if(Math.min(a.x+a.width,b.x+b.width)-Math.max(a.x,b.x)>1 && Math.min(a.y+a.height,b.y+b.height)-Math.max(a.y,b.y)>1)failures.push({overlap:[texts[i].textContent,texts[j].textContent]});
      }
      return failures;
    });
    assert.deepEqual(issues,[],'Text must fit its own region');
    await page.locator('svg').screenshot({path:path.join(out,'algorithm-architecture-v7.png')});
    fs.writeFileSync(path.join(out,'algorithm-architecture-v7-qa.json'),JSON.stringify({width:W,height:H,pngWidth:W*3,pngHeight:H*3,textBounds:issues,minimumFontPx:40,placementWidthPt:194,effectiveMinimumPt:40*194/W,logic:'HMM/Viterbi recognition and FSM guidance have distinct outputs; only FSM feeds the display layer.',logos:['OpenCV','Ultralytics YOLO','MediaPipe','Python','Unity'],font:'Noto Sans KR'},null,2));
    console.log(JSON.stringify({svg:'algorithm-architecture-v7.svg',png:'algorithm-architecture-v7.png',textBounds:issues,effectiveMinimumPt:40*194/W}));
  }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
