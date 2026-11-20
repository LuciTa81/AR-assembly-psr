import fs from 'node:fs/promises';
import { Presentation, PresentationFile } from 'file:///C:/Program%20Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1111-574-0_26.1111.574.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const root='C:/Users/fresh/Documents/Codex/binocular-slides-20261116';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const C={blue:'#38577D',ink:'#202833',muted:'#78869B',pale:'#EDF2F8',line:'#D5DFEB',white:'#FFFFFF'};
function box(s,x,y,w,h,fill=C.pale){return s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}})}
function t(s,x,y,w,h,text,size=22,color=C.ink,bold=false){const a=box(s,x,y,w,h,'none');a.text=text;a.text.style={fontSize:size,fontFamily:bold?'Pretendard ExtraBold':'Pretendard',color,bold,verticalAlignment:'middle',insets:0,wrap:true};return a;}
function base(label,sub){const s=p.slides.add();s.background.fill=C.white;t(s,48,42,460,44,label,28,C.blue,true);t(s,620,42,612,44,sub,22,C.blue);return s;}
async function img(s,file,x,y,w,h,alt){s.images.add({blob:new Uint8Array(await fs.readFile(root+'/assets/'+file)),contentType:'image/png',fit:'contain',alt,position:{left:x,top:y,width:w,height:h}});}
function foot(s,text){t(s,70,674,1140,25,text,12,C.muted);}
const spaam='https://web.ics.purdue.edu/~mtucerya/research/AR/Tuceryan2002.pdf';
const assess='https://openaccess.thecvf.com/content_ICCVW_2019/papers/EPIC/Ballestin_Assessment_of_Optical_See-Through_Head_Mounted_Display_Calibration_for_Interactive_ICCVW_2019_paper.pdf';
{
const s=base('Stereo Projection','같은 나사 위치를 왼눈과 오른눈에 다르게 투영합니다');
t(s,70,116,600,48,'한 지점, 두 개의 투영',34,C.blue,true);
await img(s,'spaam-stereo-fig6.png',70,186,545,394,'SPAAM 논문 Figure 6: 양안 시차와 공간 지점 정렬');
t(s,70,593,550,40,'좌우 화면의 차이가 공간상의 깊이를 만듭니다.',21,C.blue,true);
t(s,670,119,535,40,'우리 시스템의 실시간 처리',26,C.blue,true);
const steps=[['01','작업대 위치 추적','ArUco 검출과 PnP로 카메라 자세 계산'],['02','나사 A~D의 3D 좌표','등록한 작업대 좌표를 카메라 좌표로 변환'],['03','왼눈 / 오른눈 화면 좌표','서로 다른 3×4 투영 행렬 적용'],['04','Unity Full SBS 출력','좌우 1920×1080 → 3840×1080']];
steps.forEach((r,i)=>{let y=186+i*97;box(s,670,y,535,83);t(s,687,y+19,44,34,r[0],23,C.blue,true);t(s,748,y+10,440,30,r[1],23,C.blue,true);t(s,748,y+43,440,30,r[2],18);});
t(s,670,590,540,46,'보정값은 미리 구하고, 화면 위치는 매번 계산합니다.',21,C.blue,true);
foot(s,'원리 그림: Tuceryan, Genc & Navab (2002), SPAAM, Fig. 6.  |  오른쪽: 본 프로젝트 구현');
s.speakerNotes.text='약 35초. 같은 화면을 두 눈에 복제하는 것이 아니라 같은 나사의 3차원 좌표를 눈마다 다른 투영 행렬로 계산합니다. SPAAM 그림은 양안 정합의 원리 참고 자료이며 본 프로젝트의 장비 또는 시험 결과가 아닙니다. 보정은 오프라인, 적용은 실시간입니다.\nSource: '+spaam;
}
{
const s=base('Calibration','직접 맞춘 관측을 모아 두 눈의 투영을 함께 보정합니다');
t(s,70,118,550,46,'실물과 화면 좌표를 연결',32,C.blue,true);
await img(s,'assessment-setup-fig2.png',70,185,550,285,'Ballestin et al. 2019 Figure 2: SPAAM 정렬과 좌표계');
t(s,70,487,550,65,'실물의 3D 위치 ↔ 눈에 맞춘 2D 위치',23,C.blue,true);
t(s,70,550,550,66,'논문의 정렬 원리를 참고하되,\n본 시스템은 마커 기반 카메라 좌표를 사용합니다.',20);
const steps=[['관측 수집','같은 착용 상태에서 목표 원을 정렬하고\n그 순간의 3D 좌표와 좌우 화면 좌표를 저장'],['양안 공동 최적화','좌우 눈의 공통 기하를 공유하고\nPD 64mm를 약한 제약으로 사용'],['저장 후 자동 적용','거리와 자세가 바뀔 때 새 3D 좌표를 투영\n사용자는 원을 다시 옮기지 않고 비교']];
steps.forEach((r,i)=>{let y=140+i*153;t(s,675,y,530,35,`${i+1}. ${r[0]}`,26,C.blue,true);t(s,675,y+45,535,75,r[1],21);if(i<2)box(s,675,y+134,535,1,C.line);});
box(s,675,608,535,42);t(s,688,612,507,34,'독립 DLT 22변수 → 공통 양안 모델 13변수',20,C.blue,true);
foot(s,'좌표계 그림: Ballestin, Chessa & Solari (2019), Fig. 2.  |  오른쪽: 본 프로젝트의 보정 절차');
s.speakerNotes.text='약 40초. 사용자가 편하게 겹친 순간의 3D-2D 대응점을 저장합니다. 기존 독립 DLT 모델과 비교한 공동 모델은 공통 회전과 초점거리, 눈별 주점, 수평 baseline 등을 사용하며 13개 변수입니다. PD64는 고정 정답이 아니라 soft prior입니다. 그림의 Vive 장비를 사용했다는 뜻이 아닙니다.\nSource: '+assess+'\nImplementation evidence: docs/beast_joint_fit_comparison_20261007.md and candidate-ABCD-joint-unverified.json. Calibration fit residuals are not measured physical registration error.';
}
{
const s=base('Alignment Check','거리와 시점을 바꿔 정합의 일관성을 확인합니다');
t(s,70,118,500,46,'정합을 확인하는 방법',32,C.blue,true);
await img(s,'assessment-validation-fig1.png',70,193,455,280,'Ballestin et al. 2019 Figure 1: 카메라를 눈 위치에 둔 정합 평가 장치');
t(s,70,485,455,32,'관련 연구의 정량 평가 장치',23,C.blue,true);
t(s,70,529,455,77,'눈 위치의 카메라로 실물과 표시를 비교합니다.\n이 사진은 논문의 실험 장치입니다.',20);
t(s,585,122,625,38,'본 프로젝트: 동일 착용에서 A~D 반복 확인',26,C.blue,true);
const xs=[585,715,961],ws=[130,246,249];
['목표','정면: 가까이 ↔ 기준 거리','측면 이동 → 정면 복귀'].forEach((a,i)=>{box(s,xs[i],191,ws[i],53,C.blue);t(s,xs[i]+12,198,ws[i]-22,38,a,i?18:21,C.white,true)});
['A','B','C','D'].forEach((a,i)=>{let y=248+i*63;xs.forEach((x,j)=>box(s,x,y,ws[j],59,i%2? '#F5F7FA':C.pale));t(s,607,y+8,80,43,a,25,C.blue,true);t(s,731,y+8,220,43,'대체로 하나로 겹침',20);t(s,977,y+8,220,43,'겹침 유지 · 복귀 확인',20);});
t(s,585,523,625,40,'위치·깊이와 표시 끊김을 따로 기록',24,C.blue,true);
t(s,585,572,625,68,'표는 착용자의 정성 확인 결과입니다.\n보정 잔차나 마커 RMS를 실물 정합 정확도로 쓰지 않았습니다.',19);
foot(s,'평가 장치 사진: Ballestin et al. (2019), Fig. 1.  |  표: 2026.11.14 동일 착용 세션의 사용자 확인');
s.speakerNotes.text='약 35~40초. 표는 A B C D 각각에서 가까운 거리와 기준 거리, 한쪽으로 조금 이동한 상태와 정면 복귀를 확인한 사용자 응답입니다. 이 결과는 해당 착용 조건에서의 정성 확인이며 여러 사용자에 대한 정량 실험 또는 mm 정확도 측정이 아닙니다. 논문의 카메라 평가 장치와 우리 착용자 확인은 구분합니다. 가끔 끊기는 구간은 별도 표시 안정성 문제로 기록했습니다.\nSource image: '+assess+'\nProject record: docs/beast_candidate_poll_diagnosis_20261114.md and same-session user feedback. No paper accuracy values are attributed to this project.';
}
await fs.mkdir(root+'/build',{recursive:true});
await (await PresentationFile.exportPptx(p)).save(root+'/build/additions.pptx');
console.log('Created 3 editable additions');
