const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const sharp = require('C:/Users/fresh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out = __dirname;
const photo = 'C:/Users/fresh/Downloads/Beast_202mm_AD_20261108/live-20261108T012754Z-f8cf2d50/frame-000017/raw.png';
const unity = path.join(out,'unity-b-capture-v10','189-SBS_GUIDANCE_GUIDING_screw_b.png');
const crop = {left:250,top:198,width:720,height:405};
const width=1920,height=1080;
const sha = file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async()=>{
  const base=await sharp(photo).extract(crop).resize(width,height,{kernel:'lanczos3'}).removeAlpha().raw().toBuffer();
  const {data,info}=await sharp(unity).extract({left:0,top:0,width:768,height:432}).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const rgba=Buffer.alloc(info.width*info.height*4);
  for(let y=0;y<info.height;y++) for(let x=0;x<info.width;x++){
    if(y>=396)continue; // Omit the diagnostic footer only; retain the original capture separately.
    const targetY = y < 50 ? y - 16 : y >= 290 ? y + 22 : y;
    if(targetY < 0 || targetY >= info.height)continue;
    const p=(y*info.width+x)*3,q=(targetY*info.width+x)*4;
    const alpha=Math.max(data[p],data[p+1],data[p+2]);
    for(let c=0;c<3;c++) rgba[q+c]=alpha?Math.round(data[p+c]*255/alpha):0;
    rgba[q+3]=alpha;
  }
  const overlay=await sharp(rgba,{raw:{width:768,height:432,channels:4}})
    .resize(width,height,{kernel:'lanczos3'}).png().toBuffer();
  const output=await sharp(base,{raw:{width,height,channels:3}})
    .composite([{input:overlay}]).removeAlpha().raw().toBuffer();
  const mask=await sharp(overlay).ensureAlpha().raw().toBuffer();
  let untouched=0,unexpectedChanges=0,overlayPixels=0;
  for(let i=0;i<width*height;i++){
    if(mask[i*4+3]===0){
      untouched++;
      if(output[i*3]!==base[i*3]||output[i*3+1]!==base[i*3+1]||output[i*3+2]!==base[i*3+2])unexpectedChanges++;
    }else overlayPixels++;
  }
  assert.equal(unexpectedChanges,0,'Non-overlay pixels must match the photo crop exactly');
  await sharp(base,{raw:{width,height,channels:3}}).png().toFile(path.join(out,'photo-only-v10.png'));
  await sharp(overlay).toFile(path.join(out,'unity-overlay-transparent-v10.png'));
  const image=sharp(output,{raw:{width,height,channels:3}});
  await image.clone().png().toFile(path.join(out,'ar-guidance-B-photo-unity-v10-wide.png'));
  const pamphletCrop={left:195,top:0,width:1530,height:1020};
  await image.clone().extract(pamphletCrop).png().toFile(path.join(out,'ar-guidance-B-photo-unity-v10.png'));
  await sharp(base,{raw:{width,height,channels:3}}).extract(pamphletCrop).png().toFile(path.join(out,'photo-only-v10-compact.png'));
  const report={
    photo,photo_sha256:sha(photo),unity,unity_sha256:sha(unity),
    cameraStarted:false,sourceScene:'original archived camera photograph',
    uiSource:'Actual existing Unity player, laptop-only metadata fixture; Korean next_action supplied by fixture',
    generativeImageModelUsed:false,crop,resize:{width,height,scaleX:width/crop.width,scaleY:height/crop.height},
    uiSourceEye:'left half',uiScale:2.5,sourceFooterRetainedInCapture:true,footerOmittedFromComposition:true,
    editorialUiOffsetsAtCaptureScale:{titleY:-16,instructionGroupY:22},
    fixtureTargetPixel:[1237,248],photoEquivalentTargetPixel:[250+1237/(1920/720),198+248/(1080/405)],
    targetPlacement:'Editorial image correspondence, not measured headset registration',
    pamphletCrop,unchangedPhotoPixels:untouched,overlayPixels,unexpectedChanges,
    sourceNote:'This is an original-photo + actual Unity-render composition, not a through-lens photograph. No box, mat, marker or lighting reconstruction.',
    runtimeChanged:false,googleSlidesChanged:false
  };
  fs.writeFileSync(path.join(out,'visual-provenance-v10.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({untouched,overlayPixels,unexpectedChanges,outputs:['ar-guidance-B-photo-unity-v10-wide.png','ar-guidance-B-photo-unity-v10.png']}));
})();

