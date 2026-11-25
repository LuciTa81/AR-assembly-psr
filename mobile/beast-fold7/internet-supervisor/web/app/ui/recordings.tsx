'use client';
import {useEffect,useState} from 'react';
import {Download,Trash2,RefreshCw,X,Film} from 'lucide-react';
type Row={id:string;status:string;created_ms:string;expires_ms:string;duration_ms:string;bytes:string;reason:string;segment?:number;gap_before_ms?:string};
const date=(ms:string)=>new Date(Number(ms)).toLocaleString('ko-KR',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const duration=(ms:string)=>`${Math.floor(Number(ms)/60000)}:${String(Math.floor(Number(ms)/1000)%60).padStart(2,'0')}`;
const day=(ms:string)=>{const d=new Date(Number(ms));return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
const size=(bytes:string)=>`${(Number(bytes)/1000000).toFixed(1)} MB`;
async function request(path:string,method='GET'){
  const r=await fetch('/api/observer/'+path,{method,cache:'no-store',signal:AbortSignal.timeout(8000)});
  if(r.status===401){location.assign('/login');throw Error('로그인이 필요해요');}
  const data=await r.json();if(!r.ok)throw Error(data.error??'영상 요청을 처리하지 못했어요');return data;
}
export default function Recordings({device,active}:{device:string;active:boolean}){
  const [rows,setRows]=useState<Row[]>([]),[error,setError]=useState(''),[loaded,setLoaded]=useState(false),[busy,setBusy]=useState(''),[reload,setReload]=useState(0);
  const [dateFilter,setDateFilter]=useState(''),[enabled,setEnabled]=useState<boolean|null>(null);
  useEffect(()=>{
    if(!active||!device)return;
    let done=false,timer:ReturnType<typeof setTimeout>;
    async function load(){
      try{const data=await request(`devices/${device}/recordings`);if(!done){setRows(data.recordings);setEnabled(typeof data.enabled==='boolean'?data.enabled:null);setLoaded(true);setError('');}}
      catch(e){if(!done){setError((e as Error).message);setLoaded(true);}}
      finally{if(!done)timer=setTimeout(()=>void load(),5000);}
    }
    void load();return()=>{done=true;clearTimeout(timer);};
  },[device,active,reload]);
  async function action(row:Row,kind:'download'|'delete'){
    if(kind==='delete'&&!window.confirm('이 영상을 삭제할까요? 삭제한 영상은 복구할 수 없어요.'))return;
    setBusy(row.id);setError('');
    try{
      const data=await request(`recordings/${row.id}/${kind}`,'POST');
      if(kind==='download'){
        const url=new URL(data.url);if(url.protocol!=='https:')throw Error('다운로드 주소를 확인하지 못했어요');
        const link=document.createElement('a');link.href=url.href;link.referrerPolicy='no-referrer';link.download='';document.body.append(link);link.click();link.remove();
      }
      setReload(n=>n+1);
    }catch(e){setError((e as Error).message);}finally{setBusy('');}
  }
  const visible=rows.filter(row=>!dateFilter||day(row.created_ms)===dateFilter);
  return <section className="recordings" aria-label="저장 영상 목록"><div className="recordings-toolbar"><div className="recordings-total"><Film size={20}/><h2>저장 파일</h2><span>{loaded?`${visible.length}개`:'--'}</span></div><div className="recording-filters"><label>촬영일 <input type="date" value={dateFilter} onChange={e=>setDateFilter(e.target.value)}/></label>{dateFilter&&<button className="icon-button" title="날짜 필터 초기화" aria-label="날짜 필터 초기화" onClick={()=>setDateFilter('')}><X size={16}/></button>}<button className="icon-button" title="영상 목록 새로고침" aria-label="영상 목록 새로고침" disabled={!!busy} onClick={()=>setReload(n=>n+1)}><RefreshCw size={18}/></button></div></div>
    {error&&<p role="alert" className="warning">{error}</p>}
    {device&&!error&&enabled!==null&&<p role="status" className={enabled?'label':'warning'}>{enabled?'서버 녹화 사용 가능':'서버 녹화가 꺼져 있어 새 영상은 저장되지 않아요.'}</p>}
    {!device?<p className="empty-state">기기를 선택해 주세요</p>:!loaded?<p className="empty-state" role="status">영상을 불러오는 중이에요</p>:!visible.length?<p className="empty-state">{dateFilter?'해당 날짜에 저장된 영상이 없어요':'저장된 영상이 없어요'}</p>:<div className="recordings-scroll"><table><thead><tr><th>촬영 시각</th><th>길이 · 용량</th><th>상태</th><th>삭제 예정</th><th><span className="recording-actions-label">파일</span></th></tr></thead><tbody>{visible.map(row=>{
      const expired=Number(row.expires_ms)<=Date.now(),ready=row.status==='ready'&&!expired;
      const status=expired?'보관 만료':row.status==='capturing'?'저장 중':row.status==='deleting'?'삭제 중':row.reason==='stopped'||row.reason==='completed'?'저장됨':'일부 구간 저장';
      return <tr key={row.id}><td>{date(row.created_ms)}<small className="recording-segment">구간 {row.segment??1}{Number(row.gap_before_ms)>0?` · 앞 구간 이후 약 ${Math.ceil(Number(row.gap_before_ms)/1000)}초 공백`:''}</small></td><td>{row.status==='capturing'?'--:--':duration(row.duration_ms)}<small className="recording-segment">{size(row.bytes)}</small></td><td><span className="recording-status" data-status={ready?'ready':row.status}>{status}</span></td><td>{date(row.expires_ms)}</td><td><div className="recording-actions"><button className="icon-button" title="영상 다운로드" aria-label={`${date(row.created_ms)} 구간 ${row.segment??1} 영상 다운로드`} disabled={!ready||!!busy} onClick={()=>void action(row,'download')}><Download size={19}/></button><button className="icon-button" title="영상 삭제" aria-label={`${date(row.created_ms)} 구간 ${row.segment??1} 영상 삭제`} disabled={row.status!=='ready'||!!busy} onClick={()=>void action(row,'delete')}><Trash2 size={19}/></button></div></td></tr>;
    })}</tbody></table></div>}
  </section>;
}
