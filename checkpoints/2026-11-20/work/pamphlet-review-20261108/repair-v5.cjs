const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = __dirname;
const deck = JSON.parse(fs.readFileSync(path.join(root, 'raw-output-v5.json'), 'utf8')).structuredContent;
const plan = JSON.parse(fs.readFileSync(path.join(root, 'native-requests-v5.json'), 'utf8'));
const elements = new Map(deck.slides[0].pageElements.map(e => [e.objectId, e]));
const requests = [];
const points = v => v.magnitude / (v.unit === 'EMU' ? 12700 : 1);
function place(id, x, y, w, h) {
  const e = elements.get(id);
  requests.push({updatePageElementTransform:{objectId:id,applyMode:'ABSOLUTE',transform:{scaleX:w/points(e.size.width),scaleY:h/points(e.size.height),translateX:x,translateY:y,unit:'PT'}}});
}
function replace(id, text) {
  requests.push({deleteText:{objectId:id,textRange:{type:'ALL'}}}, {insertText:{objectId:id,text,insertionIndex:0}});
  requests.push({updateTextStyle:{objectId:id,textRange:{type:'ALL'},style:{fontFamily:'Noto Sans KR',fontSize:{magnitude:id==='pamv2_fsm'?9:9.5,unit:'PT'}},fields:'fontFamily,fontSize'}});
}
for (const request of plan.requests.filter(r=>r.createLine)) {
  const {objectId,elementProperties:p} = request.createLine;
  const t = plan.requests.find(r=>r.updatePageElementTransform?.objectId===objectId).updatePageElementTransform.transform;
  const e = elements.get(objectId);
  const sx = (t.scaleX||0)*points(p.size.width)/points(e.size.width);
  const sy = (t.scaleY||0)*points(p.size.height)/points(e.size.height);
  const x2 = t.translateX + sx*points(e.size.width), y2 = t.translateY + sy*points(e.size.height);
  assert(Math.min(t.translateX,x2)>=270 && Math.max(t.translateX,x2)<=470);
  assert(Math.min(t.translateY,y2)>=506 && Math.max(t.translateY,y2)<=686);
  requests.push({updatePageElementTransform:{objectId,applyMode:'ABSOLUTE',transform:{...t,scaleX:sx,scaleY:sy}}});
}
for (const [i,name] of ['python','opencv','yolo','mediapipe','unity','csharp'].entries()) {
  const x=137+(i%2)*52, y=264+Math.floor(i/2)*35;
  const id=`pamv5_logo_${name}`, e=elements.get(id);
  const w=points(e.size.width)*e.transform.scaleX, h=points(e.size.height)*e.transform.scaleY;
  const s=Math.min(18/w,18/h);
  place(id,x+(52-w*s)/2,y+(18-h*s)/2,w*s,h*s);
  place(`pamv5_logo_label_${name}`,x,y+18,52,15);
  requests.push({updateShapeProperties:{objectId:`pamv5_logo_label_${name}`,shapeProperties:{contentAlignment:'MIDDLE'},fields:'contentAlignment'}});
}
replace('pamv2_fsm','FSM 단계 전이\n유지 → 이탈');
replace('h4e60779ebe987e3a_0_5','도구 동작에 따라 A–D 단계를 전환하고\n현재 목표와 다음 행동을 관제로 공유한다.');
place('h4e60779ebe987e3a_0_5',49.17,419,194,33);
const shot=elements.get('pamv4_supervisor_photo');
const sw=points(shot.size.width)*shot.transform.scaleX, sh=points(shot.size.height)*shot.transform.scaleY;
place('pamv4_supervisor_photo',57,456,178,178*sh/sw);
fs.writeFileSync(path.join(root,'repair-requests-v5.json'),JSON.stringify({presentation_id:deck.presentationId,write_control:{requiredRevisionId:deck.revisionId},requests},null,2));
console.log(JSON.stringify({repairs:requests.length,verifiedLineBounds:true}));
