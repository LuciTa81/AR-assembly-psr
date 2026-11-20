const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out = __dirname;
const width = 1530, height = 1020, brightness = 0.88;
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  const previous = JSON.parse(fs.readFileSync(path.join(out, 'visual-provenance-v11.json')));
  assert.equal(sha(previous.photo),previous.photo_sha256,'Original photograph changed');
  assert.equal(sha(previous.baseCrop),previous.baseCrop_sha256,'Original photo crop changed');
  const source = await sharp(previous.baseCrop).removeAlpha().raw().toBuffer();
  const base = Buffer.from(source.map(value=>Math.round(value*brightness)));
  assert.equal(base.length,width*height*3);
  const captures = path.join(out,'unity-overlay-capture-v12');
  const black = await sharp(path.join(captures,'black.png')).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const white = await sharp(path.join(captures,'white.png')).removeAlpha().raw().toBuffer({resolveWithObject:true});
  for (const {info} of [black,white]) {
    assert.equal(info.width,width);
    assert.equal(info.height,height);
  }
  assert.ok(black.data.some(value=>value>32),'Blank Unity foreground');
  assert.ok(white.data.some(value=>value>240),'Blank white matte');
  const rgba = Buffer.alloc(width*height*4);
  let matteDisagreement = 0;
  for(let i=0;i<width*height;i++) {
    const p=i*3,q=i*4;
    const differences=[0,1,2].map(c=>white.data[p+c]-black.data[p+c]);
    matteDisagreement=Math.max(matteDisagreement,Math.max(...differences)-Math.min(...differences));
    const alpha=Math.max(0,Math.min(255,Math.round(255-differences.reduce((a,b)=>a+b,0)/3)));
    for(let c=0;c<3;c++) rgba[q+c]=alpha ? Math.min(255,Math.round(black.data[p+c]*255/alpha)) : 0;
    rgba[q+3]=alpha;
  }
  assert.ok(matteDisagreement<=3,`Mismatched matte captures: ${matteDisagreement}`);
  const priorOverlay=await sharp(path.join(out,'unity-overlay-transparent-v11.png')).ensureAlpha().raw().toBuffer();
  let unchangedGeometryPixels=0,changedGeometryPixels=0;
  for(let y=100;y<800;y++) for(let x=0;x<width;x++) {
    const q=(y*width+x)*4;
    if(!rgba[q+3]&&!priorOverlay[q+3]) continue;
    if([0,1,2,3].some(c=>Math.abs(rgba[q+c]-priorOverlay[q+c])>2)) changedGeometryPixels++;
    else unchangedGeometryPixels++;
  }
  assert.equal(changedGeometryPixels,0,'Lid, ring and arrow must retain their previous geometry and colors');
  const overlay=await sharp(rgba,{raw:{width,height,channels:4}}).png().toBuffer();
  const result=await sharp(base,{raw:{width,height,channels:3}}).composite([{input:overlay}]).removeAlpha().raw().toBuffer();
  let filteredPhotoPixels=0,overlayPixels=0,unexpectedChanges=0,greenTextPixels=0,whiteTitlePixels=0;
  for(let i=0;i<width*height;i++) {
    const p=i*3,q=i*4,y=Math.floor(i/width);
    if(rgba[q+3]) overlayPixels++;
    else {
      filteredPhotoPixels++;
      if([0,1,2].some(c=>result[p+c]!==base[p+c])) unexpectedChanges++;
    }
    if(y>850&&rgba[q+3]>240&&rgba[q+1]>240&&rgba[q]<150) greenTextPixels++;
    if(y<100&&rgba[q+3]>240&&[0,1,2].every(c=>rgba[q+c]>245)) whiteTitlePixels++;
  }
  assert.equal(unexpectedChanges,0,'Only uniform photo dimming and the UI overlay are allowed');
  assert.ok(overlayPixels>10000&&overlayPixels<width*height*0.15,'Unexpected overlay coverage');
  assert.ok(greenTextPixels>2000,'Main instruction must be bright green');
  assert.ok(whiteTitlePixels>500,'Step title must remain white');
  const output=path.join(out,'ar-guidance-B-photo-unity-v12.png');
  await sharp(result,{raw:{width,height,channels:3}}).png().toFile(output);
  await sharp(base,{raw:{width,height,channels:3}}).png().toFile(path.join(out,'photo-dimmed-v12.png'));
  await sharp(overlay).toFile(path.join(out,'unity-overlay-transparent-v12.png'));
  for(const [suffix,size] of [['half',765],['small',306]]) {
    await sharp(output).resize(size).png().toFile(path.join(out,`ar-guidance-B-photo-unity-v12-${suffix}.png`));
  }
  const report={
    ...previous,output,
    font:{family:'Noto Sans KR',titleWeight:600,instructionWeight:700},
    captureFiles:['black.png','white.png'].map(name=>({path:path.join(captures,name),sha256:sha(path.join(captures,name))})),
    photoFilter:{type:'uniform black overlay',opacity:1-brightness,channelMultiplier:brightness,appliedBeforeUi:true},
    mainInstructionColor:'#7AFFAB',titleColor:'#FFFFFF',
    untouchedOriginalFile:true,photoGeometryChanged:false,generativeImageModelUsed:false,
    description:'Archived photo with a uniform 12% darkening filter and separate Unity-rendered guidance. Design preview, not a calibrated through-lens capture.',
    matteDisagreement,filteredPhotoPixels,overlayPixels,unexpectedChanges,
    unchangedGeometryPixels,changedGeometryPixels,greenTextPixels,whiteTitlePixels
  };
  delete report.unchangedPhotoPixels;
  fs.writeFileSync(path.join(out,'visual-provenance-v12.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({output,filteredPhotoPixels,unexpectedChanges,changedGeometryPixels,greenTextPixels,whiteTitlePixels}));
})().catch(error=>{console.error(error);process.exitCode=1;});
