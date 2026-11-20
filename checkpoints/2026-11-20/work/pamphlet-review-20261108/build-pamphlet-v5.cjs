const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root = __dirname;
const raw = JSON.parse(fs.readFileSync(path.join(root, 'raw-before-v5.json'), 'utf8'));
const deck = raw.structuredContent;
const slide = deck.slides[0];
assert.equal(slide.objectId, 'p');
const existing = new Map(slide.pageElements.map(e => [e.objectId, e]));
const requests = [], images = [];
const rgb = h => ({red:parseInt(h.slice(0,2),16)/255,green:parseInt(h.slice(2,4),16)/255,blue:parseInt(h.slice(4,6),16)/255});
const color = '373d40', teal = '3b737a', blue = '506d9b';
const pt = n => ({magnitude:n,unit:'PT'});
const properties = (x,y,w,h) => ({pageObjectId:'p',size:{width:pt(w),height:pt(h)},transform:{scaleX:1,scaleY:1,translateX:x,translateY:y,unit:'PT'}});
function place(id,x,y,w,h) {
  const e=existing.get(id); assert(e, id);
  const unit = e.size.width.unit==='EMU' ? 12700 : 1;
  requests.push({updatePageElementTransform:{objectId:id,applyMode:'ABSOLUTE',transform:{scaleX:w/(e.size.width.magnitude/unit),scaleY:h/(e.size.height.magnitude/unit),translateX:x,translateY:y,unit:'PT'}}});
}
function text(id,content,x,y,w,h,{size=9.5,align='START',middle=false,bold=false,fill=null,stroke=teal,dash='SOLID',lineSpacing=112}={}) {
  if(existing.has(id)) {
    const styles = existing.get(id).shape.text.textElements.filter(e=>e.textRun).map(e=>JSON.stringify(e.textRun.style));
    assert.equal(new Set(styles).size,1,`Mixed-style text needs explicit range mapping: ${id}`);
    requests.push({deleteText:{objectId:id,textRange:{type:'ALL'}}});
    place(id,x,y,w,h);
  } else requests.push({createShape:{objectId:id,shapeType:fill?'RECTANGLE':'TEXT_BOX',elementProperties:properties(x,y,w,h)}});
  requests.push({insertText:{objectId:id,insertionIndex:0,text:content}});
  requests.push({updateTextStyle:{objectId:id,textRange:{type:'ALL'},style:{fontFamily:'Noto Sans KR',weightedFontFamily:{fontFamily:'Noto Sans KR',weight:bold?600:400},fontSize:pt(size),bold,foregroundColor:{opaqueColor:{rgbColor:rgb(color)}}},fields:'fontFamily,weightedFontFamily,fontSize,bold,foregroundColor'}});
  requests.push({updateParagraphStyle:{objectId:id,textRange:{type:'ALL'},style:{alignment:align,lineSpacing,spaceAbove:pt(0),spaceBelow:pt(0),indentStart:pt(0),indentEnd:pt(0),indentFirstLine:pt(0)},fields:'alignment,lineSpacing,spaceAbove,spaceBelow,indentStart,indentEnd,indentFirstLine'}});
  requests.push({updateShapeProperties:{objectId:id,shapeProperties:{contentAlignment:middle?'MIDDLE':'TOP',autofit:{autofitType:'NONE'},shapeBackgroundFill:fill?{solidFill:{color:{rgbColor:rgb(fill)},alpha:1}}:{propertyState:'NOT_RENDERED'},outline:fill?{outlineFill:{solidFill:{color:{rgbColor:rgb(stroke)},alpha:1}},weight:pt(0.65),dashStyle:dash,propertyState:'RENDERED'}:{propertyState:'NOT_RENDERED'}},fields:'contentAlignment,autofit.autofitType,shapeBackgroundFill,outline'}});
}
function box(id,content,x,y,w,h,opts={}) { text(id,content,x,y,w,h,{size:9,align:'CENTER',middle:true,fill:'f3f8f8',lineSpacing:100,...opts}); }
function line(id,x1,y1,x2,y2,{arrow=true,dashed=false,tint=teal}={}) {
  requests.push({createLine:{objectId:id,lineCategory:'STRAIGHT',elementProperties:properties(x1,y1,Math.max(1,Math.abs(x2-x1)),Math.max(1,Math.abs(y2-y1)))}});
  // Slides normalizes line size to 3,000,000 EMU; scale endpoints to that base.
  requests.push({updatePageElementTransform:{objectId:id,applyMode:'ABSOLUTE',transform:{scaleX:(x2-x1)*12700/3000000,scaleY:(y2-y1)*12700/3000000,translateX:x1,translateY:y1,unit:'PT'}}});
  requests.push({updateLineProperties:{objectId:id,lineProperties:{lineFill:{solidFill:{color:{rgbColor:rgb(tint)},alpha:1}},weight:pt(.65),dashStyle:dashed?'DASH':'SOLID',startArrow:'NONE',endArrow:arrow?'FILL_ARROW':'NONE'},fields:'lineFill,weight,dashStyle,startArrow,endArrow'}});
}
async function image(id,file,x,y,w,h) {
  const meta=await sharp(file).metadata();
  const s=Math.min(w/meta.width,h/meta.height),iw=meta.width*s,ih=meta.height*s;
  requests.push({createImage:{objectId:id,url:file,elementProperties:properties(x+(w-iw)/2,y+(h-ih)/2,iw,ih)}});
  images.push(file);
}
function del(id) { assert(existing.has(id)); requests.push({deleteObject:{objectId:id}}); }
async function main() {
  await sharp(path.join(root,'beast-home-official-v5.webp')).png().toFile(path.join(root,'beast-official-front-v5.png'));
  for(const name of ['python','opencv','unity','csharp','mediapipe'])
    await sharp(path.join(root,`logo-${name}-v5.svg`),{density:288}).resize({width:256,height:256,fit:'inside'}).png().toFile(path.join(root,`logo-${name}-v5.png`));

  for(const id of ['pamv4_photo_aruco','pamv4_photo_mediapipe','pamv4_photo_yolo','pamv4_label_aruco','pamv4_label_mediapipe','pamv4_label_yolo','pamv3_supervisor_caption']) del(id);
  for(const e of slide.pageElements.filter(e=>e.objectId.startsWith('pamv2_line_'))) del(e.objectId);

  // The original technology-list object becomes the device caption.
  text('h4e60779ebe987e3a_0_0','VITURE Beast\n양안 AR 표시\nWindows PC 연결',54,326,89,43,{size:9.5,align:'CENTER',lineSpacing:116});
  await image('pamv5_beast',path.join(root,'beast-official-front-v5.png'),54,266,89,56);
  const logos=[['python','Python'],['opencv','OpenCV'],['yolo','YOLO'],['mediapipe','MediaPipe'],['unity','Unity'],['csharp','C#']];
  for(const [i,[name,label]] of logos.entries()) {
    const x=148+(i%2)*47,y=266+Math.floor(i/2)*33;
    await image(`pamv5_logo_${name}`,path.join(root,`logo-${name}-v5.png`),x+12,y,20,20);
    text(`pamv5_logo_label_${name}`,label,x,y+20.5,44,13,{size:9,align:'CENTER',lineSpacing:100});
  }

  place('pamv4_ar_example',277,267,186,124);
  text('pamv2_visual_caption','AR 작업 안내 예시',277,395,186,17,{size:9.5,align:'CENTER'});
  text('pamv5_demo_action','목표 위치를 확인하고\n다음 행동을 시야에서 안내받는다.',277,418,186,30,{size:9.5,align:'CENTER',lineSpacing:118});

  text('h4e60779ebe987e3a_0_5','도구 동작에 따라 A–D 단계를 전환하고\n현재 목표·다음 행동을 관제로 공유한다.',49.17,422,194,27,{size:9.5,lineSpacing:110});
  const shot=await sharp(path.join(root,'supervisor-current-saved-data-v4.png')).metadata();
  place('pamv4_supervisor_photo',54,451,184,184*shot.height/shot.width);

  text('h4e60779ebe987e3a_0_6','조립 중 설명서와 작업 대상을 번갈아\n확인하면 시선이 분산되고, 다음 작업의\n위치와 순서를 찾는 부담이 생긴다.\n\n작업자의 시야에 목표 위치와 다음 행동을\n표시하여 작업에 집중할 수 있는\nAR 기반 조립 안내 환경을 구현한다.',49.17,576,194,108,{size:9.5,lineSpacing:118});

  box('pamv2_input','작업 영상 입력',277,506,186,16,{fill:'ffffff'});
  box('pamv2_pose','ArUco 검출\n마커 좌표',277,526,88,27);
  box('pamv2_tool','YOLO 검출\n도구 위치',375,526,88,27,{fill:'f2f5fa',stroke:blue});
  box('pamv5_pnp','PnP 자세 추정\nA–D 좌표 변환',277,557,88,27);
  box('pamv5_relation','목표·도구 관계\n접근 · 유지 · 이탈',375,557,88,27,{fill:'f2f5fa',stroke:blue});
  box('pamv2_relation','관측 유효성 · 시간 연속성 확인',277,588,186,18,{fill:'ffffff'});
  box('pamv2_fsm','FSM 단계 전이\nHOLD → MOVE CLEAR',277,610,88,28);
  box('pamv5_recovery','진행 정보 보존\n관측 복구 · 재확인',375,610,88,28,{fill:'f8f4e9',stroke:'9b804b'});
  box('pamv2_output','양안 보정 · Unity SBS · 웹 관제',277,642,186,18,{fill:'ffffff'});
  box('pamv5_analysis','MediaPipe → HMM·Viterbi 분석',277,668,186,18,{fill:'f2f5fa',stroke:blue,dash:'DASH'});
  // Solid path drives guidance; the dashed branch is feature/time-series analysis.
  line('pamv5_l01',370,522,370,524,{arrow:false});
  line('pamv5_l02',321,524,419,524,{arrow:false});
  line('pamv5_l03',321,524,321,526);
  line('pamv5_l04',419,524,419,526,{tint:blue});
  line('pamv5_l05',321,553,321,557);
  line('pamv5_l06',419,553,419,557,{tint:blue});
  line('pamv5_l07',365,570.5,375,570.5);
  line('pamv5_l08',321,584,321,586,{arrow:false});
  line('pamv5_l09',419,584,419,586,{arrow:false,tint:blue});
  line('pamv5_l10',321,586,419,586,{arrow:false});
  line('pamv5_l11',370,586,370,588);
  line('pamv5_l12',321,606,321,610);
  line('pamv5_l13',419,606,419,610,{tint:'9b804b'});
  line('pamv5_l14',321,638,321,640,{arrow:false});
  line('pamv5_l15',321,640,370,640,{arrow:false});
  line('pamv5_l16',370,640,370,642);
  line('pamv5_l17',463,624,469,624,{arrow:false,tint:'9b804b'});
  line('pamv5_l18',469,624,469,597,{arrow:false,tint:'9b804b'});
  line('pamv5_l19',469,597,463,597,{tint:'9b804b'});
  line('pamv5_a01',277,514,272,514,{arrow:false,dashed:true,tint:blue});
  line('pamv5_a02',272,514,272,677,{arrow:false,dashed:true,tint:blue});
  line('pamv5_a03',272,677,277,677,{dashed:true,tint:blue});

  fs.writeFileSync(path.join(root,'native-requests-v5.json'),JSON.stringify({presentation_id:deck.presentationId,write_control:{requiredRevisionId:deck.revisionId},image_uris:images.join('\n'),requests},null,2));
  fs.writeFileSync(path.join(root,'visual-provenance-v5.json'),JSON.stringify({beast:{page:'https://www.viture.com/product/viture-beast-xr-glasses',image:'https://www.viture.com/images/home/section8/beast.webp',use:'Product identification; format conversion only'},logos:{devicon:'https://github.com/devicons/devicon',ultralytics:'https://github.com/ultralytics/assets',mediapipe:'https://cdn.simpleicons.org/mediapipe/0097A7'},ar:'Existing user-provided illustration; enlarged without modification',supervisor:'Existing v4 saved-data UI example; retained without changing its contents',imageCount:images.length},null,2));
  console.log(JSON.stringify({requests:requests.length,images:images.length}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
