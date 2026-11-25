const fs=require('node:fs');const path=require('node:path');
const {chromium}=require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1123-915-0_26.1123.915.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:900}});
 const dir=path.join(__dirname,process.argv.includes('--connected')?'connected-v6':process.argv.includes('--render-detail')?'render-detailed-v5':process.argv.includes('--design')?'integrated-design-v4':process.argv.includes('--integrated')?'integrated-v3':'professional-v2');const geometry=JSON.parse(fs.readFileSync(path.join(dir,'geometry.json')));const reports=[];
 try{for(const g of geometry){
  await page.setContent(fs.readFileSync(path.join(dir,g.name+'.svg'),'utf8'));await page.evaluate(()=>document.fonts.ready);
  const result=await page.evaluate(({edges})=>{
   const errors=[];let textCount=0;
   for(const n of document.querySelectorAll('g[data-node]')){
    const b=n.querySelector('rect').getBBox();
    for(const t of n.querySelectorAll('text')){const r=t.getBBox();textCount++;if(r.x<b.x||r.y<b.y||r.x+r.width>b.x+b.width-8||r.y+r.height>b.y+b.height-8)errors.push('Text overflow: '+n.getAttribute('data-node')+' / '+t.textContent);}
   }
   for(const t of document.querySelectorAll('text')){
    const r=t.getBBox();
    for(const e of edges)for(let i=1;i<e.points.length;i++){
     const a=e.points[i-1],b=e.points[i];
     const hit=a[0]===b[0]?a[0]>r.x&&a[0]<r.x+r.width&&Math.max(a[1],b[1])>r.y&&Math.min(a[1],b[1])<r.y+r.height:a[1]>r.y&&a[1]<r.y+r.height&&Math.max(a[0],b[0])>r.x&&Math.min(a[0],b[0])<r.x+r.width;
     if(hit)errors.push('Arrow/text overlap: '+e.id+' / '+t.textContent);
    }
   }
   return {textCount,errors};
  },g);
  if(process.argv.includes('--connected')){
   const active=g.boxes.filter(n=>n.y<3100),parent=new Map();
   const root=x=>{if(!parent.has(x))parent.set(x,x);if(parent.get(x)!==x)parent.set(x,root(parent.get(x)));return parent.get(x);};
   const join=(a,b)=>parent.set(root(a),root(b));
   const on=(p,a,b)=>p[0]>=Math.min(a[0],b[0])&&p[0]<=Math.max(a[0],b[0])&&p[1]>=Math.min(a[1],b[1])&&p[1]<=Math.max(a[1],b[1])&&(a[0]===b[0]?p[0]===a[0]:p[1]===a[1]);
   for(const e of g.edges){for(const p of [e.points[0],e.points.at(-1)]){
    for(const n of active)if(p[0]>=n.x&&p[0]<=n.x+n.w&&p[1]>=n.y&&p[1]<=n.y+n.h)join('e:'+e.id,'n:'+n.id);
    for(const f of g.edges)for(let i=1;i<f.points.length;i++)if(on(p,f.points[i-1],f.points[i]))join('e:'+e.id,'e:'+f.id);
   }}
   result.runtimeConnectedComponents=new Set(active.map(n=>root('n:'+n.id))).size;
   result.runtimeNodes=active.length;
   if(result.runtimeConnectedComponents!==1)result.errors.push('Disconnected runtime graph');
  }
  reports.push({page:g.name,...result});
 }}finally{await browser.close();}
 fs.writeFileSync(path.join(dir,'visual-validation.json'),JSON.stringify(reports,null,2));console.log(JSON.stringify(reports,null,2));if(reports.some(r=>r.errors.length))process.exitCode=1;
})();
