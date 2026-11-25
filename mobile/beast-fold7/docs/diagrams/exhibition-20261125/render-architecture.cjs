const fs = require('node:fs');
const path = require('node:path');
const deps = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const sharp = require(path.join(deps, 'sharp'));
const { PDFDocument } = require(path.join(deps, 'pdf-lib'));
const W=2600, H=1530;
const colors={ink:'#243143', muted:'#718096', line:'#8290A0', border:'#CAD5E2', phone:'#E87C28', cloud:'#59799A', web:'#6F618E', teal:'#078E94'};
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const svg=[];
function text(x,y,s,size=20,color=colors.ink,weight=400){svg.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}">${esc(s)}</text>`);}
function rect(x,y,w,h,stroke=colors.border,fill='white',r=12,shadow=false){svg.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="1.5" ${shadow?'filter="url(#shadow)"':''}/>`);}
function arrow(points,dash=false,color=colors.line){svg.push(`<path d="${points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="2" ${dash?'stroke-dasharray="7 6"':''} marker-end="url(#arrow)"/>`);}
function label(x,y,s,size=17){const width=[...s].reduce((a,c)=>a+(c.charCodeAt(0)>255?size:size*.55),0);rect(x-5,y-size,width+10,size+8,'none');text(x,y,s,size,colors.muted);}
function node(x,y,w,title,lines,badge,color=colors.teal,h=146){rect(x,y,w,h,colors.border,'white',12,true);rect(x+20,y+27,46,46,'none',color,9);text(x+27,y+57,badge,19,'white',700);text(x+84,y+41,title,23,colors.ink,600);lines.forEach((s,i)=>text(x+84,y+73+i*25,s,18,colors.muted));}
function group(x,y,w,h,title,color){rect(x,y,w,h,color,'none',16);text(x+23,y+35,title,22,color,600);}
svg.push(`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs><filter id="shadow" x="-5%" y="-5%" width="110%" height="115%"><feDropShadow dx="0" dy="3" stdDeviation="2" flood-color="#253349" flood-opacity="0.07"/></filter><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="${colors.line}"/></marker></defs><rect width="${W}" height="${H}" fill="white"/><g font-family="Malgun Gothic, sans-serif">`);
text(60,72,'AR 조립 안내 시스템 아키텍처',38,colors.ink,700);
text(60,111,'VITURE Beast · Samsung Z Fold7 / Android 16 · C3.2 부분 가림 추적 · AWS 중계·저장 · Next.js 웹 관제',21,colors.muted);
text(2250,70,'전시 버전  /  2026.11.25',20,colors.muted);
group(440,190,1200,1140,'휴대폰 앱 · Android / Java 실행 경로',colors.phone);
group(1700,190,440,1140,'AWS · EC2 + PostgreSQL + S3',colors.cloud);
group(2200,190,340,1140,'웹 · Vercel / 브라우저',colors.web);

// Connections are drawn before nodes so ports terminate cleanly at their edges.
arrow([[220,480],[220,406]]);label(245,451,'작업대 촬영');
arrow([[380,333],[480,333]]);label(384,312,'UVC');
arrow([[415,333],[415,553],[480,553]]);label(423,530,'RGBA');
arrow([[400,333],[400,1213],[480,1213]]);label(405,1165,'NV21');
arrow([[900,333],[1120,333]]);label(938,311,'R, t · A–D');
arrow([[900,553],[1120,553]]);label(934,531,'검출 상자');
arrow([[1355,406],[1355,480]]);label(1373,450,'3D / 2D 위치');
arrow([[900,773],[1030,773],[1030,380],[900,380]],true);
label(933,429,'모서리 지도');label(933,455,'자세 교차 검증');
arrow([[1355,626],[1355,700]]);label(1373,669,'근접 증거');
arrow([[900,993],[1120,993]]);label(931,971,'보정 행렬');
arrow([[1590,333],[1617,333],[1617,993],[1590,993]]);label(1455,895,'카메라 XYZ');
arrow([[1355,846],[1355,920]]);label(1373,891,'현재 대상 · 색 · 문구');
arrow([[1120,1030],[1075,1030],[1075,1085],[220,1085],[220,1066]]);label(478,1076,'좌안 1920×1080 + 우안 1920×1080 → Full SBS 3840×1080');
arrow([[900,1213],[1120,1213]]);label(930,1191,'H.264 / AVC');
arrow([[1590,800],[1664,800],[1664,1180],[1590,1180]]);label(1601,1116,'상태');
arrow([[1590,1240],[1680,1240],[1680,773],[1730,773]]);label(1625,1357,'HTTPS / WSS');

arrow([[2230,333],[2110,333]]);label(2145,310,'인증 API');
arrow([[1920,406],[1920,480]]);label(1937,449,'소유자 · 기기');
arrow([[1920,626],[1920,700]]);label(1937,670,'권한 검증');
arrow([[2110,760],[2230,760]]);label(2145,739,'WSS');
arrow([[1920,846],[1920,920]]);label(1937,890,'저장 동의 시');
arrow([[1920,1066],[1920,1140]]);label(1937,1109,'MP4 업로드');
arrow([[2110,1213],[2230,1213]]);label(2147,1191,'직접 수신');
arrow([[2370,1140],[2370,1078],[2168,1078],[2168,284],[2110,284]],true);
label(2220,1056,'다운로드 권한 요청');

node(60,260,320,'Beast · 카메라',['USB-C / UVC 입력','1280×720 작업대 영상','카메라·디스플레이 직결'],'CAM','#202B36');
node(60,480,320,'고정 작업대',['ArUco 마커 / 상자 / 뚜껑','A–D 나사 / 드라이버','기존 배치·보정 유지'],'WS',colors.cloud);
node(60,920,320,'Beast · 양안 표시',['나사 구 / 윤곽 / 한글 안내','화면 고정 3D 부품','0DoF · Extra Large · 4.5m'],'SBS','#202B36');

node(480,260,420,'ArUco 검출 · PnP 자세',['OpenCV DICT_4X4_50','카메라 내부값·왜곡 보정','작업대 자세 R, t 계산'],'CV',colors.teal);
node(1120,260,470,'A–D 카메라 좌표',['등록된 나사 3D 좌표 → 카메라 좌표','Xcamera = R · Xworld + t','영상 픽셀 위치도 함께 계산'],'XYZ',colors.cloud);
node(480,480,420,'YOLO 도구 검출',['driver.onnx / ONNX Runtime','640×384 입력 · 검출 후처리','driver · handle · screw'],'NN','#3469C1');
node(1120,480,470,'도구 근접 · 유효 증거',['도구 검출과 현재 나사 위치 비교','유효 자세·관측 신선도 확인','체결 토크를 측정하는 센서는 아님'],'EV',colors.cloud);
node(480,700,420,'C3.2 부분 가림 추적',['5개 이상 관측 → 모서리 지도 학습','3~4개: 비공선·지도 신선도 검사','다중 지도·마커 제외 결과 교차 검증'],'C3',colors.teal);
node(1120,700,470,'작업 상태 전이 · 안내',['상자 7초 → 뚜껑 6초 → A–D → 검사','주황 → 파랑 → 초록 표시 후 3초','준비 타이머는 유효 추적 시간만 누적'],'FSM',colors.phone);
node(480,920,420,'기존 보정·모델 자산',['카메라 / 작업대 205·205 / 눈별 투영','검증된 A–D 위치 보정 유지','SHA-256 기반 프로필·모델 확인'],'CAL',colors.cloud);
node(1120,920,470,'눈별 투영 · 안내 렌더',['좌·우 3×4 투영 / 깊이·화면 범위 검사','Android Presentation · 구·윤곽·문구','로컬 Three.js → 오른쪽 위 3D 부품'],'L/R',colors.web);
node(480,1140,420,'실시간 영상 인코딩',['MediaCodec 하드웨어 H.264','1280×720 · 목표 30fps · 2Mbps','카메라 영상만 / 음성·AR 합성 없음'],'AVC','#3469C1');
node(1120,1140,470,'인터넷 관제 전송',['OkHttp · 상태 / 영상 채널 분리','실행 중 상태 샘플 250ms','상태·영상 공유·서버 저장 동의 구분'],'NET',colors.teal);

node(1730,260,380,'인증 · 접속 제어',['nginx HTTPS / Node.js API','연결 코드 12시간 / 기기 인증 30일','웹 관제용 단기 티켓 30초'],'API',colors.cloud);
node(1730,480,380,'PostgreSQL',['기기·소유자·토큰 해시','작업 이벤트·녹화 메타데이터','외부 비공개 / 서버 내부 연결'],'DB',colors.cloud);
node(1730,700,380,'Node.js 실시간 중계',['/ws 상태 · /video AVC 패킷','기기 인증 / 관제 티켓 검사','허용된 관제자로 실시간 분배'],'WS',colors.cloud);
node(1730,920,380,'Recorder · MP4',['H.264 재인코딩 없이 remux','비공개 임시 파일 → 완료 처리','최대 10분 또는 300MB'],'REC',colors.phone);
node(1730,1140,380,'S3 비공개 저장소',['EC2 역할 권한 / AES256 암호화','계정 총 10GB · 7일 보관','만료 접근 차단·삭제 재시도'],'S3',colors.phone);

node(2230,260,280,'로그인 · API',['Next.js / NextAuth','GitHub OAuth','현재 본인 전용 운영'],'GH',colors.web);
node(2230,700,280,'실시간 관제',['WebCodecs → Canvas','단계·안내·추적 상태','최신 작업 표시 기록'],'WEB',colors.web);
node(2230,1140,280,'저장 영상',['본인 소유·만료 확인','최대 60초 서명 URL','S3 다운로드 / 삭제'],'MP4',colors.web);
text(2230,464,'웹 앱 제공·권한 API: Vercel',17,colors.muted);
text(2230,496,'실시간 영상: EC2 ↔ 브라우저',17,colors.muted);
text(2230,891,'웹 영상은 카메라 시점',18,colors.ink,600);
text(2230,920,'안경의 양안 오버레이와 별도',17,colors.muted);
text(1730,1370,'서버 역할: 인증·중계·녹화·저장',18,colors.cloud);

arrow([[60,1380],[110,1380]]);text(124,1386,'실시간 데이터 / 제어 흐름',17,colors.muted);
arrow([[60,1416],[110,1416]],true);text(124,1422,'보조 검증 / 권한 요청',17,colors.muted);
text(440,1410,'실행 경계',18,colors.ink,700);
text(555,1410,'AR 판단·양안 투영은 폰 내부에서 실행. 노트북은 관제용이며 같은 Wi-Fi일 필요가 없다.',19,colors.muted);
text(440,1445,'개발 기반',18,colors.ink,700);
text(555,1445,'Python·Unity는 기존 모델·보정·투영 검증 기반. 현재 Android 실행에는 필수가 아니다.',19,colors.muted);
text(440,1480,'검증 범위',18,colors.ink,700);
text(555,1480,'좌우 가림의 3마커 표시 확인 / 녹화 실측 평균 약 6.7fps. 목표 30fps와 실측 성능은 구분한다.',19,colors.muted);
svg.push('</g></svg>');
(async()=>{
 const base=path.join(__dirname,'AR-Assembly-Architecture-Exhibition');
 const source=svg.join('\n');fs.writeFileSync(base+'.svg',source);
 const png=await sharp(Buffer.from(source)).resize(W*2,H*2).png().toBuffer();fs.writeFileSync(base+'.png',png);
 await sharp(png).resize(1800).png().toFile(base+'-preview.png');
 const pdf=await PDFDocument.create();const img=await pdf.embedPng(png);const page=pdf.addPage([1300,765]);page.drawImage(img,{x:0,y:0,width:1300,height:765});fs.writeFileSync(base+'.pdf',await pdf.save());
 console.log(base);
})();
