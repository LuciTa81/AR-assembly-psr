const fs = require('node:fs');
const path = require('node:path');
const C = { ink:'#182b35', muted:'#526773', ar:'#168672', video:'#307bc2', state:'#976329', border:'#cad7dd' };
const out = path.join(__dirname, 'video-transport-comparison');
const escape = s => s.replaceAll('&','&amp;').replaceAll('<','&lt;');
const p = [];
function text(x,y,s,size=23,color=C.ink,bold=false) { p.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${bold?700:400}">${escape(s)}</text>`); }
function box(x,y,w,h,fill='#fff',stroke=C.border) { p.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`); }
function node(x,y,w,title,lines,color=C.video) { box(x,y,w,124); p.push(`<path d="M${x+22} ${y+25}h25" stroke="${color}" stroke-width="5"/>`); text(x+22,y+57,title,27,C.ink,true); lines.forEach((s,i)=>text(x+22,y+88+25*i,s,20,C.muted)); }
function arrow(x,y,end,color=C.video) { p.push(`<path d="M${x} ${y}V${end}" stroke="${color}" stroke-width="3" marker-end="url(#${color===C.state?'state':'video'})"/>`); }
p.push(`<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="1630" viewBox="0 0 2000 1630"><defs>${['video','state'].map(k=>`<marker id="${k}" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="${C[k]}"/></marker>`).join('')}</defs><style>text{font-family:'Malgun Gothic',sans-serif;letter-spacing:0}</style><rect width="2000" height="1630" fill="white"/>`);
text(55,74,'AR Assembly',44,C.ink,true);
text(370,74,'현재 구조와 IVS 도입안',36,C.ink,true);
text(55,119,'영상 전달 경로 비교 · 인식과 양안 AR은 두 구성 모두 Fold7에서 실행',24,C.muted);
text(1710,72,'2026.11.25',22,C.muted);
box(55,155,1890,190,'#f1f8f5','#accfc0');
text(85,199,'공통 핵심 · 변경 없음',27,C.ar,true);
text(85,247,'Beast 카메라 → Fold7: OpenCV ArUco + YOLO ONNX → 도구 근접 증거 → 단계 판단',29,C.ink,true);
text(85,294,'기존 A~D 보정 → 좌·우 눈별 투영 → Beast Full SBS   /   상자·뚜껑·나사 안내와 3D 부품 예시',24,C.muted);
const cols = [70,1040];
cols.forEach((x,i)=>{
  text(x,409,i?'B  IVS Real-Time 도입안':'A  현재 구현 · 1.4.1',32,C.ink,true);
  text(x,450,i?'제안 단계 · 앱·서버·웹 추가 구현 필요':'배포·설치 완료 · Beast 실영상 통합 시험 남음',22,i?C.state:C.ar);
});
node(90,485,820,'Fold7 · MediaCodec',['Beast 프레임 → 하드웨어 H.264 인코딩','현재 앱의 영상 전송 동의가 켜진 동안만 전송']);
arrow(500,609,675); text(530,650,'인증된 WSS /video',21,C.video);
node(90,675,820,'AWS EC2 · 영상 중계',['Nginx TLS → Node.js Relay','H.264 패킷 전달 · 기기별 격리 · 서버 추론 없음']);
arrow(500,799,865); text(530,840,'인증된 WSS /video',21,C.video);
node(90,865,820,'웹 관제 · WebCodecs',['브라우저에서 H.264 디코딩·표시','영상은 Vercel을 경유하지 않음']);
node(1060,485,820,'Fold7 · IVS Broadcast SDK',['Beast 프레임 → CustomImageSource / Surface 연동','기존 UVC 캡처는 유지 · 영상 송출 부분을 교체']);
arrow(1470,609,675); text(1500,650,'참가 토큰 · 영상 게시',21,C.video);
node(1060,675,820,'AWS IVS · Real-Time Stage',['관리형 실시간 영상 전달','EC2는 영상 패킷을 중계하지 않음']);
arrow(1470,799,865); text(1500,840,'참가 토큰 · 영상 구독',21,C.video);
node(1060,865,820,'웹 관제 · IVS Web SDK',['권한이 있는 관제자가 Stage 영상 구독','현재 WebCodecs 직접 재생 경로를 교체']);
box(55,1025,1890,220,'#faf7f1','#d6c8ad');
text(85,1070,'상태·로그·로그인은 별도 경로로 유지',27,C.state,true);
text(85,1117,'Fold7 ── WSS /ws ── EC2 Node.js ── WSS ── 관제 브라우저',27,C.ink,true);
text(85,1158,'Vercel Next.js + GitHub 로그인 · 소유자 인증 · PostgreSQL 기기/작업 기록',23,C.muted);
text(85,1200,'IVS 도입 시 추가: EC2가 권한 확인 후 게시/구독 토큰 발급 · AWS 자격 증명은 서버에만 보관',23,C.muted);
text(90,1304,'지금 얻는 것',27,C.ar,true);
text(90,1348,'기존 시스템으로 단일 작업자·관제 시연 가능',23);
text(90,1387,'추가 미디어 서비스 없이 운영 · 실기 검증 우선',23);
text(90,1426,'혼잡 회선·발열·재연결은 실제 장비로 확인 필요',23,C.muted);
text(1060,1304,'IVS로 얻는 것 / 추가 부담',27,C.video,true);
text(1060,1348,'관리형 영상 전달 · 여러 시청자 대응 기반',23);
text(1060,1387,'SDK·토큰·UVC 연동 및 회귀 시험 · 이용량 과금',23);
text(1060,1426,'YOLO 정확도·AR 정합·입력 프레임률은 개선하지 않음',23,C.muted);
p.push('<path d="M55 1475H1945" stroke="#cad7dd" stroke-width="2"/>');
text(55,1522,'판단: 전시에는 현재 구조 검증부터. 원격 영상의 확장·운영 요구가 커지면 IVS를 도입.',27,C.ink,true);
text(55,1570,'IVS는 현재 /video 경로의 대체안이며 이중 송출안이 아님 · 저장은 어느 쪽도 별도 동의·구현 필요',22,C.muted);
p.push('</svg>');
const svg=p.join('\n'); fs.writeFileSync(out+'.svg',svg);
(async()=>{
  const {chromium}=require(path.join(process.env.CODEX_NODE_MODULES,'playwright'));
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:2000,height:1630},deviceScaleFactor:1});
    await page.setContent(svg); await page.evaluate(()=>document.fonts.ready);
    const overflow=await page.locator('text').evaluateAll(items=>items.filter(e=>{const b=e.getBBox();return b.x<0||b.y<0||b.x+b.width>2000||b.y+b.height>1630;}).map(e=>e.textContent));
    if(overflow.length) throw new Error(JSON.stringify(overflow));
    await page.locator('svg').screenshot({path:out+'.png'});
    console.log(JSON.stringify({svg:out+'.svg',png:out+'.png',overflow}));
  } finally {await browser.close();}
})();
