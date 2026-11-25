const fs=require('node:fs');const path=require('node:path');
const assets={
 viture:'https://www.viture.com/beast/icon.png?icon.168eb4f7.png',
 vitureGlasses:'https://www.viture.com/beast/images/icons/glasses-blue.svg',
 onnxruntime:'https://onnxruntime.ai/images/logos/onnxruntime/ORT_icon_for_light_bg.svg'
};
(async()=>{
 for(const [name,url] of Object.entries(assets)){
  const r=await fetch(url);if(!r.ok)throw Error(name+': '+r.status);
  const ext=name==='viture'?'.png':'.svg';
  fs.writeFileSync(path.join(__dirname,'icons',name+ext),Buffer.from(await r.arrayBuffer()));
  console.log(name+': '+r.headers.get('content-type'));
 }
 fs.writeFileSync(path.join(__dirname,'icons','official-render-sources.json'),JSON.stringify(assets,null,2));
})();
