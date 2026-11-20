const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root = __dirname;
const d = JSON.parse(fs.readFileSync(path.join(root,'raw-output-v5-verified.json'),'utf8')).structuredContent;
const pt = v => v.magnitude/(v.unit==='EMU'?12700:1);
const e = new Map(d.slides[0].pageElements.map(x=>[x.objectId,x]));
const text = x => x.shape?.text?.textElements?.filter(t=>t.textRun).map(t=>t.textRun.content).join('') || '';
assert.equal(d.slides.length,1);
assert.equal(d.slides[0].objectId,'p');
assert.equal(d.pageSize.width.magnitude,6552000);
assert.equal(d.pageSize.height.magnitude,9252000);
assert.equal(e.get('h4e60779ebe987e3a_0_2').shape.text.textElements.find(t=>t.textRun).textRun.style.fontSize.magnitude,26);
for (const id of ['h4e60779ebe987e3a_0_3','h4e60779ebe987e3a_0_4']) {
  const s=e.get(id).shape.text.textElements.find(t=>t.textRun).textRun.style;
  assert.equal(s.fontSize.magnitude,11);
  assert.equal(s.weightedFontFamily.weight,600);
}
for (const el of e.values()) {
  if (!el.shape) continue;
  for (const t of el.shape.text?.textElements || []) {
    if (!t.textRun) continue;
    const s=t.textRun.style;
    assert.equal(s.fontFamily,'Noto Sans KR');
    assert(s.fontSize.magnitude>=9);
  }
}
const content=[...e.values()].map(text).join('\n');
assert(!/한계점|실측 아님|합성|포함하지 않는다/.test(content));
assert(content.includes('MediaPipe → HMM·Viterbi 분석'));
assert.equal(text(e.get('pamv5_logo_label_mediapipe')).trim(),'MediaPipe');
for (const el of e.values()) {
  if (!el.line) continue;
  const t=el.transform,u=t.unit==='EMU'?12700:1;
  const x=t.translateX/u,y=t.translateY/u;
  const x2=x+(t.scaleX||0)*pt(el.size.width),y2=y+(t.scaleY||0)*pt(el.size.height);
  assert(Math.min(x,x2)>=270 && Math.max(x,x2)<=470,el.objectId);
  assert(Math.min(y,y2)>=506 && Math.max(y,y2)<=686,el.objectId);
}
async function main(){
  const files=[['pamv5_beast','beast-official-front-v5.png'],['pamv4_supervisor_photo','supervisor-current-saved-data-v4.png'],...['python','opencv','yolo','mediapipe','unity','csharp'].map(n=>[`pamv5_logo_${n}`,`logo-${n}-v5.png`])];
  for(const [id,file] of files){
    const el=e.get(id),m=await sharp(path.join(root,file)).metadata();
    const ratio=pt(el.size.width)*el.transform.scaleX/(pt(el.size.height)*el.transform.scaleY);
    assert(Math.abs(ratio/(m.width/m.height)-1)<0.003,`${id}: distorted media`);
  }
  const ar=e.get('pamv4_ar_example');
  assert(Math.abs(pt(ar.size.width)*ar.transform.scaleX/(pt(ar.size.height)*ar.transform.scaleY)-1.5)<0.003);
  console.log(JSON.stringify({slideCount:1,templatePreserved:true,bodyMinimumPt:9,titlePt:26,identityPt:11,identityWeight:600,mediaAspectRatios:'passed',algorithmLineBounds:'passed',sourceRevision:d.revisionId}));
}
main().catch(err=>{console.error(err);process.exitCode=1;});
