const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const d=JSON.parse(fs.readFileSync(path.join(__dirname,'raw-before-v6.json'),'utf8')).structuredContent;
const existing=new Map(d.slides[0].pageElements.map(e=>[e.objectId,e]));
const requests=[];
const pt=n=>({magnitude:n,unit:'PT'});
const points=v=>v.magnitude/(v.unit==='EMU'?12700:1);
const rgb=h=>({red:parseInt(h.slice(0,2),16)/255,green:parseInt(h.slice(2,4),16)/255,blue:parseInt(h.slice(4,6),16)/255});
function place(id,x,y,w,h){const e=existing.get(id);assert(e);requests.push({updatePageElementTransform:{objectId:id,applyMode:'ABSOLUTE',transform:{scaleX:w/points(e.size.width),scaleY:h/points(e.size.height),translateX:x,translateY:y,unit:'PT'}}});}
function box(id,text,x,y,w,h,blue=false){
  const e=existing.get(id);assert(e?.shape);
  const styles=e.shape.text.textElements.filter(t=>t.textRun).map(t=>JSON.stringify(t.textRun.style));
  assert.equal(new Set(styles).size,1,'Preserve mixed styles explicitly');
  place(id,x,y,w,h);
  requests.push({deleteText:{objectId:id,textRange:{type:'ALL'}}},{insertText:{objectId:id,text,insertionIndex:0}},
    {updateTextStyle:{objectId:id,textRange:{type:'ALL'},style:{fontFamily:'Noto Sans KR',weightedFontFamily:{fontFamily:'Noto Sans KR',weight:400},fontSize:pt(9),bold:false},fields:'fontFamily,weightedFontFamily,fontSize,bold'}},
    {updateParagraphStyle:{objectId:id,textRange:{type:'ALL'},style:{alignment:'CENTER',lineSpacing:100,spaceAbove:pt(0),spaceBelow:pt(0)},fields:'alignment,lineSpacing,spaceAbove,spaceBelow'}},
    {updateShapeProperties:{objectId:id,shapeProperties:{contentAlignment:'MIDDLE',autofit:{autofitType:'NONE'},shapeBackgroundFill:{solidFill:{color:{rgbColor:rgb(blue?'f2f5fa':'f3f8f8')},alpha:1}},outline:{outlineFill:{solidFill:{color:{rgbColor:rgb(blue?'506d9b':'3b737a')},alpha:1}},weight:pt(.65),dashStyle:'SOLID',propertyState:'RENDERED'}},fields:'contentAlignment,autofit.autofitType,shapeBackgroundFill,outline'}});
}
function line(id,x1,y1,x2,y2,arrow=true,blue=false){
  assert(Math.min(x1,x2)>=277 && Math.max(x1,x2)<=463);
  assert(Math.min(y1,y2)>=506 && Math.max(y1,y2)<=686);
  requests.push({createLine:{objectId:id,lineCategory:'STRAIGHT',elementProperties:{pageObjectId:'p',size:{width:pt(3000000/12700),height:pt(3000000/12700)},transform:{scaleX:(x2-x1)*12700/3000000,scaleY:(y2-y1)*12700/3000000,translateX:x1,translateY:y1,unit:'PT'}}}},
    {updateLineProperties:{objectId:id,lineProperties:{lineFill:{solidFill:{color:{rgbColor:rgb(blue?'506d9b':'3b737a')},alpha:1}},weight:pt(.65),dashStyle:'SOLID',startArrow:'NONE',endArrow:arrow?'FILL_ARROW':'NONE'},fields:'lineFill,weight,dashStyle,startArrow,endArrow'}});
}
for(const e of existing.values())if(e.line)requests.push({deleteObject:{objectId:e.objectId}});
for(const id of ['pamv2_tool','pamv5_pnp'])requests.push({deleteObject:{objectId:id}});
box('pamv2_input','작업 영상 입력',277,506,186,18);
box('pamv2_pose','ArUco · YOLO · MediaPipe',277,531,186,20);
box('pamv5_relation','좌표 변환 · 손·도구 특징 추출\n거리 · 움직임 · ROI 변화',277,558,186,28);
box('pamv5_analysis','HMM 상태 모델\nViterbi 경로 추론',277,596,88,30,true);
box('pamv2_fsm','FSM 단계 전이\n접근·유지·이탈',375,596,88,30);
box('pamv2_relation','작업 단계 인식',277,636,88,20,true);
box('pamv5_recovery','진행 보존·재확인',375,636,88,20);
box('pamv2_output','Unity SBS · 웹 관제',277,668,186,18);
line('pamv6_l01',370,524,370,531);
line('pamv6_l02',370,551,370,558);
line('pamv6_l03',370,586,370,591,false);
line('pamv6_l04',321,591,419,591,false);
line('pamv6_l05',321,591,321,596,true,true);
line('pamv6_l06',419,591,419,596);
line('pamv6_l07',321,626,321,636,true,true);
line('pamv6_l08',419,626,419,636);
line('pamv6_l09',419,656,419,668);
// The recognition model and live guidance controller share the figure, not a fictitious runtime link.
place('h4e60779ebe987e3a_0_5',49.17,417,194,33);
place('pamv4_supervisor_photo',54,450,184,184*1431/3204);
place('pamv5_beast',54,264,89,89*2560/3841);
const beast=path.join(__dirname,'beast-official-v5.jpg');
requests.push({replaceImage:{imageObjectId:'pamv5_beast',url:beast,imageReplaceMethod:'CENTER_INSIDE'}});
const shot=path.join(__dirname,'supervisor-B-workspace-v6.png');
const imageRequest={replaceImage:{imageObjectId:'pamv4_supervisor_photo',url:shot,imageReplaceMethod:'CENTER_INSIDE'}};
fs.writeFileSync(path.join(__dirname,'native-requests-v6.json'),JSON.stringify({presentation_id:d.presentationId,write_control:{requiredRevisionId:d.revisionId},image_uris:beast,requests},null,2));
fs.writeFileSync(path.join(__dirname,'image-request-v6.json'),JSON.stringify({presentation_id:d.presentationId,image_uris:shot,requests:[imageRequest]},null,2));
console.log(JSON.stringify({requests:requests.length,secondImage:shot}));
