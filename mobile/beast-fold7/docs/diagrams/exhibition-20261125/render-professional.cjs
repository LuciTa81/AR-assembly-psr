const fs=require('node:fs');
const path=require('node:path');
const deps='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const sharp=require(path.join(deps,'sharp'));
const {PDFDocument}=require(path.join(deps,'pdf-lib'));
const lucide=require(path.join(deps,'lucide')).icons;
let W=3200,H=1800;
const C={ink:'#243247',muted:'#748399',edge:'#8B98A9',border:'#C8D4E3',phone:'#E98134',cloud:'#587797',teal:'#068F97',purple:'#8260A2'};
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
let parts,boxes,edges,texts;
const pages=[];
function text(x,y,s,size=22,color=C.ink,weight=400){parts.push(`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" font-weight="${weight}">${esc(s)}</text>`);texts.push({x,y,s,size});}
function rect(x,y,w,h,stroke=C.border,fill='white',r=12,dash=false,shadow=false){parts.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" stroke="${stroke}" fill="${fill}" stroke-width="1.6" ${dash?'stroke-dasharray="8 7"':''} ${shadow?'filter="url(#shadow)"':''}/>`);}
function icon(name,x,y,size=58,color=C.cloud){
 let file=path.join(__dirname,'icons',name+'.svg');
 if(!fs.existsSync(file))file=path.join(__dirname,'icons',name+'.png');
 if(fs.existsSync(file)){
  let b=fs.readFileSync(file);const mime=file.endsWith('svg')?'image/svg+xml':'image/png';
  if(name==='mediapipe'||name==='onnx'||name==='ultralytics')b=Buffer.from(b.toString().replace('<svg ',`<svg fill="${name==='ultralytics'?'#245BCD':C.teal}" `));
  parts.push(`<image x="${x}" y="${y}" width="${size}" height="${size}" href="data:${mime};base64,${b.toString('base64')}"/>`);
 }else{
  const nodes=lucide[name];if(!nodes)throw Error('Missing icon '+name);
  parts.push(`<g transform="translate(${x},${y}) scale(${size/24})" fill="none" stroke="${color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${nodes.map(([tag,attr])=>`<${tag} ${Object.entries(attr).map(([k,v])=>`${k}="${esc(v)}"`).join(' ')}/>`).join('')}</g>`);
 }
}
function box(id,x,y,w,title,body,ico,opts={}){
 parts.push(`<g data-node="${id}">`);
 const h=opts.h||220;rect(x,y,w,h,opts.stroke||C.border,opts.fill||'white',12,opts.dash,false);boxes.push({id,x,y,w,h});
 icon(ico,x+26,y+35,58,opts.color||C.cloud);
 text(x+112,y+50,title,28,C.ink,600);
 body.forEach((s,i)=>text(x+112,y+88+i*31,s,22,C.muted));
 if(opts.extraIcons)opts.extraIcons.forEach((n,i)=>icon(n,x+w-42-i*39,y+h-33,24));
 parts.push('</g>');
}
function flow(id,points,caption=null,at=null,dash=false){
 edges.push({id,points});
 parts.push(`<path d="${points.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ')}" fill="none" stroke="${C.edge}" stroke-width="2.4" ${dash?'stroke-dasharray="7 6"':''} marker-end="url(#arrow)"/>`);
 if(caption&&at){text(at[0],at[1],caption,19,C.muted);}
}
function group(x,y,w,h,title,color,ico){rect(x,y,w,h,color,'none',16);if(ico)icon(ico,x+22,y+17,32,color);text(x+(ico?70:24),y+42,title,23,color,500);}
function header(title,sub,num,total=2){
 parts=[`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="${C.edge}"/></marker><filter id="shadow" x="-5%" y="-10%" width="110%" height="120%"><feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#283A51" flood-opacity="0.06"/></filter></defs><rect width="${W}" height="${H}" fill="white"/><g font-family="Malgun Gothic, sans-serif">`];boxes=[];edges=[];texts=[];
 text(60,90,title,43,C.ink,700);text(60,137,sub,23,C.muted);
 text(W-440,89,'EXHIBITION ARCHITECTURE',19,C.muted,600);text(W-218,134,`0${num} / 0${total}`,23,C.muted);
}
function finish(name){parts.push('</g></svg>');pages.push({name,svg:parts.join('\n'),boxes,edges,texts,w:W,h:H});}

header('AR 조립 안내 시스템 아키텍처','VITURE Beast · Samsung Z Fold7 · OpenCV / YOLO · 양안 AR 안내 · 인터넷 관제 및 영상 기록',1);
group(460,240,1740,1125,'휴대폰 앱  ·  Android 16 / Java  ·  실시간 인식·판단·렌더링',C.phone,'android');
text(60,275,'현장 입력',21,C.cloud,600);text(2300,275,'출력 및 원격 관제',21,C.cloud,600);
// Three separate lanes keep all cross-module connections outside node bounds.
flow('bench-camera',[[225,710],[225,560]],'작업대 촬영',[245,637]);
flow('camera-tracker',[[390,450],[500,450]],'UVC',[421,429]);
flow('camera-yolo',[[425,450],[425,820],[500,820]],'RGB',[444,795]);
flow('camera-encoder',[[410,450],[410,1190],[500,1190]],'NV21',[430,1165]);
flow('track-points',[[960,450],[1090,450]],'R · t',[1005,427]);
flow('points-eye',[[1550,450],[1680,450]],'3D 좌표',[1574,427]);
flow('eye-display',[[2140,450],[2300,450]],'Full SBS',[2165,427]);
flow('yolo-evidence',[[960,820],[1090,820]],'검출 상자',[983,796]);
flow('points-evidence',[[1320,560],[1320,710]],'대상 나사 위치',[1341,642]);
flow('evidence-state',[[1550,820],[1680,820]],'근접 증거',[1574,796]);
flow('state-render',[[1910,710],[1910,560]],'대상 · 색상 · 문구',[1932,641]);
flow('encoder-transport',[[960,1190],[1090,1190]],'H.264',[992,1167]);
flow('state-transport',[[1910,930],[1910,1080]],'작업 상태 · 진단',[1932,1012]);
flow('phone-relay',[[2140,1190],[2300,1190]],'WSS',[2190,1167]);
flow('relay-web',[[2720,1080],[2720,930]],'상태 JSON · H.264',[2742,1011]);
box('camera',60,340,330,'Beast 카메라',['작업대 영상 입력','USB-C / UVC','1280×720'],'Camera');
box('workspace',60,710,330,'작업대',['ArUco 마커','상자 · 뚜껑 · A–D','드라이버'],'ScanLine');
box('tracking',500,340,460,'ArUco 검출 · PnP',['OpenCV · 카메라 왜곡 보정','C3.2 모서리 기반 부분 추적','5개 이상 학습 → 3~4개 검증','회전 R · 이동 t 산출'],'opencv');
box('coordinates',1090,340,460,'A–D 카메라 좌표',['등록된 나사 3D 좌표 변환','Xcamera = R · Xworld + t','화면 픽셀 위치 계산','기존 205 / 205 배치 유지'],'Axis3d');
box('projection',1680,340,460,'눈별 투영 · 안내 렌더',['좌·우 3×4 투영 행렬 적용','Android Presentation 출력','구·윤곽·한글 / 3D 부품 HUD','깊이 · 신선도 · 화면 범위 검사'],'Glasses',{extraIcons:['threejs','android']});
box('display',2300,340,840,'VITURE Beast · 양안 AR 표시',['좌안 1920×1080 + 우안 1920×1080 → Full SBS 3840×1080','실제 나사 위치의 구 · 상자/뚜껑 윤곽 · 현재 작업 안내','오른쪽 위: 화면 고정 3D 부품 / 로컬 Three.js','0DoF · Extra Large · 4.5m / 검증된 착용·배치 유지'],'Glasses',{stroke:'#52657E',color:'#26364A'});
box('detector',500,710,460,'YOLO 도구 검출',['driver.onnx · ONNX Runtime','640×384 letterbox 입력','driver · handle · screw','검출 후처리 및 신뢰도 필터'],'ultralytics',{extraIcons:['onnx']});
box('evidence',1090,710,460,'도구 근접 · 관측 증거',['도구와 현재 나사 위치 비교','유효 자세 · 최신 관측 확인','접근 · 유지 · 이탈 상태 판단','체결 토크를 직접 측정하지 않음'],'Ruler');
box('state',1680,710,460,'작업 단계 · 상태 전이',['상자 7초 → 뚜껑 6초 → A–D','주황 → 파랑 → 초록 안내','초록 실제 표시 후 3초 전환','마지막 단계: 조립 상태 확인'],'Workflow');
box('web',2300,710,840,'웹 관제 · Next.js / Vercel',['GitHub 로그인 → 본인 폰 연결 → 실시간 상태·영상 확인','WebCodecs로 영상 디코딩 / 단계·추적 상태·작업 기록 표시','카메라 영상과 안경 양안 오버레이는 서로 다른 출력','저장 영상: 본인 권한 확인 후 다운로드 / 삭제'],'chrome',{extraIcons:['github','nextjs','vercel']});
box('encoder',500,1080,460,'카메라 영상 인코딩',['MediaCodec · H.264 / AVC','1280×720 · 목표 30fps','목표 비트레이트 2Mbps','음성·안경 오버레이 합성 없음'],'Film');
box('transport',1090,1080,1050,'인터넷 관제 클라이언트 · OkHttp',['상태 채널 /ws 와 영상 채널 /video 를 분리하여 전송','상태·영상 공유·서버 저장 동의 및 기기 인증값 확인','실행 중 상태 샘플 250ms / AVC 패킷·시각·순번 전달','AR 연산은 폰 내부에서 유지하며, 인터넷 연결은 원격 관제에 사용'],'Radio');
box('cloud',2300,1080,840,'AWS EC2 · 인증 / 실시간 중계 / 영상 저장',['nginx HTTPS/WSS → Node.js 중계 → 인증된 관제 브라우저','PostgreSQL: 기기·권한·작업 이벤트·녹화 메타데이터','녹화 동의 시 MP4 remux → S3 비공개 저장소','한 건 최대 10분·300MB / 계정 총 10GB / 7일 보관'],'ec2',{extraIcons:['s3','postgresql','nodejs','nginx']});

text(60,1443,'개발 기반 · 확장 설계',25,C.ink,600);
text(390,1443,'현재 폰 실행 경로와 구분한 구성 요소',21,C.muted);
box('python',60,1490,720,'Python · 기존 개발 기반',['데스크톱 인식·실험·모델 및 보정 도구','현재 폰 실행에서는 Python 서버 불필요'],'python',{h:170,fill:'#FCFDFE'});
box('unity',850,1490,720,'Unity · 기존 양안 렌더 기반',['C# 투영·SBS 검증 → Android 눈별 투영으로 이전','현재 폰 실행에서는 Unity 앱 불필요'],'unity',{h:170,fill:'#FCFDFE'});
box('mediapipe',1640,1490,720,'MediaPipe · 확장 설계',['손 관절·손끝 위치 → 동작 특징 추출','현재 Android 앱 미적용'],'mediapipe',{h:170,dash:true,fill:'#FCFBFE',stroke:'#B5A5C6'});
box('hmm',2430,1490,710,'HMM · Viterbi · 확장 설계',['손·도구·ROI 증거 → 시간적 단계 추정','현재 Android 앱 미적용'],'Network',{h:170,dash:true,fill:'#FCFBFE',stroke:'#B5A5C6',color:C.purple});
text(60,1740,'실선: 현재 데이터 흐름     주황 경계: 폰 실행 범위     하단 점선 박스: 미적용 확장 설계',20,C.muted);
text(1800,1740,'검증: 좌우 가림의 3마커 표시 확인 / 녹화 실측 약 6.7fps / 2026.11.25',20,C.muted);
finish('01-AR-Assembly-Architecture');

header('인터넷 관제 · 인증 · 녹화 파이프라인','상태·영상 전송과 파일 보관을 분리하고, 소유자 확인 후에만 실시간 관제 및 다운로드를 허용한다.',2);
const xs=[60,860,1660,2460], widths=[620,620,620,680];
text(60,242,'01  로그인 · 기기 연결',25,C.purple,600);
text(2460,242,'오른쪽에서 왼쪽으로 인증',20,C.muted);
flow('login-next',[[2460,420],[2280,420]],'OAuth',[2325,395]);
flow('next-api',[[1660,420],[1480,420]],'신원 확인',[1525,395]);
flow('api-phone',[[860,420],[680,420]],'연결 승인',[725,395]);
flow('device-publish',[[370,530],[370,730]],'기기 인증값',[391,643]);
flow('api-relay',[[1170,530],[1170,730]],'권한 · 티켓 검증',[1191,643]);
flow('next-browser',[[1970,530],[1970,730]],'관제용 단기 티켓',[1991,643]);
box('pairing',xs[0],310,widths[0],'휴대폰 · 기기 연결',['12시간 연결 코드로 본인 기기 승인','30일 기기 인증값을 암호화 저장','이후 상태·영상 전송 때 기기 인증'],'Smartphone');
box('api',xs[1],310,widths[1],'EC2 API · PostgreSQL',['연결 코드 · 소유자 · 기기 관계 검증','인증값·티켓은 서버에 해시로 보관','계정별 기기·영상 접근 권한 검사'],'postgresql',{extraIcons:['ec2']});
box('nextauth',xs[2],310,widths[2],'Vercel · Next.js / NextAuth',['GitHub 로그인 세션 확인','서버 API에 사용자 신원 전달','기기별 관제 티켓 요청 / 유효 30초'],'nextjs',{extraIcons:['vercel']});
box('login',xs[3],310,widths[3],'브라우저 · GitHub 로그인',['관제 페이지에서 GitHub OAuth 인증','현재 운영은 본인 계정으로 제한','Vercel은 웹 앱과 인증 API를 제공'],'github',{extraIcons:['chrome']});

text(60,695,'02  실시간 상태 · 영상 관제',25,C.teal,600);
flow('publish-relay',[[680,840],[860,840]],'HTTPS / WSS',[694,815]);
flow('relay-decode',[[1480,840],[1660,840]],'AVC · JSON',[1509,815]);
flow('decode-ui',[[2280,840],[2460,840]],'영상 · 상태',[2320,815]);
box('publish',xs[0],730,widths[0],'Fold7 · 영상 / 상태 발행',['카메라 → MediaCodec H.264 패킷','현재 작업·안내·추적 상태 JSON','상태·영상 공유·저장 동의 분리'],'android');
box('relay',xs[1],730,widths[1],'EC2 · nginx / Node.js',['443 TLS → 내부 Node.js :8787','/ws: 상태 · /video: H.264 패킷','기기 인증 및 관제자 티켓 검사'],'nodejs',{extraIcons:['nginx']});
box('decoder',xs[2],730,widths[2],'브라우저 · 영상 복원',['H.264 → WebCodecs → Canvas','누락 시 키프레임부터 복구','밀린 영상 처리량을 제한하여 지연 억제'],'chrome');
box('dashboard',xs[3],730,widths[3],'관제 대시보드',['실시간 영상·현재 작업·추적 상태','현재 작업의 표시 기록 / 작업 기록','영상 표시를 꺼도 레이아웃은 유지'],'Monitor');

text(60,1135,'03  MP4 녹화 · 저장 · 다운로드',25,C.phone,600);
flow('relay-recorder',[[1170,950],[1170,1035],[600,1035],[600,1190]],'서버 저장 동의 시 별도 분기',[680,1020]);
flow('recorder-s3',[[680,1300],[860,1300]],'완료 MP4',[718,1275]);
flow('s3-download',[[1480,1300],[1660,1300]],'직접 다운로드',[1490,1275]);
flow('retention-s3',[[2800,1410],[2800,1510],[1170,1510],[1170,1410]],'만료 객체 삭제 · 실패 시 재시도',[1880,1492]);
box('recorder',xs[0],1190,widths[0],'Recorder · MP4 remux',['계정 잔여 용량 예약 후 녹화 시작','비공개 임시 파일에 H.264 패킷 기록','최대 10분 또는 300MB / 음성 없음'],'Clapperboard');
box('s3',xs[1],1190,widths[1],'Amazon S3 · 비공개 저장',['EC2 역할의 최소 권한으로 업로드','SSE-S3 AES256 암호화','소유자·기기·파일별 저장 키 분리'],'s3');
box('download',xs[2],1190,widths[2],'저장 영상 · 다운로드',['API에서 로그인·소유자·만료 재검사','최대 60초 유효한 서명 URL 발급','브라우저가 S3에서 직접 파일 수신'],'Download');
box('retention',xs[3],1190,widths[3],'7일 보관 · 자동 삭제',['계정 총 보관량 10GB / 동시 녹화 1건','서버가 매분 만료 대상을 확인','만료 접근 차단 → 삭제 성공 후 용량 반환'],'CalendarClock');
rect(60,1605,3080,105,'#DEE5ED','#F8FAFC',8);
text(90,1647,'네트워크 경계',23,C.ink,600);text(320,1647,'공개: HTTPS / WSS 443  ·  내부: Node.js 8787 / PostgreSQL 5432  ·  S3 객체는 공개하지 않음',23,C.muted);
text(90,1683,'출력 구분',23,C.ink,600);text(320,1683,'웹 영상은 카메라 시점이며 안경 양안 오버레이를 합성하지 않는다. 인터넷 관제와 폰 내부 AR 처리는 분리된다.',23,C.muted);
text(60,1760,'AR Assembly · 현재 운영 구조 / 2026.11.25',20,C.muted);
finish('02-Cloud-Recording-Pipeline');

const renderDetail=process.argv.includes('--render-detail');
W=4800;H=renderDetail?3600:2700;
const design=process.argv.includes('--design')||renderDetail;
header(design?'AR 조립 안내 시스템 · 통합 설계 구성도':'AR 조립 안내 시스템 · 통합 파이프라인',design?'현장 입력 → 시각 인식·손 특징·시간적 단계 추정 → 양안 AR → 인터넷 관제·녹화·다운로드':'현장 입력 → 휴대폰 내부 인식·판단·양안 투영 → 인터넷 중계 → 웹 관제·녹화·다운로드까지의 전체 구성',1,1);
group(500,250,1850,1740,'01  Samsung Z Fold7 · Android 16 / Java · 온디바이스 AR 처리',C.phone,'android');
group(2430,650,1250,1340,'02  AWS · EC2 / PostgreSQL / S3',C.cloud,'aws');
group(3760,250,980,1740,'03  웹 관제 · Vercel / Next.js / 브라우저',C.purple,'vercel');
text(60,291,'현장 입력',25,C.ink,600);
text(2480,291,'안경 출력 · 실제 작업자 시야',25,C.ink,600);

flow('i-work-camera',[[240,750],[240,590]],'작업대 촬영',[260,675]);
flow('i-camera-track',[[420,480],[550,480]],'UVC',[461,456]);
flow('i-camera-yolo',[[460,480],[460,860],[550,860]],'RGB',[491,836]);
flow('i-camera-encoder',[[440,480],[440,design?1620:1240],[550,design?1620:1240]],'NV21',[484,design?1596:1216]);
if(design)flow('i-camera-hand',[[450,480],[450,1240],[550,1240]],'RGB',[491,1216]);
flow('i-track-point',[[1040,480],[1170,480]],'R · t',[1080,456]);
flow('i-point-eye',[[1660,480],[1790,480]],'XYZ',[1708,456]);
flow('i-eye-beast',[[2280,480],[2480,480]],'Full SBS',[2345,456]);
flow('i-point-evidence',[[1415,590],[1415,750]],'대상 나사 위치',[1438,675]);
flow('i-yolo-evidence',[[1040,860],[1170,860]],'검출 상자',[1060,836]);
flow('i-evidence-state',[[1660,860],[1790,860]],'근접 증거',[1683,836]);
flow('i-state-eye',[[2035,750],[2035,590]],'대상 · 색상 · 문구',[2056,675]);
flow('i-state-remote',[[2035,970],[2035,design?1510:1130]],'상태 · 진단',[2056,1056]);
flow('i-encoder-remote',[[1040,design?1620:1240],[1170,design?1620:1240]],'H.264',[1068,design?1596:1216]);
flow('i-phone-nginx',[[2280,design?1620:1240],[2390,design?1620:1240],[2390,860],[2480,860]],'WSS',[2297,design?1596:1216]);
flow('i-nginx-node',[[2980,860],[3130,860]],'내부 전달',[3011,836]);
flow('i-node-live',[[3630,860],[3720,860],[3720,1240],[3810,1240]],'AVC / JSON',[3680,1286]);
flow('i-github-vercel',[[4250,590],[4250,750]],'OAuth 세션',[4273,675]);
flow('i-vercel-nginx',[[3810,790],[3700,790],[3700,720],[2730,720],[2730,750]],'인증 API · 티켓 요청',[3240,707]);
flow('i-node-db',[[3130,930],[3060,930],[3060,1240],[2980,1240]],'조회·기록',[2993,1286]);
flow('i-node-record',[[3380,970],[3380,1130]],'저장 동의 시',[3403,1056]);
flow('i-vercel-live',[[4250,970],[4250,1130]],'단기 관제 티켓',[4273,1056]);
flow('i-vercel-download',[[4690,850],[4715,850],[4715,1620],[4690,1620]]);
flow('i-record-s3',[[3380,1350],[3380,1510]],'완료 MP4 업로드',[3403,1435]);
flow('i-db-cleanup',[[2730,1350],[2730,1510]],'만료 대상 조회',[2753,1435]);
flow('i-cleanup-s3',[[2980,1620],[3130,1620]],'객체 삭제',[3010,1596]);
flow('i-s3-download',[[3630,1620],[3810,1620]],'직접 수신',[3670,1596]);
if(design){
 flow('i-hand-hmm',[[1040,1240],[1170,1240]],'손 특징',[1067,1216]);
 flow('i-evidence-hmm',[[1415,970],[1415,1130]],'도구 · ROI 증거',[1438,1056]);
 flow('i-hmm-state',[[1660,1240],[1710,1240],[1710,1000],[1850,1000],[1850,970]],'추정 단계',[1730,1093]);
}else flow('i-map-verify',[[1660,1620],[1790,1620]],'교차 검증',[1682,1596]);

box('i-camera',60,370,360,'Beast 카메라',['USB-C / UVC 입력','1280×720 카메라 영상','카메라·디스플레이 직결'],renderDetail?'viture':'Camera');
box('i-workspace',60,750,360,'고정 작업대',['ArUco 마커','상자 · 뚜껑 · A–D 나사','드라이버 · 고정 배치'],'ScanLine');
box('i-tracking',550,370,490,'ArUco 검출 · PnP',['OpenCV DICT_4X4_50','카메라 내부값·왜곡 보정','C3.2 부분 가림 추적 적용','회전 R · 이동 t 추정'],'opencv');
box('i-points',1170,370,490,'A–D 카메라 좌표',['등록된 나사 3D 위치 → 카메라 좌표','Xcamera = R · Xworld + t','A–D 영상 픽셀 위치도 계산','기존 보정·작업대 좌표 유지'],'Axis3d');
box('i-project',1790,370,490,renderDetail?'양안 렌더링 · R1–R6':'눈별 투영 · 안내 렌더',renderDetail?['입력·좌우 투영 → 표시 조건 검사','눈별 Canvas → 3D HUD 레이어 합성','Presentation → Full SBS 출력','아래 R1–R6 상세 파이프라인 참조']:['좌·우 3×4 투영 행렬 적용','Android Presentation · Full SBS','구·윤곽·한글 / Three.js 3D HUD','깊이·신선도·화면 범위 검사'],renderDetail?'android':'Glasses',{extraIcons:['threejs','android']});
box('i-beast',2480,370,1150,'VITURE Beast · 양안 AR 표시',['좌안 1920×1080 + 우안 1920×1080 → Full SBS 3840×1080','실제 나사 위치의 표시 / 상자·뚜껑 윤곽 / 현재 단계의 한글 안내','오른쪽 위 고정 3D 부품: 상자 → 뚜껑 → 나사 → 조립체','0DoF · Extra Large · 4.5m / 기존 착용 위치·작업대 유지'],renderDetail?'viture':'Glasses',{stroke:'#536780',color:'#23374F'});
box('i-github',3810,370,880,'GitHub 로그인 · 사용자 세션',['관제 페이지에서 GitHub OAuth 로그인','현재 운영은 본인 계정으로 제한','NextAuth 세션을 통해 사용자 신원 확인','다른 사용자 기기·영상에 대한 접근은 차단'],'github',{extraIcons:['chrome']});
box('i-yolo',550,750,490,'YOLO 도구 검출',['driver.onnx · ONNX Runtime','640×384 letterbox 입력','driver · handle · screw','검출 후처리 / 신뢰도 필터'],'ultralytics',{extraIcons:[renderDetail?'onnxruntime':'onnx']});
box('i-evidence',1170,750,490,'도구 근접 · 관측 증거',['도구와 현재 나사 위치 비교','유효 자세 · 최신 프레임 확인','접근 · 유지 · 이탈 증거 판단','기계적 체결 토크의 직접 측정 아님'],'Ruler');
box('i-state',1790,750,490,'작업 단계 · 상태 전이',['상자 7초 → 뚜껑 6초 → A–D','준비 시간은 유효 추적만 누적','주황 → 파랑 → 초록 후 3초 전환','마지막 단계: 조립 상태 확인'],'Workflow');
box('i-nginx',2480,750,500,'nginx · HTTPS / WSS',['443 TLS 외부 접속','인증 API · 상태 · 영상 입구','내부 Node.js :8787로 전달','DB·내부 서비스 포트 비공개'],'nginx');
box('i-relay',3130,750,500,'Node.js · API / WSS',['/ws: 상태 · /video: AVC 패킷','기기 인증값·관제 티켓 검사','허용된 관제자에게 데이터 분배','녹화 동의 시 Recorder 분기'],'nodejs');
box('i-vercel',3810,750,880,'Vercel · Next.js / NextAuth',['웹 앱 제공 / 서버 측 중계 API(BFF)','로그인 사용자 신원으로 EC2 API 호출','기기별 30초 관제 티켓 요청 후 브라우저에 전달','영상 데이터는 Vercel을 경유하지 않고 EC2와 직접 연결'],'nextjs',{extraIcons:['vercel']});
box('i-encoder',550,design?1510:1130,490,'카메라 영상 인코딩',['MediaCodec · 하드웨어 H.264','1280×720 · 목표 30fps','목표 비트레이트 2Mbps','음성·안경 오버레이 합성 없음'],'Film');
box('i-remote',1170,design?1510:1130,1110,'인터넷 관제 클라이언트 · OkHttp',['상태 채널 /ws 와 영상 채널 /video 를 분리하여 전송','상태·영상 공유·서버 저장 동의 / 기기 인증값 확인','실행 중 상태 샘플 250ms / 영상 패킷·시각·순번 전달','12시간 연결 코드로 본인 폰 승인 → 30일 기기 인증값 암호화 저장'],'Radio');
box('i-db',2480,1130,500,'PostgreSQL · 기기 / 권한',['소유자·기기·연결 코드·세션','인증값·접속 티켓 해시 보관','작업 이벤트·녹화 메타데이터','localhost:5432 / 외부 비공개'],'postgresql');
box('i-recorder',3130,1130,500,'Recorder · MP4 remux',['계정 잔여 용량 예약 후 시작','H.264 → MP4 / 재인코딩 없음','비공개 임시 파일 → 완료 처리','한 건 최대 10분 또는 300MB'],'Clapperboard');
box('i-live',3810,1130,880,'브라우저 · 실시간 관제',['AVC → WebCodecs → Canvas / 상태 JSON → 작업·진단 UI','누락 시 키프레임부터 복구 / 밀린 프레임 처리량 제한','현재 작업·안내·추적 상태 / 현재 작업의 표시 기록','카메라 시점 영상이며 안경 양안 오버레이와는 별도'],'chrome');
if(design){
box('i-mediapipe-main',550,1130,490,'MediaPipe · 손 랜드마크',['손 관절 · 손끝 위치 추출','손 움직임의 시계열 특징','도구 접근·조작 동작의 특징화','손 특징 → 단계 추정 모듈'],'mediapipe');
box('i-hmm-main',1170,1130,490,'HMM · Viterbi 단계 추정',['손 · 도구 · ROI 관측 특징 결합','관측 점수 · 상태 전이 확률','Viterbi 기반 최적 단계열 추정','추정 단계 → 작업 상태 전이'],'Network',{color:C.purple});
}else{
text(550,1450,'보정 자산 · 추적 내부 처리 상세',22,C.phone,600);
box('i-profile',550,1510,490,'기존 보정 · 모델 자산',['카메라 내부값·왜곡 프로필','작업대 배치 205 / 205 유지','검증된 A–D 눈별 투영 유지','프로필·모델 SHA-256 확인'],'FileCheck');
box('i-map',1170,1510,490,'C3.2 · 모서리 지도 학습',['5개 이상 유효 관측에서 학습','4표본·8표본 창 / 마커별 4회','중앙값·짝수·홀수 지도 생성','실행 중 메모리 / 보정 파일 불변'],'Scan');
box('i-check',1790,1510,490,'C3.2 · 3~4마커 검증',['비공선 조건 / 지도 신선도 30초','지도 간 A–D 위치 3px·3mm 비교','마커 하나씩 제외한 민감도 검사','자세 500ms 이내 / 실패 시 숨김'],'ShieldCheck');
}
box('i-retention',2480,1510,500,'보관 정책 · 자동 삭제',['계정 총 10GB / 동시 녹화 1건','7일 보관 · 매분 만료 대상 확인','만료 시 다운로드 접근 차단','삭제 성공 후 용량 반환·실패 재시도'],'CalendarClock');
box('i-s3',3130,1510,500,'Amazon S3 · 비공개',['EC2 역할의 S3 접근 권한','SSE-S3 AES256 암호화','소유자·기기·파일별 키 분리','완료된 MP4 객체만 제공'],'s3');
box('i-download',3810,1510,880,'저장 영상 · 다운로드 / 삭제',['동일 로그인 세션으로 API에 소유자·만료 상태 재확인','최대 60초 유효한 S3 서명 URL 발급','브라우저가 S3에서 직접 파일 다운로드','저장 영상과 작업 기록은 별도 메뉴 / 본인 영상 삭제 가능'],'Download');
text(550,1838,'로컬 실행 경계',24,C.ink,600);text(550,1884,'카메라 → 인식·판단 → 양안 AR은 폰 내부 실행. 인터넷 관제와 별도로 동작한다.',24,C.muted);
text(2480,1838,'인프라 역할',24,C.ink,600);text(2480,1884,'EC2: 인증·중계·녹화 / DB: 권한·기록 / S3: 파일 보관',23,C.muted);
text(3810,1838,'관제 접속',24,C.ink,600);text(3810,1884,'같은 Wi-Fi 불필요 / 인터넷 연결·인증 필요',23,C.muted);

if(renderDetail){
 group(500,2070,4240,840,'R  양안 렌더링 상세  ·  상단 R1–R6 모듈의 내부 처리  ·  현재 Android 코드 기준',C.phone,'android');
 const rx=[550,1250,1950,2650,3350,4050];
 for(let i=0;i<5;i++)flow('r-step-'+i,[[rx[i]+600,2330],[rx[i+1],2330]]);
 flow('r-stage-canvas',[[2950,2600],[2950,2450]],'색상·문구',[2973,2526]);
 flow('r-stage-hud',[[3250,2710],[3350,2710]],'부품 ID',[3270,2685]);
 flow('r-hud-composition',[[3650,2600],[3650,2450]],'투명 WebView 레이어',[3673,2526]);
 box('r-input',550,2210,600,'R1 · 입력·프로필 확인',['카메라 좌표 XYZ / A–D·윤곽 형상','eye-projection.json의 좌·우 3×4 행렬','카메라·작업대 프로필 ID·SHA-256','기존 눈별 보정값을 읽기 전용으로 사용'],'FileCheck',{h:240});
 box('r-projection',1250,2210,600,'R2 · 좌·우 픽셀 투영',['각 눈에서 q = Meye · [X Y Z 1]','u = qx / qz,  v = qy / qz','좌안·우안의 좌표를 각각 계산','각 눈 기준 좌상단 원점 / 1920×1080'],'Axis3d',{h:240});
 box('r-validity',1950,2210,600,'R3 · 표시 조건 검사',['유한 수치 / 양의 깊이·분모 확인','0 ≤ u < 1920, 0 ≤ v < 1080','추적 결과·프레임 신선도 500ms 검사','조건 미달: 위치 표시 숨김 / 재관측 안내'],'ShieldCheck',{h:240});
 box('r-canvas',2650,2210,600,'R4 · 눈별 Canvas 렌더',['StereoOverlayView / 검정 배경 초기화','나사 마커·상자 윤곽·한글 안내 그리기','각 눈 1920×1080 영역 clipRect','좌안 x=0 / 우안 x=1920으로 배치'],'android',{h:240});
 box('r-layers',3350,2210,600,'R5 · 2D / 3D 레이어 합성',['FrameLayout 안에 두 View를 배치','아래: StereoOverlayView의 2D 안내','위: PartPreviewView의 투명 3D HUD','실물 정합 레이어와 화면 고정 HUD 분리'],'Layers',{h:240,extraIcons:['android','threejs']});
 box('r-display',4050,2210,600,'R6 · 외부 화면 출력',['Android Presentation → Beast 화면','3840×1080 Full SBS 표면 / 1:1 픽셀','왼쪽 절반: 좌안 / 오른쪽 절반: 우안','기존 착용·디스플레이 설정 유지'],'viture',{h:240,extraIcons:['android']});
 box('r-states',2650,2600,600,'작업 상태 · 부품 선택',['상단 작업 단계·현재 나사·색상 입력','상자 / 뚜껑 / 나사 / 조립체 선택','selectPart → showPart → setPart'],'Workflow');
 box('r-threejs',3350,2600,600,'Three.js · 로컬 3D HUD',['WebView / 로컬 JS·모델 / 네트워크 차단','PerspectiveCamera로 부품 형상 렌더','눈별 viewport·scissor / 오른쪽 위 고정','민트 선 부품 + 둥근 테두리'],'threejs');
 text(550,2638,'두 종류의 렌더링을 구분',29,C.ink,600);
 text(550,2690,'실물 정합 안내: 카메라 자세·눈별 보정으로 실물 위치에 표시',25,C.muted);
 text(550,2735,'3D 부품 HUD: 작업 단계에 따라 바뀌는 화면 고정 참고 모델',25,C.muted);
 text(550,2805,'Canvas 안내를 Unity가 그리는 구조가 아니며, Three.js도 나사 위치 추정을 담당하지 않는다.',24,C.muted);
}
const footerOffset=renderDetail?900:0;
group(60,2110+footerOffset,4680,430,design?(renderDetail?'05  개발 기반 · 보정 자산 · 부분 추적 상세':'04  개발 기반 · 보정 자산 · 부분 추적 상세'):'04  개발 기반 · 확장 설계  |  현재 Android 실행 경로와 구분', '#B8C2CF','Layers');
if(!design)flow('i-mediapipe-hmm',[[3510,2350],[3640,2350]],'손 특징',[3545,2325],true);
box('i-python',100,2240+footerOffset,1050,'Python · 기존 개발 기반',['데스크톱 실시간 인식·실험 / 모델·보정 도구','기존 처리·평가 로직의 개발 기반','현재 휴대폰 실행에서는 Python 서버가 필요하지 않음'],'python');
box('i-unity',1280,2240+footerOffset,1050,'Unity · 기존 양안 렌더 기반',['C# 눈별 투영·거리 보정·Full SBS 렌더링 검증','기존 투영 방식을 Android EyeProjection으로 이전','현재 휴대폰 실행에서는 Unity 앱이 필요하지 않음'],'unity');
if(design){
box('i-assets-design',2460,2240+footerOffset,1050,'보정 · 모델 자산',['카메라 내부값·왜곡 프로필 / 작업대 205·205 유지','기존 A–D 눈별 투영 보정 / 프로필·모델 SHA-256 확인','부분 추적 모서리 지도는 실행 중 메모리에서만 학습'],'FileCheck');
box('i-partial-design',3640,2240+footerOffset,1050,'C3.2 · 부분 가림 검증',['5개 이상 관측에서 4·8표본의 중앙값·짝수·홀수 지도 학습','3~4마커: 비공선·지도 신선도 / 위치 3px·3mm 교차 검증','마커 제외 민감도 / 자세 500ms 이내 / 실패 시 표시 숨김'],'ShieldCheck');
}else{
box('i-mediapipe',2460,2240,1050,'MediaPipe · 확장 설계',['손 관절·손끝 랜드마크 → 동작 특징 추출','도구·ROI 정보와 결합할 수 있는 입력 후보','현재 Android 앱 미적용'],'mediapipe',{dash:true,stroke:'#B5A5C6',fill:'#FCFBFE'});
box('i-hmm',3640,2240,1050,'HMM · Viterbi · 확장 설계',['손·도구·ROI 증거 → 시간적 단계 추정','관측 점수와 전이 확률로 단계열 추정하는 설계','현재 Android 앱 미적용'],'Network',{dash:true,stroke:'#B5A5C6',fill:'#FCFBFE',color:C.purple});
}
text(60,2620+footerOffset,design?'통합 설계안: MediaPipe·HMM은 현재 APK 미적용이며, 해당 연결은 통합 방향을 나타낸다.  |  주황: 폰 처리 · 청회색: AWS · 보라색: 웹':'실선: 현재 데이터 흐름   ·   주황: 폰 처리   ·   청회색: AWS   ·   보라색: 웹   ·   하단 점선: 미적용 확장 설계',23,C.muted);
text(60,2660+footerOffset,'검증 범위: 같은 배치·착용 조건에서 좌우 가림의 3마커 표시 확인 / 녹화 실측 평균 약 6.7fps (목표 30fps와 구분)',22,C.muted);
text(4240,2660+footerOffset,design?'AR Assembly  /  2026.11.26':'AR Assembly  /  2026.11.25',22,C.muted);
finish(renderDetail?'AR-Assembly-Render-Detailed':design?'AR-Assembly-Integrated-Design':'AR-Assembly-Integrated-Architecture');

const connected=process.argv.includes('--connected');
if(connected)require('./connected-layout.cjs')({size:(w,h)=>{W=w;H=h;},header,group,box,flow,text,rect,finish,C});

function validate(p){
 const issues=[];
 for(const e of p.edges){for(let i=1;i<e.points.length;i++){
  const [a,b]=[e.points[i-1],e.points[i]];
  if(a[0]!==b[0]&&a[1]!==b[1])issues.push('non-orthogonal: '+e.id);
  for(const n of p.boxes){const crossed=a[0]===b[0] ? a[0]>n.x&&a[0]<n.x+n.w&&Math.max(a[1],b[1])>n.y&&Math.min(a[1],b[1])<n.y+n.h : a[1]>n.y&&a[1]<n.y+n.h&&Math.max(a[0],b[0])>n.x&&Math.min(a[0],b[0])<n.x+n.w;if(crossed)issues.push(`${e.id} crosses node ${n.id}`);}
 }}
 const segments=p.edges.flatMap(e=>e.points.slice(1).map((b,i)=>({id:e.id,a:e.points[i],b})));
 for(let i=0;i<segments.length;i++)for(let j=i+1;j<segments.length;j++){
  let a=segments[i],b=segments[j];if(a.id===b.id)continue;
  if(a.a[0]===a.b[0]&&b.a[1]===b.b[1]){const c=a;a=b;b=c;}
  if(a.a[1]!==a.b[1]||b.a[0]!==b.b[0])continue;
  const x=b.a[0],y=a.a[1];
  if(x>Math.min(a.a[0],a.b[0])&&x<Math.max(a.a[0],a.b[0])&&y>Math.min(b.a[1],b.b[1])&&y<Math.max(b.a[1],b.b[1]))issues.push(`edge crossing: ${a.id} / ${b.id}`);
 }
 if(issues.length)throw Error(p.name+'\n'+issues.join('\n'));
 return {page:p.name,boxes:p.boxes.length,flows:p.edges.length,edgeNodeCrossings:0,edgeEdgeCrossings:0};
}
(async()=>{
 const integrated=process.argv.includes('--integrated')||design||connected;
 const selected=pages.filter(p=>connected?p.name==='AR-Assembly-Connected-Architecture':integrated?p.w>3200:p.w===3200);
 const out=path.join(__dirname,connected?'connected-v6':renderDetail?'render-detailed-v5':design?'integrated-design-v4':integrated?'integrated-v3':'professional-v2');fs.mkdirSync(out,{recursive:true});
 const pdf=await PDFDocument.create();const results=[];
 for(const p of selected){results.push(validate(p));fs.writeFileSync(path.join(out,p.name+'.svg'),p.svg);const png=await sharp(Buffer.from(p.svg)).resize(p.w*2,p.h*2).png().toBuffer();fs.writeFileSync(path.join(out,p.name+'.png'),png);await sharp(png).resize(integrated?2400:2000).png().toFile(path.join(out,p.name+'-preview.png'));const im=await pdf.embedPng(png);const page=pdf.addPage([p.w/2,p.h/2]);page.drawImage(im,{x:0,y:0,width:p.w/2,height:p.h/2});}
 fs.writeFileSync(path.join(out,connected?'AR-Assembly-Connected-Architecture.pdf':renderDetail?'AR-Assembly-Render-Detailed.pdf':design?'AR-Assembly-Integrated-Design.pdf':integrated?'AR-Assembly-Integrated-Architecture.pdf':'AR-Assembly-Architecture-v2.pdf'),await pdf.save());fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(results,null,2));fs.writeFileSync(path.join(out,'geometry.json'),JSON.stringify(selected.map(({name,boxes,edges})=>({name,boxes,edges})),null,2));
 if(renderDetail){const p=selected[0];await sharp(Buffer.from(p.svg)).extract({left:500,top:2070,width:4240,height:840}).resize(2544).png().toFile(path.join(out,'Rendering-Detail-preview.png'));}
 console.log(JSON.stringify(results));
})();
