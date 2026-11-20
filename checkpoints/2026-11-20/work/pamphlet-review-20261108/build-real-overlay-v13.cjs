const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out=__dirname, width=1530, height=1020, brightness=0.88;
const version=process.argv[2]||'v13';
assert.ok(['v13','v14'].includes(version),'Unsupported preview version');
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function bounds(data,top,bottom,minAlpha=128) {
  let left=width,right=-1,first=height,last=-1,count=0;
  for(let y=top;y<bottom;y++) for(let x=0;x<width;x++) {
    if(data[(y*width+x)*4+3]<=minAlpha) continue;
    left=Math.min(left,x);right=Math.max(right,x);first=Math.min(first,y);last=Math.max(last,y);count++;
  }
  return {left,right,top:first,bottom:last,width:right-left+1,height:last-first+1,count};
}

(async()=>{
  const previous=JSON.parse(fs.readFileSync(path.join(out,'visual-provenance-v12.json')));
  assert.equal(sha(previous.photo),previous.photo_sha256,'Original photograph changed');
  assert.equal(sha(previous.baseCrop),previous.baseCrop_sha256,'Original photo crop changed');
  const source=await sharp(previous.baseCrop).removeAlpha().raw().toBuffer();
  const base=Buffer.from(source.map(value=>Math.round(value*brightness)));
  const captures=path.join(out,`unity-overlay-capture-${version}`);
  const black=await sharp(path.join(captures,'black.png')).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const white=await sharp(path.join(captures,'white.png')).removeAlpha().raw().toBuffer({resolveWithObject:true});
  for(const {info} of [black,white]) { assert.equal(info.width,width);assert.equal(info.height,height); }
  assert.ok(black.data.some(v=>v>32),'Blank Unity foreground');
  assert.ok(white.data.some(v=>v>240),'Blank white matte');
  const rgba=Buffer.alloc(width*height*4);
  let matteDisagreement=0;
  for(let i=0;i<width*height;i++) {
    const p=i*3,q=i*4;
    const diff=[0,1,2].map(c=>white.data[p+c]-black.data[p+c]);
    matteDisagreement=Math.max(matteDisagreement,Math.max(...diff)-Math.min(...diff));
    const alpha=Math.max(0,Math.min(255,Math.round(255-diff.reduce((a,b)=>a+b,0)/3)));
    for(let c=0;c<3;c++) rgba[q+c]=alpha ? Math.min(255,Math.round(black.data[p+c]*255/alpha)) : 0;
    rgba[q+3]=alpha;
  }
  assert.ok(matteDisagreement<=3,`Matte disagreement: ${matteDisagreement}`);
  const oldOverlay=await sharp(path.join(out,'unity-overlay-transparent-v12.png')).ensureAlpha().raw().toBuffer();
  const title=bounds(rgba,0,100),oldTitle=bounds(oldOverlay,0,100);
  const enlargement=title.width/oldTitle.width;
  assert.ok(enlargement>=1.22&&enlargement<=1.3,'Title must be about 25% larger');
  assert.ok(title.top>=10&&title.bottom<90,'Title needs safe margins');
  const geometry=bounds(rgba,100,800,5),oldGeometry=bounds(oldOverlay,100,800,5);
  for(const key of ['left','right','top','bottom']) assert.ok(Math.abs(geometry[key]-oldGeometry[key])<=(version==='v14'?3:1),'Target geometry moved');
  let uniformRimCheck=null;
  if(version==='v14') {
    const prior=await sharp(path.join(out,'unity-overlay-transparent-v13.png')).ensureAlpha().raw().toBuffer();
    let changedOutsideRim=0,changedActiveCore=0,maxRimAlpha=0,changedRimPixels=0;
    for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
      const p=(y*width+x)*4;
      const activeTarget=x>=990&&x<=1095&&y>=110&&y<=300;
      const rimRegion=x>=548&&x<=1155&&y>=215&&y<=675;
      const changed=[0,1,2,3].some(c=>rgba[p+c]!==prior[p+c]);
      if(rimRegion) {
        if(!activeTarget)maxRimAlpha=Math.max(maxRimAlpha,rgba[p+3]);
        if(changed)changedRimPixels++;
      } else if(changed)changedOutsideRim++;
      if(activeTarget&&prior[p+3]>=250&&changed)changedActiveCore++;
    }
    assert.equal(changedOutsideRim,0,'Photo, text, B ring and arrow must remain unchanged');
    assert.equal(changedActiveCore,0,'B highlight must remain unchanged above the lid outline');
    assert.ok(maxRimAlpha>=108&&maxRimAlpha<=114,'Lid opacity must stay uniform without overlapping corner accents');
    assert.ok(changedRimPixels>500,'Corner emphasis should be removed');
    uniformRimCheck={changedOutsideRim,changedActiveCore,maxRimAlpha,changedRimPixels,width:3.4,opacity:0.44};
  }
  const overlay=await sharp(rgba,{raw:{width,height,channels:4}}).png().toBuffer();
  const result=await sharp(base,{raw:{width,height,channels:3}}).composite([{input:overlay}]).removeAlpha().raw().toBuffer();
  let unchangedFilteredPhotoPixels=0,unexpectedChanges=0,titleGreen=0,instructionGreen=0,darkTextPixels=0,haloPixels=0;
  for(let i=0;i<width*height;i++) {
    const p=i*3,q=i*4,y=Math.floor(i/width),alpha=rgba[q+3];
    if(alpha===0) {
      unchangedFilteredPhotoPixels++;
      if([0,1,2].some(c=>result[p+c]!==base[p+c])) unexpectedChanges++;
    }
    if(y<100||y>850) {
      if(alpha>128&&rgba[q+1]<220) darkTextPixels++;
      if(alpha>220&&rgba[q+1]>240&&rgba[q]<150&&rgba[q+2]<150) {
        if(y<100)titleGreen++;else instructionGreen++;
      }
      if(alpha>2&&alpha<40&&rgba[q+1]>220)haloPixels++;
    }
  }
  assert.equal(unexpectedChanges,0,'Unexpected photograph edits');
  assert.equal(darkTextPixels,0,'Dark text shadows must be absent');
  assert.ok(titleGreen>1000&&instructionGreen>2000,'Both labels must be green');
  assert.ok(haloPixels>100,'Low-opacity green edge pixels expected');
  assert.ok(unchangedFilteredPhotoPixels>width*height*0.85,'Background must remain dominant');
  const output=path.join(out,`ar-guidance-B-photo-unity-${version}.png`);
  await sharp(result,{raw:{width,height,channels:3}}).png().toFile(output);
  await sharp(overlay).toFile(path.join(out,`unity-overlay-transparent-${version}.png`));
  for(const [suffix,size] of [['half',765],['small',306]]) await sharp(output).resize(size).png().toFile(path.join(out,`ar-guidance-B-photo-unity-${version}-${suffix}.png`));
  const report={
    photo:previous.photo,photo_sha256:previous.photo_sha256,baseCrop:previous.baseCrop,baseCrop_sha256:previous.baseCrop_sha256,
    transformation:previous.transformation,photoFilter:{type:'uniform black overlay',opacity:0.12,appliedBeforeUi:true},
    unityProject:previous.unityProject,unityVersion:previous.unityVersion,rendering:previous.rendering,
    captureFiles:['black.png','white.png'].map(name=>({path:path.join(captures,name),sha256:sha(path.join(captures,name))})),
    font:{family:'Noto Sans KR',titleWeight:600,instructionWeight:600,titleHeight:55,instructionHeight:66},
    text:previous.text,color:'#76FF83',darkShadows:false,halo:{maxRadiusPixels:2,perSampleOpacity:[0.025,0.012],samplesPerRadius:8},
    targetCenterInImage:previous.targetCenterInImage,placement:previous.placement,
    originalPreserved:true,previousVersionsPreserved:true,photoGeometryChanged:false,generativeImageModelUsed:false,
    cameraStarted:false,existingRuntimeChanged:false,calibrationChanged:false,googleSlidesChanged:false,
    description:'Archived photo plus separate Unity-rendered green HUD design preview; not a measured through-lens capture or a reproduction of Rokid optics/font.',
    width,height,title,oldTitle,enlargement,geometry,oldGeometry,matteDisagreement,uniformRimCheck,
    unchangedFilteredPhotoPixels,unexpectedChanges,titleGreen,instructionGreen,darkTextPixels,haloPixels,output
  };
  fs.writeFileSync(path.join(out,`visual-provenance-${version}.json`),JSON.stringify(report,null,2));
  console.log(JSON.stringify({output,title,enlargement,unexpectedChanges,titleGreen,instructionGreen,darkTextPixels,haloPixels,uniformRimCheck}));
})().catch(error=>{console.error(error);process.exitCode=1;});
