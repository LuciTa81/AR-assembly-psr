'use client';
import {useState,useEffect,useRef} from 'react';
import {Smartphone,Link,Check,X} from 'lucide-react';
type RequestInfo={request_id:string;name:string;expires_ms:number};
export default function PairDevice({connected}:{connected:(id:string)=>void}){
  const [code,setCode]=useState(''),[request,setRequest]=useState<RequestInfo|null>(null),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[success,setSuccess]=useState(''),[now,setNow]=useState(Date.now());
  const mounted=useRef(true);
  useEffect(()=>{mounted.current=true;const timer=setInterval(()=>setNow(Date.now()),1000);return()=>{mounted.current=false;clearInterval(timer);};},[]);
  async function submit(action:'lookup'|'approve'){
    setBusy(true);setError('');setSuccess('');
    try{
      const res=await fetch('/api/observer/pairing/'+action,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({code,...(action==='approve'?{request_id:request?.request_id}:{})}),signal:AbortSignal.timeout(6000)});
      if(res.status===401){location.assign('/login');return;}
      const data=await res.json();if(!res.ok)throw new Error(data.error??'기기를 연결하지 못했어요');
      if(!mounted.current)return;
      if(action==='lookup'){setNow(Date.now());setRequest(data);}
      else{setSuccess(`${data.name} 연결을 승인했어요`);setCode('');setRequest(null);connected(data.device_id);}
    }catch(e){if(mounted.current)setError(e instanceof Error&&e.name!=='TimeoutError'?e.message:'응답이 지연되고 있어요. 휴대폰의 연결 상태를 확인해 주세요.');}
    finally{if(mounted.current)setBusy(false);}
  }
  const seconds=request?Math.max(0,Math.ceil((request.expires_ms-now)/1000)):0;
  return <section className="pair-device" aria-labelledby="pair-title"><h2 id="pair-title">새 기기 연결</h2>
    <form onSubmit={e=>{e.preventDefault();void submit('lookup');}} className="pair-form">
      <label htmlFor="pair-code">휴대폰 연결 코드</label><div className="pair-controls"><input id="pair-code" value={code} autoComplete="off" autoCapitalize="characters" spellCheck={false} maxLength={9}
        placeholder="ABCD EFGH" pattern="[A-HJ-NP-Z2-9]{8}" required disabled={busy||!!request}
        onChange={e=>{setCode(e.target.value.toUpperCase().replace(/[\s-]/g,''));setError('');setSuccess('');}}/>
      {!request&&<button className="secondary-button" disabled={busy||!/^[A-HJ-NP-Z2-9]{8}$/.test(code)}><Link size={18}/>{busy?'확인 중':'기기 확인'}</button>}</div>
    </form>
    {request&&<div className="pair-confirm"><Smartphone size={24}/><div><strong>{request.name}</strong><small>{seconds?`코드 만료까지 ${seconds}초`:'코드가 만료됐어요'}</small></div>
      <div className="pair-actions"><button className="primary-button" disabled={busy||!seconds} onClick={()=>void submit('approve')}><Check size={18}/>{busy?'연결 중':'연결 승인'}</button>
      <button className="icon-button" disabled={busy} title="취소" aria-label="기기 연결 취소" onClick={()=>{setRequest(null);setError('');}}><X size={20}/></button></div></div>}
    {error&&<p className="warning" role="alert">{error}</p>}{success&&<p className="pair-success" role="status">{success}</p>}
  </section>;
}
