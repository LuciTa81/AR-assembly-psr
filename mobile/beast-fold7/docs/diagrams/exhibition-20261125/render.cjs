const fs = require('node:fs');
const path = require('node:path');
const deps = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const sharp = require(path.join(deps, 'sharp'));
const { PDFDocument } = require(path.join(deps, 'pdf-lib'));
const out = __dirname;
const W = 2000, H = 1400;
const C = {ink:'#1E292D',muted:'#59696D',line:'#CCD6D8',bg:'#F7F9FA',teal:'#087E82',blue:'#2864B4',orange:'#B56A18',purple:'#75569C'};
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
let a=[];
function text(x,y,t,size=25,color=C.ink,weight=400){a.push(`<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}">${esc(t)}</text>`);}
function rect(x,y,w,h,fill='white',stroke=C.line,r=8){a.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`);}
function line(points,color=C.teal,dash=false){a.push(`<path d="${points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="3" ${dash?'stroke-dasharray="9 7"':''} marker-end="url(#${Object.keys(C).find(k=>C[k]===color)||'teal'})"/>`);}
function label(x,y,t,color=C.muted){text(x,y,t,21,color,500);}
function box(x,y,w,h,tag,title,body,color=C.teal){
  rect(x,y,w,h);a.push(`<path d="M${x+2},${y+8}V${y+h-8}" stroke="${color}" stroke-width="5"/>`);
  text(x+23,y+33,tag,18,color,700);text(x+23,y+77,title,29,C.ink,700);
  body.forEach((t,i)=>text(x+23,y+118+i*35,t,23,C.muted));
}
function band(y,title,body,color=C.teal){rect(60,y,1880,105,'#EEF3F4','none',0);text(84,y+36,title,23,color,700);text(84,y+75,body,23,C.ink);}
function start(n,title,sub){
  a=[`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs>${Object.entries(C).map(([k,v])=>`<marker id="${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="${v}"/></marker>`).join('')}</defs><g font-family="Malgun Gothic, sans-serif"><rect width="${W}" height="${H}" fill="${C.bg}"/>`];
  text(60,60,'AR ASSEMBLY / EXHIBITION SYSTEM',21,C.teal,700);text(60,124,title,48,C.ink,700);text(60,170,sub,25,C.muted);
  a.push(`<path d="M60 204H1940" stroke="${C.line}" stroke-width="2"/>`);
  text(60,1355,'2026.11.25  |  Fold7 C3.2 · AR relay 20261125-07 · 기존 A–D 보정 유지',20,C.muted);
  text(1770,1355,`${String(n).padStart(2,'0')} / 04`,23,C.teal,700);
}
const pages=[];
function finish(name){a.push('</g></svg>');pages.push({name,svg:a.join('\n')});}

start(1,'전체 시스템 구성','AR 판단은 휴대폰에서, 원격 관제와 기록은 인터넷 서버에서 처리한다.');
label(60,260,'현장 하드웨어',C.teal);label(510,260,'ON-DEVICE · Android 16',C.teal);label(1000,260,'CLOUD · AWS Seoul',C.blue);label(1500,260,'OBSERVER · 웹 브라우저',C.purple);
line([[410,395],[510,395]]);label(425,375,'UVC');
line([[510,565],[410,565]]);label(421,600,'SBS');
line([[920,395],[1000,395]],C.blue);label(927,371,'WSS',C.blue);
line([[1430,395],[1500,395]],C.blue);label(1438,371,'WSS',C.blue);
line([[1215,640],[1215,800]],C.orange);label(1233,726,'동의된 영상만 저장',C.orange);
line([[1715,800],[1715,640]],C.purple);label(1732,730,'로그인·티켓',C.purple);
line([[1430,925],[1470,925],[1470,1115],[1715,1115],[1715,1050]],C.orange);label(1490,1150,'S3 → 브라우저 직접 다운로드',C.orange);
box(60,300,350,340,'01 / CAPTURE + DISPLAY','VITURE Beast',[
 'USB 카메라 입력','1280 × 720','좌우 눈 디스플레이 출력','Full SBS 3840 × 1080','0DoF · Extra Large · 4.5m']);
box(510,300,410,340,'02 / LOCAL PROCESSING','Samsung Z Fold7',[
 'UVC 프레임 수신','OpenCV 마커·자세 추정','YOLO / ONNX 도구 검출','작업 상태 + 좌우 눈 투영','H.264 영상 인코딩']);
box(1000,300,430,340,'03 / AUTHENTICATED RELAY','EC2 중계 서버',[
 'nginx HTTPS / WSS 입구','Node.js / TypeScript 중계','상태·영상 채널 분리','PostgreSQL 기록·권한','MP4 녹화 및 S3 업로드'],C.blue);
box(1500,300,440,340,'04 / LIVE SUPERVISION','노트북·PC 관제',[
 '실시간 카메라 영상','현재 작업·안내·추적 상태','작업별 단계 전환 기록','저장 영상 다운로드','안경 AR 화면과는 별도'],C.purple);
box(60,800,860,250,'LOCAL / 네트워크와 분리된 AR 실행','노트북 없이 안경 + 휴대폰으로 안내',[
 '카메라 → 추적·도구 판단 → 양안 오버레이는 폰 내부에서 실행','노트북은 원격 관제 화면이며 AR 연산 서버가 아니다.','Python·Unity는 기존 개발/검증 기반이며 현재 실행에 필수 아님']);
box(1000,800,430,250,'PRIVATE STORAGE','Amazon S3',[
 '완료된 MP4 / 음성 없음','총 10GB · 한 건 300MB','최대 10분 · 7일 보관','소유자 확인 후 다운로드'],C.orange);
box(1500,800,440,250,'WEB HOSTING + LOGIN','Vercel / Next.js',[
 'GitHub OAuth / NextAuth','서버 측 중계 API(BFF)','본인 계정·기기 권한 확인','실시간 영상은 EC2와 직결'],C.purple);
band(1190,'운영 경계','인터넷 관제는 같은 Wi-Fi가 아니어도 가능 · 카메라/영상 공유/저장 동의는 구분 · 현재 본인 전용 운영');
finish('01-system-overview');

start(2,'휴대폰 내부 AR 처리','같은 카메라 프레임에서 위치 추정·도구 판단·영상 전송을 분리하고, 좌우 눈 화면을 각각 계산한다.');
const xs=[60,550,1040,1530], bw=410;
for(let i=0;i<3;i++)line([[xs[i]+bw,385],[xs[i+1],385]]);
line([[265,520],[265,665]]);label(285,598,'동일 프레임 분기');
line([[755,520],[755,665]]);label(775,598,'자세 / A–D 위치');
line([[1245,520],[1245,585],[1490,585],[1490,835],[1530,835]]);
line([[1735,520],[1735,665]]);
for(let i=0;i<3;i++)line([[xs[i]+bw,800],[xs[i+1],800]]);
box(xs[0],260,bw,260,'INPUT / MainActivity','카메라 프레임',[
 'USB UVC · MJPEG 수신','NV21 1280 × 720','회색조 / RGBA 변환','분석 시각·프레임 ID 유지']);
box(xs[1],260,bw,260,'TRACK / WorkspaceTracker','작업대 자세 추정',[
 'ArUco DICT_4X4_50','카메라 내부값·왜곡 보정','작업대 3D ↔ 화면 2D 대응','PnP 회전 R · 이동 t']);
box(xs[2],260,bw,260,'PROJECT / EyeProjection','눈별 표시 좌표',[
 'Xcamera = R · Xworld + t','좌·우 3×4 투영 행렬 적용','각 눈 1920 × 1080 좌표','양의 깊이·화면 경계 검사']);
box(xs[3],260,bw,260,'DISPLAY / Android Presentation','안경의 양안 출력',[
 '좌안 | 우안 Full SBS 배치','A–D 작은 구와 대상 색상','상자·뚜껑 윤곽 / 한글 안내','실물 위치와 겹치는 표시']);
box(xs[0],665,bw,270,'DETECT / YoloDetector','도구 검출',[
 'driver.onnx / ONNX Runtime','640 × 384 RGB letterbox','driver · handle · screw','검출 후처리 / 신뢰도 필터']);
box(xs[1],665,bw,270,'EVIDENCE / ToolEvidence','대상 나사 근접 판단',[
 '검출된 도구와 A–D 비교','현재 프레임·유효 자세 필요','오래되거나 불확실하면 차단','기계적 체결 토크 측정 아님']);
box(xs[2],665,bw,270,'STATE / Preparation + Assembly','작업 순서와 색상',[
 '상자 7초 → 뚜껑 6초','준비 시간은 유효 추적만 누적','나사: 주황 → 파랑 → 초록','초록 실제 표시 후 3초 전환']);
box(xs[3],665,bw,270,'HUD / PartPreviewView','화면 고정 3D 부품',[
 '로컬 WebView + Three.js','상자 → 뚜껑 → 나사 → 조립체','오른쪽 위 민트 선·둥근 테두리','실물 위치 추정 근거로 쓰지 않음']);
label(1530,977,'상태 변화가 3D 부품 선택에도 반영됨');
band(1030,'보정 자산 / 원본 유지','camera-profile.json · workspace-profile.json (205 / 205) · eye-projection.json · 모델/프로필 SHA-256 검증');
band(1160,'네트워크로 나가는 별도 분기','NV21 → MediaCodec H.264 → /video  |  작업 상태·진단 → /ws  |  웹 영상에는 안경 오버레이가 합성되지 않음',C.blue);
finish('02-phone-ar-pipeline');

start(3,'부분 가림 추적 · C3.2','보이는 마커 수만 낮추는 방식이 아니라, 5개 관측에서 만든 모서리 지도를 현재 3~4개 관측과 검증한다.');
for(let i=0;i<3;i++)line([[xs[i]+bw,380],[xs[i+1],380]]);
line([[1735,520],[1735,660]]);
line([[1530,805],[1450,805]],C.teal);
line([[1040,805],[960,805]],C.teal);
line([[550,805],[470,805]],C.teal);
box(60,260,bw,260,'01 / ANCHOR','5개 이상 관측 확보',[
 '기존 자세 추정이 유효할 때','500ms 이상 간격으로 표본','현재 실행 중에만 지도 학습','보정 파일에 다시 쓰지 않음']);
box(550,260,bw,260,'02 / CORNER MAP','마커 모서리 지도',[
 '4표본 / 8표본 두 창 사용','마커별 최소 4회 관측 필요','중앙값 모서리 지도 생성','짝수·홀수 표본 지도도 생성']);
box(1040,260,bw,260,'03 / OCCLUSION','3개 또는 4개 검출',[
 '관측된 마커의 모서리 활용','3개 중심은 비공선이어야 함','학습된 마커만 사용 가능','마커별 지도 신선도 30초']);
box(1530,260,bw,260,'04 / POSE CANDIDATES','부분 집합 자세 계산',[
 '각 지도에서 자세 다시 추정','재투영·기하 조건 검사','A–D 화면·공간 위치 비교','위치 일치 기준 3px / 3mm']);
box(1530,660,bw,270,'05 / SENSITIVITY','마커 하나씩 제외',[
 '각 마커를 뺀 결과도 비교','특정 마커에 과도한 의존 검사','지도 불일치·민감한 자세 거부','2개 이하만 보이면 표시 거부']);
box(1040,660,bw,270,'06 / VALIDITY GATE','표시 가능 여부 판단',[
 '3~4개는 learned_corners만','5개 이상은 기존 유효 경로','자세 나이 0~500ms 검사','깊이·투영 범위도 별도 검사']);
box(550,660,bw,270,'07 / SHARED POLICY','모든 안내에 동일 적용',[
 '상자·뚜껑 준비 타이머','4개 구 / 현재 대상 / 윤곽','드라이버 근접 증거 판단','관제 상태의 추적 판정']);
box(60,660,bw,270,'08 / RESULT','가림 중 안내 유지',[
 '실제 남은 마커로 계속 계산','조건이 나쁘면 오버레이 숨김','낡은 좌표를 무기한 고정 안 함','추적 회복 시 다시 표시']);
band(1030,'실제 착용 확인','오른쪽 위·아래 가림 / 왼쪽 위·아래 가림에서 3마커 표시와 위치 확인 · 전체 A–D 안내 확인');
band(1160,'검증 범위','같은 작업대·보정·착용 설정의 결과다. 모든 3마커 조합, 모든 조명, 무중단 표시나 절대 정밀도를 보장하지 않는다.',C.orange);
finish('03-partial-marker-tracking');

start(4,'인터넷 관제 · 권한 · 녹화 저장','상태 제어 경로와 영상 데이터 경로를 분리한다. Vercel은 로그인/API, EC2는 지속 연결과 녹화를 담당한다.');
label(60,247,'1 / 등록과 로그인',C.purple);
for(let i=0;i<3;i++)line([[xs[i]+bw,385],[xs[i+1],385]],C.purple);
box(60,270,bw,230,'PHONE → RELAY','휴대폰 연결 요청',[
 'HTTPS 연결 코드 / 12시간','웹에서 본인 기기 승인','30일 기기 인증값 암호화 저장'],C.purple);
box(550,270,bw,230,'BROWSER → VERCEL','GitHub 로그인',[
 'NextAuth 로그인 세션','현재 본인 계정만 허용','서버 API에 소유자 신원 전달'],C.purple);
box(1040,270,bw,230,'EC2 → POSTGRESQL','기기·권한 확인',[
 '기기 / 소유자 / 세션 연결','기기 인증값·티켓은 해시 보관','다른 사용자 기기 접근 차단'],C.purple);
box(1530,270,bw,230,'VERCEL API → BROWSER','관제 접속 티켓',[
 '기기별 30초 단기 티켓','상태와 영상 연결에 각각 사용','브라우저가 EC2 WSS에 연결'],C.purple);
label(60,563,'2 / 실시간 데이터',C.blue);
for(let i=0;i<3;i++)line([[xs[i]+bw,705],[xs[i+1],705]],C.blue);
box(60,590,bw,250,'FOLD7 / PUBLISHER','상태 + 카메라 영상',[
 '상태: 실행 중 250ms 샘플','영상: 하드웨어 H.264 인코딩','720p / 2Mbps / 목표 30fps','전송·저장 동의 별도 확인'],C.blue);
box(550,590,bw,250,'NGINX → NODE.JS','HTTPS / WSS 중계',[
 '/ws: 작업 단계·진단 상태','/video: AVC 패킷·시각·순번','인증·크기·혼잡·연결 검사','localhost:8787 내부 서비스'],C.blue);
box(1040,590,bw,250,'EC2 / FAN-OUT','관제 분배 + 기록 분기',[
 '상태 이벤트 → PostgreSQL','영상 패킷 → 인증된 관제자','녹화 동의 시 Recorder 분기','관제자끼리 기기 범위 분리'],C.blue);
box(1530,590,bw,250,'BROWSER / VIEWER','실시간 화면 재구성',[
 'JSON 상태 → 단계·기록 UI','AVC → WebCodecs → Canvas','누락 시 키프레임부터 복구','저장 장애와 AR 상태 구분'],C.blue);
label(60,907,'3 / 녹화와 보관',C.orange);
line([[1245,840],[1245,875],[265,875],[265,940]],C.orange);
for(let i=0;i<3;i++)line([[xs[i]+bw,1060],[xs[i+1],1060]],C.orange);
box(60,940,bw,240,'RECORDER / PRIVATE SPOOL','MP4 파일 마무리',[
 '계정 잔여량 예약 후 시작','AVC → MP4 remux / 무음','10분 또는 300MB까지','재연결 구간도 총 예산 공유'],C.orange);
box(550,940,bw,240,'AWS S3 / PRIVATE','객체 저장',[
 'EC2 역할의 S3 권한 사용','SSE-S3 AES256 암호화','소유자 / 기기 / 파일 키 분리','완료 파일만 다운로드 허용'],C.orange);
box(1040,940,bw,240,'BROWSER → API → S3','다운로드',[
 '로그인·소유자·만료 재검사','최대 60초 서명 URL 발급','브라우저가 S3에서 직접 수신','본인 계정 총 보관량 10GB'],C.orange);
box(1530,940,bw,240,'SERVER / RETENTION','7일 보관 후 삭제',[
 '서버가 매분 만료 대상 확인','만료 시 다운로드 권한 차단','S3 삭제 성공 후 용량 반환','실패한 삭제는 후속 재시도'],C.orange);
text(60,1255,'실측: 121.44초 / 30.4MB / 819프레임 / 평균 6.7fps  ·  전체 디코딩 통과  ·  음성 및 안경 오버레이 합성 없음',24,C.muted);
finish('04-cloud-recording-security');

(async()=>{
  const pdf=await PDFDocument.create();
  for(const p of pages){
    fs.writeFileSync(path.join(out,p.name+'.svg'),p.svg);
    const png=await sharp(Buffer.from(p.svg)).png().toBuffer();
    fs.writeFileSync(path.join(out,p.name+'.png'),png);
    const img=await pdf.embedPng(png);const page=pdf.addPage([1000,700]);page.drawImage(img,{x:0,y:0,width:1000,height:700});
  }
  fs.writeFileSync(path.join(out,'AR-Assembly-Pipeline-20261125.pdf'),await pdf.save());
  console.log('Rendered '+pages.length+' SVG/PNG pages and PDF.');
})();
