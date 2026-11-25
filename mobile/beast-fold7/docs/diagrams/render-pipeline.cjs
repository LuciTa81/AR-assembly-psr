const fs=require('node:fs');
const path=require('node:path');
const out=__dirname;
const C={ink:'#182b35',muted:'#526773',border:'#cbd9dd',ar:'#168672',video:'#307bc2',state:'#976329',auth:'#7b8291'};
const xml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
let parts=[];
function text(x,y,s,size=22,fill=C.ink,weight=400){parts.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${fill}" font-weight="${weight}">${xml(s)}</text>`);}
function rect(x,y,w,h,fill,stroke=C.border,r=8){parts.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`);}
function node(x,y,w,h,title,lines,color=C.ar){rect(x,y,w,h,'#ffffff');parts.push(`<path d="M${x+20} ${y+25}h28" stroke="${color}" stroke-width="5"/>`);text(x+20,y+60,title,26,C.ink,700);lines.forEach((s,i)=>text(x+20,y+95+i*30,s,21,C.muted));}
function arrow(d,color=C.ar,dash=false){parts.push(`<path d="${d}" fill="none" stroke="${color}" stroke-width="3" ${dash?'stroke-dasharray="9 7"':''} marker-end="url(#${Object.keys(C).find(k=>C[k]===color)})"/>`);}
function label(x,y,s,color=C.muted){const w=[...s].reduce((n,c)=>n+(c.charCodeAt(0)>255?20:11),0)+22;rect(x-10,y-25,w,35,'#ffffff','none',3);text(x,y,s,20,color,500);}
parts.push(`<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1740" viewBox="0 0 2400 1740"><defs>${['ar','video','state','auth'].map(k=>`<marker id="${k}" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L8 4L0 8Z" fill="${C[k]}"/></marker>`).join('')}</defs><style>text{font-family:'Malgun Gothic','Noto Sans KR',sans-serif;letter-spacing:0}</style><rect width="2400" height="1740" fill="#ffffff"/>`);
text(50,75,'AR Assembly',52,C.ink,700);text(420,75,'전체 시스템 파이프라인',38,C.ink,600);
text(52,120,'Fold7에서 인식·판단·양안 표시, 인터넷으로 상태·영상 관제',24,C.muted);
text(1940,74,'ANDROID 1.4.1',23,C.muted,700);text(1940,113,'구현 기준 · 2026.11.24',20,C.muted);
rect(320,185,1780,835,'#f4f9f7','#b4d3c8',12);
text(350,235,'01  Fold7 · Android 16',31,C.ink,700);text(790,233,'로컬 AR 실행 / 네트워크와 분리된 처리 경로',22,C.muted);
rect(320,1120,650,455,'#f6f8fb','#c6d4e0',12);text(350,1160,'02  AWS EC2',29,C.ink,700);
rect(1480,1120,620,275,'#f6f8fb','#c6d4e0',12);text(1510,1160,'03  관제 브라우저',29,C.ink,700);

// Connections precede nodes so all line ends terminate cleanly at node boundaries.
arrow('M290 465H360');label(295,442,'USB-C',C.ar);
arrow('M610 430H650V370H700');
arrow('M610 490H650V605H700');
arrow('M1040 370H1110');label(1048,345,'자세',C.ar);
arrow('M1040 605H1110');
arrow('M1260 450V525');label(1274,490,'좌표·평면',C.ar);
arrow('M1410 370H1480');
arrow('M1780 370H1810');
arrow('M2060 370H2130');
arrow('M1410 605H1480');
arrow('M1780 605H1810');
arrow('M1630 525V485H1870V450');label(1645,477,'현재 단계·색상',C.ar);
arrow('M1985 525V450');
arrow('M1630 675V820',C.state);label(1644,754,'상태 JSON',C.state);
arrow('M490 550V820',C.video);label(505,756,'원본 프레임',C.video);
arrow('M870 790V730H675V450H700',C.auth,true);
arrow('M1040 850H1450V450H1630',C.auth,true);label(1110,840,'기존 좌·우 보정 유지',C.auth);
arrow('M490 975V1045H335V1180H490V1190',C.video);label(350,1083,'WSS /video',C.video);
arrow('M1630 975V1060H795V1190',C.state);label(1120,1050,'WSS /ws · 작업 상태',C.state);
arrow('M930 1240H1520',C.video);label(1040,1230,'H.264 영상 직접 전달',C.video);
arrow('M930 1310H1520',C.state);label(1040,1300,'현재 상태 직접 전달',C.state);
arrow('M630 1360V1430',C.auth);label(645,1405,'메타데이터만 저장',C.auth);
arrow('M1520 1465H1390',C.auth,true);label(1410,1445,'OAuth',C.auth);
arrow('M1790 1360V1410H1220V1440',C.auth,true);
arrow('M1050 1520H1000V1350H930',C.auth,true);label(1030,1600,'HTTPS · 기기 / 기록 / 접속 티켓',C.auth);

node(40,380,250,170,'Beast 카메라',['작업대·마커·도구','UVC 영상 입력']);
node(360,380,250,170,'프레임 입력',['NV21 · 1280×720','AR 분석 / 영상 분기']);
node(700,290,340,160,'마커 추적 · 자세 추정',['OpenCV ArUco','IPPE → LM · 품질 검사']);
node(1110,290,300,160,'작업대 좌표',['A~D 카메라 XYZ','상자·뚜껑 3D 윤곽']);
node(1480,290,300,160,'눈별 투영',['좌·우 3×4 행렬','카메라 XYZ → 픽셀']);
node(1810,290,250,160,'양안 렌더링',['나사·윤곽·한글','Android Presentation']);
node(2130,290,230,185,'Beast 표시',['Full SBS','3840×1080','0DoF 설정 유지']);
node(700,525,340,150,'도구 검출',['YOLO · ONNX Runtime','로컬 드라이버 검출']);
node(1110,525,300,150,'도구 근접 증거',['도구 끝 → 나사 평면','목표별 거리·점수']);
node(1480,525,300,150,'단계 안내 제어',['상자 → 뚜껑 → A~D','주황 → 파랑 → 초록']);
node(1810,525,250,150,'3D 부품 예시',['로컬 Three.js','화면 오른쪽 위']);
node(700,790,340,155,'읽기 전용 보정',['카메라 · 작업대 · 눈별','A~D / 205·205 유지'],C.auth);
node(360,820,300,155,'영상 인코딩',['MediaCodec · H.264','하드웨어 인코더'],C.video);
node(1480,820,300,155,'상태 발행',['단계·추적·표시 상태','영상과 별도 연결'],C.state);
text(1810,863,'상자 7초 · 뚜껑 6초',20,C.muted,600);
text(1810,898,'유효 추적·표시 시간 누적',19,C.muted);
text(1810,933,'초록 표시 후 3초 뒤 진행',19,C.muted);
node(360,1190,570,170,'인증된 상태·영상 중계',['Nginx TLS → Node.js Relay','소유자 인증 · 순서 검사 · 기기별 격리','서버 추론 / 영상 디코딩 없음'],C.video);
node(360,1430,570,120,'PostgreSQL',['기기 등록 · 접속 티켓 · 작업 상태 이력'],C.auth);
node(1520,1190,540,170,'실시간 관제',['WebCodecs → Canvas 카메라 영상','현재 단계 · 추적 상태 · 작업 기록','영상 표시 켜기 / 끄기'],C.video);
node(1050,1440,340,130,'Vercel · Next.js',['웹 UI · 로그인 · BFF'],C.auth);
node(1520,1440,270,130,'GitHub OAuth',['본인 계정 로그인'],C.auth);
text(1840,1478,'영상은 Vercel을',21,C.muted,600);text(1840,1513,'경유하지 않음',21,C.muted,600);
parts.push('<path d="M50 1625H2350" stroke="#d5dfe2" stroke-width="2"/>');
text(50,1665,'민트: 로컬 AR',20,C.ar,600);text(300,1665,'파랑: 영상',20,C.video,600);text(530,1665,'갈색: 상태',20,C.state,600);text(760,1665,'회색 점선: 인증·설정',20,C.auth,600);
text(1230,1665,'영상 공유 별도 동의 · 음성 전송 없음 · 영상 저장 없음',21,C.ink,600);
text(50,1710,'현재 폰 실행 경로에는 Python·Unity·HMM/MediaPipe 없음. 기존 보정만 이식. 새 영상과 AR 동시 구동은 실기 확인 예정.',21,C.muted);
parts.push('</svg>');
fs.writeFileSync(path.join(out,'ar-assembly-pipeline-1.4.1.svg'),parts.join('\n'));
console.log('SVG written');

(async()=>{
 const {chromium}=require(path.join(process.env.CODEX_NODE_MODULES,'playwright'));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
   const page=await browser.newPage({viewport:{width:2400,height:1740},deviceScaleFactor:1});
   await page.setContent(parts.join('\n'));await page.evaluate(()=>document.fonts.ready);
   await page.locator('svg').screenshot({path:path.join(out,'ar-assembly-pipeline-1.4.1.png')});
   const overflowing=await page.locator('text').evaluateAll(nodes=>nodes.filter(n=>{const b=n.getBBox();return b.x<0||b.y<0||b.x+b.width>2400||b.y+b.height>1740;}).map(n=>n.textContent));
   if(overflowing.length)throw new Error('Text outside canvas: '+overflowing.join(', '));
   console.log('PNG rendered; text bounds checked');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
