// 공용 장면 도구: 시간 계산, 자막, 배경, 헤더, 영상 맞추기
const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
const eo=x=>1-Math.pow(1-clamp(x),3);
const ss=x=>{x=clamp(x);return x*x*(3-2*x);};
const lerp=(a,b,k)=>a+(b-a)*k;
const ramp=(t,a,d=0.5)=>eo((t-a)/d);
const $=id=>document.getElementById(id);
function show(el,t,a,d=0.55,dy=18,dx=0){ if(typeof el==='string') el=$(el); const k=ramp(t,a,d); el.style.opacity=k; el.style.transform=`translate(${(1-k)*dx}px,${(1-k)*dy}px)`; return k; }
function fadeOut(el,t,a,d=0.4){ if(typeof el==='string') el=$(el); const k=1-ramp(t,a,d); el.style.opacity=Math.min(+el.style.opacity||1,k); return k; }

const KIT = {
  CHAPS:['01 배경','02 구성','03 단계 인식','04 양안 정합','05 가림과 복구','06 시연 · 가치'],
  vids:[], imgs:[], caps:[], dur:10, rate:5.8, bgOn:true, capX:960, fadeIn:'#fff', fadeOut:'#fff',
  syl(s){ const h=(s.match(/[가-힣]/g)||[]).length; const o=(s.match(/[A-Za-z0-9]/g)||[]).length; return h+o*0.55; },
  // lines: [{k:'name', t:'자막 문장', pre:추가 쉼, at:이 시각 이후}] → 각 줄의 [시작, 끝], 장면 길이
  // 긴 문장은 ' | ' 로 나누면 자막 카드만 둘로 갈린다 (사이 쉼 split 초). T[k] 는 문장 전체 [시작, 끝]
  // 내레이션(vo_data.js 의 window.VO)이 있으면 줄 길이는 실제 음성 길이, 자막 카드는 음성의 쉼에서 나눈다.
  // 줄 사이 쉼: 쉼표로 끝나면 vcomma, 문장이 끝나면 vstop (음성 조각 앞뒤 여백 0.13초는 따로)
  vcomma:0.32, vstop:0.55,
  timeline(lines,{start=1.2,gap=0.35,tail=1.8,split=0.2}={}){
    const name=decodeURIComponent(location.pathname.split('/').pop()||'').replace(/\.html$/,'');
    const V=(window.VO||{})[name];
    let t=start, g=0; const T={}; const caps=[]; const vo=[];
    for(const L of lines){ if(L.at!=null) t=Math.max(t,L.at); t+=(L.pre||0); const t0=t;
      const parts=L.t.split(' | '); const v=V&&L.k&&V[L.k];
      if(v){
        let sp=(v.sp||[]).slice(0,parts.length-1);
        if(sp.length<parts.length-1){ const tot=parts.reduce((s,p)=>s+this.syl(p),0); let acc=0; sp=parts.slice(0,-1).map(p=>(acc+=this.syl(p))/tot*v.d); }
        const b=[0,...sp,v.d];
        parts.forEach((p,i)=>caps.push({t0:t0+b[i],t1:t0+b[i+1],text:p}));
        vo.push({k:L.k,t:t0,d:v.d}); t=t0+v.d; g=/[,，]$/.test(L.t.trim())?this.vcomma:this.vstop;
      } else {
        parts.forEach((p,i)=>{ const d=Math.max(1.5, this.syl(p)/this.rate+0.3); caps.push({t0:t,t1:t+d,text:p}); t+=d; if(i<parts.length-1) t+=split; });
        g=gap;
      }
      if(L.k) T[L.k]=[t0,t]; t+=g; }
    this.caps=caps; this.vo=vo; window.SCENE_VO=vo; this.dur=+(t-g+tail).toFixed(2); window.SCENE_DUR=this.dur; return T;
  },
  header({kicker,title,sub,chap}){
    const st=$('stage'); const add=(cls,id,html)=>{const e=document.createElement('div'); e.className='a '+cls; e.id=id; e.innerHTML=html; const ref=$('cap'); if(ref) st.insertBefore(e,ref); else st.appendChild(e); return e;};
    // 장 이름 알약(kicker)은 쓰지 않는다 (참고 영상과 같은 모양이라 뺌)
    if(chap!=null) add('crumb','crumb',this.CHAPS.map((c,i)=>i===chap?`<b>${c}</b>`:c).join(' &nbsp;·&nbsp; '));
    if(title) add('title','title',title);
    if(sub) add('sub','sub',sub);
  },
  build(){
    const st=$('stage');
    if(this.bgOn){ [['b1',760,'#C9D6EC'],['b2',640,'#FBE3CF'],['b3',700,'#CFEDE6']].forEach(([id,s,c])=>{ const b=document.createElement('div'); b.className='blob'; b.id=id; b.style.width=b.style.height=s+'px'; b.style.background=c; st.insertBefore(b,st.firstChild); }); }
    const cap=document.createElement('div'); cap.id='cap'; st.appendChild(cap);
    const w=document.createElement('div'); w.id='white'; st.appendChild(w);
  },
  frame(t){
    if(this.bgOn){
      $('b1').style.left=(-180+40*Math.sin(t*0.21))+'px'; $('b1').style.top=(-260+30*Math.cos(t*0.17))+'px';
      $('b2').style.left=(1380+50*Math.cos(t*0.19))+'px'; $('b2').style.top=(-120+40*Math.sin(t*0.23))+'px';
      $('b3').style.left=(700+60*Math.sin(t*0.15))+'px'; $('b3').style.top=(620+40*Math.cos(t*0.2))+'px';
    }
    const wi=1-ramp(t,0,0.7), wo=ramp(t,this.dur-0.75,0.75); $('white').style.background = t<this.dur/2 ? this.fadeIn : this.fadeOut; $('white').style.opacity = Math.max(wi,wo);
    ['kicker','crumb','title','sub'].forEach((id,i)=>{ const e=$(id); if(e) show(e,t,[0.3,0.4,0.45,0.75][i],0.55,id==='crumb'?0:18); });
    this.caption(t);
  },
  caption(t){
    const el=$('cap'); const C=this.caps; let cur=-1;
    for(let i=0;i<C.length;i++){ if(C[i].t0<=t) cur=i; }
    if(cur<0){ el.style.opacity=0; return; }
    const c=C[cur], n=C[cur+1], p=C[cur-1];
    const joinNext = n && n.t0-c.t1<0.8, joinPrev = p && c.t0-p.t1<0.8;
    const end = joinNext ? n.t0 : c.t1+0.25;
    if(t>end){ el.style.opacity=0; return; }
    let o=1; if(!joinPrev) o=Math.min(o,ramp(t,c.t0-0.05,0.2)); if(!joinNext) o=Math.min(o,1-ramp(t,end-0.22,0.22));
    el.textContent=c.text; el.style.opacity=o; const w=el.offsetWidth; el.style.left=Math.min(Math.max(this.capX, w/2+40), 1920-w/2-40)+'px';
  },
  vid(el,fn){ this.vids.push({el:typeof el==='string'?$(el):el,fn}); },
  async seekAll(t){
    await Promise.all(this.vids.map(({el,fn})=>new Promise(res=>{ const ct=fn(t); if(Math.abs(el.currentTime-ct)<1e-3){res();return;}
      const h=()=>{el.removeEventListener('seeked',h); res();}; el.addEventListener('seeked',h); el.currentTime=ct; })));
    if(this.vids.length) await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
  },
  ready(){
    const ps=[document.fonts.ready];
    document.querySelectorAll('img').forEach(im=>ps.push(im.decode().catch(()=>{})));
    document.querySelectorAll('video').forEach(v=>ps.push(new Promise(r=>{ if(v.readyState>=2) r(); else v.addEventListener('loadeddata',()=>r(),{once:true}); })));
    return Promise.all(ps);
  }
};

// 짧은 영상을 이어 붙여 반복: 두 <video> 를 번갈아 쓰고 이음매는 xf 초 겹쳐 넘김
KIT.loopVid = function(idA,idB,{start=0,c0=0,len=5,xf=0.3}){
  const P=len-xf, A=$(idA), B=$(idB);
  const st=t=>{ const u=Math.max(0,t-start); const k=Math.floor(u/P); return {u,k,w:u-k*P}; };
  const et=(t,which)=>{ const {u,k}=st(t); const kk=(k%2===which)?k:k-1; if(kk<0) return c0; return Math.min(c0+len-0.02, c0+(u-kk*P)); };
  this.vid(A,t=>et(t,0)); this.vid(B,t=>et(t,1));
  return t=>{ const {k,w}=st(t); const top=k%2===0?A:B, und=k%2===0?B:A; top.style.zIndex=2; und.style.zIndex=1;
    top.style.opacity = k===0?1:clamp(w/xf); und.style.opacity = k===0?0:1; };
};
// 장면은 SCENE(t) 를 정의한다
window.render = async function(t){ KIT.frame(t); if(window.SCENE) window.SCENE(t); await KIT.seekAll(t); };
